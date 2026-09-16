"""Verify and encode one uncut LIBERO control-step recording as a dual-view MP4.

Usage: python -m maniloop.recording.video runs/<episode>/recording --ffmpeg PATH
The encoder is an external executable; no VLA dependency is imported here.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

from PIL import Image, ImageDraw


def verify_episode(directory):
    directory = Path(directory).resolve()
    metadata = json.loads((directory / "episode.json").read_text(encoding="utf-8"))
    if metadata.get("format") != "maniloop_control_step_recording_v1" or metadata.get("interpolated") is not False:
        raise ValueError("Unsupported or interpolated recording")
    raw = (directory / "frames.jsonl").read_bytes()
    if hashlib.sha256(raw).hexdigest() != metadata.get("frames_sha256"):
        raise ValueError("Frame index digest mismatch")
    frames = [json.loads(line) for line in raw.splitlines()]
    if not 1 <= len(frames) <= 991 or len(frames) != metadata.get("frame_count"):
        raise ValueError("Invalid recording frame count")
    evaluation = metadata.get("evaluation", {})
    if evaluation.get("control_steps") != len(frames) - 1:
        raise ValueError("Final evaluator does not match recording length")
    if evaluation.get("evaluator") != "libero_check_success" or type(evaluation.get("success")) is not bool:
        raise ValueError("Missing official LIBERO evaluator result")
    if metadata.get("control_timestep") != 0.05:
        raise ValueError("Recording must retain the original 20 Hz control clock")
    if metadata.get("initial_evaluation", {}).get("control_steps") != 0:
        raise ValueError("Recording does not start at initialization")
    for index, frame in enumerate(frames):
        if frame.get("control_step") != index or not math.isclose(frame.get("simulation_time", -1), index * 0.05, abs_tol=1e-9):
            raise ValueError("Recording has a missing, repeated, or reordered control step")
        action = frame.get("action")
        if index == 0:
            if action is not None:
                raise ValueError("Initialization must precede the first action")
        elif (not isinstance(action, list) or len(action) != 7
              or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1 for v in action)):
            raise ValueError("Invalid native control action")
        if set(frame.get("images", {})) != {"external", "wrist"}:
            raise ValueError("Missing dual-camera frame")
        for camera, image in frame["images"].items():
            filename = image.get("file", "")
            if filename != f"{index:06d}-{camera}.jpg" or not re.fullmatch(r"\d{6}-(external|wrist)\.jpg", filename):
                raise ValueError("Unsafe or mismatched camera filename")
            path = directory / filename
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != image.get("sha256"):
                raise ValueError("Camera frame digest mismatch")
    return metadata, frames


def export_video(directory, *, ffmpeg=None, allow_failure=False):
    directory = Path(directory).resolve()
    metadata, frames = verify_episode(directory)
    success = metadata["evaluation"]["success"]
    if not allow_failure and (not success or metadata["initial_evaluation"].get("success") is not False):
        raise ValueError("A successful demo must start unsuccessful and end with official success; use --allow-failure for review")
    binary = ffmpeg or shutil.which("ffmpeg")
    if not binary or not Path(binary).is_file():
        raise ValueError("ffmpeg was not found; supply --ffmpeg with an installed encoder path")
    destination = directory / "episode.mp4"
    if destination.exists():
        raise FileExistsError("Refusing to overwrite episode.mp4")
    with Image.open(directory / frames[0]["images"]["external"]["file"]) as first:
        width, height = first.size
    canvas_size = (2 * width, height + 56)
    if any(value % 2 for value in canvas_size):
        raise ValueError("H.264 export requires even image dimensions")
    partial = directory / "episode.partial.mp4"
    process = subprocess.Popen([
        str(binary), "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
        "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{canvas_size[0]}x{canvas_size[1]}",
        "-framerate", "20", "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "medium",
        "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(partial),
    ], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame in frames:
            canvas = Image.new("RGB", canvas_size, "#111b24")
            for offset, camera in enumerate(("external", "wrist")):
                with Image.open(directory / frame["images"][camera]["file"]) as image:
                    if image.size != (width, height):
                        raise ValueError("Camera resolution changed inside the episode")
                    canvas.paste(image.convert("RGB"), (offset * width, 28))
            draw = ImageDraw.Draw(canvas)
            draw.text((10, 8), "EXTERNAL CAMERA", fill="white")
            draw.text((width + 10, 8), "WRIST CAMERA", fill="white")
            label = f"Step {frame['control_step']:03d} | simulation {frame['simulation_time']:.2f}s | 20 Hz | single uncut episode"
            draw.text((10, height + 36), label, fill="white")
            process.stdin.write(canvas.tobytes())
        process.stdin.close()
        error = process.stderr.read().decode("utf-8", errors="replace")
        if process.wait() != 0:
            raise RuntimeError(f"ffmpeg failed: {error[:1000]}")
        partial.rename(destination)
    except BaseException:
        if process.poll() is None:
            process.kill()
            process.wait()
        partial.unlink(missing_ok=True)
        raise
    finally:
        process.stderr.close()
        if not process.stdin.closed:
            process.stdin.close()
    sidecar = {"video": destination.name, "video_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
               "frames_sha256": metadata["frames_sha256"], "frame_count": len(frames), "fps": 20,
               "simulation_duration_seconds": (len(frames) - 1) / 20,
               "video_duration_seconds": len(frames) / 20, "evaluation": metadata["evaluation"],
               "playback": metadata["playback"], "interpolated": False, "cut": False}
    (directory / "video.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--ffmpeg", help="Path to ffmpeg; defaults to PATH")
    parser.add_argument("--allow-failure", action="store_true", help="Also export a complete unsuccessful attempt for review")
    args = parser.parse_args()
    print(export_video(args.directory, ffmpeg=args.ffmpeg, allow_failure=args.allow_failure))


if __name__ == "__main__":
    main()
