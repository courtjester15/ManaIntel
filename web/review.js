"use strict";

const REVIEW_SCHEMA_VERSION = "1.0.0";
const reviewApp = document.querySelector("#review-app");
const reviewTitle = document.querySelector("#review-title");
const reviewMeta = document.querySelector("#review-meta");
let sourceSummary = null;
let reviewWorkflowUrl = null;
let addedPickCounter = 0;

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

function formatDate(value) {
  if (!value) return "Unknown date";
  return new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", year: "numeric" }).format(new Date(value));
}

function secondsToTimestamp(value) {
  if (!Number.isFinite(value) || value < 0) return "";
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const seconds = Math.floor(value % 60);
  return [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
}

function timestampToSeconds(value) {
  const match = String(value || "").trim().match(/^(\d{1,3}):([0-5]\d):([0-5]\d)$/);
  if (!match) throw new Error(`Timestamp "${value}" must use HH:MM:SS.`);
  return Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3]);
}

function inputField(label, name, value, options = {}) {
  const required = options.required ? " required" : "";
  const wide = options.wide ? " review-field-wide" : "";
  const type = options.type || "text";
  if (options.multiline) {
    return `<label class="review-field${wide}"><span>${escapeHtml(label)}</span><textarea name="${escapeHtml(name)}"${required}>${escapeHtml(value)}</textarea></label>`;
  }
  return `<label class="review-field${wide}"><span>${escapeHtml(label)}</span><input type="${type}" name="${escapeHtml(name)}" value="${escapeHtml(value)}"${required}></label>`;
}

function pickEditor(pick, index, isNew = false) {
  const editorId = isNew ? `new-${addedPickCounter++}` : pick.id;
  const hosts = (pick.hosts || sourceSummary.episode.hosts || []).join(", ");
  return `<article class="panel review-pick" data-review-pick="${escapeHtml(editorId)}" data-original-id="${escapeHtml(isNew ? "" : pick.id)}" data-new="${isNew}">
    <div class="panel-head">
      <div>
        <p class="eyebrow">${isNew ? "Missing pick" : `Extracted pick ${index + 1}`}</p>
        <h2>${escapeHtml(pick.card || "New pick")}</h2>
      </div>
      <div class="review-head-actions">
      <button class="link-button" type="button" data-review-listen>Listen${Number.isFinite(pick.start_seconds) ? ` · ${escapeHtml(secondsToTimestamp(pick.start_seconds))}` : ""}</button>
      ${isNew
        ? `<button class="link-button" type="button" data-remove-added>Remove draft</button>`
        : `<label class="review-action"><span>Decision</span><select name="action"><option value="keep">Keep</option><option value="exclude">Exclude</option><option value="update">Correct</option></select></label>`}
      </div>
    </div>
    <div class="panel-body review-fields" data-fields ${isNew ? "" : "hidden"}>
      ${inputField("Card", "card", pick.card || "", { required: true })}
      ${inputField("Printing", "printing", pick.printing || "")}
      ${inputField("Speaker(s), comma separated", "hosts", hosts, { required: true })}
      ${inputField("Timestamp", "timestamp", secondsToTimestamp(pick.start_seconds), { required: true })}
      ${inputField("Recommendation", "recommendation", pick.recommendation || "", { required: true, wide: true, multiline: true })}
      ${inputField("Evidence excerpt", "evidence_excerpt", pick.evidence_excerpt || "", { required: true, wide: true, multiline: true })}
    </div>
    ${isNew ? `<input type="hidden" name="action" value="add">` : ""}
  </article>`;
}

