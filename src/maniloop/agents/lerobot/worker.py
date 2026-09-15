"""Standalone LeRobot inference process. Requires only the optional policy environment."""

import base64
import contextlib
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import sys
import time
from catalog import MODELS, TOKENIZER


class Runtime:
    def __init__(self, model, root, device):
        import torch
        from lerobot.configs.policies import PreTrainedConfig
        from lerobot.policies.factory import get_policy_class, make_pre_post_processors
        from lerobot.processor.env_processor import LiberoProcessorStep

        self.torch = torch
        torch.set_num_threads(4)
        self.device = (
            (
                "cuda"
                if torch.cuda.is_available()
                else "mps"
                if torch.backends.mps.is_available()
                else "cpu"
            )
            if device == "auto"
            else device
        )
        root = Path(root)
        path = root / model
        self.family = MODELS[model]["family"]
        cfg = PreTrainedConfig.from_pretrained(str(path), local_files_only=True)
        if cfg.type != self.family:
            raise ValueError("Checkpoint family differs from selected model")
        cfg.device = "cpu"  # Strict full checkpoint load first; never silently leave random weights.
        overrides = {"device_processor": {"device": self.device}}
        if self.family == "smolvla":
            cfg.load_vlm_weights = False
            cfg.vlm_model_name = str(root / "smolvlm-tokenizer")
            overrides["tokenizer_processor"] = {"tokenizer_name": cfg.vlm_model_name}
        elif self.family == "act":
            cfg.pretrained_backbone_weights = None
        self.policy = get_policy_class(self.family).from_pretrained(
            str(path), config=cfg, local_files_only=True, strict=True
        )
        self.policy.to(self.device).eval()
        cfg.device = self.device
        self.pre, self.post = make_pre_post_processors(
            cfg,
            str(path),
            preprocessor_overrides=overrides,
            postprocessor_overrides={"device_processor": {"device": "cpu"}},
        )
        self.env_processor = LiberoProcessorStep()
        checkpoint_hashes = {}
        for file in sorted(path.iterdir()):
            if file.is_file() and (
                file.name
                in (
                    "config.json",
                    "policy_preprocessor.json",
                    "policy_postprocessor.json",
                )
                or file.suffix == ".safetensors"
            ):
                with file.open("rb") as stream:
                    checkpoint_hashes[file.name] = hashlib.file_digest(
                        stream, "sha256"
                    ).hexdigest()
        self.metadata = {
            **MODELS[model],
            "device": self.device,
            "dependencies": {
                key: importlib.metadata.version(key)
                for key in (
                    "lerobot",
                    "torch",
                    "torchvision",
                    "transformers",
                    "safetensors",
                )
            },
            "weight_sha256": checkpoint_hashes["model.safetensors"],
            "checkpoint_files_sha256": checkpoint_hashes,
            "preprocessing": "official LiberoProcessorStep + saved checkpoint pre/postprocessors; RGB256 lossless; state8 = TCP xyz + axis-angle + finger qpos",
            "config_state_dimension": cfg.input_features["observation.state"].shape[0],
            "actual_state_dimension": 8,
            "schedule": "select_action on every 20Hz simulated tick; original internal action queue; fresh observation each tick",
            "n_action_steps": cfg.n_action_steps,
            "n_obs_steps": cfg.n_obs_steps,
            "action_bounds": "postprocessed OSC values clipped to [-1,1], clipping count recorded",
            "sampling_steps": getattr(
                cfg, "num_steps", getattr(cfg, "num_inference_steps", None)
            )
            or getattr(cfg, "num_train_timesteps", None),
            "strict_weights": True,
        }
        if self.family == "smolvla":
            self.metadata["tokenizer"] = TOKENIZER
        self.reset(0)

    def reset(self, seed):
        import random
        import numpy as np

        random.seed(seed)
        np.random.seed(seed)
        self.torch.manual_seed(seed)
        self.policy.reset()
        self.pre.reset()
        self.post.reset()
        return {"reset": True}

    def act(self, task, sensors, images):
        import numpy as np
        from PIL import Image

        t = self.torch
        batch = {
            "task": [task],
            "observation.robot_state": {
                "eef": {
                    "pos": t.tensor([sensors["tcp_position"]]),
                    "quat": t.tensor([sensors["tcp_quaternion_xyzw"]]),
                },
                "gripper": {"qpos": t.tensor([sensors["gripper_joint_positions"]])},
            },
        }
        for name, key in (("external", "image"), ("wrist", "image2")):
            rgb = np.array(
                Image.open(io.BytesIO(base64.b64decode(images[name]))).convert("RGB")
            )
            if rgb.shape != (256, 256, 3):
                raise ValueError(
                    "LeRobot LIBERO checkpoints require lossless RGB 256x256 observations"
                )
            # ManiLoop sends raw[::-1] for its top-left display. Undo that before the
            # official processor flips H and W to the HuggingFace LIBERO dataset convention.
            batch[f"observation.images.{key}"] = (
                t.from_numpy(rgb[::-1].copy()).permute(2, 0, 1).unsqueeze(0).float()
                / 255
            )
        batch = self.env_processor.observation(batch)
        if batch["observation.state"].shape != (1, 8):
            raise ValueError("Invalid LIBERO proprioception shape")
        queue = (
            self.policy._queues["action"]
            if self.family != "act"
            else self.policy._action_queue
        )
        inference = not bool(queue)
        started = time.monotonic()
        with t.inference_mode():
            action = (
                self.post(self.policy.select_action(self.pre(batch)))
                .float()
                .cpu()
                .numpy()
                .reshape(-1)
            )
        if action.shape != (7,) or not np.isfinite(action).all():
            raise ValueError("Model produced invalid OSC action")
        clipped = np.clip(action, -1, 1)
        return {
            "action": clipped.tolist(),
            "usage": {
                "model_inferences": int(inference),
                "policy_seconds": time.monotonic() - started,
                "clipped_action_values": int(np.count_nonzero(action != clipped)),
            },
        }


def main():
    wire, runtime = sys.stdout, None
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                op, args = request["op"], request.get("args", {})
                if op == "init":
                    runtime = Runtime(**args)
                    result = runtime.metadata
                elif op == "reset":
                    result = runtime.reset(**args)
                elif op == "act":
                    result = runtime.act(**args)
                else:
                    raise ValueError("Unknown policy operation")
            reply = {"id": request["id"], "ok": True, "result": result}
        except Exception as exc:
            import traceback

            traceback.print_exc(file=sys.stderr)
            reply = {
                "id": request.get("id"),
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        wire.write(json.dumps(reply, allow_nan=False) + "\n")
        wire.flush()


if __name__ == "__main__":
    main()
