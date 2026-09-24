# RoboCasa 厨房操作任务

RoboCasa 通过独立 Python worker 接入同一个 ManiLoop 工作台。
本接口保留上游 PandaOmron、厨房任务与独立成功判定，首版控制机械臂和夹爪，
底座使用零速度输入、躯干使用零增量保持，不包含导航规划。

## 安装

先完成主 README 中的主环境安装。随后从仓库根目录执行：

```bash
python scripts/setup_robocasa.py --download-assets
```

安装器创建 `.venv-robocasa`（Python 3.11），不会升级 `.venv-robosuite` 或 `.venv-libero`。
uv 不在 PATH 时，使用 `--uv /absolute/path/to/uv`。
RoboCasa 源码固定为 `4f8a2980def75a55dff96b990745b83540425f09`，
配套 robosuite 源码固定为 `5ce6643f3092639d08f7b0f90ed1c6a84f50552c`。
两者由官方提交档案安装，分别保存在 `.external/robocasa` 和 `.external/robocasa-robosuite`。
仅安装 `robosuite==1.5.2` 的 PyPI 包不够：它没有此 RoboCasa 版本需要的初始化接口。

物理运行环境使用 MuJoCo 3.3.1、NumPy 2.2.5；具体依赖见 `requirements/robocasa.txt`。
安装器采用仿真专用依赖，不安装上游训练用 LeRobot/Tianshou。
因此不能把这套环境当作上游完整训练环境；直接 `pip check` 可能报告缺少这些训练依赖。
实际仿真导入、控制和渲染检查才是该配置的验收依据。

资产从固定源码内的官方 Box 注册表下载，保存下载摘要并校验 ZIP 解压。
包括普通纹理、场景引用的生成纹理、Lightwheel fixtures、Objaverse 和 Lightwheel 物体。
即使关闭随机生成纹理，部分官方风格仍直接引用生成纹理文件，因此仍需安装。
不下载示范数据集或模型权重。下载期间保留至少 5 GiB 空闲空间。

## 启动与任务目录

```bash
python -m maniloop list --backend robocasa
python -m maniloop smoke --backend robocasa --task OpenDrawer
python -m maniloop demo --backend robocasa --task OpenDrawer \
  --robocasa-layout 11 --robocasa-style 14 --port 8872
```

浏览器打开 `http://127.0.0.1:8872`。在原工作台选择 RoboCasa 和任务即可操作；
加载、点动、停止、重置均不调用模型。模型连接方式沿用现有 TOML/API 等入口。
既有 LIBERO 检查点仍只允许在 LIBERO 使用，不作为 RoboCasa 预设。

| 任务 ID | 目标 |
| --- | --- |
| `OpenDrawer` | 打开指令所指的抽屉 |
| `CloseDrawer` | 关闭打开的抽屉 |
| `OpenCabinet` | 打开指令所指的柜门 |
| `CoffeeSetupMug` | 将杯子放到咖啡机出液口下方 |

四项都已在 macOS/Apple Silicon、布局11/风格14/种子0下检查真实加载、双相机、
点动、夹爪开合、重置和独立评分接口。目录中的 verified 仅表示这个范围的接入检查，
不代表模型成功率，也不保证所有任务都能在固定底座的动作范围内完成。
其他布局/风格仍是实验性组合；上游可能排除某些任务与布局组合。

官方语言由 `get_ep_meta()['lang']` 按 episode 读取，reset 后更新。
修改用户输入的任务文字不会改变上游评分器；记录分别保留实际输入和官方指令。
使用实验矩阵时，配置 `backend="robocasa"`、`task`、`robocasa_layout`、`robocasa_style`。
完整例子见 `examples/robocasa-offline-suite.toml`。

## 动作与观察协议

上层接收米/弧度的世界坐标 TCP 增量、夹爪开合和等待；目标伺服仍按20 Hz运行，
每个目标最多20个控制步。也可提交明确标记的7维 world OSC“机械臂子接口”。
这7维不是 PandaOmron 的原生完整动作：worker 使用真实控制器基座姿态将平移和
旋转向量转换到 base 系，再按上游分段组装完整12维：机械臂6、夹爪1、底座3、躯干1、模式1。
底座速度与躯干增量为0，模式为-1（arm）；保留上游控制器参数和物理约束。
没有冻结、焊接或瞬移底座，保持精度受原控制器和物理影响。

两路相机映射为 `robot0_agentview_left` → external、`robot0_eye_in_hand` → wrist。
使用当前状态的离屏渲染，不额外推进仿真。TCP位置和姿态均使用末端site。
上游观察即使包含物体坐标，本适配器也只构造图像、机器人本体及标定字段送给模型。
独立评分调用 `_check_success()`，不把奖励、接触、物体真值和成功信号传给策略。
首次官方成功或任务控制步上限时停止；用户指令的结束声明不等于评分成功。

## 验证与限制

```bash
MANILOOP_TEST_ROBOCASA=1 python -m pytest tests/test_robocasa.py tests/test_robocasa_integration.py -q
python -m maniloop benchmark --backend robocasa --task OpenDrawer \
  --agent mock_vla --max-calls 2 --max-sim-seconds 2 --output runs/robocasa-plumbing
```

mock仅检查协议，不是训练好的策略。现有真实环境检查覆盖四任务、默认场景、
世界系小位移/旋转、全动作分段、重置后的GC渲染稳定性及前后双帧运行器。
新后端未提供完整逐控制步视频、导航、双臂、训练或匹配的本地VLA检查点。
机械臂能执行命令不代表每项任务已有自主成功；切换到新布局时先检查可达性。

自定义安装使用 `MANILOOP_ROBOCASA_PYTHON` 和 `MANILOOP_ROBOCASA_ROOT`；
源码需保留安装器写入的固定版本标记。真实运行环境与源码摘要写入实验记录。
