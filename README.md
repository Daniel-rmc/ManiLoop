# ManiLoop website

[English](https://github.com/Daniel-rmc/ManiLoop/blob/main/README.md) · [中文](https://github.com/Daniel-rmc/ManiLoop/blob/main/README.zh-CN.md) · [Project website](https://daniel-rmc.github.io/ManiLoop/)

The site introduces the implemented simulation framework, shows a complete GPT-controlled LIBERO episode, compares recorded model examples, and provides setup instructions. The [interactive workspace](https://daniel-rmc.github.io/ManiLoop/playground/?lang=en) lets visitors inspect the actual recorded observations, actions and feedback. Live simulation and inference run in the local application.

English and Chinese are available throughout the site. `?lang=en` or `?lang=zh` selects a language explicitly; otherwise the saved preference is used, followed by the browser language. The language control updates the URL and saves the choice under `maniloop-language`. The workspace uses the same preference. There are no external fonts, analytics, credentials or model requests on this site.

## Preview

From the repository root:

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory site
```

Open <http://127.0.0.1:8080/>. The static assets use relative paths and also work under `/ManiLoop/`; no package installation or build step is required.

## Episode and model results

The homepage plays a muted MP4 preview with synchronized, saved model action notes. Play/pause, previous/next decision and the time slider let visitors inspect the requested command and the **preceding** action's feedback. The preview uses simulation time; model waiting time is omitted. It is recorded output, not live inference. Reduced-motion preferences start with a still poster, and a failed autoplay attempt keeps a manual play control. Off-screen video pauses; a visitor's explicit pause is preserved.

Each lightweight preview is fetched once into a local Blob URL so seeking also works with basic static servers that do not support HTTP Range requests. Switching tasks aborts a pending preview download and releases the old Blob. Complete episode videos retain their normal file URLs.

`assets/showcase.json` is the skill gallery manifest (`format: maniloop_showcase_v1`). Each `episodes` entry contains:

- `id`, bilingual `label` and `task`, and the recorded `model` name.
- `preview`: a relative MP4 `video`, initial-frame `poster`, dimensions and `duration_seconds`. Preview time must match the complete episode's simulation-time axis, beginning with the initialization frame.
- `full_video`, `summary` (decisions, native control steps and simulation seconds), `evaluation` and a bilingual `outcome_note`. A card requires a verified, successful `LIBERO check_success` result. A selected successful example is not a success-rate estimate.
- `cues`: time-ordered `start_seconds`, `decision`, bilingual `explanation`, the actual structured `action`, and `previous_feedback` (`status` and available `position_error_m`, or `null`). The start time comes from the decision's before-action sensor record. Feedback must be from the preceding action, so the preview does not reveal an execution outcome before it occurs.
- Optional `workspace: "playground/"` only for an episode that the interactive workspace actually serves.

All media paths are relative to the site root. English action notes preserve the model's recorded output; Chinese notes are translations. Task cards select their own preview, notes and complete-video link. The detailed frame viewer below retains its explicitly identified episode.

`assets/demo-data.json` describes the displayed episode. Task labels, action-frame titles and the outcome note have `en` and `zh` values. Model explanations retain their recorded English text and include a Chinese translation in `explanation_zh`.

A success label requires agreement between the run summary and the verified independent LIBERO evaluator. The complete video also requires the initial frame plus every native control step, a complete terminal record and matching frame rate and simulation time. Changing the website language does not restart video playback.

`assets/model-comparison.json` contains one recorded example per model, with controller and observation settings, budgets, policy calls and available inference counts. These examples do not estimate success rates. Action scheduling and measurement boundaries differ, so the table is not a speed ranking. See [Results and configurations](https://github.com/Daniel-rmc/ManiLoop/blob/main/docs/RESULTS.md).

Published camera images and videos come from simulator rendering. ManiLoop source is MIT licensed; LIBERO, robosuite and their assets retain their respective licenses.

## Publish

Source files live in `main:site/`; GitHub Pages serves the root of `gh-pages`. After committing a reviewed site update:

```bash
git push origin main
git subtree push --prefix site origin gh-pages
```

Use a normal fast-forward push. `.nojekyll` keeps this a static site.

## 中文说明

官网展示已实现的框架功能、完整 GPT 仿真操作录像、各模型的实际运行示例与安装方法。[交互工作台](https://daniel-rmc.github.io/ManiLoop/playground/?lang=zh)可逐步查看真实运行的观察、动作与反馈；实时仿真和模型推理在本地应用中运行。

全站支持英文与中文。URL 参数 `lang` 优先，其次为已保存的语言偏好，最后采用浏览器语言。切换语言会同步入口链接与偏好，不会重播正在播放的视频。页面不收集密钥，也不发起模型请求。

首页短片按仿真时间静音循环，同步展示模型保存的动作说明、请求动作和上一步执行反馈；未展示模型等待时间。可暂停、前后切换决策或拖动进度，不是实时推理。系统选择减少动态效果时，默认展示静止画面；自动播放失败时可手动播放。任务卡来自 `assets/showcase.json`，只接收官方独立评分已经验证成功的回合。所有卡片明确说明是单次回合最终结果。

模型结果为单次示例，不代表基准成功率。配置、动作块、预算与计时口径不同，不能由步数或耗时进行速度排名。完整运行条件见[实际结果](https://github.com/Daniel-rmc/ManiLoop/blob/main/docs/RESULTS.md)，本地安装见[中文使用说明](https://github.com/Daniel-rmc/ManiLoop/blob/main/README.zh-CN.md)。
