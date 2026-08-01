"use strict";

(function exposeAudioPlayback(global) {
  let player = null;
  let pendingSeek = null;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function safeUrl(value) {
    try {
      const url = new URL(value, global.location?.href || "https://example.invalid/");
      return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
    } catch { return "#"; }
  }

  function parseTime(value) {
    if (typeof value === "number") return Number.isFinite(value) && value >= 0 ? Math.floor(value) : null;
    const raw = String(value ?? "").trim();
    if (/^\d+(?:\.\d+)?$/.test(raw)) return Math.floor(Number(raw));
    const parts = raw.split(":");
    if (parts.length < 2 || parts.length > 3 || parts.some((part) => !/^\d{1,3}$/.test(part))) return null;
    const numbers = parts.map(Number);
    const seconds = numbers.pop();
    const minutes = numbers.pop();
    const hours = numbers.pop() || 0;
    if (minutes > 59 || seconds > 59) return null;
    return hours * 3600 + minutes * 60 + seconds;
  }

  function formatTime(value) {
    const seconds = parseTime(value);
    if (seconds === null) return "--:--";
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainder = seconds % 60;
    return hours
      ? [hours, minutes, remainder].map((part) => String(part).padStart(2, "0")).join(":")
      : [minutes, remainder].map((part) => String(part).padStart(2, "0")).join(":");
  }

  function clampTime(seconds, duration) {
    const parsed = parseTime(seconds);
    if (parsed === null) return null;
    if (!Number.isFinite(duration) || duration <= 0) return parsed;
    return Math.max(0, Math.min(parsed, Math.max(0, duration - 0.25)));
  }

  function setStatus(message, kind = "") {
    if (!player) return;
    player.status.textContent = message;
    player.status.dataset.kind = kind;
  }

  async function applySeek(request) {
    if (!player || !request) return false;
    const seconds = clampTime(request.seconds, player.audio.duration);
    if (seconds === null) {
      setStatus("That timestamp is not valid.", "error");
      return false;
    }
    try {
      player.audio.currentTime = seconds;
      player.selected.textContent = `${request.label || "Selected context"} · ${formatTime(seconds)}`;
      setStatus(`Ready at ${formatTime(seconds)}.`, "ready");
      if (request.autoplay) {
        try { await player.audio.play(); }
        catch { setStatus(`Ready at ${formatTime(seconds)} — press play to listen.`, "ready"); }
      }
      return true;
    } catch {
      setStatus("This audio host would not seek. Use the original episode link.", "error");
      return false;
    }
  }

  function seekTo(value, options = {}) {
    if (!player) return false;
    const seconds = parseTime(value);
    if (seconds === null) {
      setStatus("That timestamp is not valid.", "error");
      return false;
    }
    pendingSeek = { seconds, autoplay: options.autoplay !== false, label: options.label };
    player.root.hidden = false;
    player.root.scrollIntoView({ behavior: options.scroll === false ? "auto" : "smooth", block: "nearest" });
    if (player.audio.readyState >= 1) applySeek(pendingSeek);
    else {
      setStatus(`Loading audio to seek to ${formatTime(seconds)}…`);
      player.audio.load();
    }
    return true;
  }

  function mount(options) {
    const container = typeof options.container === "string" ? document.querySelector(options.container) : options.container;
    if (!container) return null;
    const audioUrl = safeUrl(options.audioUrl);
    const sourceUrl = safeUrl(options.sourceUrl);
    if (audioUrl === "#") {
      container.innerHTML = `<div class="audio-player-fallback">Audio is unavailable. <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noreferrer">Open the original episode</a>.</div>`;
      return null;
    }
    container.innerHTML = `<section class="context-player" aria-label="Episode context player">
      <div class="context-player-head"><div><p class="eyebrow">Listen for context</p><strong>${escapeHtml(options.title || "Episode audio")}</strong></div><span data-player-selected>Choose a timestamp below</span></div>
      <audio controls preload="metadata" src="${escapeHtml(audioUrl)}"></audio>
      <div class="context-player-tools"><button type="button" data-skip="-15">−15 sec</button><button type="button" data-skip="15">+15 sec</button><span data-player-status>Ready to listen.</span><a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noreferrer">Original episode</a></div>
    </section>`;
    const root = container.firstElementChild;
    player = {
      root,
      audio: root.querySelector("audio"),
      selected: root.querySelector("[data-player-selected]"),
      status: root.querySelector("[data-player-status]"),
    };
    player.audio.addEventListener("loadedmetadata", () => {
      if (pendingSeek) applySeek(pendingSeek);
    });
    player.audio.addEventListener("error", () => setStatus("Audio could not be loaded here. Use the original episode link.", "error"));
    root.querySelectorAll("[data-skip]").forEach((button) => button.addEventListener("click", () => {
      const next = Math.max(0, player.audio.currentTime + Number(button.dataset.skip));
      seekTo(next, { label: "Manual position", autoplay: !player.audio.paused, scroll: false });
    }));
    return player;
  }

  function bind(root = document) {
    root.addEventListener("click", (event) => {
      const control = event.target.closest("[data-listen-seconds]");
      if (!control) return;
      event.preventDefault();
      const label = control.dataset.listenLabel || "Selected context";
      if (seekTo(control.dataset.listenSeconds, { label })) {
        const href = control.getAttribute("href");
        if (href && global.history?.replaceState) global.history.replaceState(null, "", href);
        const targetId = control.dataset.listenTarget;
        if (targetId) document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }

  const api = { bind, clampTime, formatTime, mount, parseTime, seekTo };
  global.AudioPlayback = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
