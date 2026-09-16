"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const slider = byId("frame-slider");
  const playButton = byId("play-toggle");
  const previous = byId("previous-frame");
  const next = byId("next-frame");
  let frames = [];
  let index = 0;
  let timer = null;
  const stageLabels = { before: "动作前 / BEFORE", after: "动作后 / AFTER", final: "最终帧 / FINAL" };
  const imagePath = /^assets\/(frames|episodes)\/[a-zA-Z0-9_/-]+\.(jpg|jpeg|png|webp)$/;
  const videoPath = /^assets\/episodes\/[a-zA-Z0-9_/-]+\.mp4$/;
  const terminationLabels = {
    success: "官方任务条件满足后终止",
    task_success: "官方任务条件满足后终止",
    decision_budget: "决策预算耗尽",
    simulation_budget: "仿真时间预算耗尽",
    wall_budget: "墙钟时间预算耗尽",
    model_done: "模型声明结束",
    stopped: "运行停止"
  };

  // Public data is curated from one run. A model's own `done` cannot verify
  // success; both the summary and the separately checked evaluator must agree.
  function hasVerifiedSuccess(data) {
    return data.summary?.success === true && data.evaluation?.success === true &&
      data.evaluation?.verified === true && data.evaluation?.source === "LIBERO check_success";
  }

  function nonnegativeNumber(value) {
    return typeof value === "number" && Number.isFinite(value) && value >= 0;
  }

  function metric(value, precision = 0) {
    return nonnegativeNumber(value) ? value.toLocaleString("en-US", {
      maximumFractionDigits: precision
    }) : "—";
  }

  function safeReportUrl(value) {
    if (typeof value !== "string") return null;
    try {
      const url = new URL(value);
      return url.protocol === "https:" && !url.username && !url.password ? url.href : null;
    } catch {
      return null;
    }
  }

  function renderRecordingMetadata(data) {
    const summary = data.summary || {};
    const context = data.context || {};
    const verified = hasVerifiedSuccess(data);
    const failed = summary.success === false;
    const model = typeof data.model === "string" ? data.model : "模型未记录";
    if (typeof data.task === "string") byId("record-task").textContent = data.task;
    byId("record-date").textContent = /^\d{4}-\d{2}-\d{2}$/.test(data.date || "")
      ? data.date.replaceAll("-", ".") : "日期未记录";
    const modelDetails = [model];
    if (typeof data.context_mode === "string") modelDetails.push(data.context_mode + " 视觉上下文");
    if (typeof context.reasoning_effort === "string") modelDetails.push(context.reasoning_effort + " 推理");
    byId("record-model").textContent = modelDetails.join(" · ");
    const conditions = [];
    if (typeof context.suite === "string") conditions.push(context.suite);
    for (const [key, label] of [["task_id", "task"], ["init_state_id", "init"], ["seed", "seed"]]) {
      if (Number.isInteger(context[key]) && context[key] >= 0) conditions.push(label + " " + context[key]);
    }
    if (typeof context.timing === "string") conditions.push(context.timing + " 时序");
    byId("record-conditions").textContent = conditions.length ? conditions.join(" / ") : "完整运行条件见实测报告";
    byId("metric-decisions").textContent = metric(summary.decisions);
    byId("metric-steps").textContent = metric(summary.control_steps);
    byId("metric-seconds").textContent = metric(summary.simulation_seconds, 2);
    byId("metric-outcome").textContent = verified ? "成功" : failed ? "未成功" : "待核验";
    byId("metric-result").dataset.result = verified ? "success" : failed ? "failure" : "unknown";
    byId("metric-evaluator").textContent = verified ? "LIBERO 官方评分 · true" : failed
      ? "独立任务结果 · false" : "成功结果尚未独立核验";
    byId("record-tag").textContent = verified ? "VERIFIED EPISODE" : "RECORDED ATTEMPT";
    byId("record-result-note").textContent = verified
      ? "同一次运行的终止结果已核对：LIBERO check_success 返回 true。独立评分未进入模型输入。"
      : failed ? "该次尝试的独立成功结果为 false；" +
        (terminationLabels[summary.termination_reason] || "终止原因见实测报告") + "。"
        : "任务是否完成仍需核对独立评分；模型声明和控制到位均不能替代任务成功。";
    if (verified && typeof data.outcome_note === "string") {
      byId("record-result-note").textContent += " " + data.outcome_note;
    }
    const reportUrl = safeReportUrl(data.report_url);
    if (reportUrl) byId("record-report").href = reportUrl;
    byId("demo-intro").textContent = model + " 的真实仿真操作记录。浏览页面只播放已保存的媒体，不会调用模型或运行仿真。";
    renderEpisode(data, verified);
  }

  function renderEpisode(data, verified) {
    const episode = data.episode;
    const summary = data.summary || {};
    // Initial image + every native control step, ending at the terminal state.
    // Reject selected-frame slideshows and mismatched timing as full episodes.
    const complete = episode && episode.complete === true &&
      episode.starts_at_initialization === true && episode.ends_at_terminal_state === true &&
      Number.isInteger(episode.frame_count) && Number.isInteger(summary.control_steps) &&
      episode.frame_count === summary.control_steps + 1 && summary.control_steps > 0 &&
      nonnegativeNumber(episode.fps) && episode.fps > 0 &&
      nonnegativeNumber(summary.simulation_seconds) &&
      Math.abs(summary.control_steps / episode.fps - summary.simulation_seconds) < 0.001 &&
      typeof episode.video === "string" && videoPath.test(episode.video);
    if (!verified || !complete) return;
    const video = byId("episode-video");
    video.src = episode.video;
    if (typeof episode.poster === "string" && imagePath.test(episode.poster)) video.poster = episode.poster;
    video.setAttribute("aria-label", (data.task || "机器人操作") + "：从初始化到官方成功的完整 episode");
    byId("episode-download").href = episode.video;
    byId("episode-meta").textContent = metric(episode.fps, 2) + " FPS · " +
      metric(episode.frame_count) + " FRAMES · " + metric(summary.simulation_seconds, 2) + " s SIM";
    byId("episode-caption").textContent = "同一次尝试，从初始化到 LIBERO 官方成功终止；保留初始画面与每个控制步，未拼接其他运行。";
    byId("episode-timing-note").textContent = "按仿真时间 1× 播放，" + metric(episode.fps, 2) +
      " 帧/秒；模型推理等待期间物理暂停，因此不计入视频时长。";
    byId("episode-player").hidden = false;
    byId("demo-title").textContent = "从开始到完成，一次完整操作。";
    video.addEventListener("error", () => {
      byId("episode-timing-note").textContent = "视频暂时无法播放，请刷新或使用右侧链接打开录像。独立结果与实测报告仍可查阅。";
    });
  }

  function setPlaying(playing) {
    if (timer !== null) {
      window.clearInterval(timer);
      timer = null;
    }
    playButton.setAttribute("aria-pressed", String(playing));
    playButton.setAttribute("aria-label", playing ? "暂停播放精选记录" : "播放精选记录");
    byId("play-icon").textContent = playing ? "Ⅱ" : "▶";
    byId("play-label").textContent = playing ? "暂停精选帧" : "播放精选帧";
    if (playing) {
      if (index === frames.length - 1) renderFrame(0);
      timer = window.setInterval(() => {
        if (index < frames.length - 1) renderFrame(index + 1);
        if (index === frames.length - 1) setPlaying(false);
      }, 3500);
    }
  }

  function renderFrame(requestedIndex) {
    if (!frames.length) return;
    index = Math.max(0, Math.min(frames.length - 1, requestedIndex));
    const frame = frames[index];
    const ordinal = String(index + 1).padStart(2, "0");
    byId("external-frame").src = frame.external;
    byId("wrist-frame").src = frame.wrist;
    byId("external-frame").alt = "第 " + frame.step + " 次决策，" + frame.title + "：外部相机";
    byId("wrist-frame").alt = "第 " + frame.step + " 次决策，" + frame.title + "：腕部相机";
    byId("frame-stage").textContent = stageLabels[frame.stage] || "记录帧 / FRAME";
    byId("frame-step").textContent = "STEP " + String(frame.step).padStart(2, "0");
    byId("frame-title").textContent = frame.title;
    byId("frame-explanation").textContent = frame.explanation;
    byId("frame-status").textContent = frame.feedback?.status || "未记录";
    const error = frame.feedback?.position_error_m;
    byId("frame-error").textContent = typeof error === "number" && Number.isFinite(error)
      ? (error * 1000).toFixed(2) + " mm" : "未记录";
    slider.value = String(index);
    slider.setAttribute("aria-valuetext", "精选帧 " + (index + 1) + "，共 " + frames.length + " 帧；" + frame.title);
    byId("frame-counter").textContent = ordinal + " / " + String(frames.length).padStart(2, "0");
    previous.disabled = index === 0;
    next.disabled = index === frames.length - 1;
  }

  function selectFrame(requestedIndex) {
    setPlaying(false);
    renderFrame(requestedIndex);
  }

  previous.addEventListener("click", () => selectFrame(index - 1));
  next.addEventListener("click", () => selectFrame(index + 1));
  playButton.addEventListener("click", () => setPlaying(timer === null && frames.length > 1));
  slider.addEventListener("input", () => selectFrame(Number(slider.value)));
  byId("playback-controls").addEventListener("keydown", (event) => {
    if (event.target === slider || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      selectFrame(index + (event.key === "ArrowRight" ? 1 : -1));
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) setPlaying(false);
  });

  async function loadRecording() {
    try {
      const response = await fetch("assets/demo-data.json", { credentials: "omit" });
      if (!response.ok) throw new Error("Recording unavailable");
      const data = await response.json();
      if (!data || typeof data !== "object" || !Array.isArray(data.frames) || data.frames.length > 100) {
        throw new Error("Invalid recording");
      }
      const valid = data.frames.every((frame) =>
        frame && Number.isInteger(frame.step) && frame.step >= 0 &&
        typeof frame.title === "string" && typeof frame.explanation === "string" &&
        typeof frame.external === "string" && imagePath.test(frame.external) &&
        typeof frame.wrist === "string" && imagePath.test(frame.wrist)
      );
      if (!valid) throw new Error("Invalid frame");
      frames = data.frames;
      renderRecordingMetadata(data);
      if (!frames.length) {
        byId("selected-heading").hidden = true;
        byId("record-layout").hidden = true;
        return;
      }
      slider.max = String(frames.length - 1);
      byId("hero-image").src = frames[0].external;
      byId("hero-image").alt = "真实 LIBERO 仿真记录：" + (data.task || "机器人操作任务");
      renderFrame(0);
      byId("playback-controls").hidden = false;
      for (const frame of frames.slice(1)) {
        const external = new Image();
        const wrist = new Image();
        external.src = frame.external;
        wrist.src = frame.wrist;
      }
    } catch {
      byId("metric-outcome").textContent = "未载入";
      byId("frame-title").textContent = "记录暂时无法载入";
      byId("frame-explanation").textContent = "请刷新页面重试，或通过下方链接阅读完整实测报告。";
      byId("playback-note").textContent = "记录加载失败；展示页不会调用模型或启动仿真。";
    }
  }

  for (const button of document.querySelectorAll("[data-copy]")) {
    button.addEventListener("click", async () => {
      const code = byId(button.dataset.copy);
      try {
        if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
        await navigator.clipboard.writeText(code.textContent);
        button.textContent = "已复制";
        byId("copy-status").textContent = "命令已复制到剪贴板。";
        window.setTimeout(() => { button.textContent = "复制"; }, 2200);
      } catch {
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(code);
        selection.removeAllRanges();
        selection.addRange(range);
        button.textContent = "请手动复制";
        byId("copy-status").textContent = "已选中命令，请使用系统复制快捷键。";
      }
    });
  }
  loadRecording();
})();
