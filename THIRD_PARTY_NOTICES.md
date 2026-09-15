# Third-party notices

The original code and documentation in this repository are distributed under the
root [MIT license](LICENSE).

The ARX X5 URDF, SDK configuration excerpt, and derived mesh assets originate from
[real-stanford/arx5-sdk](https://github.com/real-stanford/arx5-sdk), revision
`a8890c9bae94464abd1cb7c5e4da7c4a62104a3a`.
They retain the upstream MIT notice, Copyright (c) 2024 Yihuai Gao, in
[LICENSE.arx5-sdk](src/maniloop/assets/robots/arx5/upstream/LICENSE.arx5-sdk).
The split fingers, approximate actuators and collision geometry are documented in
[model provenance](src/maniloop/assets/robots/arx5/SOURCES.md).

Python dependencies are installed separately and retain their own licenses;
the project license does not replace those licenses. No Python environment,
API credentials, or vendor SDK binaries are bundled in this repository.

## Franka Emika Panda

The Panda model and meshes are from [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie/tree/8161bba264d7fa7c99ca301e91e7fb44737676ad/franka_emika_panda),
revision `8161bba264d7fa7c99ca301e91e7fb44737676ad`, under the
[Apache-2.0 license](src/maniloop/assets/robots/panda/LICENSE).
The original model, README and changelog are retained. No upstream NOTICE file is supplied in this model directory.
ManiLoop composes the unmodified robot file with a shared tabletop and cube,
adds a TCP site and wrist camera, enables gravity compensation, changes the
initial posture and external camera placement, and applies the common tabletop
contact defaults. The standard Panda tendon and finger equality constraint are retained.
These runtime adaptations do not establish real-robot fidelity or calibration.

## Optional LIBERO backend

[LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO), revision
`8f1084e3132a39270c3a13ebe37270a43ece2a01`, is installed separately under
`.external/LIBERO` with its original MIT license (Copyright 2023 Lifelong Robot
Learning) and included asset provenance. Its resources are not copied into
ManiLoop's package. Preserve upstream and asset-specific notices when redistributing
those resources. Robosuite and the isolated Python dependencies retain their own
licenses; ManiLoop's MIT license does not replace them.

## Optional learned-policy checkpoints

The optional LeRobot integration uses the Apache-2.0 LeRobot package and downloads public model snapshots separately. No learned weights are redistributed in this repository. The selected `lerobot/smolvla_libero`, `Deepkar/libero-test-act` and `ttotmoon/diffusion-libero-v3` model cards declare Apache-2.0; preserve upstream notices when redistributing snapshots. The latter two are community checkpoints, not official LeRobot releases. Sources and pinned revisions are in `src/maniloop/agents/lerobot/catalog.py` and `docs/VLA.md`.
