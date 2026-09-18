# robosuite 操作任务

ManiLoop 的可选 robosuite 后端使用独立进程运行仿真，复用现有网页、
`EpisodeRunner`、模型接口和决策回看。无需修改 LIBERO 的环境。

## 已接入任务

| ID | 内容 |
| --- | --- |
| `Lift` | 抓起方块 |
| `Stack` | 堆叠方块 |
| `PickPlaceCan` | 将易拉罐放入对应格子 |
| `Door` | 操作把手并开门 |
| `NutAssemblySquare` | 将方形螺母套到对应柱子 |

首版只支持 Panda 平行夹爪。任务目录可用不代表某个模型已经完成任务。

## 安装与启动

先按主 README 准备 ManiLoop 主环境，再安装 uv。以下命令在仓库根目录执行。
安装器单独创建 Python 3.11 的 `.venv-robosuite`；不修改 `.venv-libero`。

```bash
python scripts/setup_robosuite.py
python -m maniloop list --backend robosuite
python -m maniloop smoke --backend robosuite --task Lift
python -m maniloop demo --backend robosuite --task Lift --port 8870
```

打开 `http://127.0.0.1:8870`，在“环境后端”选择 robosuite，再选择任务并应用。
无需 API 密钥即可看相机、点动、开合夹爪、停止和重置。
原有“加载 GPT-6 抓放演示”按钮仍是 LIBERO 专用预设，会切换到 LIBERO。

uv 不在 PATH 时，安装器接受 `--uv /absolute/path/to/uv`。
自定义运行环境可设置 `MANILOOP_ROBOSUITE_PYTHON`；源码覆盖可设置
`MANILOOP_ROBOSUITE_ROOT`，指向含 `robosuite/__init__.py` 的源码根目录。
worker 检查版本，并在记录中保存实际源码摘要，不能把修改版当作官方原版。

## 依赖与控制语义

运行依赖固定在 `requirements/robosuite.txt`：robosuite 1.5.2、MuJoCo 3.3.7。
使用 PyPI 发布包，不将 assets 复制进 ManiLoop。完整安装快照保存在
`.runtime/robosuite-packages.txt`。主环境的 MuJoCo 版本不受影响。

沿用上游 Panda 的复合控制器；**明确将手臂 OSC 参考系配置为 world**，
并在 manifest 中记录这一覆盖。这是 ManiLoop 的适配协议，不声称等同于论文评测。
机器人、物体、任务重置逻辑、接触参数和成功判定不作额外修改。

动作使用 7 维归一化 OSC：世界系平移增量、世界系旋转增量、夹爪输入。
尺度为每控制步 0.05 米 / 0.5 弧度；夹爪 `-1` 打开，`+1` 关闭。
公开 TCP 动作使用米和弧度；底层读取实际控制器的动作分段并检查边界。
`execute()` 只提交动作，`step()` 才推进一个 20 Hz 原生控制步。

目标跟踪模式复用固定目标伺服，每次最多执行 20 个控制步；只依赖机器人本体感知。
TCP 位置和姿态使用一致的末端 site，姿态取 `robot0_eef_quat_site`，
不混用旧版 body 四元数。反馈中 `reached` 表示运动到达，不表示抓取成功。

## 观察、评分与限制

模型只接收两路 RGB、机器人关节 / TCP / 夹爪状态、相机标定和动作反馈。
外部相机为 `agentview`，腕部相机为 `robot0_eye_in_hand`；支持 128 / 512 像素，
每次观察显式渲染当前状态，再按 OpenGL 原始图像翻转一次，输出顶左像素原点。
渲染不推进物理，不依赖上次控制步的图像缓存。没有深度查询。

离屏运行显式选择 `renderer="mujoco"`，同时保持 `has_renderer=False`。
这是渲染资源生命周期配置，不是更换物理引擎或打开原生窗口。robosuite 1.5.2
的默认 `mjviewer` 路径在硬重置时可能留下旧的离屏上下文；其延迟析构可能在
新上下文中释放同编号的 OpenGL 资源，造成花屏或相机串帧。当前配置使用上游
在重建仿真前销毁旧资源的路径，不依赖禁用垃圾回收，也不修改上游安装文件。
manifest 中的 `renderer` / `render_lifecycle` 字段记录这一设置。

物体真值、接触列表、奖励和成功信号不进入策略输入。

评分单独调用上游 `_check_success()`。首次成功或 1000 个控制步后终止；
不添加自建桌面任务的静置窗口。记录保留上游版本、源码摘要、控制器与相机设置。

当前不支持双臂、换机器人、深度查询、完整逐控制步录像或 RoboCasa。
现有 LIBERO 训练的 LeRobot 预设继续限制在 LIBERO，不作为这些新任务的默认策略。
决策级事件日志、前后帧回看、受控 / 实时模式和现有云端模型入口可以复用。
真实模型是否成功需要单独测试；mock 和下面的物理诊断都不是模型成绩。

## 无模型验证

