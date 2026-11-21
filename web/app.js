"use strict";

const state = {
  index: null, cards: [], route: "dashboard", query: "", status: "all",
  episodeSource: "all", pickSource: "all",
  reviewIssue: "all",
  episodeSort: { key: "processed_at", direction: "desc" },
  pickSort: { key: "published_at", direction: "desc" },
};
const app = document.querySelector("#app");
const pageTitle = document.querySelector("#page-title");
const dialog = document.querySelector("#pick-dialog");
const dialogContent = document.querySelector("#dialog-content");
const dialogClose = document.querySelector(".dialog-close");
const dialogState = {
  view: null,
  episodeGuid: null,
  episodeScrollTop: 0,
  pickId: null,
};

const routes = {
  dashboard: { title: "Dashboard", render: renderDashboard },
  episodes: { title: "Episode Archive", render: renderEpisodes },
  picks: { title: "All Picks", render: renderPicks },
  review: { title: "Review Queue", render: renderReviewQueue },
  status: { title: "Processing Status", render: renderStatus },
  about: { title: "About ManaIntel", render: renderAbout },
};

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

function formatDate(value, long = false) {
  if (!value) return "Unknown date";
  return new Intl.DateTimeFormat("en-US", long
    ? { month: "long", day: "numeric", year: "numeric" }
    : { month: "short", day: "numeric", year: "numeric" }
  ).format(new Date(value));
}
function rawSafeUrl(value) {
  if (typeof value !== "string" || !value.trim()) return "#";
  try {
    const url = new URL(value, window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch { return "#"; }
}

function formatDateTime(value) {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
  }).format(new Date(value));
}

function isSuccessfulEpisode(episode) {
  return ["complete", "needs_review"].includes(episode?.processing_status);
}

function isRecentlyAdded(episode) {
  if (!isSuccessfulEpisode(episode)) return false;
  const timestamp = Date.parse(episode?.processed_at || "");
  const age = Date.now() - timestamp;
  return Number.isFinite(timestamp) && age >= 0 && age <= 72 * 60 * 60 * 1000;
}

function recentBadge(episode) {
  return isRecentlyAdded(episode) ? `<span class="recent-badge" title="Added within the last 72 hours">New</span>` : "";
}

function activityLabel(episode) {
  return isSuccessfulEpisode(episode) ? "Added" : "Attempted";
}

function activityDate(episode) {
  return `<span class="muted">${activityLabel(episode)}</span><br>${formatDate(episode.processed_at)} ${recentBadge(episode)}`;
}

function sortRows(rows, sort, accessors) {
  const accessor = accessors[sort.key];
  if (!accessor) return [...rows];
  const direction = sort.direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    const a = accessor(left);
    const b = accessor(right);
    if (a === null || a === undefined || a === "") return b === null || b === undefined || b === "" ? 0 : 1;
    if (b === null || b === undefined || b === "") return -1;
    if (typeof a === "number" && typeof b === "number") return (a - b) * direction;
    return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" }) * direction;
  });
}

function toggleSort(name, key) {
  const current = state[name];
  state[name] = current.key === key
    ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
    : { key, direction: ["published_at", "processed_at", "pick_count", "episode_number"].includes(key) ? "desc" : "asc" };
}

function episodeSortHeader(labelText, key) {
  const active = state.episodeSort.key === key;
  const direction = active ? state.episodeSort.direction : null;
  const ariaSort = direction ? ` aria-sort="${direction === "asc" ? "ascending" : "descending"}"` : "";
  return `<th${ariaSort}><button class="table-sort" type="button" data-episode-sort="${escapeHtml(key)}">${escapeHtml(labelText)}<span aria-hidden="true">${active ? (direction === "asc" ? "▲" : "▼") : ""}</span></button></th>`;
}

const episodeSortAccessors = {
  episode_number: (episode) => Number(episode.episode_number || 0),
  published_at: (episode) => Date.parse(episode.published_at || "") || 0,
  processed_at: (episode) => Date.parse(episode.processed_at || "") || 0,
  title: (episode) => `${sourceName(episode)} ${episode.title}`,
  processing_status: (episode) => episode.processing_status,
  pick_count: (episode) => Number(episode.pick_count || 0),
  review_state: (episode) => episode.review_state,
};

function display(value, fallback = "Not stated") {
  return value === null || value === undefined || value === "" ? fallback : escapeHtml(value);
}

function target(value) { return value ? escapeHtml(value.raw) : "Not stated"; }
function sourceName(item) { return item?.source_name || item?.episode?.source_name || "Source not recorded"; }
function sourceId(item) {
  const explicit = item?.source_id || item?.episode?.source_id;
  if (explicit) return explicit;
  const name = sourceName(item);
  if (name === "MTG Fast Finance") return "mtg-fast-finance";
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}
function sourceAbbreviation(item) {
  return { "mtg-fast-finance": "FF", "brainstorm-brewery": "BB" }[sourceId(item)] || "Unknown";
}
function sourceFilterOptions(items, selected) {
  const sources = new Map();
  items.forEach((item) => {
    const id = sourceId(item);
    const current = sources.get(id) || { name: sourceName(item), count: 0 };
    current.count += 1;
    sources.set(id, current);
  });
  return [...sources.entries()]
    .sort((left, right) => left[1].name.localeCompare(right[1].name))
    .map(([id, source]) => `<option value="${escapeHtml(id)}" ${selected === id ? "selected" : ""}>${escapeHtml(source.name)} (${source.count})</option>`)
    .join("");
}
function label(value) { return value === "approved" ? "machine checked" : String(value ?? "unknown").replaceAll("_", " "); }
function pickReviewBadge(pick) { return pick.human_reviewed ? badge("human_reviewed") : badge(pick.review_status); }