function renderReview() {
  const episode = sourceSummary.episode;
  const processing = sourceSummary.processing;
  reviewTitle.textContent = episode.title;
  reviewMeta.textContent = [
    episode.source_name || "MTG Fast Finance",
    episode.episode_number ? `Episode ${episode.episode_number}` : null,
    formatDate(episode.published_at),
    `${sourceSummary.recommendations.length} extracted picks`,
  ].filter(Boolean).join(" · ");

  reviewApp.innerHTML = `
    <section class="panel review-overview">
      <div class="panel-head"><h2>Why this needs review</h2><button class="link-button" type="button" data-listen-seconds="0" data-listen-label="Episode start">Listen from start</button></div>
      <div class="panel-body">
        <p>${escapeHtml(processing.review_reason || "The extraction was flagged for human verification.")}</p>
        <p class="muted">If everything is correct, leave every pick on <strong>Keep</strong> and prepare the review.</p>
      </div>
    </section>
    <section class="review-pick-list" id="review-picks">
      ${sourceSummary.recommendations.map((pick, index) => pickEditor(pick, index)).join("")}
    </section>
    <section class="panel">
      <div class="panel-head"><h2>Missing picks</h2><button class="link-button" id="add-pick" type="button">Add missing pick</button></div>
      <div class="panel-body" id="added-picks"><p class="muted" id="no-added-picks">No missing picks added.</p></div>
    </section>
    <section class="panel review-finalize">
      <div class="panel-head"><h2>Finalize review</h2><span class="status approved">Human verified</span></div>
      <div class="panel-body">
        ${inputField("Review note (optional)", "review-note", "", { wide: true, multiline: true })}
        <div class="latest-actions">
          <button class="button" id="prepare-review" type="button">Prepare review payload</button>
        </div>
        <div id="review-output" hidden>
          <label class="review-field review-field-wide"><span>Validated review payload</span><textarea id="review-payload" readonly></textarea></label>
          <p class="muted">Copy this payload, open the review workflow, paste it into <strong>review_payload</strong>, and run it. GitHub will validate, save, rebuild, and deploy the review.</p>
          <div class="latest-actions">
            <button class="button" id="copy-review" type="button">Copy payload</button>
            <a class="button secondary" href="${safeUrl(reviewWorkflowUrl)}" target="_blank" rel="noreferrer">Open review workflow</a>
          </div>
        </div>
        <div class="failure-note" id="review-error" hidden></div>
      </div>
    </section>`;
  AudioPlayback.mount({
    container: "#audio-player",
    audioUrl: episode.audio_url,
    sourceUrl: episode.episode_url,
    title: episode.title,
  });
  AudioPlayback.bind(document);
  bindReviewEvents();

  const params = new URLSearchParams(window.location.search);
  const requestedTime = AudioPlayback.parseTime(params.get("t"));
  if (requestedTime !== null) {
    const pick = sourceSummary.recommendations.find((item) => item.id === params.get("pick"));
    AudioPlayback.seekTo(requestedTime, { label: pick?.card || "Linked review context", autoplay: false, scroll: false });
    if (pick) document.querySelector(`[data-original-id="${CSS.escape(pick.id)}"]`)?.scrollIntoView({ block: "center" });
  }
}

function readPickValues(editor) {
  const field = (name) => editor.querySelector(`[name="${name}"]`).value.trim();
  return {
    card: field("card"),
    printing: field("printing"),
    hosts: field("hosts").split(",").map((host) => host.trim()).filter(Boolean),
    start_seconds: timestampToSeconds(field("timestamp")),
    recommendation: field("recommendation"),
    evidence_excerpt: field("evidence_excerpt"),
  };
}

function validatePickValues(values) {
  if (!values.card) throw new Error("Every included pick needs a card name.");
  if (!values.hosts.length) throw new Error(`${values.card} needs at least one speaker.`);
  if (!values.recommendation) throw new Error(`${values.card} needs a recommendation.`);
  if (!values.evidence_excerpt) throw new Error(`${values.card} needs a short evidence excerpt.`);
}

function changedFields(original, values) {
  const changes = {};
  const originalValues = {
    card: original.card,
    printing: original.printing || "",
    hosts: original.hosts || [],
    start_seconds: original.start_seconds,
    recommendation: original.recommendation,
    evidence_excerpt: original.evidence_excerpt,
  };
  Object.entries(values).forEach(([key, value]) => {
    if (JSON.stringify(value) !== JSON.stringify(originalValues[key])) changes[key] = value;
  });
  return changes;
}