```bash
python -m maniloop benchmark --backend robosuite --task Lift \
  --agent mock_vla --max-calls 2 --max-sim-seconds 2 \
  --output runs/robosuite-plumbing
MANILOOP_TEST_ROBOSUITE=1 python -m pytest \
  tests/test_robosuite.py tests/test_robosuite_integration.py -q
```

普通 `pytest` 会跳过需要可选环境和图形设备的真实仿真检查。
真实检查覆盖五个任务的重置、双相机、动作步进、评分分离，
以及 Lift 的目标平移 / 旋转、夹爪保持、取消和 512 像素相机。
另有五个任务 × 两种分辨率的渲染生命周期回归：反复重置，分别在首个动作前后
强制垃圾回收，确认物理状态不变时两路图像逐像素不变、相机不串帧。
该检查专门覆盖“初始画面正常、第一次动作后损坏”的延迟资源释放故障。

独立的 Lift 物理诊断必须用 robosuite 环境运行：

```bash
.venv-robosuite/bin/python scripts/diagnose_robosuite_lift.py
```

该脚本读取方块真值进行抓取和抬升，结果明确标记 `is_oracle=true`、
`model_tested=false`。它不经过策略输入接口，也不向模型提供真值。
结果和末帧保存在 `artifacts/robosuite-lift-diagnostic/`，不提交到 Git。

## 常见问题

找不到环境：检查是否在仓库根目录启动，或显式设置 worker 的 Python 路径。
找不到 uv：使用安装器的 `--uv` 参数，不需要修改系统 Python。
版本不兼容：重新运行安装器，勿把新版包装进已有 `.venv-libero`。
图形初始化失败：Linux 使用与驱动匹配的 `MUJOCO_GL=egl` 或 OSMesa；
macOS 已验证普通 Python 的离屏渲染，不要照搬 Linux 的 EGL 设置。
`robosuite_models` / mink 警告不影响本版 Panda 任务；不需要安装额外机器人包。
图像正常但操作失败：先看目标执行反馈与原生任务成功规则，不把 `accepted` 当作到达。
旧开发版本出现“动作后花屏 / 画面乱跳”：更新代码并重启 ManiLoop 服务，
使仿真 worker 使用上述生命周期配置。只刷新网页不会替换仍在运行的旧 worker。
不要用增大控制阻尼、降低画质或反复重置来掩盖这个渲染故障。

上游项目：[robosuite](https://github.com/ARISE-Initiative/robosuite)。
控制器说明：[官方文档](https://robosuite.ai/docs/modules/controllers.html)。

## API 动作中的 camera / pixel 报错

`Unused camera/pixel fields must be empty and [0,0].` 是本地动作响应校验错误，
不是 TOML 解析或 API Key 认证报错。`camera` 和 `pixel` 只用于 `query_depth`，
不是用来说明模型看了哪张图，也不是抓取目标在图像中的位置。
对于 move / gripper / wait / done，这两个输出字段必须为 `""` 和 `[0, 0]`。

Responses 请求现在按本次观测声明的能力生成 Schema：robosuite / LIBERO 的
RGB-only 观测不提供 `query_depth`，并用 enum 约束上述两个字段；内置任务在明确
提供外部相机深度时保留查询能力。切换后端不会修改全局 Schema。
兼容服务若未遵守 Schema，本地校验仍拒绝非法输出，不删除校验、不自动重试付费请求。

保留浏览器中选择的 TOML / API Key，先点击“3 · 动作格式诊断”。该入口只请求
一个 wait 格式动作，不执行机器人操作。诊断成功后再使用单步验证真实控制。
诊断失败不代表仿真场景损坏；记录脱敏错误，不公开 TOML 中的凭据或服务响应原文。

## 观测有效期与旧观测拒绝

工作台新增“观测有效期（秒，仅实时模式）”，在开始实验或应用场景配置时生效。
默认 60 秒（兼容既有 `ARX_OBSERVATION_MAX_AGE` 环境变量）；可设 300、600 等。
设为 **0** 仅关闭观测的墙钟时间限制，不关闭重置 / 停止 / 决策版本检查，
也不关闭画面变化检查。受控时序在推理期间冻结物理，始终不因等待时长拒绝观测。
API 请求超时、实验总时限和目标伺服执行时限是不同设置，不受这个参数影响。

```bash
python -m maniloop demo --backend robosuite --task Lift --port 8870 \
  --observation-max-age-seconds 300
```

批量实验的 TOML 可以在 `[experiment]` 中设置
`observation_max_age_seconds = 300`，也可将它作为 `[matrix]` 的实验轴。
这是 ManiLoop 实验参数，不是供应商连接 TOML 的 API 参数。
记录同时保存配置值与实际生效的时间限制；不限时间时有效限制写为 null。

`Observation expired` 表示等待超时，可通过有效期参数调整。
`Observation belongs to an old reset or decision` 表示观测版本失效，
不是“超时设得太小”，不能通过放大秒数来恢复旧指令。
运行器会在发起新请求之前完成上一动作的后观测记录，避免被拒绝的动作
在新请求已经发出后再覆盖观测编号。旧错误场景已有延迟响应回归，
包含 current / paired 模式及真实 robosuite 的 128 / 512 像素验证。
