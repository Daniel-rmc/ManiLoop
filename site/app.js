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
  const imagePath = /^assets\/frames\/[a-zA-Z0-9_-]+\.(jpg|jpeg|png|webp)$/;

  function setPlaying(playing) {
    if (timer !== null) {
      window.clearInterval(timer);
      timer = null;
    }
    playButton.setAttribute("aria-pressed", String(playing));
    playButton.setAttribute("aria-label", playing ? "暂停播放精选记录" : "播放精选记录");
    byId("play-icon").textContent = playing ? "Ⅱ" : "▶";
    byId("play-label").textContent = playing ? "暂停记录" : "播放记录";
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
      if (!Array.isArray(data.frames) || !data.frames.length || data.frames.length > 100) {
        throw new Error("Invalid recording");
      }
      const valid = data.frames.every((frame) =>
        Number.isInteger(frame.step) && frame.step >= 0 &&
        typeof frame.title === "string" && typeof frame.explanation === "string" &&
        typeof frame.external === "string" && imagePath.test(frame.external) &&
        typeof frame.wrist === "string" && imagePath.test(frame.wrist)
      );
      if (!valid) throw new Error("Invalid frame");
      frames = data.frames;
      slider.max = String(frames.length - 1);
      if (typeof data.task === "string") byId("record-task").textContent = data.task;
      byId("hero-image").src = frames[0].external;
      renderFrame(0);
      byId("playback-controls").hidden = false;
      for (const frame of frames.slice(1)) {
        const external = new Image();
        const wrist = new Image();
        external.src = frame.external;
        wrist.src = frame.wrist;
      }
    } catch {
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