function episodeReviewLabel(episode) {
  if (episode.human_reviewed) return "human reviewed";
  return episode.review_state === "not_applicable" ? "Not extracted" : label(episode.review_state);
}
function badge(value, kind = "status") { return `<span class="${kind} ${escapeHtml(value ?? "unknown")}">${escapeHtml(label(value))}</span>`; }
function episodeSummaryUrl(episode) { return `summary.html?episode=${encodeURIComponent(episode.directory.replace(/^episodes\//, ""))}`; }
function episodeReviewUrl(episode) { return `review.html?episode=${encodeURIComponent(episode.directory.replace(/^episodes\//, ""))}`; }
function pickSummaryUrl(pick, review = false) {
  const episode = state.index?.episodes?.find((item) => item.guid === pick.episode.guid);
  if (!episode) return rawSafeUrl(pick.listen_url || pick.episode.audio_url);
  const params = new URLSearchParams({ episode: episode.directory.replace(/^episodes\//, "") });
  if (typeof pick.start_seconds === "number") params.set("t", Math.floor(pick.start_seconds));
  if (pick.id) params.set("pick", pick.id);
  return `${review ? "review" : "summary"}.html?${params}`;
}
function canOpenSummary(episode) { return Boolean(episode?.outputs?.summary_markdown); }
function episodeListenUrl(episode) {
  if (!canOpenSummary(episode)) return rawSafeUrl(episode.audio_url);
  const firstPick = state.cards
    .filter((pick) => pick.episode.guid === episode.guid && typeof pick.start_seconds === "number")
    .sort((left, right) => left.start_seconds - right.start_seconds)[0];
  return firstPick ? pickSummaryUrl(firstPick) : episodeSummaryUrl(episode);
}
function episodeListenLabel(episode) { return canOpenSummary(episode) ? "Listen to recommendations" : "Listen to episode"; }
function sentenceList(items, empty = "Not stated") {
  return items?.length ? items.map((item) => `<li>${escapeHtml(item)}</li>`).join("") : `<li>${escapeHtml(empty)}</li>`;
}
function finishLabel(pick) {
  return pick.foil === true ? "Foil" : pick.foil === false ? "Nonfoil" : null;
}
function finishBadge(pick) {
  const finish = finishLabel(pick);
  return finish ? `<span class="finish ${pick.foil ? "foil" : "nonfoil"}">${finish}</span>` : "";
}
function versionDisplay(pick, fallback = "Printing not stated") {
  return `<span class="version-display"><span>${escapeHtml(pick.printing || fallback)}</span>${finishBadge(pick)}</span>`;
}
function pickMeta(pick) {
  return [
    versionDisplay(pick),
    escapeHtml(pick.printing_certainty ? `${label(pick.printing_certainty)} printing` : "printing certainty unknown"),
    escapeHtml(pick.hosts?.length ? pick.hosts.join(", ") : "host attribution unavailable"),
  ].join(" · ");
}
function cardName(pick) {
  return pick.card_resolution?.status === "verified" && pick.resolved_card
    ? pick.resolved_card
    : pick.card;
}
function scryfallUrl(pick, allowSearch = false) {
  const resolution = pick.card_resolution;
  if (["verified", "suggested"].includes(resolution?.status)) {
    if (resolution.scryfall_uri) return rawSafeUrl(resolution.scryfall_uri);
    if (resolution.oracle_id) {
      return `https://scryfall.com/search?q=${encodeURIComponent(`oracleid:${resolution.oracle_id}`)}`;
    }
  }
  return allowSearch
    ? `https://scryfall.com/search?q=${encodeURIComponent(`!"${cardName(pick)}"`)}`
    : null;
}
function cardImageUrl(pick) {
  const resolution = pick.card_resolution;
  return resolution?.image_uri || resolution?.card_face_images?.[0]?.image_uri || null;
}
function cardReferenceLink(pick, { allowSearch = false, includeSuggested = false, label: linkLabel = cardName(pick) } = {}) {
  const suggested = pick.card_resolution?.status === "suggested";
  const url = suggested && !includeSuggested
    ? (allowSearch ? `https://scryfall.com/search?q=${encodeURIComponent(`!"${cardName(pick)}"`)}` : null)
    : scryfallUrl(pick, allowSearch);
  if (!url) return escapeHtml(linkLabel);
  return `<a class="card-reference-link" href="${safeUrl(url)}" target="_blank" rel="noreferrer" title="Open ${escapeHtml(linkLabel)} on Scryfall">${escapeHtml(linkLabel)}<span aria-hidden="true"> &nearr;</span></a>`;
}
function cardPreview(pick) {
  const imageUrl = cardImageUrl(pick);
  const pageUrl = scryfallUrl(pick, true);
  if (!imageUrl || !pageUrl) return "";
  return `<a class="card-preview-link" href="${safeUrl(pageUrl)}" target="_blank" rel="noreferrer" aria-label="Open ${escapeHtml(cardName(pick))} on Scryfall"><img class="card-preview" src="${safeUrl(imageUrl)}" alt="${escapeHtml(cardName(pick))} card image" loading="lazy"></a>`;
}
function cardResolutionNote(pick) {
  const resolution = pick.card_resolution;
  if (resolution?.status === "verified" && cardName(pick) !== pick.card) {
    return `<p class="resolution-note verified">Transcribed as &quot;${escapeHtml(pick.card)}&quot;</p>`;
  }
  if (resolution?.status === "suggested" && resolution.canonical_name) {
    return `<p class="resolution-note suggested">Possible match: ${cardReferenceLink(pick, { includeSuggested: true, label: resolution.canonical_name })} - review required</p>`;
  }
  return "";
}
function pickCard(pick, compact = false) {
  return `<article class="pick-card ${compact ? "compact" : ""}" data-pick-id="${escapeHtml(pick.id)}" role="button" tabindex="0">
    <div class="pick-card-head">
      <div>
        <p class="eyebrow">${escapeHtml(sourceName(pick))} · Episode ${escapeHtml(pick.episode.episode_number || "?")} · ${display(pick.timestamp)}</p>
        <h3>${escapeHtml(cardName(pick))}</h3>
        ${cardResolutionNote(pick)}
        <p class="pick-meta">${pickMeta(pick)}</p>
      </div>
      <div class="pick-badges">
        ${pick.confidence ? badge(pick.confidence, "confidence") : ""}
        ${pickReviewBadge(pick)}
      </div>
    </div>
    <p class="recommendation-copy">${escapeHtml(pick.recommendation)}</p>
    <div class="target-strip">
      <div><small>Entry</small><strong>${target(pick.entry_target)}</strong></div>
      <div><small>Hold</small><strong>${display(pick.hold)}</strong></div>
      <div><small>Exit</small><strong>${target(pick.exit_target)}</strong></div>
    </div>
    ${compact ? "" : `<div class="evidence-preview">${escapeHtml(pick.evidence_excerpt || "No evidence excerpt recorded.")}</div>`}
  </article>`;
}
function deferredStatus(error) {
  if (error?.category === "capacity_deferred") return "waiting for capacity";
  if (error?.category === "repair_progress_saved") return "paused — progress saved";
  if (error?.category === "transient_provider") return "temporary provider outage";
  return null;
}
function episodeBadge(episode) {
  const deferred = deferredStatus(episode?.error);
  return episode?.processing_status === "failed" && deferred
    ? `<span class="status queued">${deferred}</span>`
    : badge(episode?.processing_status);
}
function failureReason(error) {
  if (error?.category === "repair_progress_saved") return "Transcript repair progress was saved. No repair job is running from this status alone.";
  if (error?.category === "capacity_deferred") {
    return /provider limit observed/i.test(error.message || "")
      ? "Processing paused after the AI provider refused further requests. Recovery waits for provider capacity and the retry cooldown."
      : "Processing paused because the configured request budget cannot cover the next work. Recovery waits for available capacity.";
  }
  if (error?.category === "transient_provider") return "The AI provider was temporarily unavailable or rate limited. A later attempt can reuse saved transcription progress.";
  const message = String(error?.message ?? "");
  if (!message) return "No failure message was recorded.";
  const lower = message.toLowerCase();
  if (lower.includes("resource_exhausted") || lower.includes("quota")) return "Gemini quota or rate limit was reached.";
  if (lower.includes("not_found") && lower.includes("model")) return "Gemini model was unavailable for this API key.";
  if (lower.includes("api key") || lower.includes("unauthenticated") || lower.includes("permission_denied")) return "The AI provider key was missing, invalid, or unauthorized.";
  if (lower.includes("maximum size")) return "Audio exceeded the configured maximum size.";
  if (lower.includes("response_schema") || lower.includes("response_json_schema")) return "The AI provider rejected the structured JSON schema.";
  return escapeHtml(message.length > 220 ? `${message.slice(0, 220)}…` : message);
}
function recoveryAction(error, now = Date.now()) {
  if (!error) return "";
  const attempt = Number(error.attempt);
  const maximum = Number(error.max_attempts);
  const remaining = Number.isInteger(attempt) && Number.isInteger(maximum) && attempt >= 0 && maximum > attempt
    ? `${maximum - attempt} automatic ${maximum - attempt === 1 ? "attempt remains" : "attempts remain"}. ` : "";
  if (error.recovery_mode === "periodic_provider" && error.retryable === true && !error.quarantined) {
    const eligible = Date.parse(error.next_retry_at);
    if (!Number.isFinite(eligible)) return "Provider recovery timing is not recorded; inspect the workflow.";
    return `Periodic provider recovery: ${attempt} lifetime attempts retained. Eligible ${eligible > now ? "after" : "since"} ${formatDateTime(error.next_retry_at)}; ${error.recovery_interval_hours === 168 ? "weekly" : "48-hour"} backoff. A scheduled retry run may select this episode, subject to new-release priority and shared capacity. Eligibility does not mean a job is queued or running.`;
  }
  if (maximum > 0 && attempt >= maximum) {
    return "Automatic retry limit reached. Inspect retained evidence before a manual recovery; saved progress is preserved.";
  }
  if (error.quarantined || error.retryable !== true || error.category === "manual_intervention") {
    return "Manual intervention required. Inspect the failure and retained evidence before an exact-episode recovery.";
  }
  const eligible = Date.parse(error.next_retry_at);
  if (!Number.isFinite(eligible)) {
    return "Retry timing is not recorded. Check the workflow and recovery settings before retrying.";
  }
  if (eligible > now) {
    return `${remaining}Eligible after ${formatDateTime(error.next_retry_at)} (cooldown). A later scheduled run may select this episode, subject to capacity and priority.`;
  }
  return `${remaining}Eligible since ${formatDateTime(error.next_retry_at)} for a later scheduled run, subject to capacity and priority. Eligibility does not mean a job is queued or running.`;
}

function episodeAction(episode) {
  if (!episode) return "";
  return canOpenSummary(episode)
    ? `<a class="button secondary" href="${episodeSummaryUrl(episode)}" target="_blank">Open summary</a>`
    : `<button class="button secondary" type="button" data-episode-guid="${escapeHtml(episode.guid)}">View processing details</button>`;
}

async function loadData() {
  const refresh = document.querySelector("#refresh-button");
  refresh.disabled = true;
  refresh.textContent = "Refreshing…";
  app.innerHTML = `<div class="loading"><span></span> Loading archive…</div>`;
  try {
    const nonce = Date.now();
    const [indexResponse, cardsResponse] = await Promise.all([
      fetch(`archive/index.json?v=${nonce}`),
      fetch(`archive/cards.json?v=${nonce}`),
    ]);
    if (!indexResponse.ok || !cardsResponse.ok) throw new Error("Generated archive files were not found.");
    state.index = await indexResponse.json();
    const cardsPayload = await cardsResponse.json();
    state.cards = cardsPayload.cards;
    const updated = state.index.metadata.generated_at ? formatDate(state.index.metadata.generated_at, true) : "pending";
    document.querySelector("#side-version").textContent = `Updated ${updated}`;
    document.querySelector("#mode-pill").textContent = state.index.synthetic ? "Fixture mode" : "Automated archive";
    const banner = document.querySelector("#data-banner");
    banner.hidden = !state.index.synthetic;
    banner.textContent = state.index.synthetic ? state.index.notice : "";
    setRoute();
  } catch (error) {
    app.innerHTML = `<div class="empty-state"><strong>Published archive could not be loaded</strong><p>The automated pipeline may be updating or may need attention.</p></div>`;
  } finally {
    refresh.disabled = false;
    refresh.textContent = "Refresh";
  }
}

function setRoute() {
  const [requested = "dashboard", search = ""] = window.location.hash.slice(1).split("?");
  const params = new URLSearchParams(search);
  state.route = routes[requested] ? requested : "dashboard";
  state.query = params.get("q") || "";
  state.status = params.get("status") || "all";
  state.reviewIssue = params.get("issue") || "all";
  // Each destination starts with the source requested by its URL.
  state.episodeSource = params.get("source") || "all";
  state.pickSource = params.get("source") || "all";
  renderRoute();
  const pickId = params.get("pick");
  if (pickId && state.index) showPick(pickId);
}

function renderRoute() {
  if (!state.index) return;
  const route = routes[state.route];
  pageTitle.textContent = route.title;
  document.querySelectorAll("nav a").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === state.route);
    if (link.dataset.route === state.route) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  app.innerHTML = route.render();
  bindPageEvents();
}

function renderEpisodes() {
  return `
    <div class="toolbar"><label class="search"><input id="episode-search" type="search" aria-label="Search episodes" placeholder="Search episode title, number, host…" value="${escapeHtml(state.query)}"></label><select id="episode-source" aria-label="Filter by source"><option value="all">All sources</option>${sourceFilterOptions(state.index.episodes, state.episodeSource)}</select><select id="episode-status" aria-label="Filter by status"><option value="all">All statuses</option>${["complete", "needs_review", "failed"].map((value) => `<option value="${value}" ${state.status === value ? "selected" : ""}>${value === "failed" ? "unfinished" : label(value)}</option>`).join("")}</select></div>
    <div class="browse-summary"><span id="browse-count" role="status"></span><button class="link-button" type="button" data-reset-filters>Reset filters</button><span class="table-hint">Scroll the table sideways for more details.</span></div>
    <div class="table-wrap"><table><thead><tr>${episodeSortHeader("Episode", "episode_number")}${episodeSortHeader("Published", "published_at")}${episodeSortHeader("Activity", "processed_at")}${episodeSortHeader("Podcast / title", "title")}${episodeSortHeader("Status", "processing_status")}${episodeSortHeader("Picks", "pick_count")}${episodeSortHeader("Review", "review_state")}<th>Listen</th><th>Open</th></tr></thead><tbody id="episode-rows">${episodeRows()}</tbody></table></div>`;
}

function episodeRows() {
  const query = state.query.toLowerCase();
  const episodes = sortRows(state.index.episodes.filter((episode) => {
    const haystack = `${sourceName(episode)} ${episode.episode_number} ${episode.title} ${episode.hosts.join(" ")}`.toLowerCase();
    return haystack.includes(query)
      && (state.episodeSource === "all" || sourceId(episode) === state.episodeSource)
      && (state.status === "all" || episode.processing_status === state.status);
  }), state.episodeSort, episodeSortAccessors);
  if (!episodes.length) return `<tr><td colspan="9">No matching episodes.</td></tr>`;
  return episodes.map((episode) => `<tr class="episode-row" data-episode-guid="${escapeHtml(episode.guid)}" role="button" tabindex="0"><td><strong>#${episode.episode_number || "?"}</strong></td><td>${formatDate(episode.published_at)}</td><td title="${escapeHtml(`${activityLabel(episode)} ${formatDateTime(episode.processed_at)}`)}">${activityDate(episode)}</td><td><span class="muted">${escapeHtml(sourceName(episode))}</span><br><strong>${escapeHtml(episode.title)}</strong><br><span class="muted">${escapeHtml(episode.hosts.join(", "))}</span></td><td>${episodeBadge(episode)}</td><td>${episode.pick_count}</td><td>${escapeHtml(episodeReviewLabel(episode))}</td><td><a class="link-button" href="${escapeHtml(episodeListenUrl(episode))}">Listen</a></td><td><button class="link-button" type="button" data-episode-guid="${escapeHtml(episode.guid)}">Details</button></td></tr>`).join("");
}

function renderPicks() {
  return `
    <div class="toolbar"><label class="search"><input id="pick-search" type="search" aria-label="Search picks" placeholder="Search card, printing, host, recommendation…" value="${escapeHtml(state.query)}"></label><select id="pick-source" aria-label="Filter by source"><option value="all">All sources</option>${sourceFilterOptions(state.cards, state.pickSource)}</select><select id="pick-status" aria-label="Filter by review status"><option value="all">All review states</option>${["approved", "pending", "needs_review"].map((value) => `<option value="${value}" ${state.status === value ? "selected" : ""}>${value === "failed" ? "unfinished" : label(value)}</option>`).join("")}</select></div>
    <div class="browse-summary"><span id="browse-count" role="status"></span><button class="link-button" type="button" data-reset-filters>Reset filters</button><span class="table-hint">Scroll the table sideways for more details.</span></div>
    <div id="pick-table" role="table" aria-label="Podcast recommendations"></div>`;
}

function filteredPicks() {
  const query = state.query.toLowerCase();
  const filtered = state.cards.filter((pick) => {
    const haystack = `${sourceName(pick)} ${pick.card} ${cardName(pick)} ${pick.card_resolution?.canonical_name ?? ""} ${pick.printing ?? ""} ${finishLabel(pick) ?? ""} ${pick.hosts.join(" ")} ${pick.recommendation} ${pick.episode.title}`.toLowerCase();
    return haystack.includes(query)
      && (state.pickSource === "all" || sourceId(pick) === state.pickSource)
      && (state.status === "all" || pick.review_status === state.status);
  });
  return sortRows(filtered, state.pickSort, {
    card: (pick) => cardName(pick),
    printing: (pick) => pick.printing || "",
    entry: (pick) => pick.entry_target?.minimum ?? pick.entry_target?.maximum,
    exit: (pick) => pick.exit_target?.minimum ?? pick.exit_target?.maximum,
    hold: (pick) => pick.hold || "",
    episode_number: (pick) => Number(pick.episode.episode_number || 0),
    published_at: (pick) => Date.parse(pick.episode.published_at || "") || 0,
    review_status: (pick) => pick.review_status,
  });
}

function renderPickTable() {
  const container = document.querySelector("#pick-table");
  if (!container) return;

  renderStandardTable(container, {
    tableClass: "ms-table--picks",
    rows: filteredPicks(),
    sort: state.pickSort,
    emptyText: "No matching picks. Try a different card, host, or review filter.",
    getRowId: (pick) => pick.id,
    getRowLabel: (pick) => `Open details for ${cardName(pick)}`,
    columns: [
      { label: "Card", sortKey: "card", type: "action", action: "details", value: (pick) => cardName(pick) },
      { label: "Version", sortKey: "printing", html: (pick) => versionDisplay(pick, "—"), title: (pick) => pick.printing_certainty ? `${label(pick.printing_certainty)} printing` : "Printing not stated" },
      { label: "Entry", sortKey: "entry", align: "money", value: (pick) => pick.entry_target?.raw || "—" },
      { label: "Exit", sortKey: "exit", align: "money", value: (pick) => pick.exit_target?.raw || "—" },
      { label: "Hold", sortKey: "hold", align: "center", value: (pick) => pick.hold || "—" },
      { label: "Episode", sortKey: "episode_number", align: "center", type: "action", action: "episode", value: (pick) => `${sourceAbbreviation(pick)} ${pick.episode.episode_number || "?"}`, title: (pick) => `${sourceName(pick)} · ${pick.episode.title}` },
      { label: "Published", sortKey: "published_at", align: "center", value: (pick) => formatDate(pick.episode.published_at) },
      { label: "Review", sortKey: "review_status", align: "center", html: (pick) => pickReviewBadge(pick) },
      { label: "Listen", align: "center", type: "anchor", href: (pick) => pickSummaryUrl(pick), value: (pick) => pick.timestamp || "Listen" },
      { label: "Details", align: "actions", type: "action", action: "details", value: () => "Details" },
    ],
    onRowClick: (pick) => showPick(pick.id),
    onAction: (action, pick) => { if (action === "details") showPick(pick.id); else if (action === "episode") showEpisode(pick.episode.guid); },
    onSort: (key) => { toggleSort("pickSort", key); renderPickTable(); },
  });
  updateBrowseCount();
}

function updateBrowseCount() {
  const count = document.querySelector("#browse-count");
  if (!count) return;
  count.textContent = state.route === "picks"
    ? `${filteredPicks().length} of ${state.cards.length} picks`
    : `${document.querySelectorAll("#episode-rows .episode-row").length} of ${state.index.episodes.length} episodes`;
}

function syncBrowseUrl() {
  const params = new URLSearchParams();
  if (state.query) params.set("q", state.query);
  if (state.status !== "all") params.set("status", state.status);
  if (state.route === "review" && state.reviewIssue !== "all") params.set("issue", state.reviewIssue);
  const source = state.route === "picks" ? state.pickSource : state.episodeSource;
  if (source !== "all") params.set("source", source);
  window.history.replaceState(null, "", `#${state.route}${params.size ? `?${params}` : ""}`);
  updateBrowseCount();
}

const reviewCategories = {
  coverage: { title: "Coverage & boundaries", action: "Check the full recommendation sections for missing picks and weak boundaries." },
  timing: { title: "Audio timing", action: "Check clocks against the audio; the linked timestamp may be inaccurate." },
  intent: { title: "Recommendation intent", action: "Listen for a direct endorsement, disagreement or a conditional recommendation." },
  scope: { title: "Recommendation scope", action: "Check whether this is an eligible Magic recommendation." },
  identity: { title: "Card identity", action: "Check the spoken card name against the source audio." },
  printing: { title: "Printing & price", action: "Check the version, finish and price context against the source." },
  unspecified: { title: "Other / unspecified", action: "Inspect the recorded reason and source before making a decision." },
};

function reviewQueue() {
  return state.index.episodes.filter((episode) => isSuccessfulEpisode(episode) && !episode.human_reviewed
    && episode.review_triage && canOpenSummary(episode))
    .sort((a, b) => a.review_triage.priority - b.review_triage.priority
      || (Date.parse(b.published_at) || 0) - (Date.parse(a.published_at) || 0)
      || a.guid.localeCompare(b.guid));
}

function filteredReviewQueue() {
  const query = state.query.toLowerCase();
  return reviewQueue().filter((episode) => (state.episodeSource === "all" || sourceId(episode) === state.episodeSource)
    && (state.reviewIssue === "all" || episode.review_triage.codes.includes(state.reviewIssue))
    && [episode.title, episode.episode_number, sourceName(episode), ...episode.review_triage.issues.flatMap((issue) => [issue.card, issue.reason])]
      .join(" ").toLowerCase().includes(query));
}

function reviewQueueCards() {
  const rows = filteredReviewQueue();
  if (!rows.length) return `<div class="empty-state"><strong>${reviewQueue().length ? "No matching reviews" : "No flagged episodes in the review queue"}</strong><p>Machine checked episodes have not been human verified. Unfinished episodes have separate <a href="#episodes?status=failed">recovery details</a>.</p></div>`;
  return rows.map((episode) => {
    const triage = episode.review_triage;
    const categories = triage.codes.map((code) => reviewCategories[code] || reviewCategories.unspecified);
    // Mixed categories remain visible; repeated prose is shown once per evidence path.
    const issues = [...new Map(triage.issues.map((issue) => [`${issue.path}\n${issue.reason}`, issue])).values()];
    return `<article class="panel review-queue-card"><div class="panel-body">
      <p class="eyebrow">${escapeHtml(sourceName(episode))} · Episode ${escapeHtml(episode.episode_number || "?")} · ${formatDate(episode.published_at)}</p>
      <h2>${escapeHtml(episode.title)}</h2>
      <div class="review-tags">${episodeBadge(episode)}${categories.map((category) => `<span class="status needs_review">${escapeHtml(category.title)}</span>`).join("")}</div>
      <p>${escapeHtml(categories[0].action)}</p>
      <p class="muted">${Number(episode.pick_count || 0)} published picks · ${triage.priority === 0 ? "Check coverage or timing first" : "Source check required"}${episode.review_revision ? " · Saved correction present" : ""}</p>
      <details><summary>Recorded reasons (${issues.length})</summary><ul class="review-reasons">${issues.map((issue) => {
        const params = new URLSearchParams({ episode: episode.directory.replace(/^episodes\//, "") });
        const timed = Number.isFinite(issue.start_seconds) && issue.start_seconds >= 0;
        if (timed) params.set("t", Math.floor(issue.start_seconds));
        if (issue.pick_id) params.set("pick", issue.pick_id);
        return `<li>${issue.card ? `<strong>${escapeHtml(issue.card)}:</strong> ` : ""}${escapeHtml(issue.reason)}${timed ? ` <a href="summary.html?${escapeHtml(params)}">Listen near flagged pick</a>` : ""}</li>`;
      }).join("")}</ul></details>
      <div class="latest-actions"><a class="button" href="${episodeReviewUrl(episode)}">Review episode</a><a class="button secondary" href="${escapeHtml(episodeListenUrl(episode))}">Listen to source</a><button class="link-button" type="button" data-episode-guid="${escapeHtml(episode.guid)}">Episode details</button></div>
    </div></article>`;
  }).join("");
}

function renderReviewQueue() {
  const queue = reviewQueue();
  return `<article class="panel"><div class="panel-body"><h2>Choose the next source check</h2><p>Coverage and timing first, then intent and scope, then identity and printing. Newest episodes first within each priority. These are navigation hints from recorded warnings, not verified source findings.</p><p>Includes needs-review episodes and machine checked output with retained warnings. Mixed reasons appear in every matching filter. Corrections without approval remain here; human-approved episodes are excluded. Nothing is approved or retried by opening this queue.</p></div></article>
    <div class="toolbar"><label class="search"><input id="review-search" type="search" aria-label="Search review queue" placeholder="Search episode, card or reason…" value="${escapeHtml(state.query)}"></label><select id="review-source" aria-label="Filter reviews by source"><option value="all">All sources (${queue.length})</option>${sourceFilterOptions(queue, state.episodeSource)}</select><select id="review-issue" aria-label="Filter by review issue"><option value="all">All issues</option>${Object.entries(reviewCategories).map(([code, category]) => `<option value="${code}" ${state.reviewIssue === code ? "selected" : ""}>${escapeHtml(category.title)} (${queue.filter((episode) => episode.review_triage.codes.includes(code)).length})</option>`).join("")}</select></div>
    <div class="browse-summary"><span id="review-count" role="status">${filteredReviewQueue().length} of ${queue.length} flagged episodes · category counts overlap</span><button class="link-button" type="button" data-reset-filters>Reset filters</button><a href="#episodes?status=failed">Unfinished episodes &amp; recovery</a></div>
    <section id="review-queue" class="review-queue" aria-label="Episodes needing source review">${reviewQueueCards()}</section>`;
}

function renderStatus() {
  const episodes = sortRows(state.index.episodes, { key: "processed_at", direction: "desc" }, episodeSortAccessors);
  return `<article class="panel"><div class="panel-head"><h2>Automated processing outcomes</h2><span class="muted">${state.index.episodes.length} episodes · newest activity first</span></div><div class="panel-body status-timeline">${episodes.map((episode) => `<div class="status-card"><span class="episode-no">${episode.episode_number || "—"}</span><div><strong>${escapeHtml(episode.title)} ${recentBadge(episode)}</strong><small>${escapeHtml(sourceName(episode))}</small><small>${episode.review_reason ? `${escapeHtml(episode.review_reason)} · ${episode.error ? "last attempt" : activityLabel(episode).toLowerCase()} ${formatDateTime(episode.processed_at)}` : `${episode.pick_count} structured picks · published ${formatDate(episode.published_at)} · ${episode.error ? "last attempt" : activityLabel(episode).toLowerCase()} ${formatDateTime(episode.processed_at)}`}</small>${episode.error ? `<small class="status-recovery">${failureReason(episode.error)}<br><strong>Next action:</strong> ${escapeHtml(recoveryAction(episode.error))}</small>` : ""}<div class="latest-actions"><button class="button secondary" type="button" data-episode-guid="${escapeHtml(episode.guid)}">View ${episode.error ? "recovery" : "episode"} details</button></div></div>${episodeBadge(episode)}</div>`).join("")}</div></article>`;
}

function renderAbout() {
  return `<section class="grid about-grid">
    <article class="panel prose"><div class="panel-body"><p class="eyebrow">Project</p><h2>Who recommended what, when, and why?</h2><p>Browse recorded recommendations from MTG Fast Finance and Brainstorm Brewery, compare a card’s history, and listen to the source discussion. Coverage is incomplete.</p><p><strong>Pipeline:</strong> ${escapeHtml(state.index.metadata.pipeline_version)}<br><strong>Schema:</strong> ${escapeHtml(state.index.schema_version)}<br><strong>Sources:</strong> MTG Fast Finance · Brainstorm Brewery</p></div></article>
    <article class="panel prose"><div class="panel-body"><p class="eyebrow">Trust rules</p><h2>Missing details stay unknown.</h2><ul><li>Unstated prices, printings and speakers are left blank.</li><li>Every recommendation requires evidence and a timestamp.</li><li>Machine checked means automated checks passed; it does not mean a person verified the audio.</li><li>Needs review records retain their uncertainty and remain available to inspect.</li></ul></div></article>
    <article class="panel prose"><div class="panel-body"><p class="eyebrow">Automation</p><h2>Daily unattended updates</h2><p>GitHub Actions discovers new episodes, validates generated records, commits durable state, and deploys this site.</p></div></article>
    <article class="panel prose"><div class="panel-body"><p class="eyebrow">Disclaimer</p><h2>Verify automated records.</h2><p>Transcription and extraction can be wrong. This archive faithfully attempts to capture host commentary, adds no original finance opinions, and is not financial advice.</p></div></article>
  </section>`;
}

function renderDashboard() {
  const { counts, latest_episode: latest, recent_picks: recent } = state.index;
  return `
    <section class="summary-strip" aria-label="Archive totals">
      ${metric("Episodes", counts.episodes, "recorded episodes", "#episodes")}
      ${metric("Picks", counts.picks, "recommendations", "#picks")}
      ${metric("Review queue", reviewQueue().length, "flagged episodes to check", "#review")}
      ${metric("Unfinished", counts.failed, "view recovery details", "#episodes?status=failed")}
      ${metric("Latest episode", latest?.episode_number ? `${sourceAbbreviation(latest)} #${latest.episode_number}` : "None", latest ? formatDate(latest.published_at) : "pending", "#episodes")}
    </section>
    <section class="dashboard-console">
      <article class="panel dashboard-main">
        <div class="panel-head"><h2>Recently added</h2><a href="#episodes">Open archive</a></div>
        <div class="table-wrap"><table><thead><tr>${episodeSortHeader("Ep", "episode_number")}${episodeSortHeader("Added", "processed_at")}${episodeSortHeader("Podcast / title", "title")}${episodeSortHeader("Status", "processing_status")}${episodeSortHeader("Picks", "pick_count")}${episodeSortHeader("Review", "review_state")}<th>Action</th></tr></thead><tbody>${dashboardEpisodeRows()}</tbody></table></div>
      </article>
      <aside class="dashboard-side">
        <article class="panel">
          <div class="panel-head"><h2>Latest</h2></div>
          <div class="panel-body latest compact">${latest ? `
            <div>${episodeBadge(latest)}</div>
            <div><p class="eyebrow">${escapeHtml(sourceName(latest))} · Episode ${latest.episode_number} - ${formatDate(latest.published_at)}</p><h3>${escapeHtml(latest.title)}</h3></div>
            <div class="latest-meta"><span>${latest.pick_count} picks</span><span>${escapeHtml(latest.hosts.join(" / "))}</span></div>
            ${latest.error ? `<div class="failure-note">${failureReason(latest.error)}</div>` : ""}
            <div class="latest-actions"><a class="button" href="${escapeHtml(episodeListenUrl(latest))}">${episodeListenLabel(latest)}</a>${episodeAction(latest)}</div>
          ` : `<div class="empty-state compact"><strong>No live episodes</strong><p>The first automated run is pending.</p></div>`}</div>
        </article>
        <article class="panel">
          <div class="panel-head"><h2>Recent picks</h2><a href="#picks">All picks</a></div>
          <div class="panel-body recommendation-list compact">
            ${recent.slice(0, 6).map((pick) => `<div class="recommendation-row" data-pick-id="${escapeHtml(pick.id)}" role="button" tabindex="0"><div><strong>${escapeHtml(cardName(pick))}</strong>${cardResolutionNote(pick)}<p>${escapeHtml(pick.recommendation)}</p></div><span class="muted">${escapeHtml(sourceAbbreviation(pick))} ${escapeHtml(pick.episode.episode_number || "?")}</span></div>`).join("")}
          </div>
        </article>
      </aside>
    </section>`;
}

function metric(name, value, note, href) {
  return `<a class="metric" href="${escapeHtml(href)}"><p>${escapeHtml(name)}</p><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></a>`;
}

function dashboardEpisodeRows() {
  const episodes = sortRows(state.index.episodes.filter(isSuccessfulEpisode), state.episodeSort, episodeSortAccessors).slice(0, 10);
  if (!episodes.length) return `<tr><td colspan="7">No episodes have been added yet.</td></tr>`;
  return episodes.map((episode) => `<tr class="episode-row" data-episode-guid="${escapeHtml(episode.guid)}" role="button" tabindex="0"><td><strong>#${episode.episode_number || "?"}</strong></td><td title="${escapeHtml(formatDateTime(episode.processed_at))}">${formatDate(episode.processed_at)} ${recentBadge(episode)}</td><td><span class="muted">${escapeHtml(sourceName(episode))}</span><br><strong>${escapeHtml(episode.title)}</strong></td><td>${episodeBadge(episode)}</td><td>${episode.pick_count}</td><td>${escapeHtml(episodeReviewLabel(episode))}</td><td><button class="link-button" type="button" data-episode-guid="${escapeHtml(episode.guid)}">Details</button></td></tr>`).join("");
}

function bindPageEvents() {
  bindPickButtons();
  bindEpisodeButtons();
  renderPickTable();
  const updateReviews = () => {
    document.querySelector("#review-queue").innerHTML = reviewQueueCards();
    document.querySelector("#review-count").textContent = `${filteredReviewQueue().length} of ${reviewQueue().length} flagged episodes · category counts overlap`;
    bindEpisodeButtons();
  };
  const reviewSearch = document.querySelector("#review-search");
  const reviewSource = document.querySelector("#review-source");
  const reviewIssue = document.querySelector("#review-issue");
  if (reviewSearch) reviewSearch.addEventListener("input", () => { state.query = reviewSearch.value; updateReviews(); });
  if (reviewSource) reviewSource.addEventListener("change", () => { state.episodeSource = reviewSource.value; updateReviews(); });
  if (reviewIssue) reviewIssue.addEventListener("change", () => { state.reviewIssue = reviewIssue.value; updateReviews(); });
  const episodeSearch = document.querySelector("#episode-search");
  const episodeSource = document.querySelector("#episode-source");
  const episodeStatus = document.querySelector("#episode-status");
  document.querySelectorAll("[data-episode-sort]").forEach((control) => {
    control.addEventListener("click", () => { toggleSort("episodeSort", control.dataset.episodeSort); renderRoute(); });
  });
  if (episodeSearch) episodeSearch.addEventListener("input", () => { state.query = episodeSearch.value; document.querySelector("#episode-rows").innerHTML = episodeRows(); bindEpisodeButtons(); });
  if (episodeSource) episodeSource.addEventListener("change", () => { state.episodeSource = episodeSource.value; document.querySelector("#episode-rows").innerHTML = episodeRows(); bindEpisodeButtons(); });
  if (episodeStatus) episodeStatus.addEventListener("change", () => { state.status = episodeStatus.value; document.querySelector("#episode-rows").innerHTML = episodeRows(); bindEpisodeButtons(); });
  const pickSearch = document.querySelector("#pick-search");
  const pickSource = document.querySelector("#pick-source");
  const pickStatus = document.querySelector("#pick-status");
  if (pickSearch) pickSearch.addEventListener("input", () => { state.query = pickSearch.value; renderPickTable(); });
  if (pickSource) pickSource.addEventListener("change", () => { state.pickSource = pickSource.value; renderPickTable(); });
  if (pickStatus) pickStatus.addEventListener("change", () => { state.status = pickStatus.value; renderPickTable(); });
  document.querySelectorAll(".toolbar input, .toolbar select").forEach((control) => {
    control.addEventListener(control.tagName === "INPUT" ? "input" : "change", syncBrowseUrl);
  });
  document.querySelector("[data-reset-filters]")?.addEventListener("click", () => {
    state.query = ""; state.status = "all"; state.episodeSource = "all"; state.pickSource = "all";
    state.reviewIssue = "all";
    syncBrowseUrl(); renderRoute();
    document.querySelector(".toolbar input")?.focus();
  });
  updateBrowseCount();
}

function bindPickButtons() {
  document.querySelectorAll("[data-pick-id]").forEach((element) => {
    const open = (event) => { if (!event?.target?.closest("a, button, input")) showPick(element.dataset.pickId); };
    element.addEventListener("click", open);
    element.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key) && event.target === element) { event.preventDefault(); open(event); } });
  });
}

