# ARX X5 model provenance

The arm geometry, kinematic chain, published inertias and arm joint limits come from
[real-stanford/arx5-sdk](https://github.com/real-stanford/arx5-sdk), revision
`a8890c9bae94464abd1cb7c5e4da7c4a62104a3a`.
The original `models/X5.urdf`, SDK configuration excerpt and MIT license are retained
in `upstream/`. The mesh assets are derived from the corresponding X5 meshes.

This is the **standard ARX X5**, not the ARX L5 or an assertion that the model
matches a particular X5 2025 hardware revision. Confirm the physical robot revision
before any future real-robot adaptation.

The published URDF contains six actuated arm joints; its complete gripper is static
geometry attached to link6. For this demo the supplied link6 geometry was separated
into gripper base, left finger and right finger meshes. Two symmetric slide joints
(0–44 mm travel each), approximate finger inertias, position actuators and fingertip
contact pads were added. Collision meshes separate the actual finger portions so a
convex hull does not fill the visible jaw opening. The 88 mm nominal opening is a
simulation configuration, not a calibration certificate for a physical gripper.
Finger actuation, gains, damping, friction and contact parameters are **approximations**.

The arm uses the source kinematics and simplified collision shapes. Gravity
compensation and position control approximate a local robot controller. The scene,
RGB-D/external and RGB/wrist cameras, tabletop, 30 mm red cube and green target area
were authored for this experiment. RGB-D depth is ideal simulated depth; the current
demo does not model the full noise/failure characteristics of a real depth camera.

The cube is an ordinary MuJoCo free body manipulated through contact and friction.
There are no weld constraints, object attachments or object teleportation during
control. The reset function alone initializes the cube position.

The contact grasp/transport/release regression test validates this model's ability
to manipulate the cube. It is a scripted **test of the execution layer**, separate
from the GPT policy, and does not establish model-driven or real-world success.
