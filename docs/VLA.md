# 本地学习策略：SmolVLA、ACT 与 Diffusion

ManiLoop 的 `lerobot` 策略适配器连接已训练权重与官方 LIBERO Panda 环境。SmolVLA 使用图像、机器人本体状态和语言指令；本页 ACT / Diffusion 检查点是视觉模仿策略，不使用语言，作为不同策略家族的基线。

## 模型与来源

| 选择名 | 检查点 | 来源 | 权重体积 |
|---|---|---|---|
| `smolvla-libero` | [lerobot/smolvla_libero](https://huggingface.co/lerobot/smolvla_libero) | LeRobot 官方；LIBERO 数据训练 | 907 MB |
| `act-libero` | [Deepkar/libero-test-act](https://huggingface.co/Deepkar/libero-test-act) | 社区；HuggingFaceVLA/libero 数据训练 | 207 MB |
| `diffusion-libero` | [ttotmoon/diffusion-libero-v3](https://huggingface.co/ttotmoon/diffusion-libero-v3) | 社区；HuggingFaceVLA/libero 数据训练 | 1.07 GB |

固定 Hub 版本见 [模型目录](../src/maniloop/agents/lerobot/catalog.py)。这些是公开检查点，下载不需要 API Key。ACT / DP 使用上表列明的社区检查点。检查点标题和训练数据声明不能保证任务成功率。

## 安装与启动

先按 [主 README](../README.md) 安装 ManiLoop，再按 [LIBERO 说明](LIBERO.md) 安装可选仿真环境。以下命令均从仓库根目录执行：

```bash
python -m pip install uv
python scripts/setup_vla.py
```

默认只下载 SmolVLA，以及它需要的分词器和配置。安装全部三个模型：

```bash
python scripts/setup_vla.py --models smolvla-libero act-libero diffusion-libero
```

推理使用独立 `.venv-vla`（Python 3.12、LeRobot 0.4.4、PyTorch），不会修改 `.venv` 或 `.venv-libero`。安装器将所需 Python 和权重放在仓库内忽略目录，支持再次运行补全下载。首次安装需下载数 GB 依赖与模型。已下载后，推理进程强制离线，不访问模型服务或读取 API 密钥。

Apple Silicon 自动选择 MPS；NVIDIA 环境自动选择 CUDA；否则使用 CPU。可用 `--device cpu` 显式切换。建议先验证少量动作，再运行完整预算：

```bash
python -m maniloop benchmark --backend libero --agent lerobot \
  --local-model smolvla-libero --max-calls 2 --max-wall-seconds 600

python -m maniloop benchmark --backend libero --agent lerobot \
  --local-model smolvla-libero --max-calls 500 \
  --max-sim-seconds 25 --max-wall-seconds 1800
```

替换 `--local-model act-libero` 或 `--local-model diffusion-libero` 可测试其他家族；批量入口是：

```bash
python -m maniloop benchmark --suite examples/libero-local-suite.toml
```

网页入口：

```bash
python -m maniloop demo --backend libero
```

打开提示的本地地址，选择「本地 LeRobot · 真实模型」与模型，再开始执行。首次模型加载需要等待；开始时自动采用 256 像素相机，并从选定官方初始化重新开始。应使用场景原有英文任务；ACT / DP 不读取文本，即使修改指令也不会改变其目标条件。

自定义安装位置可使用 `MANILOOP_VLA_PYTHON` 和 `MANILOOP_MODELS_ROOT`；后者包含上述选择名的模型子目录及 `smolvlm-tokenizer`。当前适配器接受上述三个目录配置，不提供任意检查点导入。

## 输入、控制与评测边界

- 两路 256×256 RGB：agentview 与 wrist。PNG 无损传输；先恢复 LIBERO 原始图像，再调用 LeRobot 官方 `LiberoProcessorStep` 完成与数据集一致的双轴翻转。
- 状态为 8 维：末端 xyz、四元数转换的轴角、两个夹指关节位置。它们来自机器人自身感知，不含物体状态、目标坐标、接触或评分信息。
- 加载检查点保存的前处理、训练统计和动作反归一化。SmolVLA 配置残留的 6 维声明与其 8 维统计不一致；实际输入遵循官方 LIBERO 处理器的 8 维，保留原文件并记录差异。配置中的第三路相机未用于这个两相机检查点的输入，不伪造图像。
- 每个仿真控制步调用一次 `select_action`，LeRobot 自己管理原始动作队列。尤其 DP 的两个历史观测必须每步更新，不能等整个动作块执行完才给新图像。
- 7 维 OSC 动作，20 Hz 仿真控制；保留检查点的原始动作块和采样步数。动作反归一化后按控制器边界裁剪到 [-1,1]，裁剪数量写入记录。
- 默认受控时序：等待推理时暂停物理。500 次决策表示最多 25 秒仿真时间，实际耗时取决于硬件和策略。决策预算、墙钟预算与官方成功判定分别记录。

每次运行的 manifest 保存模型来源、版本、权重摘要、依赖、设备、预处理与时序；结果保存官方评分、推理次数和裁剪数量。已记录的单任务结果与 GPT-6 对比见 [模型对比与指标定义](RESULTS.md)。单个任务／初始化无法估计基准成功率，完成推理也不等于任务成功。

## 独立开发工作区复用已有安装

Git worktree 不会复制被忽略的运行环境与模型。LIBERO 场景可以打开，
并不意味着 SmolVLA 的推理环境也已经配置：它们分别使用 `.venv-libero` 和 `.venv-vla`。

原工作区已安装本地模型时，在新工作区根目录执行以下命令，无需重新下载：

```bash
python scripts/setup_vla.py --reuse-from ../ManiLoop
# 同时检查已有的三个模型：
python scripts/setup_vla.py --reuse-from ../ManiLoop \
  --models smolvla-libero act-libero diffusion-libero
```

该命令检查 Python 和固定依赖、模型来源声明、模型家族、前后处理及其统计文件，
以及 SmolVLA 的分词器文件，然后建立 `.venv-vla` 与 `.runtime/models` 的相对目录链接。
它不会执行 pip 或下载，不覆盖已有目录；重复执行可重新校验。
共享目录的原位置必须保留，勿移动或删除。普通安装模式发现共享路径会拒绝修改。
不支持目录链接的平台可设置 `MANILOOP_VLA_PYTHON` 和 `MANILOOP_MODELS_ROOT`。

路径检查不等于真实推理成功。补充的模型层集成检查会严格加载实际权重，
使用真实 LIBERO 双相机观测并执行少量控制步；与纯仿真测试分开启用：

```bash
MANILOOP_TEST_VLA=1 python -m pytest tests/test_vla_integration.py -q
```

此检查需要上述三个模型全部准备好，运行时不下载或访问云端 API。
少量动作验证用于发现安装、预处理、推理和执行链路问题，不作为任务成功率评测。
