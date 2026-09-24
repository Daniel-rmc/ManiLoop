# Jev：文本原语控制

本版将 Jev 作为高层选择器，沿用现有机器人控制器。不是将云端模型放进20Hz伺服循环。
纯Jev模式仅发送显式指令和公开本体状态，不发送图像，不读取物体真值。
每行一个动作，成功执行后再处理下一行；序列结束不代表官方操作任务成功。

## 运行入口

网页可以直接填写 TypeSafe 专用密钥，无需先设置终端环境变量。不要把密钥写入仓库或分享日志。
当前版本直接使用官方HTTP接口，不需要安装TypeSafe SDK或Jev权重，不会复用OpenAI认证。

```bash
cd /path/to/ManiLoop
source .venv/bin/activate
python -m maniloop demo --backend robosuite --task Lift --port 8873
```

已有8873服务时无需重复启动；升级后端代码须重启一次，之后更换网页密钥无需重启。
网页选择“模型运行 → Jev · 文本原语控制”，在 **Jev API Key · TypeSafe 专用** 密码框输入密钥。
点击“保存到本次服务”只检查格式并保存在服务内存，不发模型请求，不验证认证有效性。
也可直接填写后点击“Jev连接诊断 · 不动作”或开始执行。提交成功后输入框清空，留空复用已保存值。
“清除网页密钥”清除本次服务的覆盖值及闲置Jev客户端；任务/请求/动作未结束时不能更换。
优先级为本次填写、服务内存中的网页密钥、可选环境变量 `TYPESAFE_API_KEY`。不改写环境变量。
清除后若启动环境仍有密钥，会明确显示使用环境变量；本按钮不是撤销供应商账号中的Key。
密钥不写文件、浏览器存储或实验日志；状态接口只返回已配置标记及来源，不回传密钥。
刷新页面或切换策略不丢失服务内存里的密钥；重启服务会清除网页保存值。OpenAI配置独立。
保存成功不等于认证成功，请用下方无动作诊断查看真实服务结果。
诊断只调用一次Choice查询，不执行机器人动作；成功响应会显示实际模型版本与概率。
没有访问条件时明确报错，不切换到其他模型或本地mock。

## 三步演示

点击“载入三步演示指令”，或逐行输入：

```text
Move up along world Z by 10 mm.
Rotate about the tool Z axis by 5 degrees.
Open the gripper.
```

也可测试中文：“沿世界Z轴上移10毫米”“绕工具自身Z轴旋转5度”“打开夹爪”。中文理解效果需单独验证。
支持单步/继续以及连续消费最多20行。每行只发起一次Jev选择，不在运动中重复调用。
含糊指令、未知候选、低候选概率、API错误或本地动作超时会停止，不跳过失败继续下一行。
当前仅支持受控时序。开始不自动重置场景；需要时先在手动控制中重新初始化。
默认平移10mm、旋转5度；指令含一个明确数值和单位时优先使用该值。
只接受单一数值；复合数值、科学计数法等未实现的解析形式会拒绝，不静默误读。
候选包含固定/工具轴三轴正负平移旋转、夹爪、wait，以及需要澄清/需要视觉定位的出口。
精确单位换算、坐标转换、范围与可达性检查由本地代码处理，不从概率回归坐标。
选择概率阈值默认0.7，可调整；它不是成功率或安全保证。
手臂目标跟踪默认3秒，可设0.05–10秒。仅Jev控制路径使用该预算，其他策略不受影响。
现有夹爪路径/上游评分不变。UI策略调用计数与实际jev_requests在日志中分别可查。

```bash
# CLI 使用其启动环境中的 TYPESAFE_API_KEY，不读取网页服务内存。
python -m maniloop benchmark --backend robosuite --task Lift --agent jev \
  --instruction 'Move up 10 mm' --max-calls 2 --output runs/jev-demo
```

## 记录与边界

provider_decision记录候选、概率、模型版本、候选摘要和当前观测ID。
说明文字标记为程序模板，不声称Jev生成思考过程。停止/reset后的迟到响应仍丢弃。
默认模型是jev-1.13.0；使用别名时查看响应实际版本。HTTP不自动重试或跟随重定向。
文本模式不读取图片，图像仅用于工作台显示和现有变化检查。不支持“找到杯子并抓取”。
核心代码：providers/typesafe.py、agents/jev.py，复用runtime/runner.py及现有目标控制器。
组合策略要另设信息来源和评测组，不把VLM输出、特权状态或脚本技能收益算作纯Jev能力。

## 验证命令

```bash
python -m pytest tests/test_jev.py -q
MANILOOP_TEST_JEV_SIM=1 python -m pytest tests/test_jev_integration.py -q
```

第二组是真实仿真加模拟Jev响应，用于验证接线、单位、序列终止和本地执行，不证明真实Jev的判断能力。
真实在线能力应使用配置好的TypeSafe账号在网页诊断和指令demo中另测。

官方协议：https://docs.typesafe.ai/api
模型与输入边界：https://docs.typesafe.ai/models
Choice语义：https://docs.typesafe.ai/primitives/choice