function bindEpisodeButtons() {
  document.querySelectorAll("[data-episode-guid]").forEach((element) => {
    const open = (event) => {
      event?.stopPropagation();
      if (event?.target?.closest("a")) return;
      showEpisode(element.dataset.episodeGuid);
    };
    element.addEventListener("click", open);
    element.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key) && event.target === element && element.tagName !== "BUTTON") { event.preventDefault(); open(event); } });
  });
}

function openDialog() {
  if (!dialog.open) dialog.showModal();
}

function setDialogCloseAction(isBack) {
  const label = isBack ? "Back to episode picks" : "Close details";
  dialogClose.setAttribute("aria-label", label);
  dialogClose.title = label;
  dialogClose.textContent = isBack ? "←" : "×";
}

function verifiedIdentity(pick) {
  return pick.card_resolution?.status === "verified" ? pick.card_resolution.oracle_id || null : null;
}

function recordedHistory(pick) {
  const identity = verifiedIdentity(pick);
  // Raw spelling and fuzzy suggestions cannot establish a shared card identity.
  return (identity ? state.cards.filter((item) => verifiedIdentity(item) === identity) : [pick])
    .slice().sort((a, b) => (Date.parse(b.episode.published_at) || 0) - (Date.parse(a.episode.published_at) || 0)
      || (a.start_seconds ?? 0) - (b.start_seconds ?? 0) || String(a.id).localeCompare(String(b.id)));
}

