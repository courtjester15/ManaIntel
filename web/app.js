"use strict";

const state = {
  index: null, cards: [], route: "dashboard", query: "", status: "all",
  episodeSource: "all", pickSource: "all",
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
  status: { title: "Processing Status", render: renderStatus },
  about: { title: "Settings / About", render: renderAbout },
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
function sourceName(item) { return item?.source_name || item?.episode?.source_name || "MTG Fast Finance"; }
function sourceId(item) {
  const explicit = item?.source_id || item?.episode?.source_id;
  if (explicit) return explicit;
  const name = sourceName(item);
  if (name === "MTG Fast Finance") return "mtg-fast-finance";
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
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
function label(value) { return String(value ?? "unknown").replaceAll("_", " "); }
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
function episodeListenLabel(episode) { return canOpenSummary(episode) ? "Listen to Cards to Watch" : "Listen"; }
function sentenceList(items, empty = "Not stated") {
  return items?.length ? items.map((item) => `<li>${escapeHtml(item)}</li>`).join("") : `<li>${escapeHtml(empty)}</li>`;
}
function pickMeta(pick) {
  return [
    pick.printing || "Printing not stated",
    pick.printing_certainty ? `${label(pick.printing_certainty)} printing` : "printing certainty unknown",
    pick.hosts?.length ? pick.hosts.join(", ") : "host not stated",
  ].map(escapeHtml).join(" · ");
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
        <h3>${cardReferenceLink(pick)}</h3>
        ${cardResolutionNote(pick)}
        <p class="pick-meta">${pickMeta(pick)}</p>
      </div>
      <div class="pick-badges">
        ${pick.confidence ? badge(pick.confidence, "confidence") : ""}
        ${badge(pick.review_status)}
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
function failureReason(error) {
  const message = String(error?.message ?? "");
  if (!message) return "No failure message was recorded.";
  const lower = message.toLowerCase();
  if (lower.includes("resource_exhausted") || lower.includes("quota")) return "Gemini quota or rate limit was reached.";
  if (lower.includes("not_found") && lower.includes("model")) return "Gemini model was unavailable for this API key.";
  if (lower.includes("api key") || lower.includes("unauthenticated") || lower.includes("permission_denied")) return "The AI provider key was missing, invalid, or unauthorized.";
  if (lower.includes("maximum size")) return "Audio exceeded the configured maximum size.";
  if (lower.includes("response_schema") || lower.includes("response_json_schema")) return "The AI provider rejected the structured JSON schema.";
  return message.length > 220 ? `${escapeHtml(message.slice(0, 220))}â€¦` : escapeHtml(message);
}
function episodeAction(episode) {
  if (!episode) return "";
  return canOpenSummary(episode)
    ? `<a class="button secondary" href="${episodeSummaryUrl(episode)}" target="_blank">Open summary</a>`
    : `<button class="button secondary" type="button" data-episode-guid="${escapeHtml(episode.guid)}">View failure details</button>`;
}

async function loadData() {
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
    document.querySelector("#mode-pill").textContent = state.index.synthetic ? "Fixture mode" : "Live pipeline";
    const banner = document.querySelector("#data-banner");
    banner.hidden = !state.index.synthetic;
    banner.textContent = state.index.synthetic ? state.index.notice : "";
    renderRoute();
  } catch (error) {
    app.innerHTML = `<div class="empty-state"><strong>Published archive could not be loaded</strong><p>The automated pipeline may be updating or may need attention.</p></div>`;
  }
}

function setRoute() {
  const requested = window.location.hash.replace("#", "") || "dashboard";
  state.route = routes[requested] ? requested : "dashboard";
  renderRoute();
}

function renderRoute() {
  if (!state.index) return;
  const route = routes[state.route];
  pageTitle.textContent = route.title;
  document.querySelectorAll("nav a").forEach((link) => link.classList.toggle("active", link.dataset.route === state.route));
  app.innerHTML = route.render();
  bindPageEvents();
}

function renderDashboard() {
  const { counts, latest_episode: latest, recent_picks: recent } = state.index;
  return `
    <section class="grid metrics" aria-label="Archive totals">
      ${metric("Episodes", counts.episodes, state.index.synthetic ? "synthetic fixtures" : "real podcast episodes")}
      ${metric("Picks", counts.picks, "structured records")}
      ${metric("Completed", counts.completed, "validated outputs")}
      ${metric("Needs review", counts.needs_review, "human attention")}
      ${metric("Failed", counts.failed, "exercised failure")}
    </section>
    <section class="grid dashboard-grid">
      <article class="panel">
        <div class="panel-head"><h2>Latest episode</h2><a href="#episodes">View archive →</a></div>
        <div class="panel-body latest">${latest ? `
          <div>${badge(latest.processing_status)} ${latest.review_state === "needs_review" ? badge("needs_review") : ""}</div>
          <div><p class="eyebrow">${escapeHtml(sourceName(latest))} · Episode ${latest.episode_number} · ${formatDate(latest.published_at)}</p><h3>${escapeHtml(latest.title)}</h3></div>
          <div class="latest-meta"><span>${latest.pick_count} picks</span><span>${escapeHtml(latest.hosts.join(" · "))}</span><span>GUID ${escapeHtml(latest.guid)}</span></div>
          ${latest.error ? `<div class="failure-note">${failureReason(latest.error)}</div>` : ""}
          <div class="latest-actions"><a class="button" href="${escapeHtml(episodeListenUrl(latest))}">${episodeListenLabel(latest)}</a>${episodeAction(latest)}</div>
        ` : `<div class="empty-state"><strong>No live episodes published yet</strong><p>The first automated run is pending.</p></div>`}</div>
      </article>
      <article class="panel">
        <div class="panel-head"><h2>Recent recommendations</h2><a href="#picks">View all →</a></div>
        <div class="panel-body recommendation-list">
          ${recent.map((pick) => `<div class="recommendation-row" data-pick-id="${escapeHtml(pick.id)}" role="button" tabindex="0"><div><strong>${cardReferenceLink(pick)}</strong>${cardResolutionNote(pick)}<p>${escapeHtml(pick.recommendation)}</p></div><time>${escapeHtml(pick.timestamp)}</time></div>`).join("")}
        </div>
      </article>
    </section>`;
}

function metric(name, value, note) {
  return `<article class="metric"><p>${escapeHtml(name)}</p><strong>${Number(value)}</strong><small>${escapeHtml(note)}</small></article>`;
}

function renderEpisodes() {
  return `
    <div class="toolbar"><label class="search"><input id="episode-search" type="search" placeholder="Search episode title, number, host…" value="${escapeHtml(state.query)}"></label><select id="episode-source" aria-label="Filter by source"><option value="all">All sources</option>${sourceFilterOptions(state.index.episodes, state.episodeSource)}</select><select id="episode-status" aria-label="Filter by status"><option value="all">All statuses</option>${["complete", "needs_review", "failed"].map((value) => `<option value="${value}" ${state.status === value ? "selected" : ""}>${label(value)}</option>`).join("")}</select></div>
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
  return episodes.map((episode) => `<tr class="episode-row" data-episode-guid="${escapeHtml(episode.guid)}" role="button" tabindex="0"><td><strong>#${episode.episode_number || "?"}</strong></td><td>${formatDate(episode.published_at)}</td><td title="${escapeHtml(`${activityLabel(episode)} ${formatDateTime(episode.processed_at)}`)}">${activityDate(episode)}</td><td><span class="muted">${escapeHtml(sourceName(episode))}</span><br><strong>${escapeHtml(episode.title)}</strong><br><span class="muted">${escapeHtml(episode.hosts.join(", "))}</span></td><td>${badge(episode.processing_status)}</td><td>${episode.pick_count}</td><td>${escapeHtml(label(episode.review_state))}</td><td><a class="link-button" href="${escapeHtml(episodeListenUrl(episode))}">Listen</a></td><td><button class="link-button" type="button" data-episode-guid="${escapeHtml(episode.guid)}">Details</button></td></tr>`).join("");
}

function renderPicks() {
  return `
    <div class="toolbar"><label class="search"><input id="pick-search" type="search" placeholder="Search card, printing, host, recommendation…" value="${escapeHtml(state.query)}"></label><select id="pick-source" aria-label="Filter by source"><option value="all">All sources</option>${sourceFilterOptions(state.cards, state.pickSource)}</select><select id="pick-status" aria-label="Filter by review status"><option value="all">All review states</option>${["approved", "pending", "needs_review"].map((value) => `<option value="${value}" ${state.status === value ? "selected" : ""}>${label(value)}</option>`).join("")}</select></div>
    <div id="pick-table" aria-label="Cards to Watch recommendations"></div>`;
}

function filteredPicks() {
  const query = state.query.toLowerCase();
  const filtered = state.cards.filter((pick) => {
    const haystack = `${sourceName(pick)} ${pick.card} ${cardName(pick)} ${pick.card_resolution?.canonical_name ?? ""} ${pick.printing ?? ""} ${pick.hosts.join(" ")} ${pick.recommendation} ${pick.episode.title}`.toLowerCase();
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
      { label: "Card", sortKey: "card", html: (pick) => `${cardReferenceLink(pick)}${cardResolutionNote(pick)}` },
      { label: "Printing", sortKey: "printing", value: (pick) => pick.printing || "—", title: (pick) => pick.printing_certainty ? `${label(pick.printing_certainty)} printing` : "Printing not stated" },
      { label: "Entry", sortKey: "entry", align: "money", value: (pick) => pick.entry_target?.raw || "—" },
      { label: "Exit", sortKey: "exit", align: "money", value: (pick) => pick.exit_target?.raw || "—" },
      { label: "Hold", sortKey: "hold", align: "center", value: (pick) => pick.hold || "—" },
      { label: "Episode", sortKey: "episode_number", align: "center", value: (pick) => pick.episode.episode_number ? `#${pick.episode.episode_number}` : "—", title: (pick) => pick.episode.title },
      { label: "Published", sortKey: "published_at", align: "center", value: (pick) => formatDate(pick.episode.published_at) },
      { label: "Review", sortKey: "review_status", align: "center", html: (pick) => badge(pick.review_status) },
      { label: "Listen", align: "center", type: "anchor", href: (pick) => pickSummaryUrl(pick), value: (pick) => pick.timestamp || "Listen" },
      { label: "Details", align: "actions", type: "action", action: "details", value: () => "Details" },
    ],
    onRowClick: (pick) => showPick(pick.id),
    onAction: (action, pick) => { if (action === "details") showPick(pick.id); },
    onSort: (key) => { toggleSort("pickSort", key); renderPickTable(); },
  });
}

function renderStatus() {
  const episodes = sortRows(state.index.episodes, { key: "processed_at", direction: "desc" }, episodeSortAccessors);
  return `<article class="panel"><div class="panel-head"><h2>Automated processing outcomes</h2><span class="muted">${state.index.episodes.length} episodes · newest activity first</span></div><div class="panel-body status-timeline">${episodes.map((episode) => `<div class="status-card"><span class="episode-no">${episode.episode_number || "—"}</span><div><strong>${escapeHtml(episode.title)} ${recentBadge(episode)}</strong><small>${episode.review_reason ? `${escapeHtml(episode.review_reason)} · ${activityLabel(episode).toLowerCase()} ${formatDateTime(episode.processed_at)}` : `${episode.pick_count} structured picks · published ${formatDate(episode.published_at)} · ${activityLabel(episode).toLowerCase()} ${formatDateTime(episode.processed_at)}`}</small></div>${badge(episode.processing_status)}</div>`).join("")}</div></article>`;
}

function renderAbout() {
  return `<section class="grid about-grid">
    <article class="panel prose"><div class="panel-body"><p class="eyebrow">Project</p><h2>FFW updates without a laptop or manual downloads.</h2><p>A scheduled pipeline checks the podcast feed, temporarily processes new audio, and publishes only structured Cards to Watch data.</p><p><strong>Pipeline:</strong> ${escapeHtml(state.index.metadata.pipeline_version)}<br><strong>Schema:</strong> ${escapeHtml(state.index.schema_version)}<br><strong>Source:</strong> ${escapeHtml(state.index.metadata.source?.name || state.index.metadata.generated_from)}</p></div></article>
    <article class="panel prose"><div class="panel-body"><p class="eyebrow">Trust rules</p><h2>Unknown means null.</h2><ul><li>No missing price, printing, host, or confidence is inferred.</li><li>Every recommendation requires evidence and a timestamp.</li><li>Markdown is rendered deterministically from JSON.</li><li>Ambiguity is surfaced as review state, not hidden.</li></ul></div></article>
    <article class="panel prose"><div class="panel-body"><p class="eyebrow">Automation</p><h2>Daily unattended updates</h2><p>GitHub Actions discovers new episodes, validates generated records, commits durable state, and deploys this site.</p></div></article>
    <article class="panel prose"><div class="panel-body"><p class="eyebrow">Disclaimer</p><h2>Verify automated records.</h2><p>Transcription and extraction can be wrong. This archive faithfully attempts to capture host commentary, adds no original finance opinions, and is not financial advice.</p></div></article>
  </section>`;
}

function renderDashboard() {
  const { counts, latest_episode: latest, recent_picks: recent } = state.index;
  return `
    <section class="summary-strip" aria-label="Archive totals">
      ${metric("Episodes", counts.episodes, state.index.synthetic ? "fixtures" : "live")}
      ${metric("Picks", counts.picks, "records")}
      ${metric("Review", counts.needs_review, "needs review")}
      ${metric("Failed", counts.failed, "attention")}
      ${metric("Latest", latest?.episode_number ? `#${latest.episode_number}` : "None", latest ? formatDate(latest.published_at) : "pending")}
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
            <div>${badge(latest.processing_status)} ${latest.review_state === "needs_review" ? badge("needs_review") : ""}</div>
            <div><p class="eyebrow">${escapeHtml(sourceName(latest))} · Episode ${latest.episode_number} - ${formatDate(latest.published_at)}</p><h3>${escapeHtml(latest.title)}</h3></div>
            <div class="latest-meta"><span>${latest.pick_count} picks</span><span>${escapeHtml(latest.hosts.join(" / "))}</span></div>
            ${latest.error ? `<div class="failure-note">${failureReason(latest.error)}</div>` : ""}
            <div class="latest-actions"><a class="button" href="${escapeHtml(episodeListenUrl(latest))}">${episodeListenLabel(latest)}</a>${episodeAction(latest)}</div>
          ` : `<div class="empty-state compact"><strong>No live episodes</strong><p>The first automated run is pending.</p></div>`}</div>
        </article>
        <article class="panel">
          <div class="panel-head"><h2>Recent picks</h2><a href="#picks">All picks</a></div>
          <div class="panel-body recommendation-list compact">
            ${recent.slice(0, 6).map((pick) => `<div class="recommendation-row" data-pick-id="${escapeHtml(pick.id)}" role="button" tabindex="0"><div><strong>${cardReferenceLink(pick)}</strong>${cardResolutionNote(pick)}<p>${escapeHtml(pick.recommendation)}</p></div><time>${escapeHtml(pick.timestamp)}</time></div>`).join("")}
          </div>
        </article>
      </aside>
    </section>`;
}

function metric(name, value, note) {
  return `<article class="metric"><p>${escapeHtml(name)}</p><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></article>`;
}

function dashboardEpisodeRows() {
  const episodes = sortRows(state.index.episodes.filter(isSuccessfulEpisode), state.episodeSort, episodeSortAccessors).slice(0, 10);
  if (!episodes.length) return `<tr><td colspan="7">No episodes have been added yet.</td></tr>`;
  return episodes.map((episode) => `<tr class="episode-row" data-episode-guid="${escapeHtml(episode.guid)}" role="button" tabindex="0"><td><strong>#${episode.episode_number || "?"}</strong></td><td title="${escapeHtml(formatDateTime(episode.processed_at))}">${formatDate(episode.processed_at)} ${recentBadge(episode)}</td><td><span class="muted">${escapeHtml(sourceName(episode))}</span><br><strong>${escapeHtml(episode.title)}</strong></td><td>${badge(episode.processing_status)}</td><td>${episode.pick_count}</td><td>${escapeHtml(label(episode.review_state))}</td><td><button class="link-button" type="button" data-episode-guid="${escapeHtml(episode.guid)}">Details</button></td></tr>`).join("");
}

function bindPageEvents() {
  bindPickButtons();
  bindEpisodeButtons();
  renderPickTable();
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
}

function bindPickButtons() {
  document.querySelectorAll("[data-pick-id]").forEach((element) => {
    const open = (event) => { if (!event?.target?.closest("a")) showPick(element.dataset.pickId); };
    element.addEventListener("click", open);
    element.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) open(event); });
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
    element.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); open(event); } });
  });
}

