"""Read-only rendering/projection diagnostic, separate from the online policy."""

import io
import json
from pathlib import Path
import numpy as np
from PIL import Image
from .sim import RobotSim


def main():
    sim = RobotSim()
    try:
        observation, images = sim.observe()
        rgb = np.array(Image.open(io.BytesIO(images["external"])))
        green = (
            (rgb[:, :, 1] > 1.5 * rgb[:, :, 0])
            & (rgb[:, :, 1] > 1.5 * rgb[:, :, 2])
            & (rgb[:, :, 1] > 75)
        )
        v, u = np.where(green)
        assert len(u) > 50, "Green reference region not visible"
        pixel = [int(np.median(u)), int(np.median(v))]
        result = sim.depth_query(
            {
                "observation_id": observation["observation_id"],
                "camera": "external",
                "pixel": pixel,
            }
        )
        assert result["valid"], result
        point = np.array(result["position_in_base"])
        target = np.array(sim.config["target_center"])
        assert np.linalg.norm(point[:2] - target[:2]) < 0.03, (point, target)
        assert abs(point[2]) < 0.005, point
        report = {
            "render_ok": True,
            "camera_sizes": {
                k: list(Image.open(io.BytesIO(v)).size) for k, v in images.items()
            },
            "projection_check": result,
            "reference_region_center": target.tolist(),
            "note": "Diagnostic only: reference truth stays outside policy input.",
        }
        path = Path.cwd() / "artifacts" / "render_check.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, ensure_ascii=False))
    finally:
        sim.close()


if __name__ == "__main__":
    main()