function preparePayload() {
  const error = document.querySelector("#review-error");
  error.hidden = true;
  try {
    const operations = [];
    document.querySelectorAll(".review-pick[data-new='false']").forEach((editor) => {
      const action = editor.querySelector('[name="action"]').value;
      const pickId = editor.dataset.originalId;
      if (action === "exclude") {
        operations.push({ action: "exclude", pick_id: pickId });
      } else if (action === "update") {
        const values = readPickValues(editor);
        validatePickValues(values);
        const original = sourceSummary.recommendations.find((pick) => pick.id === pickId);
        const changes = changedFields(original, values);
        if (!Object.keys(changes).length) throw new Error(`${original.card} is marked Correct but has no changes.`);
        operations.push({ action: "update", pick_id: pickId, changes });
      }
    });
    document.querySelectorAll(".review-pick[data-new='true']").forEach((editor) => {
      const values = readPickValues(editor);
      validatePickValues(values);
      operations.push({ action: "add", pick: values });
    });
    const payload = {
      schema_version: REVIEW_SCHEMA_VERSION,
      source_id: sourceSummary.episode.source_id || "mtg-fast-finance",
      episode_guid: sourceSummary.episode.guid,
      expected: {
        processed_at: sourceSummary.processing.processed_at,
        pick_ids: sourceSummary.recommendations.map((pick) => pick.id),
      },
      decision: "approve",
      note: document.querySelector('[name="review-note"]').value.trim() || null,
      operations,
    };
    document.querySelector("#review-payload").value = JSON.stringify(payload);
    document.querySelector("#review-output").hidden = false;
    document.querySelector("#review-output").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (problem) {
    error.textContent = problem.message;
    error.hidden = false;
  }
}

function bindReviewEvents() {
  document.querySelector("#review-app").addEventListener("click", (event) => {
    const listen = event.target.closest("[data-review-listen]");
    if (!listen) return;
    const editor = listen.closest(".review-pick");
    const value = editor.querySelector('[name="timestamp"]').value;
    const card = editor.querySelector('[name="card"]').value.trim() || "Review context";
    const seconds = AudioPlayback.parseTime(value);
    if (seconds === null) {
      document.querySelector("#review-error").textContent = `Timestamp "${value}" must use HH:MM:SS.`;
      document.querySelector("#review-error").hidden = false;
      return;
    }
    AudioPlayback.seekTo(seconds, { label: card });
    const params = new URLSearchParams(window.location.search);
    params.set("t", seconds);
    if (editor.dataset.originalId) params.set("pick", editor.dataset.originalId);
    else params.delete("pick");
    history.replaceState(null, "", `${window.location.pathname}?${params}`);
  });
  document.querySelectorAll(".review-pick[data-new='false'] [name='action']").forEach((select) => {
    select.addEventListener("change", () => {
      select.closest(".review-pick").querySelector("[data-fields]").hidden = select.value !== "update";
    });
  });
  document.querySelector("#add-pick").addEventListener("click", () => {
    const container = document.querySelector("#added-picks");
    document.querySelector("#no-added-picks")?.remove();
    container.insertAdjacentHTML("beforeend", pickEditor({
      card: "",
      printing: null,
      hosts: sourceSummary.episode.hosts,
      recommendation: "",
      start_seconds: null,
      evidence_excerpt: "",
    }, container.querySelectorAll(".review-pick").length, true));
  });
  document.querySelector("#added-picks").addEventListener("click", (event) => {
    const remove = event.target.closest("[data-remove-added]");
    if (remove) remove.closest(".review-pick").remove();
  });
  document.querySelector("#prepare-review").addEventListener("click", preparePayload);
  document.querySelector("#review-output").addEventListener("click", (event) => {
    if (!event.target.closest("#copy-review")) return;
    const button = event.target.closest("#copy-review");
    navigator.clipboard.writeText(document.querySelector("#review-payload").value).then(() => {
      button.textContent = "Payload copied";
    });
  });
}

async function loadReview() {
  const episodeDir = new URLSearchParams(window.location.search).get("episode")?.replace(/^episodes\//, "");
  if (!episodeDir || !/^[a-z0-9][a-z0-9-]*$/i.test(episodeDir)) {
    reviewApp.innerHTML = `<div class="empty-state"><strong>Episode not found</strong><p>Open review from a needs-review episode in ManaIntel.</p></div>`;
    return;
  }
  try {
    const nonce = Date.now();
    const [summaryResponse, indexResponse] = await Promise.all([
      fetch(`archive/episodes/${episodeDir}/summary.json?v=${nonce}`),
      fetch(`archive/index.json?v=${nonce}`),
    ]);
    if (!summaryResponse.ok || !indexResponse.ok) throw new Error("Review data could not be loaded.");
    sourceSummary = await summaryResponse.json();
    const index = await indexResponse.json();
    reviewWorkflowUrl = index.metadata.review_workflow_url;
    if (!reviewWorkflowUrl) throw new Error("The review workflow is not configured.");
    if (sourceSummary.processing.status !== "needs_review") {
      throw new Error("This episode is not currently awaiting review.");
    }
    renderReview();
  } catch (problem) {
    reviewApp.innerHTML = `<div class="empty-state"><strong>Review could not be opened</strong><p>${escapeHtml(problem.message)}</p></div>`;
  }
}

loadReview();
