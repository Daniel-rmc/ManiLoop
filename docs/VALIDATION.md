# ManiLoop validation

## GitHub Actions — 2026-09-16

Commit `27092ba` passed all four checks in
[this workflow run](https://github.com/Daniel-rmc/ManiLoop/actions/runs/35047335420):

| Check | Result |
| --- | --- |
| Ubuntu / Python 3.12 offline tests | Passed |
| macOS / Python 3.12 offline tests | Passed |
| Windows / Python 3.12 offline tests | Passed |
| Linux OSMesa rendering, ARX X5 and Franka Panda | Passed |

The same offline suite passed locally with **119 tests and 49 subtests**;
7 optional LIBERO integration checks were skipped. Windows fixes explicitly
specify UTF-8 when tests read logs and use short IDs for oversized input cases.
No test coverage was removed. The optional LIBERO Linux workflow and Windows
rendering have not been verified by this run. CI does not measure model task
success; real-policy results are recorded separately below.

## Framework baseline — 2026-09-15

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
an autonomous LLM success rate. At this milestone, the VLA adapter validated only the interface; later real-policy
results are recorded below.

macOS rendering emits `ARB_clip_control unavailable`; RGB images are available,
but depth precision may be lower on this backend. Subsequent cross-platform CI
and Linux OSMesa rendering results are recorded above.

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
Windows LIBERO and cloud-model task success remain unverified. Trained-policy
validation followed this integration milestone and is recorded below.
This integration uses a declared ManiLoop observation/action/timing protocol and
must not be presented as an unchanged reproduction of the LIBERO paper evaluation.


## 2026-09-15：真实 LeRobot 策略接入

正式仓库完整回归通过：126 项测试、49 项子测试，其中 7 项为可选真实 LIBERO 集成检查。普通离线运行对应 119 项通过、7 项跳过。安装脚本重跑、网页真实模型任务和 Python wheel 构建通过。

在同一 LIBERO spatial task 0 / init 0 / seed 0，官方 SmolVLA 于 79 步成功，社区 Diffusion 于 108 步成功；社区 ACT 执行 500 步后预算结束，未成功。网页 SmolVLA 再次于 79 步成功。三者均严格加载真实权重，未调用云端 API。这是单任务集成检查，不是整个基准成功率。

来源、预算、动作处理和实际用时见 [实验报告](experiments/2026-09-15-libero-local.md)；安装和复现见 [VLA 说明](VLA.md)。

## 2026-09-16：云端诊断与 LLM 目标控制

macOS Apple Silicon 的正式环境运行 `MANILOOP_TEST_LIBERO=1 python -m pytest -q`：
**142 项测试、55 项子测试通过**，其中 13 项为真实 LIBERO 集成检查。

- 固定目标跟踪覆盖平移、旋转、速度与连续稳定判据、超时和取消；真实环境检查夹爪初始保持、闭合和张开。原生 VLA 单步／动作块节奏保持原协议。
- 本地 HTTP 模拟供应商经 SDK 完成文本、单图及双图结构化动作诊断，各一次请求，分别含 0 / 1 / 2 张图像；诊断不执行返回动作，不推进仿真。失败日志保存耗时和错误类别，未知 token 用量为 null，批量报告正常结束。
- 真实 LIBERO 渲染与新版网页双相机均为 512×512。网页 +Z 10 mm 点动实际位移约 9.31 mm，三维位置残差约 0.74 mm；这只证明该初始化下的小位移控制。
- 网页入口已验证可调请求超时、推理强度、三种诊断、动作／相机配置和独立预算。诊断完成后手动调试可继续推进物理。

以上未调用付费云端 API。FC 服务连通性、云端模型自主抓放成功率，以及更广泛的初始化／接触条件尚未验证。原始单步控制与目标跟踪的对照实验见 [设计与诊断记录](design/LLM_LOOP_V2.md)；工程进展见 [工作记录](worknotes/worknote.md)。

本次实现提交 `3ff9985` 的 [GitHub Actions](https://github.com/Daniel-rmc/ManiLoop/actions/runs/35051694421) 四项均通过：Windows、macOS、Linux 离线测试和 Linux OSMesa 双机器人渲染。用户随后进行的 Astra / Sol 云端调用均未通过响应完整性检查，未执行动作；这是 API 接入失败记录，不是任务成功率评测。