function renderCardHistory(pick) {
  const history = recordedHistory(pick);
  const episodeCount = new Set(history.map((item) => item.episode.guid)).size;
  return `<section class="detail-section card-history" aria-label="Recorded card history"><h3>Pick history</h3>
    <p class="history-coverage">${verifiedIdentity(pick)
      ? `${history.length} recorded ${history.length === 1 ? "recommendation" : "recommendations"} across ${episodeCount} ${episodeCount === 1 ? "episode" : "episodes"}. Matched by verified card identity, newest first. Printing and finish may differ.`
      : "Card identity is unresolved. Only this recommendation is shown; possible matches stay separate."} This archive has incomplete coverage; this is not a complete history of either show.</p>
    <ol class="history-list">${history.map((item) => `<li class="history-item${item.id === pick.id ? " current" : ""}">
      <div class="history-heading"><strong>${escapeHtml(sourceName(item))} · ${escapeHtml(item.episode.episode_number || "?")}</strong><time>${escapeHtml(formatDate(item.episode.published_at))}</time></div>
      <p>${versionDisplay(item)} · ${escapeHtml(item.recommendation)}</p>
      <p class="muted">Speaker: ${escapeHtml(item.hosts?.length ? item.hosts.join(", ") : "not recorded")}</p>
      ${item.card !== cardName(item) ? `<p class="muted">Transcribed as ${escapeHtml(item.card)}</p>` : ""}
      <p>${escapeHtml(item.reasoning?.join(" ") || "No reasoning recorded.")}</p>
      <dl class="history-prices"><div><dt>Mentioned price</dt><dd>${display(item.mentioned_price)}</dd></div><div><dt>Entry target</dt><dd>${target(item.entry_target)}</dd></div></dl>
      <div class="latest-actions">${pickReviewBadge(item)}${item.id === pick.id ? `<span class="muted">Selected pick</span>` : `<button class="link-button" type="button" data-history-pick="${escapeHtml(item.id)}">View this pick</button>`}<a class="link-button" href="${escapeHtml(pickSummaryUrl(item))}">Listen${item.timestamp ? ` at ${escapeHtml(item.timestamp)}` : " to episode"}</a></div>
    </li>`).join("")}</ol></section>`;
}

