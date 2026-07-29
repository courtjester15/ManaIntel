"use strict";

const app = document.querySelector("#summary-app");
const title = document.querySelector("#summary-title");
const meta = document.querySelector("#summary-meta");
const actions = document.querySelector("#summary-actions");
const reviewBanner = document.querySelector("#review-banner");

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
    const url = new URL(value, window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? escapeHtml(url.href) : "#";
  } catch { return "#"; }
}

function formatDate(value, long = false) {
  if (!value) return "Unknown date";
  return new Intl.DateTimeFormat("en-US", long
    ? { month: "long", day: "numeric", year: "numeric" }
    : { month: "short", day: "numeric", year: "numeric" }
  ).format(new Date(value));
}

function display(value, fallback = "Not stated") {
  return value === null || value === undefined || value === "" ? fallback : escapeHtml(value);
}

function label(value) { return String(value ?? "unknown").replaceAll("_", " "); }
function target(value) { return value ? escapeHtml(value.raw) : "Not stated"; }
function badge(value, kind = "status") { return `<span class="${kind} ${escapeHtml(value ?? "unknown")}">${escapeHtml(label(value))}</span>`; }
function sentenceList(items, empty = "Not stated") {
  return items?.length ? items.map((item) => `<li>${escapeHtml(item)}</li>`).join("") : `<li>${escapeHtml(empty)}</li>`;
}

function timestamp(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const seconds = Math.floor(value % 60);
  return [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
}

function pickMeta(pick) {
  return [
    pick.printing || "Printing not stated",
    pick.printing_certainty ? `${label(pick.printing_certainty)} printing` : "printing certainty unknown",
    pick.hosts?.length ? pick.hosts.join(", ") : "host not stated",
  ].map(escapeHtml).join(" · ");
}

function listenUrl(episode, pick) {
  const start = typeof pick.start_seconds === "number" ? `#t=${Math.floor(pick.start_seconds)}` : "";
  return `${safeUrl(episode.audio_url)}${start}`;
}

function pickCard(episode, pick, index) {
  const time = timestamp(pick.start_seconds);
  return `<article class="summary-pick-card">
    <div class="pick-card-head">
      <div>
        <p class="eyebrow">Pick ${index + 1}${time ? ` · ${escapeHtml(time)}` : ""}</p>
        <h2>${escapeHtml(pick.card)}</h2>
        <p class="pick-meta">${pickMeta(pick)}</p>
      </div>
      <div class="pick-badges">
        ${pick.confidence ? badge(pick.confidence, "confidence") : ""}
        ${pick.review_status ? badge(pick.review_status) : ""}
      </div>
    </div>
    <div class="target-strip">
      <div><small>Entry</small><strong>${target(pick.entry_target)}</strong></div>
      <div><small>Hold</small><strong>${display(pick.hold)}</strong></div>
      <div><small>Exit</small><strong>${target(pick.exit_target)}</strong></div>
    </div>
    <div class="recommendation-callout"><small>Host recommendation</small><p>${escapeHtml(pick.recommendation)}</p></div>
    <div class="summary-columns">
      <section><h3>Reasoning</h3><ul>${sentenceList(pick.reasoning)}</ul></section>
      <section><h3>Caveats</h3><ul>${sentenceList(pick.caveats, "None stated")}</ul></section>
    </div>
    <details class="evidence-disclosure"><summary>Evidence${time ? ` · ${escapeHtml(time)}` : ""}</summary><div class="evidence">${escapeHtml(pick.evidence_excerpt || "No evidence excerpt recorded.")}</div></details>
    <div class="latest-actions"><a class="button" href="${listenUrl(episode, pick)}" target="_blank" rel="noreferrer">Listen at timestamp</a></div>
  </article>`;
}

async function loadSummary() {
  const params = new URLSearchParams(window.location.search);
  const requestedEpisode = params.get("episode");
  const episodeDir = requestedEpisode?.replace(/^episodes\//, "");
  if (!episodeDir || !/^[a-z0-9][a-z0-9-]*$/i.test(episodeDir)) {
    app.innerHTML = `<div class="empty-state"><strong>Episode not found</strong><p>This summary viewer needs an episode directory in the URL.</p></div>`;
    return;
  }

  const summaryUrl = `archive/episodes/${episodeDir}/summary.json`;
  const effectiveUrl = `archive/episodes/${episodeDir}/effective.json`;
  try {
    let response = await fetch(`${effectiveUrl}?v=${Date.now()}`);
    const humanReviewed = response.ok;
    if (!humanReviewed) response = await fetch(`${summaryUrl}?v=${Date.now()}`);
    if (!response.ok) throw new Error("Structured summary JSON was not found.");
    const summary = await response.json();
    const markdownUrl = `archive/episodes/${episodeDir}/${humanReviewed ? "effective.md" : "summary.md"}`;
    const episode = summary.episode || {};
    const processing = summary.processing || {};
    const picks = summary.recommendations || [];

    document.title = `${episode.source_name || "ManaIntel"} · ${episode.title || "Episode Summary"}`;
    title.textContent = episode.title || "Episode Summary";
    meta.innerHTML = [
      episode.episode_number ? `Episode ${escapeHtml(episode.episode_number)}` : null,
      formatDate(episode.published_at, true),
      episode.source_name || "MTG Fast Finance",
      `${picks.length} recommendations`,
      processing.status ? label(processing.status) : null,
    ].filter(Boolean).join(" · ");
    actions.innerHTML = `<a class="button" href="${safeUrl(episode.audio_url)}" target="_blank" rel="noreferrer">Listen</a><a class="button secondary" href="${escapeHtml(markdownUrl)}" target="_blank">Raw Markdown</a>`;

    if (processing.human_review) {
      reviewBanner.hidden = false;
      reviewBanner.textContent = `Human reviewed by ${processing.human_review.reviewed_by}${processing.human_review.note ? ` · ${processing.human_review.note}` : ""}`;
    } else if (processing.review_reason) {
      reviewBanner.hidden = false;
      reviewBanner.textContent = processing.review_reason;
    }

    app.innerHTML = `
      <section class="grid metrics summary-metrics">
        <article class="metric"><p>Status</p><strong>${escapeHtml(label(processing.status))}</strong><small>${escapeHtml(label(processing.review_state))}</small></article>
        <article class="metric"><p>Picks</p><strong>${Number(picks.length)}</strong><small>structured records</small></article>
        <article class="metric"><p>Duration</p><strong>${timestamp(episode.duration_seconds) || "—"}</strong><small>source audio</small></article>
      </section>
      <section class="summary-picks">
        ${picks.length ? picks.map((pick, index) => pickCard(episode, pick, index)).join("") : `<div class="empty-state"><strong>No recommendations found</strong><p>The pipeline did not publish structured picks for this episode.</p></div>`}
      </section>
      <section class="panel prose summary-source"><div class="panel-body"><p class="eyebrow">Source description</p><p>${escapeHtml(episode.description || "No feed description was captured.")}</p></div></section>
    `;
  } catch (error) {
    app.innerHTML = `<div class="empty-state"><strong>Summary could not be loaded</strong><p>${escapeHtml(error.message)}</p></div>`;
  }
}

loadSummary();
