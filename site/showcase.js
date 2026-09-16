"use strict";

// Saved, independently scored episodes only. This module never calls a policy.
(() => {
  const messages = {
    en: {
      heading: "RECORDED POLICY LOOP", recorded: "RECORDED · EXTERNAL CAMERA",
      play: "Play", pause: "Pause", play_aria: "Play the recorded task preview", pause_aria: "Pause the recorded task preview",
      seek: "Seek in the recorded preview", previous: "Previous decision, paused", next: "Next decision, paused", timing: "Simulation time · Model waits omitted", full_video: "Full episode",
      action_note: "MODEL ACTION NOTE · RECORDED", command: "Requested action", feedback: "Previous action feedback",
      pause_hint: "Pause or use ← / → to inspect each saved action note. This page makes no model requests.",
      gallery_eyebrow: "RECORDED SKILLS", gallery_title: "See a task through.",
      gallery_description: "Select a task to play its recorded actions above. Each card is one independently verified episode, not a benchmark success rate.",
      gallery_aria: "Select a recorded task", workspace: "Inspect this episode", verified: "FINAL RESULT · SUCCESS",
      step: "DECISION {step} / {total}", final: "FINAL FRAME", summary: "{model} · {decisions} decisions · {steps} control steps · {seconds} s simulation",
      card_summary: "{decisions} decisions · {seconds} s simulation", move: "Move TCP", gripper: "Gripper", wait: "Wait", done: "Done",
      gripper_command: "gripper {value}", no_feedback: "No preceding action", status_reached: "Target reached", status_timed_out: "Controller timed out",
      status_completed: "Action completed", unavailable_feedback: "Not recorded", preview_aria: "Recorded preview: {task}",
      unavailable: "Preview unavailable. Open the full episode.", manual_play: "Press Play · Simulation time · Model waits omitted",
      reduced_motion: "Motion paused by your preference · Press Play to watch", seek_value: "{seconds} of {total} seconds",
      feedback_error: "TCP error {error} mm", terminal_note: "Environment terminated during the last action; see the episode result below.",
      card_aria: "Play recorded task: {task}",
    },
    zh: {
      heading: "策略闭环 · 录制回放", recorded: "录制回放 · 外部相机",
      play: "播放", pause: "暂停", play_aria: "播放任务录像预览", pause_aria: "暂停任务录像预览",
      seek: "选择录像预览时间", previous: "跳至上一次决策并暂停", next: "跳至下一次决策并暂停", timing: "按仿真时间播放 · 未展示模型等待时间", full_video: "完整录像",
      action_note: "模型动作说明 · 原始记录", command: "请求动作", feedback: "上一步执行反馈",
      pause_hint: "暂停或使用 ← / →，逐步细看模型当时输出的动作说明。此页面不会发起模型请求。",
      gallery_eyebrow: "已录制的操作技能", gallery_title: "看任务如何完成。",
      gallery_description: "选择任务，在上方播放其真实操作记录。每张卡片代表一次经过独立验证的回合，不代表基准成功率。",
      gallery_aria: "选择已录制的任务", workspace: "逐步检查此回合", verified: "回合最终结果 · 成功",
      step: "决策 {step} / {total}", final: "最终画面", summary: "{model} · {decisions} 次决策 · {steps} 个控制步 · {seconds} 秒仿真",
      card_summary: "{decisions} 次决策 · {seconds} 秒仿真", move: "移动 TCP", gripper: "夹爪", wait: "等待", done: "完成声明",
      gripper_command: "夹爪 {value}", no_feedback: "尚无前一步动作", status_reached: "目标到位", status_timed_out: "控制器超时",
      status_completed: "动作完成", unavailable_feedback: "未记录", preview_aria: "录制任务预览：{task}",
      unavailable: "预览暂时无法播放，可打开完整录像。", manual_play: "点击播放 · 按仿真时间播放 · 未展示模型等待时间",
      reduced_motion: "已按你的动态效果偏好暂停 · 点击播放即可观看", seek_value: "第 {seconds} 秒，共 {total} 秒",
      feedback_error: "TCP 误差 {error} 毫米", terminal_note: "环境在最后一次动作中终止，详见下方回合结果。",
      card_aria: "播放已录制任务：{task}",
    },
  };
  const byId = (id) => document.getElementById(id);
  const video = byId("hero-video");
  const image = byId("hero-image");
  const play = byId("hero-play-toggle");
  const progress = byId("hero-progress");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const videoPath = /^assets\/episodes\/[a-zA-Z0-9_/-]+\.mp4$/;
  const imagePath = /^assets\/episodes\/[a-zA-Z0-9_/-]+\.(jpg|jpeg|png|webp)$/;
  let language = document.documentElement.lang.startsWith("zh") ? "zh" : "en";
  let episodes = [];
  let selected = null;
  let cueIndex = -1;
  let mediaFailed = false;
  let autoplayBlocked = false;
  let visible = true;
  let wanted = !reducedMotion.matches && !navigator.connection?.saveData;
  let selectionVersion = 0;
  let mediaReady = false;
  let previewRequest = null;
  let previewBlobUrl = null;

  function t(key, values = {}) {
    return (messages[language][key] || key).replace(/\{(\w+)\}/g, (match, name) => String(values[name] ?? match));
  }
  function localized(value) { return value?.[language] || value?.en || ""; }
  function finite(value) { return typeof value === "number" && Number.isFinite(value) && value >= 0; }
  function bilingual(value) { return value && typeof value.en === "string" && typeof value.zh === "string"; }
  function number(value, precision = 2) { return value.toLocaleString(language === "zh" ? "zh-CN" : "en-US", { maximumFractionDigits: precision }); }

  function validEpisode(item) {
    if (!item || typeof item.id !== "string" || !/^[a-zA-Z0-9_-]+$/.test(item.id) || !bilingual(item.label) || !bilingual(item.task) ||
        typeof item.model !== "string" || !videoPath.test(item.preview?.video) || !imagePath.test(item.preview?.poster) ||
        !videoPath.test(item.full_video) || !finite(item.preview.duration_seconds) || item.preview.duration_seconds <= 0 ||
        !Number.isInteger(item.summary?.decisions) || item.summary.decisions < 1 || !Number.isInteger(item.summary.control_steps) ||
        !finite(item.summary.simulation_seconds) || item.summary.simulation_seconds <= 0 ||
        item.evaluation?.source !== "LIBERO check_success" || item.evaluation.success !== true || item.evaluation.verified !== true ||
        !Array.isArray(item.cues) || !item.cues.length || item.cues.length > 10000) return false;
    return item.cues.every((cue, i) => finite(cue.start_seconds) && cue.start_seconds < item.preview.duration_seconds &&
      (i === 0 ? cue.start_seconds === 0 : cue.start_seconds >= item.cues[i - 1].start_seconds) &&
      Number.isInteger(cue.decision) && cue.decision > 0 && cue.decision <= item.summary.decisions && bilingual(cue.explanation) &&
      cue.action && typeof cue.action.kind === "string" &&
      ["delta_position", "delta_rotation"].every((key) => cue.action[key] === undefined ||
        (Array.isArray(cue.action[key]) && cue.action[key].length === 3 && cue.action[key].every(Number.isFinite))));
  }

  function playbackLabels() {
    const playing = !video.paused && !mediaFailed;
    play.setAttribute("aria-pressed", String(playing));
    play.setAttribute("aria-label", t(playing ? "pause_aria" : "play_aria"));
    byId("hero-play-label").textContent = t(playing ? "pause" : "play");
    byId("hero-play-icon").textContent = playing ? "Ⅱ" : "▶";
    for (const [id, key] of [["hero-previous-decision", "previous"], ["hero-next-decision", "next"]]) {
      byId(id).setAttribute("aria-label", t(key)); byId(id).title = t(key);
    }
    byId("hero-playback-note").textContent = t(mediaFailed ? "unavailable" : autoplayBlocked ? "manual_play" :
      reducedMotion.matches && !wanted ? "reduced_motion" : "timing");
  }

  async function startPreview() {
    if (!selected || !mediaReady || mediaFailed || document.hidden || !visible) return;
    const version = selectionVersion;
    try {
      video.muted = true;
      await video.play();
      if (version !== selectionVersion) return;
      autoplayBlocked = false;
      if (!wanted || document.hidden || !visible) video.pause();
    } catch {
      if (version !== selectionVersion) return;
      autoplayBlocked = true;
      if (video.currentTime === 0) { video.hidden = true; image.hidden = false; }
    }
    playbackLabels();
  }

  function formatAction(action) {
    const parts = [messages[language][action.kind] || action.kind];
    if (Array.isArray(action.delta_position)) parts.push("Δxyz [" + action.delta_position.map((v) => number(v * 1000, 1)).join(", ") + "] mm");
    if (Array.isArray(action.delta_rotation) && action.delta_rotation.some((v) => v !== 0)) parts.push("Δrot [" + action.delta_rotation.map((v) => number(v, 3)).join(", ") + "] rad");
    if (finite(action.gripper_opening)) parts.push(t("gripper_command", { value: number(action.gripper_opening, 3) }));
    return parts.join(" · ");
  }

  function renderCue(force = false) {
    if (!selected) return;
    let next = 0;
    for (let i = 1; i < selected.cues.length; i++) {
      if (selected.cues[i].start_seconds > video.currentTime + 0.0001) break;
      next = i;
    }
    const terminal = video.currentTime >= selected.summary.simulation_seconds;
    const key = next + (terminal ? selected.cues.length : 0);
    if (!force && cueIndex === key) return;
    cueIndex = key;
    const cue = selected.cues[next];
    byId("hero-decision").dataset.decision = String(cue.decision);
    byId("hero-previous-decision").disabled = !mediaReady || mediaFailed || next === 0;
    byId("hero-next-decision").disabled = !mediaReady || mediaFailed || next === selected.cues.length - 1;
    byId("hero-decision-number").textContent = terminal ? t("final") : t("step", { step: cue.decision, total: selected.summary.decisions });
    byId("hero-action-explanation").textContent = localized(cue.explanation);
    byId("hero-action-command").textContent = formatAction(cue.action);
    const feedback = cue.previous_feedback;
    let status = !feedback ? t("no_feedback") : messages[language]["status_" + feedback.status] || t("unavailable_feedback");
    if (finite(feedback?.position_error_m)) status += " · " + t("feedback_error", { error: number(feedback.position_error_m * 1000, 2) });
    byId("hero-action-feedback").textContent = status;
  }

  function updateProgress() {
    if (!selected) return;
    const duration = Number.isFinite(video.duration) ? video.duration : selected.preview.duration_seconds;
    progress.max = String(duration);
    progress.value = String(video.currentTime);
    progress.setAttribute("aria-valuetext", t("seek_value", { seconds: number(video.currentTime, 2), total: number(duration, 2) }));
    byId("hero-time").textContent = video.currentTime.toFixed(2) + " / " + duration.toFixed(2) + " s";
    renderCue();
  }

  function renderDetails() {
    if (!selected) return;
    const title = localized(selected.task);
    video.setAttribute("aria-label", t("preview_aria", { task: title }));
    image.alt = t("preview_aria", { task: title });
    byId("hero-task-name").textContent = title;
    byId("hero-task-summary").textContent = t("summary", { model: selected.model, decisions: number(selected.summary.decisions), steps: number(selected.summary.control_steps), seconds: number(selected.summary.simulation_seconds) });
    byId("hero-outcome-note").textContent = localized(selected.outcome_note);
    byId("hero-full-video").href = selected.full_video;
    const workspace = byId("hero-workspace-link");
    workspace.hidden = !/^playground\/$/.test(selected.workspace || "");
    if (!workspace.hidden) workspace.href = selected.workspace + "?lang=" + language;
    for (const card of document.querySelectorAll("[data-showcase-episode]")) card.setAttribute("aria-pressed", String(card.dataset.showcaseEpisode === selected.id));
    renderCue(true);
    updateProgress();
    playbackLabels();
  }

  function selectEpisode(item, userInitiated = false) {
    if (selected?.id === item.id) return;
    selectionVersion++;
    mediaReady = false;
    video.pause();
    releasePreview();
    selected = item;
    byId("hero-decision").dataset.episode = item.id;
    cueIndex = -1;
    mediaFailed = false;
    autoplayBlocked = false;
    if (userInitiated) wanted = !reducedMotion.matches;
    image.src = item.preview.poster;
    image.hidden = false;
    video.hidden = true;
    video.poster = item.preview.poster;
    play.disabled = true;
    progress.disabled = true;
    byId("hero-decision").hidden = false;
    renderDetails();
    loadPreview(item, selectionVersion);
  }

  function releasePreview() {
    previewRequest?.abort();
    previewRequest = null;
    video.removeAttribute("src");
    video.load();
    if (previewBlobUrl) URL.revokeObjectURL(previewBlobUrl);
    previewBlobUrl = null;
  }

  function previewError() {
    mediaReady = false;
    mediaFailed = true;
    video.hidden = true; image.hidden = false;
    play.disabled = true; progress.disabled = true;
    byId("hero-previous-decision").disabled = true;
    byId("hero-next-decision").disabled = true;
    playbackLabels();
  }

  async function loadPreview(item, version) {
    const controller = new AbortController();
    previewRequest = controller;
    try {
      // Small previews are downloaded once. A local Blob remains seekable even
      // when a basic static server does not implement HTTP Range requests.
      const response = await fetch(item.preview.video, { credentials: "omit", signal: controller.signal });
      if (!response.ok) throw new Error("Preview unavailable");
      const blob = await response.blob();
      if (version !== selectionVersion || controller.signal.aborted) return;
      if (!blob.size) throw new Error("Empty preview");
      previewBlobUrl = URL.createObjectURL(blob);
      video.src = previewBlobUrl;
      video.load();
    } catch {
      if (version === selectionVersion && !controller.signal.aborted) previewError();
    } finally {
      if (previewRequest === controller) previewRequest = null;
    }
  }

  function renderCards() {
    const container = byId("skill-cards");
    container.replaceChildren();
    container.setAttribute("aria-label", t("gallery_aria"));
    for (const item of episodes) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "skill-card";
      button.dataset.showcaseEpisode = item.id;
      button.setAttribute("aria-pressed", String(selected?.id === item.id));
      button.setAttribute("aria-label", t("card_aria", { task: localized(item.task) }));
      const thumbnail = document.createElement("img");
      thumbnail.src = item.preview.poster; thumbnail.alt = ""; thumbnail.width = 128; thumbnail.height = 128; thumbnail.loading = "lazy";
      const copy = document.createElement("span"); copy.className = "skill-card-copy";
      for (const [className, text] of [["skill-card-result", t("verified")], ["skill-card-title", localized(item.label)], ["skill-card-meta", t("card_summary", { decisions: number(item.summary.decisions), seconds: number(item.summary.simulation_seconds) })]]) {
        const field = document.createElement("span"); field.className = className; field.textContent = text; copy.appendChild(field);
      }
      button.append(thumbnail, copy);
      button.addEventListener("click", () => {
        selectEpisode(item, true);
        byId("hero-video").closest(".hero-visual").scrollIntoView({ behavior: reducedMotion.matches ? "instant" : "smooth", block: "start" });
      });
      container.appendChild(button);
    }
  }

  function setLanguage(next) {
    language = next === "zh" ? "zh" : "en";
    for (const element of document.querySelectorAll("[data-showcase-i18n]")) element.textContent = t(element.dataset.showcaseI18n);
    renderCards(); renderDetails(); playbackLabels();
  }

  play.addEventListener("click", () => {
    wanted = video.paused;
    if (wanted) startPreview(); else video.pause();
  });
  progress.addEventListener("input", () => {
    if (!mediaReady || mediaFailed) return;
    wanted = false;
    video.pause();
    video.currentTime = Number(progress.value);
    video.hidden = false; image.hidden = true;
    updateProgress();
  });
  function jumpDecision(delta) {
    if (!selected || !mediaReady || mediaFailed) return;
    const current = Math.max(0, cueIndex % selected.cues.length);
    const next = Math.max(0, Math.min(selected.cues.length - 1, current + delta));
    wanted = false; video.pause();
    video.currentTime = selected.cues[next].start_seconds;
    video.hidden = false; image.hidden = true; updateProgress();
  }
  byId("hero-previous-decision").addEventListener("click", () => jumpDecision(-1));
  byId("hero-next-decision").addEventListener("click", () => jumpDecision(1));
  video.addEventListener("playing", () => { video.hidden = false; image.hidden = true; playbackLabels(); });
  video.addEventListener("pause", playbackLabels);
  video.addEventListener("timeupdate", updateProgress);
  video.addEventListener("seeked", updateProgress);
  video.addEventListener("loadedmetadata", () => {
    if (!previewBlobUrl || video.getAttribute("src") !== previewBlobUrl) return;
    mediaReady = true;
    play.disabled = false; progress.disabled = false;
    renderCue(true); updateProgress();
    if (wanted) startPreview();
  });
  if ("requestVideoFrameCallback" in video) {
    const onFrame = () => { updateProgress(); video.requestVideoFrameCallback(onFrame); };
    video.requestVideoFrameCallback(onFrame);
  }
  video.addEventListener("error", () => { if (previewBlobUrl) previewError(); });
  window.addEventListener("pagehide", (event) => { if (!event.persisted) releasePreview(); });
  document.addEventListener("maniloop:language", (event) => setLanguage(event.detail.language));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) video.pause(); else if (wanted) startPreview();
  });
  reducedMotion.addEventListener("change", () => {
    if (reducedMotion.matches) { wanted = false; video.pause(); }
    playbackLabels();
  });
  if ("IntersectionObserver" in window) new IntersectionObserver((entries) => {
    visible = entries[0].isIntersecting;
    if (!visible) video.pause(); else if (wanted) startPreview();
  }, { threshold: 0.1 }).observe(video.closest(".hero-image-frame"));
  // A visitor explicitly starting the full episode takes precedence over the loop.
  byId("episode-video").addEventListener("play", () => { wanted = false; video.pause(); });

  async function load() {
    try {
      const response = await fetch("assets/showcase.json?v=recorded-skills-1", { credentials: "omit" });
      if (!response.ok) return;
      const data = await response.json();
      if (data.format !== "maniloop_showcase_v1" || !Array.isArray(data.episodes) || data.episodes.length > 50) return;
      const seen = new Set();
      episodes = data.episodes.filter((item) => validEpisode(item) && !seen.has(item.id) && seen.add(item.id));
      if (!episodes.length) return;
      byId("skills").hidden = false;
      renderCards(); selectEpisode(episodes[0]);
    } catch { /* The original poster and complete episode remain usable offline. */ }
  }
  setLanguage(language);
  load();
})();