function showPick(id, { fromEpisode = false } = {}) {
  const pick = state.cards.find((item) => item.id === id);
  if (!pick) return;
  if (fromEpisode && dialogState.view === "episode" && dialogState.episodeGuid === pick.episode.guid) {
    dialogState.episodeScrollTop = dialog.scrollTop;
  } else {
    dialogState.episodeGuid = null;
    dialogState.episodeScrollTop = 0;
  }
  dialogState.view = "pick";
  dialogState.pickId = pick.id;
  dialogContent.innerHTML = `<div class="dialog-content pick-detail"><p class="eyebrow">${escapeHtml(sourceName(pick))} · Episode ${escapeHtml(pick.episode.episode_number || "?")} · ${formatDate(pick.episode.published_at, true)}</p><h2 id="dialog-card">${escapeHtml(cardName(pick))}</h2><div class="dialog-sub">${pickMeta(pick)}</div><div class="detail-grid"><div class="detail-box"><small>Entry target</small><strong>${target(pick.entry_target)}</strong></div><div class="detail-box"><small>Hold</small><strong>${display(pick.hold)}</strong></div><div class="detail-box"><small>Exit target</small><strong>${target(pick.exit_target)}</strong></div></div><p class="mentioned-price">Mentioned price: ${display(pick.mentioned_price)} · A mentioned price is not automatically an entry target.</p><div class="recommendation-callout"><small>Recommendation</small><p>${escapeHtml(pick.recommendation)}</p></div><div class="detail-section"><h3>Why it was mentioned</h3><ul>${sentenceList(pick.reasoning)}</ul></div><div class="detail-section"><h3>Caveats</h3><ul>${sentenceList(pick.caveats, "None stated")}</ul></div><div class="detail-section"><h3>Evidence · ${display(pick.timestamp)}</h3><div class="evidence">${escapeHtml(pick.evidence_excerpt || "No evidence excerpt recorded.")}</div>${pick.review_reason ? `<p class="review-context">Review note: ${escapeHtml(pick.review_reason)}</p>` : ""}</div><div class="latest-actions detail-actions"><a class="button" href="${escapeHtml(pickSummaryUrl(pick))}">Listen${pick.timestamp ? ` at ${escapeHtml(pick.timestamp)}` : " to episode"}</a><button class="button secondary" type="button" data-open-pick-episode="${escapeHtml(pick.episode.guid)}">Episode details</button>${pickReviewBadge(pick)}<a class="link-button" href="${safeUrl(scryfallUrl(pick, true))}" target="_blank" rel="noreferrer">${verifiedIdentity(pick) ? "View card on Scryfall ↗" : "Search Scryfall ↗"}</a></div>${renderCardHistory(pick)}</div>`;
  const cardHeading = dialogContent.querySelector("#dialog-card");
  if (cardResolutionNote(pick)) {
    cardHeading.insertAdjacentHTML("afterend", cardResolutionNote(pick));
  }
  if (cardPreview(pick)) {
    cardHeading.insertAdjacentHTML("afterend", `<figure class="detail-card-art">${cardPreview(pick)}<figcaption>${verifiedIdentity(pick) ? "Catalog image; may show a different printing." : "Possible match image; card identity is unverified."}</figcaption></figure>`);
  }
  setDialogCloseAction(Boolean(dialogState.episodeGuid));
  openDialog();
  dialog.scrollTop = 0;
  cardHeading.tabIndex = -1;
  cardHeading.focus({ preventScroll: true });
}

