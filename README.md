# ManiLoop

**[English](README.md)** · [简体中文](README.zh-CN.md)

**Run robot manipulation experiments locally, and inspect the full visual control loop.** ManiLoop connects GPT or learned policies to MuJoCo tasks through a browser workspace and CLI: choose a task, connect a model, execute actions, and review what actually happened.

**[Get started ↓](#step-1--open-the-local-workspace)** · [Connect a model](#step-3--connect-your-model) · [Observed results](docs/RESULTS.md#english) · [Project website](https://daniel-rmc.github.io/ManiLoop/?lang=en)

![The running local ManiLoop application: dual simulation cameras, task selection, and Codex model configuration](docs/images/workspace-local.png)

*The actual local application, shown in its current Chinese interface. This is the working simulator UI, not the website’s recorded replay.*

[Watch GPT place a bowl, turn a stove knob, and move cream cheese into a basket](https://daniel-rmc.github.io/ManiLoop/?lang=en#skills): play verified episodes, pause at each action, and read the model's recorded action notes alongside the controller feedback. Full videos and execution conditions are included.

These three recorded GPT successes took **5.5–11.1 minutes of episode wall time**, including model planning, communication, execution and recording, after scene and policy loading. These are selected examples, not average completion times or a speed ranking. [See timing and results](docs/RESULTS.md#recorded-wall-clock-time).

## What you can run

The workspace brings **camera observations, model actions, controller feedback, and independent evaluation** together. Use manual controls before connecting a model, single-step GPT decisions, pause and resume, compare before/after observations, run CLI experiment matrices, and export complete LIBERO episodes.

| Environment / task | Available operations |
| --- | --- |
| Built-in `pick_place` | Lift the red cube, place it inside the target region, release, and settle |
| Built-in `push` | Push the cube along the table into the target region without lifting it |
| `libero_spatial` · 10 tasks | Select and move a bowl based on its spatial relationship to other objects |
| `libero_object` · 10 tasks | Pick different objects and place them in a basket |
| `libero_goal` · 10 tasks | Goal variants including drawer opening, object placement, plate pushing, and stove control |
| `libero_90` · 90 tasks | Kitchen, living-room, and study tasks, including drawers, microwaves, and stacking |
| `libero_10` · 10 tasks | Longer tasks combining multiple objects or manipulation operations |

The built-in tasks support **ARX X5 and Franka Panda**, each with `tabletop_a` and `tabletop_b` layouts. LIBERO uses its official Panda, initial states, OSC controller, and success rules. These are available task catalogs; they do not mean every task has been completed by every model. Changing the instruction text does not change a task’s evaluator.

Policies receive images and robot sensor state. **Object ground truth, simulator contacts, rewards, and success signals are excluded from policy input.** Independent evaluation can inspect simulator state and stop an episode; a model’s `done` declaration is not the success criterion.

[See real manual debugging: arm and gripper controls, sensor readings, execution feedback, and independent evaluation](docs/images/workspace-feedback.png). This screenshot shows feedback from a manual jog, not a successful task.

## Step 1 · Open the local workspace

Use **Python 3.12**, Git, and an OpenGL-capable environment. Hosted GPT inference does not require local model weights or a local GPU. The base application needs neither ROS, Docker, nor a physical robot.

**macOS / Linux**

```bash
git clone https://github.com/Daniel-rmc/ManiLoop.git
cd ManiLoop
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m maniloop demo
```

**Windows PowerShell**

```powershell
git clone https://github.com/Daniel-rmc/ManiLoop.git
cd ManiLoop
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m maniloop demo
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Select a robot, layout, and task; apply the configuration, try manual arm and gripper controls, then reset. **No API key is needed for this step.** The server listens on localhost; keep its terminal open and press `Ctrl+C` to stop it. Use `--port 8766` if needed.

Continue from the repository root after stopping the server. **Windows:** replace subsequent `python` commands with `.\.venv\Scripts\python.exe`; join multiline Bash examples into one line, removing trailing `\`. After installing `uv`, add `--uv .\.venv\Scripts\uv.exe` when running either setup script. No activation script or execution-policy change is required.

For headless Ubuntu/Debian, install `libosmesa6` and set `MUJOCO_GL=osmesa` before starting Python. EGL is another option with compatible drivers. These Linux settings do not apply to macOS.

<a id="run-gpt-on-libero"></a>

## Step 2 · Add official LIBERO tasks

```bash
python -m pip install uv
python scripts/setup_libero.py
python -m maniloop list --backend libero --libero-suite libero_goal
python -m maniloop smoke --backend libero
python -m maniloop demo --backend libero --port 8767
```

Open [http://127.0.0.1:8767](http://127.0.0.1:8767). Select a suite, task ID, and initialization ID in the environment panel. IDs start at zero; `list` prints the available task names. The default is `libero_spatial` task 0, init 0: move the black bowl between the plate and ramekin onto the plate.

The installer needs network access and several GB of disk space, but no demonstration dataset or policy weights. It downloads the pinned official source, assets, and a managed interpreter while keeping dependencies separate:

| Environment | Purpose |
| --- | --- |
| `.venv` · Python 3.12 | Main application, UI, model connections, bundled MuJoCo scenes |
| `.venv-libero` · Python 3.10 | LIBERO simulation and its pinned dependencies |
| `.venv-vla` · Python 3.12 | Optional LeRobot inference and learned policies |

Keep these environments separate. See [LIBERO setup and task selection](docs/LIBERO.md).

## Step 3 · Connect your model

Choose one route below. Stop the existing server before running a different launch command.

| Model route | How to connect | Compatibility boundary |
| --- | --- | --- |
| GPT through Codex | Official Codex CLI login; select the Codex source | Uses models available to that CLI/account; ManiLoop does not extract login tokens |
| Hosted or self-hosted vision model | Enter the service base URL, model ID, and API key, or import provider TOML | Robot control requires **Responses API + image input + JSON Schema output** |
| Local LeRobot checkpoints | Select a supported model loaded by the isolated inference worker | Three reviewed LIBERO checkpoint presets; not arbitrary model-folder import |

<details><summary>See model controls in the actual local application</summary>

![Task and model configuration in the running local ManiLoop application](docs/images/workspace-models.png)

*Current local UI; model and task settings here configure real execution.*
</details>

### GPT / compatible model APIs

Install a current official [Codex CLI](https://github.com/openai/codex), then:

```bash
codex login
python -m maniloop demo --backend libero --codex-login --port 8767
```

Choose the Codex source and load the GPT demo preset. Start with the text/image/action-format diagnostics or a single action. `MANILOOP_CODEX_BIN` selects the executable if several CLI versions are installed. See [GPT controls](docs/GPT6_DEMO.md).

For an API connection, select the manual or imported-config source, enter your model ID and the provider’s base URL, then supply its key. Examples: [OpenAI configuration](examples/openai.example.toml), [custom provider configuration](examples/custom.example.toml). A model you host locally can use this route **if its server implements the required Responses protocol**; a local base URL can be `http://127.0.0.1:8000/v1`. A Chat Completions-only server is not compatible with robot control; the separate [text chat page](docs/API_CHAT.md) supports both protocols. Selecting a model ID does not guarantee it supports vision or structured actions. Requests consume the selected account quota or provider billing; opening the page does not start inference.

### Local SmolVLA, ACT, and Diffusion Policy

```bash
python scripts/setup_vla.py --models smolvla-libero act-libero diffusion-libero
python -m maniloop demo --backend libero --port 8767
```

Select the local LeRobot source and a downloaded model. Omit `--models` to install only SmolVLA. Inference runs offline on CPU, Apple MPS, or CUDA; the checkpoint’s saved preprocessing and action queue are retained.

Or run a local checkpoint from the CLI; replace `smolvla-libero` with `act-libero` or `diffusion-libero` to select another installed preset:

```bash
python -m maniloop benchmark --backend libero --agent lerobot \
  --local-model smolvla-libero --libero-suite libero_spatial --libero-task-id 0 \
  --init-state-id 0 --seed 0 --max-calls 500 --max-sim-seconds 25 \
  --max-wall-seconds 1800 --output runs/local-demo
```

| Preset | Checkpoint | Input |
| --- | --- | --- |
| `smolvla-libero` | [lerobot/smolvla_libero](https://huggingface.co/lerobot/smolvla_libero) · official | Images, robot state, language |
| `act-libero` | [Deepkar/libero-test-act](https://huggingface.co/Deepkar/libero-test-act) · community | Images and robot state |
| `diffusion-libero` | [ttotmoon/diffusion-libero-v3](https://huggingface.co/ttotmoon/diffusion-libero-v3) · community | Images and robot state |

To use these presets **already stored on another local disk**, set `MANILOOP_MODELS_ROOT` to their parent directory. It must contain the preset-named folders, such as `smolvla-libero/`, plus `smolvlm-tokenizer/` for SmolVLA. `MANILOOP_VLA_PYTHON` can point to a compatible inference environment. These options relocate supported snapshots; they do not import arbitrary Hugging Face repositories or custom weights. Details and fixed revisions: [local model guide](docs/VLA.md).

### Integrating your own checkpoint or policy

A new checkpoint needs its own model registration, correct preprocessing and action mapping, and source metadata. Do not replace a preset’s files and treat the result as that preset. For a custom inference implementation, implement [`Agent`](src/maniloop/agents/base.py): `reset()` and `decide(task, observation, images, history, geometry_results)`, returning an action dictionary or [`ActionChunk`](src/maniloop/core/actions.py). Connect it to `EpisodeRunner`, and add a CLI/UI choice if needed; there is no automatic arbitrary-checkpoint loader.

A new simulation backend implements [`Environment`](src/maniloop/backends/base.py) and is registered through the [environment factory](src/maniloop/backends/factory.py). Match camera/state inputs, action dimensions, units, and timing, while keeping evaluation separate. See [architecture and extension interfaces](docs/ARCHITECTURE.md).

## Step 4 · Record a run and inspect its result

Run a new GPT-6 attempt from official initialization, with all LIBERO control steps recorded:

```bash
python -m maniloop benchmark \
  --backend libero --libero-suite libero_spatial --libero-task-id 0 \
  --init-state-id 0 --seed 0 --agent llm_cloud --codex-login \
  --model gpt-6-astra --context-mode paired --reasoning-effort medium \
  --max-calls 0 --max-wall-seconds 3600 --record-episode \
  --output runs/gpt-demo
```

Default `controlled` timing pauses physics during inference. `--max-calls 0` removes the decision-count cap; official termination, simulation limits, and the wall-clock budget still apply. Each attempt gets a separate directory containing `manifest.json`, `events.jsonl`, `result.json`, and `replay.html`. Inspect **`result.json → evaluation.success`** for the independent outcome; open `replay.html` locally for decision-by-decision review. Full frames and integrity metadata are in `recording/`.

With `ffmpeg` installed, export the video:

```bash
python -m maniloop.recording.video runs/gpt-demo/EPISODE_ID/recording
```

Replace `EPISODE_ID` with the actual run directory name. The exporter checks frame order and hashes before creating `episode.mp4`; use `--ffmpeg /path/to/ffmpeg` if needed. Failed runs remain saved and can be exported with `--allow-failure`. Playback follows simulation time and omits frozen model waiting. See [recording and export](docs/EPISODE_RECORDING.md). To batch the three local models using the [example matrix](examples/libero-local-suite.toml), run `python -m maniloop benchmark --suite examples/libero-local-suite.toml --output runs/local-suite`.

## Recorded examples and observed results

[Explore the recorded workspace](https://daniel-rmc.github.io/ManiLoop/playground/?lang=en) or [watch the successful episode](https://daniel-rmc.github.io/ManiLoop/?lang=en#demo) without installing anything. The public replay uses saved data; **new tasks and model calls run in the local application**. Try “Single step”, compare “Before action” / “After action”, and jump to decision 46’s final frame.

The GPT episode contains 46 decisions and 706 control steps, including grasp retries. Its complete video has 707 dual-camera frames at 20 fps, lasting 35.35 seconds. Official success triggered during the final lowering action; the environment stopped immediately without an additional release or retreat check.

| Model | Official outcome | GPT requests / local inferences | Control steps | Simulation time |
| --- | --- | ---: | ---: | ---: |
| GPT-6 Astra | Success | 46 | 706 | 35.30 s |
| SmolVLA | Success | 2 | 78 | 3.90 s |
| ACT | Not successful within budget | 5 | 500 | 25.00 s |
| Diffusion Policy | Success | 10 | 79 | 3.95 s |

Each row is **one selected run** on `libero_spatial` task 0 / init 0 / seed 0, not a success rate or ranking. GPT produces high-level actions; local inference generates queues consumed over multiple control steps. Inputs, controllers, budgets, and execution paths differ, so wall-clock times are not directly comparable. New model runs may produce different outcomes. [Full results and conditions](docs/RESULTS.md#english).

## Guides, checks, and scope

[LIBERO tasks](docs/LIBERO.md) · [GPT controls](docs/GPT6_DEMO.md) · [Local checkpoints](docs/VLA.md) · [API text chat](docs/API_CHAT.md) · [Recording](docs/EPISODE_RECORDING.md) · [Architecture](docs/ARCHITECTURE.md)

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m maniloop smoke
```

These checks do not make model requests. Offline tests cover macOS, Linux, and Windows; rendering has been verified on macOS and Linux OSMesa. Windows rendering and LIBERO execution have not been validated. Rendering needs a graphics backend. ManiLoop is simulation software: the ARX gripper is approximate, and real-robot control or safety has not been validated. Official LIBERO assets alone do not establish paper-level benchmark comparability.

<a id="许可证与贡献"></a>

## License

ManiLoop is [MIT licensed](LICENSE). ARX X5 assets retain MIT; Panda assets retain Apache-2.0. LIBERO, LeRobot, and downloaded checkpoints retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md).

## Optional robosuite tasks

Add Panda Lift, Stack, PickPlaceCan, Door, and NutAssemblySquare in an isolated
robosuite runtime, without changing LIBERO. Use the existing workspace for manual
control, model connections, and decision review. See [setup and limitations](docs/ROBOSUITE.md).

```bash
python scripts/setup_robosuite.py
python -m maniloop demo --backend robosuite --task Lift --port 8870
```

These are integrated environments, not model-success claims. Existing LIBERO-trained
local checkpoint presets remain LIBERO-only; RoboCasa is not included in this backend.

## Optional RoboCasa kitchen tasks

Four kitchen tasks are available through a separate PandaOmron backend: `OpenDrawer`,
`CloseDrawer`, `OpenCabinet`, and `CoffeeSetupMug`. The first integration controls the
arm and gripper; base velocity and torso delta inputs are held at zero.

```bash
python scripts/setup_robocasa.py --download-assets
python -m maniloop demo --backend robocasa --task OpenDrawer --port 8872
```

Use the same workspace for camera observations, manual controls, model connections,
and decision review. The installer pins both source projects and isolates their dependencies.
The five required asset groups occupy about 11.1 GB unpacked, excluding source/runtime files.
Default layout 11 / style 14 / seed 0 has real interface checks for all four tasks;
this is not a model success result or a guarantee of arm-only task solvability in every scene.
See [RoboCasa setup, action semantics, and limitations](docs/ROBOCASA.md).


### Operator workspace

The workspace separates manual control, model execution, and scene settings. Stop stays available while switching panels; camera layouts do not advance physics. See [workspace usage](docs/WORKSPACE.md) and [six-dimensional manual control](docs/MANUAL_CONTROL.md).

### Jev text commands

Choose **Jev · 文本原语控制** in the model panel to map explicit, one-line commands
to bounded arm or gripper primitives. Enter a separate TypeSafe API key in the workspace;
it is kept in server memory and is not shared with OpenAI connections. Saving the key
does not call the model; connection diagnostics and execution use the TypeSafe API.

Jev receives text and robot proprioception, without camera images or object state.
This mode supports commands such as moving 10 mm or rotating the tool 5 degrees;
it does not autonomously locate or grasp objects. Completing the command sequence
is distinct from task success. See [Jev setup, examples, and verification](docs/JEV.md).
