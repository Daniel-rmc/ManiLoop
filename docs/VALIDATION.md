# ManiLoop v0.1 validation

Validation date: 2026-09-15. Host: macOS Apple Silicon, Python 3.12.14.

Offline test result: **105 passed, 49 subtests passed**.

## Scope and evidence

- The offline suite exercises both ARX X5 and Franka Panda, both tabletop layouts,
  and pick/place plus push tasks through real MuJoCo contact physics.
- The scripted physics tests physically lift, transport and release the cube for
  pick/place; push tests move it along the tabletop. All eight combinations pass.
  These fixtures are confined to tests and never become model policies.
- Runtime tests cover sensor field isolation, reset reproducibility, named joint
  mapping, Panda finger encoders, controlled vs realtime inference clocks, action
  chunk cadence, invalid samples, stopping and discarding old responses, time
  budgets, fixed-policy configuration locking, and recorded comparison groups.
- Existing provider/configuration tests cover TOML plus separate keys, local
  configuration switching, key redaction, model discovery and Responses parsing.
- The eight-case mock VLA batch completes. Its records explicitly identify a mock
  agent; task success is false because the adapter performs only small joint moves.
- A wheel was built and installed with dependencies into a separate fresh virtual
  environment (without system site packages). `pip check` passed; the installed
  package ran a Panda offline episode from outside the source checkout.
- ARX X5 and Panda camera rendering are checked separately. The web interface
  exposes robot, layout, task and timing choices; its debug loop uses the same
  runner as the command-line evaluator.

## Reproduce

From the repository root after installing development dependencies:

```bash
python -m pytest -q
python -m maniloop benchmark --suite examples/offline-suite.toml --no-render
python -m maniloop smoke --robot arx5
python -m maniloop smoke --robot panda
python -m maniloop demo --robot panda
```

The first two commands need no API key or display. Rendering needs a supported
OpenGL backend; Linux CI uses OSMesa. Dependency versions and setup instructions
are in the README and pyproject.toml.

## Limits of these results

No paid model request, real VLA inference, online learning or real robot was used
in this framework validation. Passing physics/controller tests does not establish
an autonomous LLM success rate. The current VLA adapter validates only the interface.

macOS rendering emits `ARB_clip_control unavailable`; RGB images are available,
but depth precision may be lower on this backend. Linux/Windows test workflows and
Linux OSMesa rendering are configured; their actual results must be checked after
publishing the repository to GitHub.

## LIBERO integration — 2026-09-15

The optional backend was installed and tested from the repository on macOS Apple
Silicon. Main Python: 3.12.14; worker Python: 3.10.21, MuJoCo 2.3.7,
robosuite 1.4.0, NumPy 1.23.5. Full runtime setup is in [LIBERO.md](LIBERO.md).

- `MANILOOP_TEST_LIBERO=1 python -m pytest -q`: **121 passed, 49 subtests passed**.
  Without the opt-in flag, 115 tests pass and 6 integration checks are skipped.
- Official spatial task 0 / init 0: deterministic reset checks, two nonblank
  128×128 camera images, native OSC movement and official success evaluation pass.
- All five official task catalogs load. This is catalog coverage, not physical
  completion of all tasks.
- The example batch using init 0 and init 1 completes; the no-render mock episode
  also completes. Success is false, as expected for the mock adapter.
- The web demo displays the official scene and task catalog, and completes two
  mock decisions with two native OSC samples. No paid API request was made.
- The setup script was rerun successfully. Its generated Python is stored inside
  the repository's ignored runtime directory. The wheel builds and contains the
  worker/adapter modules, with no downloaded LIBERO assets or private runtime data.
- Source whitespace and documentation links pass inspection. Optional dependency,
  upstream asset and output directories are ignored by Git.

The optional Linux Actions workflow is provided but has not been run remotely.
Windows LIBERO, trained VLA policies and cloud-model task success remain unverified.
This integration uses a declared ManiLoop observation/action/timing protocol and
must not be presented as an unchanged reproduction of the LIBERO paper evaluation.


## 2026-09-15：真实 LeRobot 策略接入

正式仓库完整回归通过：126 项测试、49 项子测试，其中 7 项为可选真实 LIBERO 集成检查。普通离线运行对应 119 项通过、7 项跳过。安装脚本重跑、网页真实模型任务和 Python wheel 构建通过。

在同一 LIBERO spatial task 0 / init 0 / seed 0，官方 SmolVLA 于 79 步成功，社区 Diffusion 于 108 步成功；社区 ACT 执行 500 步后预算结束，未成功。网页 SmolVLA 再次于 79 步成功。三者均严格加载真实权重，未调用云端 API。这是单任务集成检查，不是整个基准成功率。

来源、预算、动作处理和实际用时见 [实验报告](experiments/2026-09-15-libero-local.md)；安装和复现见 [VLA 说明](VLA.md)。
