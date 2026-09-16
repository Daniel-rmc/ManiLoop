# ManiLoop

**[English](README.md)** · [简体中文](README.zh-CN.md)

A MuJoCo framework for testing GPT and learned robot manipulation policies with visual feedback, local controls, and recorded episodes.

[Project website](https://daniel-rmc.github.io/ManiLoop/) · [Interactive workspace](https://daniel-rmc.github.io/ManiLoop/playground/?lang=en) · [Watch the successful episode](https://daniel-rmc.github.io/ManiLoop/#demo) · [Model results](docs/RESULTS.md)

![ManiLoop tabletop simulation](docs/images/scene.jpg)

## What you can do

- **Run GPT in a visual control loop.** The model observes external and wrist cameras, chooses a bounded action, and sees the result before deciding again. Connect through Codex ChatGPT login or a compatible Responses API.
- **Test local policies.** Run SmolVLA, ACT, and Diffusion Policy checkpoints through an isolated LeRobot process, with CPU, Apple MPS, or CUDA inference.
- **Choose a simulation environment.** Use the bundled ARX X5 and Franka Panda tabletop scenes, or install official LIBERO tasks with their original Panda controller, initial states, and success checks.
- **Inspect individual decisions.** Use the browser interface for manual controls, single steps, pause/resume, paired before/after observations, and offline decision replay.
- **Record complete episodes.** Save every LIBERO control-step frame and export a dual-camera MP4. CLI runs also save actions, observations, configuration, and independent evaluation results.

Policies receive camera observations and robot sensor state. Object ground truth, simulator contact lists, rewards, and success signals stay outside the policy input. The evaluator can use simulator state independently, and its result controls episode termination.

## Successful demonstration

[Watch GPT-6 Astra perform the LIBERO bowl task →](https://daniel-rmc.github.io/ManiLoop/#demo)

GPT-6 completed one continuous attempt from the official initialization with **46 decisions and 706 control steps**. The video retains the unsuccessful grasp attempts and subsequent adjustments within that episode: **707 dual-camera frames, 20 fps, 35.35 seconds**. Playback follows simulation time and omits the waiting time between model responses.

The official success condition became true during the final lowering action, and execution stopped immediately. Release and retreat after that point were not tested. This is an observed task success, not evidence of a benchmark-wide success rate. See [results and evaluation details](docs/RESULTS.md).

## Install and open the simulator

Use **Python 3.12** and run commands from the repository root. You need an OpenGL rendering context; a local GPU or model weights are not required for hosted GPT inference. The base installation does not require ROS, Docker, or a physical robot.

### macOS / Linux

```bash
git clone https://github.com/Daniel-rmc/ManiLoop.git
cd ManiLoop
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m maniloop demo
```

### Windows PowerShell

```powershell
git clone https://github.com/Daniel-rmc/ManiLoop.git
cd ManiLoop
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m maniloop demo
```

On Windows, use `.\.venv\Scripts\python.exe` in place of `python`. The remaining multiline examples use Bash syntax; in PowerShell, join their lines into one command. No activation script or execution-policy change is required.

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). You can choose a robot and task, move the arm, operate the gripper, and reset the scene without connecting a model. Keep the terminal running; `Ctrl+C` closes the server. The service listens only on localhost.

For headless Ubuntu/Debian, install `libosmesa6` and set `MUJOCO_GL=osmesa` before launching Python. EGL is another option when compatible GPU drivers are available. Do not apply these Linux settings to macOS.

## Run GPT on LIBERO

LIBERO uses its own Python 3.10 environment. Install it separately from the main Python 3.12 application:

```bash
python -m pip install uv
python scripts/setup_libero.py
python -m maniloop list --backend libero
python -m maniloop smoke --backend libero
```

The installer needs Git and network access; it downloads a managed Python interpreter and the pinned LIBERO source and assets. No VLA weights or demonstration dataset are needed. If you use Windows without activation, pass the installed `uv` explicitly:

```powershell
.\.venv\Scripts\python.exe -m pip install uv
.\.venv\Scripts\python.exe scripts/setup_libero.py --uv .\.venv\Scripts\uv.exe
```

For account-based access, install a current official [Codex CLI](https://github.com/openai/codex), run `codex login`, and then start the page:

```bash
python -m maniloop demo --backend libero --codex-login --port 8767
```

Open [http://127.0.0.1:8767](http://127.0.0.1:8767). Choose the Codex source, load a task, and use single-step or continuous execution. Codex manages its own login; ManiLoop does not extract its tokens. If multiple CLI versions are installed, set `MANILOOP_CODEX_BIN` to the intended executable.

You can instead select an API provider in the page and supply its base URL, model ID, and API key, or import a TOML configuration. Robot control requires image input and JSON Schema output through the Responses API. Model requests use the selected account's quota or provider billing; opening the page does not start inference.

To record a complete attempt with GPT-6:

```bash
python -m maniloop benchmark \
  --backend libero --libero-suite libero_spatial --libero-task-id 0 \
  --init-state-id 0 --seed 0 --agent llm_cloud --codex-login \
  --model gpt-6-astra --context-mode paired --reasoning-effort medium \
  --max-calls 0 --max-wall-seconds 3600 --record-episode \
  --output runs/gpt-demo
```

`--max-calls 0` removes the decision-count limit. Official environment termination, simulation limits, and the wall-clock budget still apply. Physics pauses during inference in the default `controlled` mode. A new run is not guaranteed to reproduce the showcased outcome.

See the [LIBERO guide](docs/LIBERO.md) and [GPT control guide](docs/GPT6_DEMO.md) for task selection, diagnostics, camera profiles, and control settings.

## Test local models

After installing LIBERO, download the supported checkpoints into a separate inference environment:

```bash
python scripts/setup_vla.py --models smolvla-libero act-libero diffusion-libero
python -m maniloop benchmark --backend libero --agent lerobot \
  --local-model smolvla-libero --max-calls 500 \
  --max-sim-seconds 25 --max-wall-seconds 1800
```

Running the installer without `--models` downloads only SmolVLA. Windows users can add `--uv .\.venv\Scripts\uv.exe` as above. In the browser, choose the local LeRobot source and a downloaded model. SmolVLA accepts the language instruction; the selected ACT and Diffusion checkpoints use images and robot state without language conditioning.

| Environment | Purpose |
| --- | --- |
| `.venv` · Python 3.12 | ManiLoop, UI, model connections, and bundled MuJoCo scenes |
| `.venv-libero` · Python 3.10 | Official LIBERO simulation and its pinned dependencies |
| `.venv-vla` · Python 3.12 | LeRobot and learned-policy inference |

Keep these environments separate. Checkpoints are downloaded independently and are not included in the repository. See [local model setup and sources](docs/VLA.md).

### Observed model results

Each row is **one selected run** of `libero_spatial`, task 0, init 0, seed 0.

| Model | Official result | Control steps | GPT requests / local inferences | Simulation time |
| --- | --- | ---: | ---: | ---: |
| GPT-6 Astra | Success | 706 | 46 | 35.30 s |
| SmolVLA | Success | 78 | 2 | 3.90 s |
| ACT | Not successful within the budget | 500 | 5 | 25.00 s |
| Diffusion Policy | Success | 79 | 10 | 3.95 s |

These observations are not a success-rate estimate or a model ranking. GPT requests produce individual high-level actions; local policies cache action chunks, so their inference counts have a different meaning. The runs also differ in observations, controllers, budgets, and entry points. Wall-clock durations are not directly comparable. [Full conditions and sources](docs/RESULTS.md).

## Record, replay, and diagnose

Runs are saved under `runs/` with their manifest, events, observations, independent score, and decision replay. With `--record-episode`, `recording/` also contains the initial frame and every native control-step frame from that same attempt. Successful and unsuccessful attempts remain separate.

With `ffmpeg` installed, export the complete recording:

```bash
python -m maniloop.recording.video runs/gpt-demo/EPISODE_ID/recording
```

Replace `EPISODE_ID` with the actual run directory name. The exporter verifies the frame sequence and hashes before creating `episode.mp4`. Use `--ffmpeg /path/to/ffmpeg` for an encoder outside PATH, or `--allow-failure` to export an unsuccessful attempt for review. See [episode recording](docs/EPISODE_RECORDING.md).

For a standalone API text chat page:

```bash
python -m maniloop chat --port 8769
```

Open [http://127.0.0.1:8769/chat](http://127.0.0.1:8769/chat). This page supports Responses and Chat Completions and operates independently of robot tasks. [Chat setup](docs/API_CHAT.md).

To check the installation without model requests:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m maniloop smoke
```

Offline tests run on macOS, Linux, and Windows. Rendering has been checked on macOS and Linux OSMesa; Windows rendering and LIBERO execution have not been validated. A rendering check needs a graphics backend; the test suite does not make paid model requests.

The framework runs in simulation. The ARX gripper is approximate, and the software has not been validated as a real-robot control or safety system. Using official LIBERO assets does not by itself reproduce a paper's complete evaluation protocol. See [architecture and interfaces](docs/ARCHITECTURE.md) for the observation, action, and evaluation boundaries.

<a id="许可证与贡献"></a>

## License

ManiLoop is [MIT licensed](LICENSE). ARX X5 assets retain their upstream MIT notice; Panda assets retain Apache-2.0. LIBERO, LeRobot, and downloaded checkpoints retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md) for sources and redistribution requirements.
