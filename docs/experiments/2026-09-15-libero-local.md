# LIBERO 本地学习策略集成验证 · 2026-09-15

本次验证了三种真实、已用 LIBERO 数据训练的策略在 ManiLoop 上的输入处理、模型推理和原生 OSC 控制。SmolVLA 与 Diffusion 在所选任务上获得官方成功判定；ACT 完成控制闭环但未在预算内成功。

## 条件

- 设备：Apple Silicon Mac16,12，16 GB 统一内存；PyTorch MPS、float32。
- 任务：`libero_spatial`，task 0，init 0，seed 0。
- 英文任务：`pick up the black bowl between the plate and the ramekin and place it on the plate`。
- 仿真：固定 LIBERO `8f1084e3132a39270c3a13ebe37270a43ece2a01`，robosuite 1.4.0，MuJoCo 2.3.7，官方 Panda / OSC_POSE / 初始化与 `check_success`。
- 输入：两路 256×256 PNG RGB、8 维本体状态。使用 LeRobot 官方 LIBERO 处理器和检查点自带前后处理；不传入物体、接触或评分真值。
- 控制：受控时序，20 Hz 仿真步进；每步新观测，保留模型自己的动作队列。上限 500 步 / 25 秒仿真时间。到官方成功时立即结束，不做后续稳定性补测。
- 推理依赖：LeRobot 0.4.4、PyTorch 2.10.0、torchvision 0.25.0、transformers 4.57.6。完整 safetensors 严格加载；未运行远程模型代码或云端 API。

## 实际结果

| 模型 | 来源 / 类型 | 控制步 | 真正模型推理次数 | 仿真秒 | 墙钟秒 | 官方成功 |
|---|---|---:|---:|---:|---:|---|
| SmolVLA | LeRobot 官方，语言条件 | 79 | 2 | 3.95 | 12.57 | 是 |
| ACT | 社区，视觉模仿 | 500 | 5 | 25.00 | 68.51 | 否，预算结束 |
| Diffusion Policy | 社区，视觉模仿 | 108 | 14 | 5.40 | 167.24 | 是 |

墙钟时间从模型加载后开始，包含图像处理、传输、推理、仿真和记录；不包含下载、场景创建与模型加载。这些是同一机器上依次运行的集成检查，存在后台负载，不能当作严格的硬件性能比较。

SmolVLA 使用原始 50 步动作队列与 10 次采样；ACT 为 100 步队列；Diffusion 使用 2 个连续历史观测、8 步动作队列和原始 100 次 DDPM 采样。ACT / DP 不读取语言，不能用于证明语言理解能力。

动作反归一化后按原生控制器边界裁剪到 [-1,1]；SmolVLA / ACT / Diffusion 分别有 53 / 251 / 0 个标量发生裁剪。没有在本轮训练、调参或使用评分调整策略。

## 模型版本与证据

| 模型 | 仓库 | Hub revision |
|---|---|---|
| SmolVLA | [lerobot/smolvla_libero](https://huggingface.co/lerobot/smolvla_libero) | `31d453f7edd78c839a8bbc39744a292686daf0de` |
| ACT | [Deepkar/libero-test-act](https://huggingface.co/Deepkar/libero-test-act) | `b6a5253edf0c9d9e458629fdeb489f514ff6300f` |
| Diffusion | [ttotmoon/diffusion-libero-v3](https://huggingface.co/ttotmoon/diffusion-libero-v3) | `5825af28c585ade6827ea7e8f6234f3ab04e8ab1` |

原始 run ID 分别为 `20260915-231438-844f9319`、`20260915-231622-80954ef8`、`20260915-231827-1e603683`。每次实验保留 manifest、逐步观测、RGB、实际动作、用量、反馈与独立 result。大体积运行文件按仓库规范不纳入 Git。

复现步骤见 [本地策略说明](../VLA.md)，批量配置见 [libero-local-suite.toml](../../examples/libero-local-suite.toml)。首次两步 SmolVLA 检查也通过：一次真实推理约 6.77 秒、两个控制步、无动作裁剪；后续运行受暖缓存影响，不用两者计算加速比。

## 结论的范围

这次结果证明三个真实策略家族的接口能够运行，并证明两个检查点在该初始化上完成了官方任务。它不代表整个 LIBERO 的成功率，也不是论文评测复现；没有测试未见任务泛化、不同语言表达、跨机器人迁移或真机。ACT 的这次失败不能代表 ACT 方法整体不可用。

后续应固定多个任务、全部或预先选定的初始化、随机种子和相同预算，分组报告置信区间；任何动作或观测辅助都须独立记录。
