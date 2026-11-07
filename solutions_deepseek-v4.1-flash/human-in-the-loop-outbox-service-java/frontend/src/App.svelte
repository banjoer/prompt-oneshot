<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from './lib/api.js';
  import {
    channelInfo, formatTimestamp, isTerminal, remaining, statusInfo
  } from './lib/format.js';
  import MessageDetail from './components/MessageDetail.svelte';
  import DestinationPanel from './components/DestinationPanel.svelte';
  import Modal from './components/Modal.svelte';

  /* global __BUILD_TIME__, __BUILD_BY__ */

  const statusFilters = [
    { value: 'active', label: 'Actionable' },
    { value: 'pending', label: 'Pending' },
    { value: 'approved', label: 'Approved' },
    { value: 'rejected', label: 'Rejected' },
    { value: 'sent', label: 'Sent' },
    { value: 'stale', label: 'Stale' },
    { value: 'cancelled', label: 'Cancelled' },
    { value: 'all', label: 'All' }
  ];

  let view = 'queue';
  let info = null;
  let infoError = '';
  let messages = [];
  let total = 0;
  let loading = true;
  let loadingMore = false;
  let error = '';

  let statusFilter = 'active';
  let channel = '';
  let destination = '';
  let createdAfter = '';
  let createdBefore = '';
  let expiresAfter = '';
  let expiresBefore = '';
  let sort = 'review';
  const limit = 50;
  let offset = 0;

  let selectedId = null;
  let aboutOpen = false;
  let toast = null;
  let toastTimer = null;
  let now = Date.now();
  let clock = null;

  $: actionable = messages.filter((m) => !isTerminal(m.status));
  $: terminal = messages.filter((m) => isTerminal(m.status));
  $: showTerminalSection = terminal.length > 0 && (statusFilter === 'all' || isTerminal(statusFilter));
  $: filterLabel = statusFilter === 'active' ? 'actionable' : statusFilter;
  $: builtLine = info?.built_at
    ? `Built ${formatTimestamp(info.built_at)} by ${info.built_by || __BUILD_BY__}`
    : `Built ${formatTimestamp(__BUILD_TIME__)} by ${__BUILD_BY__}`;

  onMount(() => {
    loadInfo();
    load(true);
    clock = setInterval(() => { now = Date.now(); }, 30000);
    return () => clearInterval(clock);
  });

  onDestroy(() => clearInterval(clock));

  async function loadInfo() {
    try {
      info = await api.info();
    } catch (e) {
      infoError = e.message;
    }
  }

  function params() {
    return {
      status: statusFilter === 'all' ? 'all' : statusFilter,
      channel,
      destination,
      created_after: createdAfter,
      created_before: createdBefore,
      expires_after: expiresAfter,
      expires_before: expiresBefore,
      sort,
      limit,
      offset
    };
  }

  async function load(reset = false) {
    if (reset) {
      offset = 0;
      loading = true;
      messages = [];
    } else {
      loadingMore = true;
    }
    error = '';
    try {
      const data = await api.listMessages(params());
      messages = reset ? (data.items || []) : [...messages, ...(data.items || [])];
      total = data.total || 0;
      offset = messages.length;
    } catch (loadError) {
      error = loadError.message;
      if (reset) messages = [];
    } finally {
      loading = false;
      loadingMore = false;
    }
  }

  function applyFilters() {
    load(true);
  }

  function setStatus(value) {
    statusFilter = value;
    load(true);
  }

  function resetFilters() {
    statusFilter = 'active';
    channel = '';
    destination = '';
    createdAfter = '';
    createdBefore = '';
    expiresAfter = '';
    expiresBefore = '';
    sort = 'review';
    load(true);
  }

  function openMessage(id) {
    selectedId = id;
  }

  function closeMessage() {
    selectedId = null;
  }

  function refreshAfterChange() {
    load(true);
  }

  function notify(message, type = 'ok') {
    toast = { message, type };
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast = null; toastTimer = null; }, 4200);
  }

  function badgeExpiry(message) {
    if (!message.expires_at) return null;
    if (isTerminal(message.status)) return `expired ${formatTimestamp(message.expires_at)}`;
    return remaining(message.expires_at, now);
  }

  function loadMore() {
    if (!loadingMore && messages.length < total) load(false);
  }

  function onNav(target) {
    view = target;
    if (target === 'queue') load(true);
  }