function showEpisode(guid, { returning = false, focusPickId = null } = {}) {
  const episode = state.index.episodes.find((item) => item.guid === guid);
  if (!episode) return;
  if (!returning) dialogState.episodeScrollTop = 0;
  dialogState.view = "episode";
  dialogState.episodeGuid = guid;
  dialogState.pickId = null;
  const error = episode.error || {};
  const summaryLink = canOpenSummary(episode) ? `<a class="button secondary" href="${episodeSummaryUrl(episode)}" target="_blank">Open summary</a>` : "";
  const episodePicks = state.cards.filter((pick) => pick.episode.guid === episode.guid);
  const workflowUrl = safeUrl(state.index.metadata.workflow_url);
  const retryControls = episode.error ? `<div class="detail-section"><h3>Retry this exact episode</h3><p>Copy the GUID, open Actions, choose <strong>Run workflow</strong>, leave mode at <strong>next</strong>, and paste it into <strong>force_guid</strong>. Inspect retained evidence first: exact retry bypasses cooldown and quarantine. Copying the GUID or opening Actions does not start a job.</p><div class="latest-actions"><button class="button secondary" type="button" data-copy-guid="${escapeHtml(episode.guid)}">Copy retry GUID</button><input id="copy-guid-fallback" aria-label="Retry GUID to copy" readonly hidden><a class="button secondary" href="${workflowUrl}" target="_blank" rel="noreferrer">Open retry workflow</a></div></div>` : "";
  const reviewControls = isSuccessfulEpisode(episode) && !episode.human_reviewed && canOpenSummary(episode)
    ? `<div class="detail-section"><h3>Human review</h3><p>Verify the extracted picks against the source, then keep, exclude, correct, or add picks through a durable review override.</p><div class="latest-actions"><a class="button" href="${episodeReviewUrl(episode)}">Review episode</a></div></div>`
    : episode.human_reviewed
      ? `<div class="detail-section"><h3>Human review</h3><p>${badge("human_reviewed")} Reviewed by ${escapeHtml(episode.reviewed_by || "an authenticated reviewer")}${episode.review_note ? ` · ${escapeHtml(episode.review_note)}` : ""}</p></div>`
      : "";
  const picksSection = episodePicks.length
    ? `<div class="detail-section"><h3>Recommendations</h3><div class="episode-pick-list">${episodePicks.map((pick) => pickCard(pick, true)).join("")}</div></div>`
    : `<div class="detail-section"><h3>Recommendations</h3><p>No structured picks were published for this episode.</p></div>`;
  dialogContent.innerHTML = `<div class="dialog-content"><p class="eyebrow">${escapeHtml(sourceName(episode))} · Episode ${episode.episode_number || "unknown"} · ${formatDate(episode.published_at, true)}</p><h2 id="dialog-card">${escapeHtml(episode.title)}</h2><div class="dialog-sub">${escapeHtml(episode.hosts.join(", ") || "Hosts not stated")} · GUID ${escapeHtml(episode.guid)}</div><div class="detail-grid"><div class="detail-box"><small>Status</small><strong>${escapeHtml(deferredStatus(error) || label(episode.processing_status))}</strong></div><div class="detail-box"><small>Picks</small><strong>${Number(episode.pick_count || 0)}</strong></div><div class="detail-box"><small>Review</small><strong>${escapeHtml(episodeReviewLabel(episode))}</strong></div></div>${episode.error ? `<div class="detail-section"><h3>${deferredStatus(error) ? "Processing deferred" : "Failure details"}</h3><div class="failure-note">${failureReason(error)}</div><dl class="failure-grid"><div><dt>Stage</dt><dd>${display(error.stage, "Unknown")}</dd></div><div><dt>Retryable</dt><dd>${error.retryable === true ? "Yes" : "No"}</dd></div><div><dt>Retry eligible</dt><dd>${error.retryable === true && !error.quarantined && error.next_retry_at ? escapeHtml(formatDateTime(error.next_retry_at)) : "No automatic retry recorded"}</dd></div><div><dt>Last attempt</dt><dd>${display(formatDateTime(episode.processed_at), "Not recorded")}</dd></div></dl><p><strong>Next action:</strong> ${escapeHtml(recoveryAction(error))}</p><details><summary>Technical message</summary><pre>${escapeHtml(error.message || "No raw error recorded.")}</pre></details></div>` : picksSection}${reviewControls}${retryControls}<div class="detail-section"><h3>Source</h3><p>${escapeHtml(ManaUI.sourceText(episode.description || "No feed description was captured."))}</p></div><div class="latest-actions" style="margin-top:20px"><a class="button" href="${safeUrl(episode.audio_url)}" target="_blank" rel="noreferrer">Listen</a>${summaryLink}</div></div>`;
  setDialogCloseAction(false);
  openDialog();
  if (!returning) {
    dialog.scrollTop = 0;
    const heading = dialogContent.querySelector("#dialog-card");
    heading.tabIndex = -1;
    heading.focus({ preventScroll: true });
  }
  if (returning) {
    requestAnimationFrame(() => {
      dialog.scrollTop = dialogState.episodeScrollTop;
      const pickElement = [...dialogContent.querySelectorAll("[data-pick-id]")]
        .find((element) => element.dataset.pickId === focusPickId);
      pickElement?.focus();
    });
  }
}