function openDialog() {
  if (!dialog.open) dialog.showModal();
}

function setDialogCloseAction(isBack) {
  const label = isBack ? "Back to episode picks" : "Close details";
  dialogClose.setAttribute("aria-label", label);
  dialogClose.title = label;
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
  dialogContent.innerHTML = `<div class="dialog-content pick-detail"><p class="eyebrow">Episode ${pick.episode.episode_number} · ${formatDate(pick.episode.published_at, true)}</p><h2 id="dialog-card">${escapeHtml(pick.card)}</h2><div class="dialog-sub">${pickMeta(pick)}</div><div class="detail-grid"><div class="detail-box"><small>Entry</small><strong>${target(pick.entry_target)}</strong></div><div class="detail-box"><small>Hold</small><strong>${display(pick.hold)}</strong></div><div class="detail-box"><small>Exit</small><strong>${target(pick.exit_target)}</strong></div></div><div class="recommendation-callout"><small>Host recommendation</small><p>${escapeHtml(pick.recommendation)}</p></div><div class="detail-section"><h3>Why it was mentioned</h3><ul>${sentenceList(pick.reasoning)}</ul></div><div class="detail-section"><h3>Caveats</h3><ul>${sentenceList(pick.caveats, "None stated")}</ul></div><div class="detail-section"><h3>Evidence · ${display(pick.timestamp)}</h3><div class="evidence">${escapeHtml(pick.evidence_excerpt || "No evidence excerpt recorded.")}</div></div><div class="latest-actions" style="margin-top:20px"><a class="button" href="${escapeHtml(pickSummaryUrl(pick))}">Listen at timestamp</a>${badge(pick.review_status)}</div></div>`;
  const cardHeading = dialogContent.querySelector("#dialog-card");
  cardHeading.innerHTML = cardReferenceLink(pick, { allowSearch: true });
  if (cardResolutionNote(pick)) {
    cardHeading.insertAdjacentHTML("afterend", cardResolutionNote(pick));
  }
  if (cardPreview(pick)) {
    cardHeading.insertAdjacentHTML("afterend", cardPreview(pick));
  }
  setDialogCloseAction(Boolean(dialogState.episodeGuid));
  openDialog();
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
  const retryControls = episode.error ? `<div class="detail-section"><h3>Retry this exact episode</h3><p>Copy the GUID, open Actions, choose <strong>Run workflow</strong>, leave mode at <strong>next</strong>, and paste it into <strong>force_guid</strong>. Exact retry bypasses cooldown and quarantine.</p><div class="latest-actions"><button class="button secondary" type="button" data-copy-guid="${escapeHtml(episode.guid)}">Copy retry GUID</button><a class="button secondary" href="${workflowUrl}" target="_blank" rel="noreferrer">Open retry workflow</a></div></div>` : "";
  const reviewControls = episode.processing_status === "needs_review" && canOpenSummary(episode)
    ? `<div class="detail-section"><h3>Human review</h3><p>Verify the extracted picks against the source, then keep, exclude, correct, or add picks through a durable review override.</p><div class="latest-actions"><a class="button" href="${episodeReviewUrl(episode)}">Review episode</a></div></div>`
    : episode.human_reviewed
      ? `<div class="detail-section"><h3>Human review</h3><p>${badge("human_reviewed")} Reviewed by ${escapeHtml(episode.reviewed_by || "an authenticated reviewer")}${episode.review_note ? ` · ${escapeHtml(episode.review_note)}` : ""}</p></div>`
      : "";
  const picksSection = episodePicks.length
    ? `<div class="detail-section"><h3>Cards to Watch</h3><div class="episode-pick-list">${episodePicks.map((pick) => pickCard(pick, true)).join("")}</div></div>`
    : `<div class="detail-section"><h3>Cards to Watch</h3><p>No structured picks were published for this episode.</p></div>`;
  dialogContent.innerHTML = `<div class="dialog-content"><p class="eyebrow">${escapeHtml(sourceName(episode))} · Episode ${episode.episode_number || "unknown"} · ${formatDate(episode.published_at, true)}</p><h2 id="dialog-card">${escapeHtml(episode.title)}</h2><div class="dialog-sub">${escapeHtml(episode.hosts.join(", ") || "Hosts not stated")} · GUID ${escapeHtml(episode.guid)}</div><div class="detail-grid"><div class="detail-box"><small>Status</small><strong>${escapeHtml(label(episode.processing_status))}</strong></div><div class="detail-box"><small>Picks</small><strong>${Number(episode.pick_count || 0)}</strong></div><div class="detail-box"><small>Review</small><strong>${escapeHtml(label(episode.review_state))}</strong></div></div>${episode.error ? `<div class="detail-section"><h3>Failure details</h3><div class="failure-note">${failureReason(error)}</div><dl class="failure-grid"><div><dt>Stage</dt><dd>${display(error.stage, "Unknown")}</dd></div><div><dt>Retryable</dt><dd>${error.retryable === true ? "Yes" : "No"}</dd></div><div><dt>Attempted</dt><dd>${display(formatDate(episode.processed_at, true), "Not recorded")}</dd></div></dl><details><summary>Technical message</summary><pre>${escapeHtml(error.message || "No raw error recorded.")}</pre></details></div>` : picksSection}${reviewControls}${retryControls}<div class="detail-section"><h3>Source</h3><p>${escapeHtml(episode.description || "No feed description was captured.")}</p></div><div class="latest-actions" style="margin-top:20px"><a class="button" href="${safeUrl(episode.audio_url)}" target="_blank" rel="noreferrer">Listen</a>${summaryLink}</div></div>`;
  setDialogCloseAction(false);
  openDialog();
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
  const copyButton = event.target.closest("[data-copy-guid]");
  if (copyButton) {
    navigator.clipboard.writeText(copyButton.dataset.copyGuid).then(() => { copyButton.textContent = "GUID copied"; });
    return;
  }
  if (event.target.closest("a")) return;
  const pickElement = event.target.closest("[data-pick-id]");
  if (pickElement) showPick(pickElement.dataset.pickId, { fromEpisode: dialogState.view === "episode" });
});
dialogContent.addEventListener("keydown", (event) => {
  if (!["Enter", " "].includes(event.key) || event.target.closest("a")) return;
  const pickElement = event.target.closest("[data-pick-id]");
  if (pickElement) {
    event.preventDefault();
    showPick(pickElement.dataset.pickId, { fromEpisode: dialogState.view === "episode" });
  }
});
document.querySelector("#refresh-button").addEventListener("click", loadData);
window.addEventListener("hashchange", () => { state.query = ""; state.status = "all"; setRoute(); });
state.route = window.location.hash.replace("#", "") || "dashboard";
loadData();