</script>

<svelte:window on:keydown={(e) => { if (e.key === 'Escape' && aboutOpen) aboutOpen = false; }} />

<div class="app-shell">
  <header class="topbar">
    <div class="brand">
      <div class="brand-mark" aria-hidden="true">◇</div>
      <div class="brand-text">
        <h1>Outbox</h1>
        <p>Human-in-the-loop review for email, WhatsApp &amp; Telegram</p>
      </div>
    </div>
    <nav class="topnav" aria-label="Main sections">
      <button class="navbtn" type="button" aria-current={view === 'queue' ? 'page' : undefined} on:click={() => onNav('queue')}>
        Review queue
      </button>
      <button class="navbtn" type="button" aria-current={view === 'destinations' ? 'page' : undefined} on:click={() => onNav('destinations')}>
        Destinations
      </button>
      <button class="navbtn" type="button" on:click={() => { aboutOpen = true; if (!info) loadInfo(); }}>
        About
      </button>
    </nav>
  </header>

  <main class="page">
    {#if view === 'queue'}
      <div class="page-head">
        <div>
          <h2>Review queue</h2>
          <p class="sub">Nothing is sent by the service. Approve, hand off through your own app, then confirm you sent it.</p>
        </div>
        <div class="page-actions">
          <button class="btn" type="button" on:click={() => load(true)} disabled={loading}>
            {loading ? 'Refreshing…' : '↻ Refresh'}
          </button>
        </div>
      </div>

      <div class="toolbar">
        <div class="chips" role="group" aria-label="Filter by status">
          {#each statusFilters as filter}
            <button class="chip" type="button" aria-pressed={statusFilter === filter.value}
              on:click={() => setStatus(filter.value)}>
              {filter.label}
            </button>
          {/each}
        </div>

        <div class="filter-grid" style="margin-top:12px">
          <div class="field">
            <label for="filter-channel">Channel</label>
            <select id="filter-channel" bind:value={channel} on:change={applyFilters}>
              <option value="">Any channel</option>
              <option value="email">Email</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="telegram">Telegram</option>
            </select>
          </div>
          <div class="field wide">
            <label for="filter-destination">Destination or label contains</label>
            <input id="filter-destination" bind:value={destination} placeholder="e.g. alex, group:ops, Finance"
              on:change={applyFilters} on:keydown={(e) => { if (e.key === 'Enter') applyFilters(); }} />
          </div>
          <div class="field wide-sort">
            <label for="filter-sort">Sort</label>
            <select id="filter-sort" bind:value={sort} on:change={applyFilters}>
              <option value="review">Queue order</option>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="expires_soon">Expiring soonest</option>
              <option value="expires_late">Expiring latest</option>
            </select>
          </div>
          <div class="field">
            <label for="filter-created-after">Created from</label>
            <input id="filter-created-after" type="date" bind:value={createdAfter} on:change={applyFilters} />
          </div>
          <div class="field">
            <label for="filter-created-before">Created until</label>
            <input id="filter-created-before" type="date" bind:value={createdBefore} on:change={applyFilters} />
          </div>
          <div class="field">
            <label for="filter-expires-after">Expires from</label>
            <input id="filter-expires-after" type="date" bind:value={expiresAfter} on:change={applyFilters} />
          </div>
          <div class="field">
            <label for="filter-expires-before">Expires until</label>
            <input id="filter-expires-before" type="date" bind:value={expiresBefore} on:change={applyFilters} />
          </div>
          <div class="field">
            <span class="field-label">&nbsp;</span>
            <button class="btn" type="button" on:click={resetFilters}>Reset filters</button>
          </div>
        </div>
      </div>

      <div class="queue-meta" aria-live="polite">
        <span>
          {#if loading}Loading {filterLabel} messages…
          {:else}{total} {filterLabel} message{total === 1 ? '' : 's'}{#if messages.length < total} · showing {messages.length}{/if}
          {/if}
        </span>
        <span>Times shown in your local timezone · expiration is UTC internally</span>
      </div>

      {#if loading}
        <div class="notice"><span class="spinner" aria-hidden="true"></span> Loading messages…</div>
      {:else if error}
        <div class="notice error" role="alert">
          <h3>Could not load the queue</h3>
          <p>{error}</p>
          <div class="actions" style="justify-content:center">
            <button class="btn small" type="button" on:click={() => load(true)}>Try again</button>
          </div>
        </div>
      {:else if messages.length === 0}
        <div class="notice">
          <h3>No messages in this view</h3>
          <p>
            {#if statusFilter === 'active'}
              Nothing needs review right now. Submit a message through <code>POST /api/messages</code>, or open
              another status filter to inspect history.
            {:else}
              No messages match the current filters. Try resetting them.
            {/if}
          </p>
        </div>
      {:else}
        <div class="queue">
          {#if showTerminalSection && actionable.length > 0}
            {#each actionable as message (message.id)}
              <button class="message-card" type="button" class:selected={selectedId === message.id}
                on:click={() => openMessage(message.id)}
                aria-label={`Open ${statusInfo(message.status).label} message to ${message.destination}`}>
                <div class="card-top">
                  <div class="card-title">
                    <div class="dest-line">
                      <span class="dest">{message.destination}</span>
                      {#if message.display_label}<span class="dest-label">{message.display_label}</span>{/if}
                    </div>
                    {#if message.subject}<div class="subject">{message.subject}</div>{/if}
                    <div class="preview">{message.body_preview}</div>
                  </div>
                  <div class="card-side">
                    <span class="status-badge tone-{statusInfo(message.status).tone}">
                      <span class="icon" aria-hidden="true">{statusInfo(message.status).icon}</span>
                      {statusInfo(message.status).label}
                    </span>
                  </div>
                </div>
                <div class="badges">
                  <span class="badge channel">{channelInfo(message.channel).icon} {channelInfo(message.channel).label}</span>
                  <span class="badge">rev {message.revision_number}</span>
                  <span class="badge">created {formatTimestamp(message.created_at)}</span>
                  {#if message.expires_at}
                    <span class="badge expiring">expires {formatTimestamp(message.expires_at)} · {badgeExpiry(message)}</span>
                  {:else}
                    <span class="badge">no expiration</span>
                  {/if}
                  <span class="badge">{message.attachment_count} attachment{message.attachment_count === 1 ? '' : 's'}</span>
                  {#if message.rejection_reason}<span class="badge wrap">rejection: {message.rejection_reason}</span>{/if}
                </div>
              </button>
            {/each}
            <div class="terminal-divider">Terminal &amp; history</div>
          {/if}

          {#each (showTerminalSection ? terminal : messages) as message (message.id)}
            <button class="message-card" type="button" class:selected={selectedId === message.id}
              on:click={() => openMessage(message.id)}
              aria-label={`Open ${statusInfo(message.status).label} message to ${message.destination}`}>
              <div class="card-top">
                <div class="card-title">
                  <div class="dest-line">
                    <span class="dest">{message.destination}</span>
                    {#if message.display_label}<span class="dest-label">{message.display_label}</span>{/if}
                  </div>
                  {#if message.subject}<div class="subject">{message.subject}</div>{/if}
                  <div class="preview">{message.body_preview}</div>
                </div>
                <div class="card-side">
                  <span class="status-badge tone-{statusInfo(message.status).tone}">
                    <span class="icon" aria-hidden="true">{statusInfo(message.status).icon}</span>
                    {statusInfo(message.status).label}
                  </span>
                </div>
              </div>
              <div class="badges">
                <span class="badge channel">{channelInfo(message.channel).icon} {channelInfo(message.channel).label}</span>
                <span class="badge">rev {message.revision_number}</span>
                <span class="badge">created {formatTimestamp(message.created_at)}</span>
                {#if message.expires_at}
                  <span class="badge expiring">expires {formatTimestamp(message.expires_at)} · {badgeExpiry(message)}</span>
                {:else}
                  <span class="badge">no expiration</span>
                {/if}
                <span class="badge">{message.attachment_count} attachment{message.attachment_count === 1 ? '' : 's'}</span>
                {#if isTerminal(message.status)}<span class="badge terminal-note">terminal — history only</span>{/if}
                {#if message.rejection_reason}<span class="badge wrap">rejection: {message.rejection_reason}</span>{/if}
              </div>
            </button>
          {/each}
        </div>

        {#if messages.length < total}
          <div class="actions" style="justify-content:center; margin-top:16px">
            <button class="btn" type="button" on:click={loadMore} disabled={loadingMore}>
              {loadingMore ? 'Loading…' : `Load more (${messages.length} of ${total})`}
            </button>
          </div>
        {/if}
      {/if}
    {:else}
      <DestinationPanel onnotify={notify} />
    {/if}
  </main>

  <footer class="footer">
    <span class="built">{builtLine}</span>
    <span class="links">
      {#if info}<span>v{info.version} · {info.runtime}</span>{/if}
      <a href="/api/docs" target="_blank" rel="noopener">API docs</a>
      <a href="/openapi.json" target="_blank" rel="noopener">OpenAPI</a>
      <button class="btn ghost small" type="button" on:click={() => { aboutOpen = true; if (!info) loadInfo(); }}>About</button>
    </span>
  </footer>
</div>

{#if selectedId}
  <MessageDetail
    messageId={selectedId}
    onclose={closeMessage}
    onchanged={refreshAfterChange}
    onnotify={notify}
  />
{/if}

<Modal open={aboutOpen} title="About this outbox" subtitle="Local, single-user, no provider integrations. Nothing is ever sent by this service." onclose={() => { aboutOpen = false; }}>
  <dl class="kv">
    <dt>Built</dt>
    <dd>{info?.built_at ? formatTimestamp(info.built_at) : 'Unavailable until /api/info loads'}</dd>
    <dt>Author / model</dt>
    <dd>{info?.built_by || __BUILD_BY__}</dd>
    <dt>Version</dt>
    <dd>{info?.version || '—'}</dd>
    <dt>Runtime</dt>
    <dd>{info?.runtime || '—'}</dd>
    <dt>Data directory</dt>
    <dd class="mono">{info?.data_dir || '—'}</dd>
    <dt>Attachment directory</dt>
    <dd class="mono">{info?.attachment_dir || '—'}</dd>
    <dt>Per-file limit</dt>
    <dd>{info ? `${info.max_attachment_bytes.toLocaleString()} bytes` : '—'}</dd>
    <dt>Per-message limit</dt>
    <dd>{info ? `${info.max_message_attachment_bytes.toLocaleString()} bytes` : '—'}</dd>
    <dt>Webhook attempts</dt>
    <dd>{info?.webhook_max_attempts ?? '—'}</dd>
    <dt>Private URLs</dt>
    <dd>{info ? (info.allow_private_urls ? 'Allowed (local testing override)' : 'Blocked (SSRF protection on)') : '—'}</dd>
    <dt>Schema</dt>
    <dd>v{info?.schema?.schema_version ?? '—'} · {info?.schema?.journal_mode || '—'}</dd>
  </dl>
  {#if infoError}<p class="error-text" role="alert">{infoError}</p>{/if}
  <p class="history-note" style="margin-top:12px">
    The service never integrates with email, WhatsApp or Telegram APIs. It prepares handoff links and
    records the reviewer's actions. All data lives in local SQLite and the local attachment directory.
  </p>
  <div class="modal-actions">
    <a class="btn small" href="/api/docs" target="_blank" rel="noopener">API docs</a>
    <a class="btn small" href="/openapi.json" target="_blank" rel="noopener">OpenAPI JSON</a>
    <button class="btn primary" type="button" on:click={() => { aboutOpen = false; }}>Close</button>
  </div>
</Modal>

{#if toast}
  <div class="toast {toast.type === 'error' ? 'error' : ''}" role="status" aria-live="polite">
    {toast.message}
  </div>
{/if}
