"use strict";

const REVIEW_SCHEMA_VERSION = "1.1.0";
const reviewApp = document.querySelector("#review-app");
const reviewTitle = document.querySelector("#review-title");
const reviewMeta = document.querySelector("#review-meta");
let sourceSummary = null;
let originalSummary = null;
let expectedReviewRevision = null;
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
  if (typeof value !== "string" || !value.trim()) return "#";
  try {
    const url = new URL(value, window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? escapeHtml(url.href) : "#";
  } catch { return "#"; }
}
function scryfallUrl(pick) {
  const resolution = pick.card_resolution;
  if (!["verified", "suggested"].includes(resolution?.status)) return null;
  if (resolution.scryfall_uri) return resolution.scryfall_uri;
  return resolution.oracle_id
    ? `https://scryfall.com/search?q=${encodeURIComponent(`oracleid:${resolution.oracle_id}`)}`
    : null;
}
function cardReferenceLink(pick, label, includeSuggested = false) {
  if (pick.card_resolution?.status === "suggested" && !includeSuggested) return escapeHtml(label);
  const url = scryfallUrl(pick);
  if (!url) return escapeHtml(label);
  return `<a class="card-reference-link" href="${safeUrl(url)}" target="_blank" rel="noreferrer" title="Open ${escapeHtml(label)} on Scryfall">${escapeHtml(label)}<span aria-hidden="true"> &nearr;</span></a>`;
}
function cardPreview(pick) {
  const resolution = pick.card_resolution;
  const imageUrl = resolution?.image_uri || resolution?.card_face_images?.[0]?.image_uri;
  const pageUrl = scryfallUrl(pick);
  if (!imageUrl || !pageUrl) return "";
  const name = resolution.canonical_name || pick.card;
  return `<a class="card-preview-link" href="${safeUrl(pageUrl)}" target="_blank" rel="noreferrer" aria-label="Open ${escapeHtml(name)} on Scryfall"><img class="card-preview" src="${safeUrl(imageUrl)}" alt="${escapeHtml(name)} card image" loading="lazy"></a>`;
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

function finishLabel(pick) {
  return pick.foil === true ? "Foil" : pick.foil === false ? "Nonfoil" : "Finish not stated";
}
function finishBadge(pick) {
  if (pick.foil !== true && pick.foil !== false) return "";
  return `<span class="finish ${pick.foil ? "foil" : "nonfoil"}">${finishLabel(pick)}</span>`;
}
function foilField(value) {
  const selected = value === true ? "true" : value === false ? "false" : "unknown";
  return `<label class="review-field"><span>Finish</span><select name="foil"><option value="unknown"${selected === "unknown" ? " selected" : ""}>Not stated</option><option value="true"${selected === "true" ? " selected" : ""}>Foil</option><option value="false"${selected === "false" ? " selected" : ""}>Nonfoil</option></select></label>`;
}

function targetEditor(name, label, value) {
  return `<fieldset class="review-target"><legend>${escapeHtml(label)}</legend>
    <p class="muted">Only an explicit target. Leave blank when the discussion merely mentions a price.</p>
    <button class="link-button" type="button" data-clear-target="${name}">Clear this target</button>
    <div class="review-fields">
      ${inputField("Source wording", `${name}_raw`, value?.raw || "", { wide: true })}
      ${inputField("Currency (if stated)", `${name}_currency`, value?.currency || "")}
      ${inputField("Minimum (if stated)", `${name}_minimum`, value?.minimum ?? "")}
      ${inputField("Maximum (if stated)", `${name}_maximum`, value?.maximum ?? "")}
    </div></fieldset>`;
}

function resolutionNote(pick) {
  const resolution = pick.card_resolution;
  if (resolution?.status === "verified" && resolution.canonical_name !== pick.card) {
    return `<p class="resolution-note verified">Catalog match: ${cardReferenceLink(pick, resolution.canonical_name)}</p>`;
  }
  if (resolution?.status === "suggested" && resolution.canonical_name) {
    return `<p class="resolution-note suggested">Possible match: ${cardReferenceLink(pick, resolution.canonical_name, true)} - choose Correct to apply</p>`;
  }
  return "";
}
function pickEditor(pick, index, isNew = false) {
  const editorId = isNew ? `new-${addedPickCounter++}` : pick.id;
  const hosts = (pick.hosts || []).join(", ");
  return `<article class="panel review-pick" data-review-pick="${escapeHtml(editorId)}" data-original-id="${escapeHtml(isNew ? "" : pick.id)}" data-new="${isNew}">
    <div class="panel-head">
      <div class="review-card-identity">
        ${cardPreview(pick)}
        <div>
          <p class="eyebrow">${isNew ? "Missing pick" : `Extracted pick ${index + 1}`}</p>
          <h2>${cardReferenceLink(pick, pick.card || "New pick")}</h2>
          ${resolutionNote(pick)}
          <p class="pick-meta"><span>${escapeHtml(pick.printing || "Printing not stated")}</span>${finishBadge(pick)}</p>
        </div>
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
      ${foilField(pick.foil)}
      ${inputField("Pick speaker(s), comma separated; blank if unknown", "hosts", hosts)}
      ${inputField("Start timestamp (HH:MM:SS)", "timestamp", secondsToTimestamp(pick.start_seconds), { required: true })}
      ${inputField("End timestamp (optional, HH:MM:SS)", "end_timestamp", secondsToTimestamp(pick.end_seconds))}
      ${inputField("Recommendation", "recommendation", pick.recommendation || "", { required: true, wide: true, multiline: true })}
      ${inputField("Evidence excerpt", "evidence_excerpt", pick.evidence_excerpt || "", { required: true, wide: true, multiline: true })}
      ${inputField("Mentioned price (context, not a target)", "mentioned_price", pick.mentioned_price || "")}
      ${inputField("Hold period (only if stated)", "hold", pick.hold || "")}
      ${targetEditor("entry_target", "Entry target", pick.entry_target)}
      ${targetEditor("exit_target", "Exit target", pick.exit_target)}
      ${inputField("Reasoning (one point per line)", "reasoning", (pick.reasoning || []).join("\n"), { wide: true, multiline: true })}
      ${inputField("Caveats (one point per line)", "caveats", (pick.caveats || []).join("\n"), { wide: true, multiline: true })}
    </div>
    ${isNew ? `<input type="hidden" name="action" value="add">` : ""}
  </article>`;
}

function renderReview() {
  const episode = sourceSummary.episode;
  const processing = sourceSummary.processing;
  reviewTitle.textContent = episode.title;
  reviewMeta.textContent = [
    episode.source_name || "Source not recorded",
    episode.episode_number ? `Episode ${episode.episode_number}` : null,
    formatDate(episode.published_at),
    `${sourceSummary.recommendations.length} extracted picks`,
  ].filter(Boolean).join(" · ");

  reviewApp.innerHTML = `
    <section class="panel review-overview">
      <div class="panel-head"><h2>Review context</h2><button class="link-button" type="button" data-listen-seconds="0" data-listen-label="Episode start">Listen from start</button></div>
      <div class="panel-body">
        <p>${escapeHtml(processing.review_reason || "Automated checks passed, but source accuracy has not been human verified. Review any questionable field against the audio.")}</p>
        <p class="muted">Check the source before approving. Unknown pick speakers stay blank; the show host list does not establish who made a recommendation.</p>
        ${expectedReviewRevision ? `<p class="review-saved">Saved corrections are loaded below and will be preserved, including picks left on Keep. The original extraction stays unchanged.</p>` : ""}
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
      <div class="panel-head"><h2>Review outcome</h2><span class="muted">Preview changes before copying</span></div>
      <div class="panel-body">
        <label class="review-field"><span>Choose an outcome</span><select name="decision">
          <option value="">Choose an outcome…</option>
          <option value="approve">Approve the whole episode</option>
          <option value="correct_without_approval">Limited correction — keep needs review</option>
        </select></label>
        <p class="muted">Whole-episode approval includes every kept, corrected and added pick. A limited correction can add a pick with unknown attribution, repair source-backed listening times or printing, or clear unsupported entry targets or speakers. It requires an evidence note and keeps the episode in review.</p>
        ${inputField("Evidence / review note (required for a limited correction)", "review-note", "", { wide: true, multiline: true })}
        <div class="latest-actions">
          <button class="button" id="prepare-review" type="button">Prepare review payload</button>
        </div>
        <div id="review-output" hidden>
          <section id="review-preview" aria-label="Prepared change preview"></section>
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
  const foil = field("foil");
  return {
    card: field("card"),
    printing: field("printing"),
    foil: foil === "true" ? true : foil === "false" ? false : null,
    hosts: field("hosts").split(",").map((host) => host.trim()).filter(Boolean),
    start_seconds: timestampToSeconds(field("timestamp")),
    end_seconds: field("end_timestamp") ? timestampToSeconds(field("end_timestamp")) : null,
    recommendation: field("recommendation"),
    evidence_excerpt: field("evidence_excerpt"),
    mentioned_price: field("mentioned_price") || null,
    hold: field("hold") || null,
    entry_target: readTarget(field, "entry_target"),
    exit_target: readTarget(field, "exit_target"),
    reasoning: field("reasoning").split("\n").map((line) => line.trim()).filter(Boolean),
    caveats: field("caveats").split("\n").map((line) => line.trim()).filter(Boolean),
  };
}

function readTarget(field, name) {
  const raw = field(`${name}_raw`), currency = field(`${name}_currency`);
  const minimum = field(`${name}_minimum`), maximum = field(`${name}_maximum`);
  if (![raw, currency, minimum, maximum].some(Boolean)) return null;
  if (!raw) throw new Error(`${name.replaceAll("_", " ")} needs source wording; clear all its fields to remove it.`);
  const number = (value) => {
    if (!value) return null;
    if (!/^(?:\d+(?:\.\d+)?|\.\d+)$/.test(value) || !Number.isFinite(Number(value))) {
      throw new Error("Target bounds must be non-negative numbers, without currency symbols.");
    }
    return Number(value);
  };
  const target = { raw, currency: currency || null, minimum: number(minimum), maximum: number(maximum) };
  if (target.minimum !== null && target.maximum !== null && target.minimum > target.maximum) {
    throw new Error("A target minimum cannot exceed its maximum.");
  }
  return target;
}

function validatePickValues(values) {
  if (!values.card) throw new Error("Every included pick needs a card name.");
  if (!values.recommendation) throw new Error(`${values.card} needs a recommendation.`);
  if (!values.evidence_excerpt) throw new Error(`${values.card} needs a short evidence excerpt.`);
  if (!Number.isInteger(values.start_seconds) || values.start_seconds < 0) throw new Error(`${values.card} needs a valid start timestamp.`);
  if (values.end_seconds !== null && values.end_seconds < values.start_seconds) throw new Error(`${values.card}: end must not precede start.`);
  const duration = sourceSummary.episode.duration_seconds;
  if (duration && (values.start_seconds > duration || values.end_seconds !== null && values.end_seconds > duration)) {
    throw new Error(`${values.card}: timestamp exceeds the source audio duration.`);
  }
}

function changedFields(original, values) {
  const changes = {};
  const originalValues = {
    card: original.card,
    printing: original.printing || "",
    foil: original.foil ?? null,
    hosts: original.hosts || [],
    start_seconds: original.start_seconds,
    end_seconds: original.end_seconds ?? null,
    recommendation: original.recommendation,
    evidence_excerpt: original.evidence_excerpt,
    mentioned_price: original.mentioned_price || null,
    hold: original.hold || null,
    entry_target: original.entry_target ?? null,
    exit_target: original.exit_target ?? null,
    reasoning: original.reasoning || [],
    caveats: original.caveats || [],
  };
  Object.entries(values).forEach(([key, value]) => {
    if (!sameValue(value, originalValues[key])) changes[key] = value;
  });
  return changes;
}

function sameValue(left, right) {
  if (left === right) return true;
  if (!left || !right || typeof left !== "object" || typeof right !== "object") return false;
  if (Array.isArray(left) !== Array.isArray(right)) return false;
  const keys = Object.keys(left);
  return keys.length === Object.keys(right).length && keys.every((key) => Object.hasOwn(right, key) && sameValue(left[key], right[key]));
}

function editableValues(pick) {
  return Object.fromEntries(["card", "printing", "foil", "hosts", "start_seconds", "end_seconds", "recommendation",
    "evidence_excerpt", "mentioned_price", "hold", "entry_target", "exit_target", "reasoning", "caveats"]
    .map((key) => [key, key === "printing" ? pick[key] || "" : pick[key] ?? (["hosts", "reasoning", "caveats"].includes(key) ? [] : null)]));
}

function validateOutcome(decision, operations, note) {
  if (!["approve", "correct_without_approval"].includes(decision)) throw new Error("Choose a review outcome before preparing the payload.");
  if (decision !== "correct_without_approval") return;
  if (!note) throw new Error("A limited correction requires an evidence note. Describe what you checked and what remains uncertain.");
  if (!operations.length) throw new Error("A limited correction needs at least one supported change.");
  for (const operation of operations) {
    if (operation.action === "add" && operation.pick && !(operation.pick.hosts || []).length) continue;
    if (operation.action !== "update" || Object.entries(operation.changes).some(([key, value]) =>
      !["printing", "entry_target", "hosts", "start_seconds", "end_seconds"].includes(key) || key === "entry_target" && value !== null || key === "hosts" && (!Array.isArray(value) || value.length))) {
      throw new Error("Limited corrections can add unattributed picks, repair listening times/printing, or clear unsupported entry targets or speakers. Other edits require whole-episode approval after source verification.");
    }
  }
}

function previewValue(value, field) {
  if (value === null || value === undefined || value === "" || Array.isArray(value) && !value.length) return field === "hosts" ? "Unknown speaker" : "Not stated";
  if (field === "foil") return value ? "Foil" : "Nonfoil";
  if (["start_seconds", "end_seconds"].includes(field)) return secondsToTimestamp(value);
  if (Array.isArray(value)) return value.join("\n");
  if (typeof value === "object") return `${value.raw} | Currency: ${value.currency || "not stated"} | Min: ${value.minimum ?? "not stated"} | Max: ${value.maximum ?? "not stated"}`;
  return String(value);
}

function renderChangePreview(payload) {
  const labels = { hosts: "Pick speaker(s)", foil: "Finish", start_seconds: "Start", end_seconds: "End",
    entry_target: "Entry target", exit_target: "Exit target", mentioned_price: "Mentioned price", evidence_excerpt: "Evidence" };
  const excluded = payload.operations.filter((op) => op.action === "exclude").length;
  const added = payload.operations.filter((op) => op.action === "add").length;
  const count = originalSummary.recommendations.length - excluded + added;
  const disposition = payload.decision === "approve"
    ? `Whole-episode approval: ${count} included picks will be marked human reviewed.`
    : "Limited correction: the episode stays needs review. No human approval is recorded.";
  return `<h3>Prepared changes · not applied</h3><p>${escapeHtml(disposition)}</p>
    <p class="muted">${count} included · ${excluded} excluded · ${added} added. Published value → prepared result. Previously saved corrections left on Keep are preserved.</p>
    ${plannedChanges(payload).length ? plannedChanges(payload).map((op) => {
      const original = sourceSummary.recommendations.find((pick) => pick.id === op.pick_id);
      const values = op.action === "add" ? op.pick : op.changes;
      return `<article class="review-change"><h4>${escapeHtml(op.action === "exclude" ? "Exclude" : op.action === "add" ? "Add" : "Correct")} · ${escapeHtml(original?.card || op.pick?.card)}</h4>
        ${op.action === "exclude" ? "<p>This pick will be excluded from the effective archive.</p>" : `<dl>${Object.entries(values).map(([key, value]) => `<div><dt>${escapeHtml(labels[key] || key.replaceAll("_", " "))}</dt><dd><span class="review-before">${escapeHtml(previewValue(original?.[key], key))}</span><span aria-hidden="true"> → </span><strong>${escapeHtml(previewValue(value, key))}</strong></dd></div>`).join("")}</dl>`}</article>`;
    }).join("") : "<p>No pick field changes. Published values are preserved; approval applies to all included picks.</p>"}
    ${payload.note ? `<p><strong>Review note:</strong> ${escapeHtml(payload.note)}</p>` : ""}`;
}

function plannedChanges(payload) {
  const changes = [];
  for (const original of originalSummary.recommendations) {
    const operation = payload.operations.find((op) => op.pick_id === original.id);
    if (operation?.action === "exclude") { changes.push(operation); continue; }
    const published = sourceSummary.recommendations.find((pick) => pick.id === original.id);
    const final = { ...original, ...operation?.changes };
    const fields = changedFields(published, editableValues(final));
    if (Object.keys(fields).length) changes.push({ action: "update", pick_id: original.id, changes: fields });
  }
  changes.push(...payload.operations.filter((op) => op.action === "add"));
  return changes;
}

function invalidatePayload() {
  document.querySelector("#review-output").hidden = true;
  document.querySelector("#review-payload").value = "";
  document.querySelector("#review-preview").innerHTML = "";
}

function preparePayload() {
  invalidatePayload();
  const error = document.querySelector("#review-error");
  error.hidden = true;
  try {
    const operations = [];
    document.querySelectorAll(".review-pick[data-new='false']").forEach((editor) => {
      const action = editor.querySelector('[name="action"]').value;
      const pickId = editor.dataset.originalId;
      if (action === "exclude") {
        operations.push({ action: "exclude", pick_id: pickId });
      } else {
        const published = sourceSummary.recommendations.find((pick) => pick.id === pickId);
        const values = action === "update" ? readPickValues(editor) : editableValues(published);
        validatePickValues(values);
        const original = originalSummary.recommendations.find((pick) => pick.id === pickId);
        const changes = changedFields(original, values);
        if (action === "update" && sameValue(values, editableValues(published))) throw new Error(`${original.card} is marked Correct but has no new changes.`);
        if (Object.keys(changes).length) operations.push({ action: "update", pick_id: pickId, changes });
      }
    });
    document.querySelectorAll(".review-pick[data-new='true']").forEach((editor) => {
      const values = readPickValues(editor);
      validatePickValues(values);
      operations.push({ action: "add", pick: values });
    });
    const decision = document.querySelector('[name="decision"]').value;
    const note = document.querySelector('[name="review-note"]').value.trim() || null;
    validateOutcome(decision, operations, note);
    const payload = {
      schema_version: REVIEW_SCHEMA_VERSION,
      source_id: sourceSummary.episode.source_id || "mtg-fast-finance",
      episode_guid: sourceSummary.episode.guid,
      expected: {
        processed_at: originalSummary.processing.processed_at,
        pick_ids: originalSummary.recommendations.map((pick) => pick.id),
      },
      expected_review_revision: expectedReviewRevision,
      decision,
      note,
      operations,
    };
    document.querySelector("#review-payload").value = JSON.stringify(payload);
    document.querySelector("#review-preview").innerHTML = renderChangePreview(payload);
    document.querySelector("#review-output").hidden = false;
    document.querySelector("#review-output").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (problem) {
    error.textContent = problem.message;
    error.hidden = false;
  }
}

function bindReviewEvents() {
  document.querySelector("#review-app").addEventListener("click", (event) => {
    const clearTarget = event.target.closest("[data-clear-target]");
    if (clearTarget) {
      clearTarget.closest("fieldset").querySelectorAll("input").forEach((input) => { input.value = ""; });
      invalidatePayload();
      return;
    }
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
      foil: null,
      hosts: [],
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
    ManaUI.copyText(button, document.querySelector("#review-payload").value, "Payload copied", document.querySelector("#review-payload"));
  });
  // A prepared payload must never silently represent an earlier form state.
  reviewApp.addEventListener("input", (event) => { if (!event.target.closest("#review-output")) invalidatePayload(); });
  reviewApp.addEventListener("change", (event) => { if (!event.target.closest("#review-output")) invalidatePayload(); });
  reviewApp.addEventListener("click", (event) => {
    if (event.target.closest("#add-pick, [data-remove-added]")) invalidatePayload();
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
    const [summaryResponse, indexResponse, resolutionsResponse] = await Promise.all([
      fetch(`archive/episodes/${episodeDir}/summary.json?v=${nonce}`),
      fetch(`archive/index.json?v=${nonce}`),
      fetch(`archive/resolutions.json?v=${nonce}`).catch(() => ({ ok: false })),
    ]);
    if (!summaryResponse.ok || !indexResponse.ok) throw new Error("Review data could not be loaded.");
    originalSummary = await summaryResponse.json();
    const index = await indexResponse.json();
    const episode = index.episodes.find((item) => item.guid === originalSummary.episode.guid);
    if (!episode || !["complete", "needs_review"].includes(episode.processing_status) || episode.human_reviewed) {
      throw new Error("Open a published machine extraction that has not already been human reviewed.");
    }
    expectedReviewRevision = episode.review_revision ?? null;
    sourceSummary = JSON.parse(JSON.stringify(originalSummary));
    if (expectedReviewRevision) {
      const effectiveResponse = await fetch(`archive/episodes/${episodeDir}/effective.json?v=${nonce}`);
      if (!effectiveResponse.ok) throw new Error("Saved corrections could not be loaded. Reload before preparing a review.");
      sourceSummary = await effectiveResponse.json();
      if (sourceSummary.episode.guid !== originalSummary.episode.guid || sourceSummary.processing.review_revision !== expectedReviewRevision) {
        throw new Error("Saved corrections changed while loading. Reload before preparing a review.");
      }
    } else if (episode.outputs?.effective_summary_json) {
      throw new Error("Saved corrections need a newer archive snapshot. Reload after the deployment completes.");
    }
    if (resolutionsResponse.ok) {
      const resolutionMap = (await resolutionsResponse.json()).resolutions || {};
      sourceSummary.recommendations = (sourceSummary.recommendations || []).map((pick) => {
        const resolution = resolutionMap[pick.id];
        return resolution?.raw_name === pick.card ? { ...pick, card_resolution: resolution } : pick;
      });
    }
    reviewWorkflowUrl = index.metadata.review_workflow_url;
    if (!reviewWorkflowUrl) throw new Error("The review workflow is not configured.");
    if (!["complete", "needs_review"].includes(sourceSummary.processing.status) || sourceSummary.processing.human_review) {
      throw new Error("Open a published machine extraction that has not already been human reviewed.");
    }
    renderReview();
  } catch (problem) {
    reviewApp.innerHTML = `<div class="empty-state"><strong>Review could not be opened</strong><p>${escapeHtml(problem.message)}</p></div>`;
  }
}

loadReview();
