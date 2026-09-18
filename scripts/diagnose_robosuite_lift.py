"""Privileged physics diagnostic, NOT a policy or a model success benchmark.

Run with .venv-robosuite/bin/python. This script reads the cube ground truth
only to check that the integrated controller and upstream physics can lift it.
No oracle information is added to the worker RPC or any Agent observation.
"""
import argparse
import base64
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/maniloop/backends/robosuite'))
from worker import Runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/robosuite-lift-diagnostic')
    args = parser.parse_args()
    runtime = Runtime(dict(task='Lift', seed=args.seed, render=True))
    from robosuite.utils.transform_utils import quat2axisangle, mat2quat
    report = {'is_oracle': True, 'model_tested': False, 'seed': args.seed, 'phases': []}
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        orientation = np.array(runtime.sensors()['tcp_rotation_matrix'])
        cube = np.array(runtime.env.sim.data.body_xpos[runtime.env.cube_body_id])
        def drive(name, target, grip, steps):
            for _ in range(steps):
                if runtime.done:
                    break
                sensors = runtime.sensors()
                dp = np.asarray(target) - sensors['tcp_position']
                dp *= min(1.0, .02 / max(np.linalg.norm(dp), 1e-12))
                dr = quat2axisangle(mat2quat(orientation @ np.array(sensors['tcp_rotation_matrix']).T))
                dr *= min(1.0, .2 / max(np.linalg.norm(dr), 1e-12))
                runtime.step(np.r_[dp / .05, dr / .5, grip].tolist())
            report['phases'].append({'name': name, 'tcp': runtime.sensors()['tcp_position'],
                                      'evaluation': runtime.evaluation()})
        drive('open', runtime.sensors()['tcp_position'], -1, 20)
        drive('approach', cube + [0, 0, .10], -1, 45)
        drive('descend', cube + [0, 0, .008], -1, 45)
        drive('close', cube + [0, 0, .008], 1, 25)
        drive('lift', cube + [0, 0, .18], 1, 60)
        report['evaluation'] = runtime.evaluation()
        report['description'] = runtime.description
        for camera, encoded in runtime.observe()['images'].items():
            (args.output / (camera + '.jpg')).write_bytes(base64.b64decode(encoded))
        (args.output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({'is_oracle': True, 'model_tested': False, **runtime.evaluation()}))
        if not report['evaluation']['success']:
            raise SystemExit('Physics diagnostic did not succeed; inspect recorded phases.')
    finally:
        runtime.close()


if __name__ == '__main__':
    main()