function closeDialogOrBack() {
  if (dialogState.view === "pick" && dialogState.episodeGuid) {
    showEpisode(dialogState.episodeGuid, { returning: true, focusPickId: dialogState.pickId });
    return;
  }
  dialog.close();
}

dialogClose.addEventListener("click", closeDialogOrBack);
dialog.addEventListener("click", (event) => { if (event.target === dialog) closeDialogOrBack(); });
dialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  closeDialogOrBack();
});
dialog.addEventListener("close", () => {
  dialogState.view = null;
  dialogState.episodeGuid = null;
  dialogState.episodeScrollTop = 0;
  dialogState.pickId = null;
  setDialogCloseAction(false);
});
dialogContent.addEventListener("click", (event) => {
  const historyPick = event.target.closest("[data-history-pick]");
  if (historyPick) { showPick(historyPick.dataset.historyPick); return; }
  const episodeButton = event.target.closest("[data-open-pick-episode]");
  if (episodeButton) { showEpisode(episodeButton.dataset.openPickEpisode); return; }
  const copyButton = event.target.closest("[data-copy-guid]");
  if (copyButton) {
    ManaUI.copyText(copyButton, copyButton.dataset.copyGuid, "GUID copied", dialogContent.querySelector("#copy-guid-fallback"));
    return;
  }
  if (event.target.closest("a")) return;
  const pickElement = event.target.closest("[data-pick-id]");
  if (pickElement) showPick(pickElement.dataset.pickId, { fromEpisode: dialogState.view === "episode" });
});
dialogContent.addEventListener("keydown", (event) => {
  if (!["Enter", " "].includes(event.key) || event.target.closest("a, button, input")) return;
  const pickElement = event.target.closest("[data-pick-id]");
  if (pickElement) {
    event.preventDefault();
    showPick(pickElement.dataset.pickId, { fromEpisode: dialogState.view === "episode" });
  }
});
document.querySelector("#refresh-button").addEventListener("click", loadData);
document.querySelector(".skip-link")?.addEventListener("click", (event) => {
  event.preventDefault(); app.focus();
});
window.addEventListener("hashchange", () => { if (dialog.open) dialog.close(); setRoute(); });
state.route = "dashboard";
loadData();
