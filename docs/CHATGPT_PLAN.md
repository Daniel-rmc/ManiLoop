# ChatGPT plan direct connection / ChatGPT 套餐直连

[English](#english) · [中文](#中文)

## English

ManiLoop can obtain its own ChatGPT authorization and call the public Responses API directly. This route uses eligible ChatGPT plan access and keeps the robot loop, prompts, observation history, and action validation in ManiLoop. It does not launch Codex CLI or load its harness. The existing **Codex CLI** and **API key** routes remain available.

Install the authentication extra in the main Python environment:

```bash
python -m pip install -e '.[chatgpt]'
python -m maniloop demo --port 8767
```

1. Open the local workbench and choose **模型运行 → 模型连接与认证 → ChatGPT 套餐直连 · 独立授权**.
2. Click **Continue with ChatGPT**. In the browser, authorize **ManiLoop** to use your ChatGPT plan. This is separate from your Codex login; an existing CLI login does not authorize this connection.
3. Return to the workbench. It shows the connected account and whether plan usage is enabled. Use the account selector to switch saved accounts, **重新授权此账号** to renew authorization, or **退出此账号** to disconnect locally and attempt session revocation. Account changes are locked while a run is active.
4. Click **刷新模型列表**, then choose a model from this account's catalog. GPT-6 Astra access depends on the selected account and the current service. A catalog entry alone does not establish successful inference.
5. Run **文本诊断**, **图像诊断**, and **动作格式诊断** in order. Each diagnostic makes a model request; the action-format diagnostic does not execute a robot action. After these pass, use **单步执行** before starting a complete episode.

Click **取消授权** to cancel a sign-in attempt. Closing the browser window alone does not cancel it: return to the workbench and cancel explicitly before starting again, or wait for the attempt to expire. If registration issued a client ID but code exchange failed, use **继续上次注册** to retry that registration without creating a new one. If the browser blocks the popup, allow popups for the local workbench and click again. A failed sign-in does not silently replace another saved account. Use ChatGPT **Settings → Usage** to manage app access and usage. If remote revocation cannot be confirmed during logout, disconnect the app there as well.

### Comparison and budget behavior

The direct route shares ManiLoop's sensor-only input construction, image bytes, history, action schema, and local action checks with the Responses API policy. Its application-side input manifest records the request protocol and content hashes; it does not claim visibility into server-side processing. The Codex CLI route remains a separately labeled harness configuration.

The ChatGPT plan preview requires streamed Responses requests with `store: false` and explicit input history. It does **not** accept a server-side `max_output_tokens` parameter. Set the reasoning effort and local request deadline explicitly, and distinguish these from actual reasoning-token usage. A client text-length limit or timeout is not a server token budget. Strict equal-token-budget comparisons therefore require a different supported connection. An incomplete, failed, interrupted, or invalid response never authorizes a robot action. There is no automatic switch to another model, provider, or paid API key when access fails.

### Local credentials and validation status

ManiLoop stores its own authorization records in protected local storage, separate from Codex. It never needs you to copy a token into the workbench. OAuth credentials are not sent to a custom provider, added to experiment logs, or written into browser storage. The public GitHub Pages site is a static replay and cannot run this local sign-in flow.

This feature's offline protocol and UI checks do not establish access for your account. The first successful text/image/structured-action diagnostics are the acceptance check for your selected account and model; they do not demonstrate task success or a benchmark success rate.

Official references, checked 2026-10-28: [registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in), [models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference), [preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations).

## 中文

ManiLoop 可以独立获得 ChatGPT 授权，直接请求官方 Responses API，使用符合条件的 ChatGPT 套餐。机器人闭环、提示、观测历史和动作校验均由 ManiLoop 管理，不启动 Codex CLI，也不加载其 harness。现有 **Codex CLI** 和 **API Key** 接入继续保留。

在主 Python 环境中安装认证扩展：

```bash
python -m pip install -e '.[chatgpt]'
python -m maniloop demo --port 8767
```

1. 打开本地工作台，选择 **模型运行 → 模型连接与认证 → ChatGPT 套餐直连 · 独立授权**。
2. 点击 **Continue with ChatGPT**，在浏览器中授权 **ManiLoop** 使用你的 ChatGPT 套餐。它与 Codex 登录独立，已登录 CLI 不代表此连接已授权。
3. 返回工作台，确认账号和套餐授权状态。可选择已保存的账号、点击 **重新授权此账号**，或 **退出此账号**。退出会清除本地凭据并尝试撤销远端会话；实验运行中不能切换账号。
4. 点击 **刷新模型列表** 并选择模型。GPT-6 Astra 是否可用取决于此账号与服务当前权限；出现在目录中不等于推理已通过。
5. 依次运行 **文本诊断、图像诊断、动作格式诊断**。每项都会请求模型，动作格式诊断不会移动机器人。通过后先用 **单步执行** 检查，再开始完整 episode。

点击 **取消授权** 可取消本次登录。仅关闭浏览器窗口不会取消授权；请回到工作台明确取消后再重试，或等待本次授权过期。若已取得注册 ID 但授权码交换失败，可点击 **继续上次注册** 复用该注册重试，无需创建新注册。如果弹窗被阻止，请允许本地工作台打开弹窗后重试。登录失败不会静默替换另一个已保存账号。可在 ChatGPT **设置 → 使用情况** 管理应用授权与用量；若退出时未确认远端撤销成功，也可在那里断开应用。

### 公平比较与预算

套餐直连与 Responses API 策略共用传感输入构造、图片字节、历史、动作 Schema 和本地校验。应用侧请求记录包含协议版本与输入摘要，但不代表能够看到服务端内部处理。Codex CLI 仍作为独立的 harness 配置标记。

当前套餐预览要求流式请求、`store: false` 和显式发送历史，**不支持服务端 `max_output_tokens` 上限**。请明确设置推理强度与本地请求时限，并将它们和实际推理 token 消耗区分。客户端文本长度限制或超时不是服务端 token 预算；要求严格 token 上限的对照应使用支持该能力的其他连接。断流、失败、中断或格式无效的响应都不能触发动作。权限或额度不足时，不会自动改用其他模型、供应商或付费 API Key。

### 凭据与验证范围

认证记录保存在本机受保护位置，与 Codex 分开，不需要手动粘贴 token。OAuth 凭据不会发送给自定义供应商，也不会进入实验日志或浏览器存储。GitHub Pages 是静态回放页面，不能运行此本地认证流程。

离线协议和界面检查不代表你的账号已通过接入。首次成功的文字、图像、结构化动作诊断用于验收所选账号和模型，不代表任务成功或基准成功率。

官方依据，核对日期 2026-10-28：[注册与登录](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)、[模型与推理](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)、[当前预览限制](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)。
