<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api.js';
  import {
    channelInfo, copyText, formatBytes, formatTimestamp, isTerminal,
    remaining, statusInfo
  } from '../lib/format.js';
  import Modal from './Modal.svelte';

  export let messageId = null;
  export let onclose = () => {};
  export let onchanged = () => {};
  export let onnotify = () => {};

  let message = null;
  let history = null;
  let handoff = null;
  let webhookEvents = [];
  let loading = false;
  let error = '';
  let busy = '';
  let loadedId = null;

  let rejectOpen = false;
  let rejectReason = '';
  let rejectError = '';
  let cancelOpen = false;
  let cancelReason = '';
  let sentOpen = false;
  let sentChecked = false;
  let sentError = '';

  let now = Date.now();
  let timer = null;

  $: if (messageId && messageId !== loadedId && !loading) {
    load(messageId);
  }

  onMount(() => {
    timer = setInterval(() => { now = Date.now(); }, 30000);
    return () => clearInterval(timer);
  });

  onDestroy(() => clearInterval(timer));

  async function load(id) {
    loading = true;
    error = '';
    loadedId = id;
    try {
      const [detail, revs, hooks] = await Promise.all([
        api.getMessage(id),
        api.getHistory(id),
        api.getWebhookEvents(id)
      ]);
      message = detail;
      history = revs;
      webhookEvents = hooks.items || [];
      handoff = null;
      if (detail.status === 'approved') {
        try {
          handoff = await api.getHandoff(id);
        } catch (handoffError) {
          handoff = null;
          if (handoffError.currentStatus && handoffError.currentStatus !== 'approved') {
            await reloadMessages(id);
          } else {
            error = handoffError.message;
          }
        }
      }
    } catch (loadError) {
      error = loadError.message;
    } finally {
      loading = false;
    }
  }

  async function reloadMessages(id) {
    try {
      message = await api.getMessage(id);
      history = await api.getHistory(id);
      webhookEvents = (await api.getWebhookEvents(id)).items || [];
      handoff = null;
      if (message.status === 'approved') handoff = await api.getHandoff(id);
    } catch (reloadError) {
      error = reloadError.message;
    }
  }

  async function run(name, fn) {
    busy = name;
    error = '';
    try {
      await fn();
      await reloadMessages(messageId);
      onchanged();
    } catch (actionError) {
      error = actionError.message;
      onnotify(actionError.message, 'error');
      if (actionError.currentStatus) {
        try { await reloadMessages(messageId); onchanged(); } catch { /* shown already */ }
      }
    } finally {
      busy = '';
    }
  }

  function approve() {
    run('approve', () => api.approve(messageId));
  }

  function submitReject() {
    const reason = rejectReason.trim();
    if (!reason) { rejectError = 'A rejection reason is required.'; return; }
    rejectError = '';
    run('reject', async () => {
      await api.reject(messageId, reason);
      rejectOpen = false;
      onnotify('Message rejected. The producer can submit a revised version.', 'ok');
    });
  }

  function submitCancel() {
    run('cancel', async () => {
      await api.cancel(messageId, cancelReason.trim() || null);
      cancelOpen = false;
      onnotify('Message cancelled.', 'ok');
    });
  }

  function submitSent() {
    if (!sentChecked) { sentError = 'Confirm that you actually sent this message first.'; return; }
    sentError = '';
    run('sent', async () => {
      await api.markSent(messageId);
      sentOpen = false;
      sentChecked = false;
      onnotify('Marked as sent. Nothing was sent by the service itself.', 'ok');
    });
  }

  async function copy(value, label) {
    if (value === null || value === undefined || value === '') {
      onnotify(`There is no ${label} to copy.`, 'error');
      return;
    }
    const ok = await copyText(value);
    onnotify(ok ? `${label} copied.` : `Could not copy ${label}. Select the text and copy manually.`, ok ? 'ok' : 'error');
  }

  function closeReject() { if (busy !== 'reject') { rejectOpen = false; rejectError = ''; } }
  function closeCancel() { if (busy !== 'cancel') { cancelOpen = false; } }
  function closeSent() { if (busy !== 'sent') { sentOpen = false; sentError = ''; } }

  function drawerKeydown(event) {
    if (event.defaultPrevented) return;
    if (event.key === 'Escape' && !rejectOpen && !cancelOpen && !sentOpen && !busy) {
      onclose();
    }
  }

  function metaText(metadata) {
    if (metadata === null || metadata === undefined) return 'None';
    try { return JSON.stringify(metadata, null, 2); } catch { return String(metadata); }
  }
</script>

<svelte:window on:keydown={drawerKeydown} />

<div class="drawer-backdrop" role="presentation" on:click={(e) => e.target === e.currentTarget && onclose()}>
  <aside class="drawer" aria-label="Message detail">
    <div class="drawer-head">
      <div style="flex:1; min-width:0">
        {#if message}
          <div class="dest-line">
            <span class="dest">{message.destination}</span>
            {#if message.display_label}<span class="dest-label">{message.display_label}</span>{/if}
          </div>
          <p class="sub">
            {channelInfo(message.channel).icon} {channelInfo(message.channel).label}
            · revision {message.revision_number}
            · <span class="mono">{message.id}</span>
          </p>
        {:else}
          <h2>Message detail</h2>
        {/if}
      </div>
      {#if message}
        <span class="status-badge tone-{statusInfo(message.status).tone}">
          <span class="icon" aria-hidden="true">{statusInfo(message.status).icon}</span>
          {statusInfo(message.status).label}
        </span>
      {/if}
      <button class="btn ghost small" type="button" on:click={() => load(messageId)} disabled={loading} aria-label="Refresh message">↻</button>
      <button class="btn ghost small" type="button" on:click={onclose} aria-label="Close detail panel">Close ✕</button>
    </div>

    <div class="drawer-body">
      {#if loading}
        <div class="notice"><span class="spinner" aria-hidden="true"></span> Loading message…</div>
      {:else if error && !message}
        <div class="notice error" role="alert">
          <h3>Could not load this message</h3>
          <p>{error}</p>
          <div class="actions" style="justify-content:center">
            <button class="btn small" type="button" on:click={() => load(messageId)}>Try again</button>
          </div>
        </div>
      {:else if message}
        {#if error}
          <div class="notice error" role="alert" style="margin-bottom:14px">
            <p>{error}</p>
          </div>
        {/if}

        <section class="section">
          <h3>Content</h3>
          {#if message.subject}
            <div class="kv" style="margin-bottom:10px">
              <dt>Subject</dt>
              <dd><strong>{message.subject}</strong>
                <button class="btn ghost small" type="button" on:click={() => copy(message.subject, 'Subject')}>Copy</button>
              </dd>
            </div>
          {/if}
          <div class="body-text">{message.body}</div>
          <div class="actions">
            {#if message.subject}
              <button class="btn small" type="button" on:click={() => copy(message.subject, 'Subject')}>Copy subject</button>
            {/if}
            <button class="btn small" type="button" on:click={() => copy(message.body, 'Body')}>Copy body</button>
          </div>
        </section>

        <section class="section">
          <h3>Details</h3>
          <dl class="kv">
            <dt>Channel</dt>
            <dd>{channelInfo(message.channel).icon} {channelInfo(message.channel).label}</dd>
            <dt>Destination</dt>
            <dd>{message.destination}</dd>
            <dt>Normalized</dt>
            <dd class="mono">{message.normalized_destination}</dd>
            <dt>Managed label</dt>
            <dd>{message.managed_label || '—'}</dd>
            <dt>Snapshot label</dt>
            <dd>{message.destination_label || '—'}</dd>
            <dt>Source</dt>
            <dd>{message.source || '—'}</dd>
            <dt>Created</dt>
            <dd>{formatTimestamp(message.created_at)}</dd>
            <dt>Updated</dt>
            <dd>{formatTimestamp(message.updated_at)}</dd>
            <dt>Expires</dt>
            <dd>
              {#if message.expires_at}
                {formatTimestamp(message.expires_at)}
                <span class="badge expiring">{remaining(message.expires_at, now)}</span>
              {:else}
                No expiration
              {/if}
            </dd>
            <dt>Revision</dt>
            <dd>{message.revision_number}</dd>
            <dt>Webhook</dt>
            <dd class="mono">{message.webhook_url || 'Not configured'}</dd>
            <dt>Status note</dt>
            <dd>{statusInfo(message.status).note}</dd>
          </dl>
        </section>

        {#if message.rejection_reason}
          <section class="section">
            <h3>Rejection</h3>
            <div class="notice error" style="text-align:left">
              <p><strong>Reason:</strong> {message.rejection_reason}</p>
              <p style="margin-top:5px; font-size:0.8rem">Rejected {formatTimestamp(message.rejection_at)}. Patching the message creates a new revision and returns it to pending.</p>
            </div>
          </section>
        {/if}

        {#if message.metadata}
          <section class="section">
            <h3>Metadata</h3>
            <pre class="meta-json">{metaText(message.metadata)}</pre>
          </section>
        {/if}

        <section class="section">
          <h3>Attachments ({message.attachment_count || 0})</h3>
          {#if message.attachments?.length}
            {#each message.attachments as attachment (attachment.id)}
              <div class="attachment-row">
                <div>
                  <div class="file-name">{attachment.filename}</div>
                  <div class="file-meta">
                    {attachment.mime_type} · {formatBytes(attachment.size_bytes)}
                    · {attachment.source_type === 'url_download' ? 'downloaded from URL' : 'uploaded file'}
                  </div>
                  {#if attachment.source_url}<div class="file-meta mono">{attachment.source_url}</div>{/if}
                </div>
                <span class="spacer"></span>
                <a class="btn small" href={attachment.download_url} download rel="noopener">Download</a>
              </div>
            {/each}
            <div class="actions">
              <a class="btn small" href={`/api/messages/${message.id}/attachments.zip`} download>Download all (ZIP)</a>
            </div>
            <p class="history-note" style="margin-top:8px">
              Downloading a file never marks the message sent.
            </p>
          {:else}
            <p class="history-note">No attachments.</p>
          {/if}
        </section>

        {#if message.references?.length}
          <section class="section">
            <h3>External references (stored only, never fetched)</h3>
            <div class="reference-list">
              {#each message.references as reference}
                <a href={reference} target="_blank" rel="noopener noreferrer">{reference} ↗</a>
              {/each}
            </div>
          </section>
        {/if}

        {#if message.status === 'approved'}
          <section class="section">
            <h3>Prepared handoff</h3>
            {#if handoff}
              <div class="handoff">
                <div class="target">{handoff.target_display || handoff.destination}</div>
                <div class="cap-list">
                  <span class="cap {handoff.capabilities.prefill_recipient ? 'yes' : 'no'}">
                    Recipient {handoff.capabilities.prefill_recipient ? 'prefilled' : 'manual'}
                  </span>
                  <span class="cap {handoff.capabilities.prefill_subject ? 'yes' : 'no'}">
                    Subject {handoff.capabilities.prefill_subject ? 'prefilled' : 'not supported'}
                  </span>
                  <span class="cap {handoff.capabilities.prefill_body ? 'yes' : 'no'}">
                    Body {handoff.capabilities.prefill_body ? 'prefilled' : 'copy & paste'}
                  </span>
                  <span class="cap no">Attachments manual</span>
                </div>
                <div class="actions">
                  <a class="btn primary" href={handoff.handoff_url} target="_blank" rel="noopener noreferrer">
                    Open in {channelInfo(message.channel).label} ↗
                  </a>
                  {#if handoff.copy.subject}
                    <button class="btn small" type="button" on:click={() => copy(handoff.copy.subject, 'Subject')}>Copy subject</button>
                  {/if}
                  <button class="btn small" type="button" on:click={() => copy(handoff.copy.body, 'Body')}>Copy body</button>
                </div>
                {#if handoff.warnings?.length}
                  <ul class="warning-list" aria-label="Handoff warnings">
                    {#each handoff.warnings as warning}<li>{warning}</li>{/each}
                  </ul>
                {/if}
                {#if handoff.manual_actions?.length}
                  <ul class="manual-list" aria-label="Required manual actions">
                    {#each handoff.manual_actions as action}<li>{action}</li>{/each}
                  </ul>
                {/if}
                <p class="history-note" style="margin:10px 0 0">{handoff.transport_note}</p>
                <details style="margin-top:8px">
                  <summary class="history-note" style="cursor:pointer">Show generated URL ({handoff.handoff_url_length} characters)</summary>
                  <div class="code-url" style="margin-top:6px">{handoff.handoff_url}</div>
                </details>
              </div>
            {:else}
              <p class="history-note">Handoff is being prepared…</p>
            {/if}
            <div class="actions">
              <button class="btn success" type="button" disabled={busy !== ''} on:click={() => { sentOpen = true; sentChecked = false; sentError = ''; }}>
                Mark as sent…
              </button>
              <button class="btn danger" type="button" disabled={busy !== ''} on:click={() => { cancelOpen = true; cancelReason = ''; }}>
                Cancel message
              </button>
            </div>
            <p class="history-note" style="margin-top:8px">
              Opening a link or downloading an attachment never changes the status. Marking as sent is a separate, explicit confirmation.
            </p>
          </section>
        {/if}

        {#if message.status === 'pending'}
          <section class="section">
            <h3>Review actions</h3>
            <div class="actions">
              <button class="btn primary" type="button" disabled={busy !== ''} on:click={approve}>
                {busy === 'approve' ? 'Approving…' : 'Approve for handoff'}
              </button>
              <button class="btn danger" type="button" disabled={busy !== ''} on:click={() => { rejectOpen = true; rejectReason = ''; rejectError = ''; }}>
                Reject…
              </button>
              <button class="btn" type="button" disabled={busy !== ''} on:click={() => { cancelOpen = true; cancelReason = ''; }}>
                Cancel…
              </button>
            </div>
            <p class="history-note" style="margin-top:8px">
              The reviewer cannot edit content here. The producer can revise a rejected message through the API.
            </p>
          </section>
        {/if}

        {#if message.status === 'rejected'}
          <section class="section">
            <h3>Review actions</h3>
            <p class="history-note">
              This message is waiting for the producer to submit a revised version. The revision keeps the same message ID and returns to pending.
            </p>
            <div class="actions">
              <button class="btn danger" type="button" disabled={busy !== ''} on:click={() => { cancelOpen = true; cancelReason = ''; }}>
                Cancel message…
              </button>
            </div>
          </section>
        {/if}

        {#if isTerminal(message.status)}
          <section class="section">
            <h3>Final state</h3>
            <div class="notice" style="text-align:left">
              <p><strong>{statusInfo(message.status).label}.</strong> {statusInfo(message.status).note}. This message is terminal and immutable.</p>
              <p style="margin-top:5px">All content, attachments and history are retained for audit.</p>
            </div>
          </section>
        {/if}

        <section class="section">
          <h3>Revision history</h3>
          <p class="history-note">Every revision preserves its own content, attachments, references and rejection data.</p>
          {#each history?.revisions || [] as revision (revision.revision_number)}
            <details class="revision" open={revision.revision_number === message.revision_number}>
              <summary>
                Revision {revision.revision_number}
                <span class="muted">· {revision.status} · {formatTimestamp(revision.created_at)}</span>
              </summary>
              <div class="revision-body">
                <dl class="kv">
                  <dt>Destination</dt><dd>{revision.destination}</dd>
                  {#if revision.subject}<dt>Subject</dt><dd>{revision.subject}</dd>{/if}
                  <dt>Expires</dt><dd>{revision.expires_at ? formatTimestamp(revision.expires_at) : 'No expiration'}</dd>
                  {#if revision.rejection_reason}<dt>Rejection</dt><dd>{revision.rejection_reason}</dd>{/if}
                </dl>
                <div class="body-text" style="margin-top:8px; max-height:180px">{revision.body}</div>
                {#if revision.attachments?.length}
                  <div style="margin-top:8px">
                    {#each revision.attachments as attachment (attachment.id)}
                      <div class="file-meta">📎 {attachment.filename} · {formatBytes(attachment.size_bytes)}</div>
                    {/each}
                  </div>
                {/if}
                {#if revision.references?.length}
                  <div class="reference-list" style="margin-top:6px">
                    {#each revision.references as reference}<span class="file-meta mono">{reference}</span>{/each}
                  </div>
                {/if}
              </div>
            </details>
          {/each}
        </section>

        <section class="section">
          <h3>Status history</h3>
          {#if history?.status_history?.length}
            <ol class="timeline">
              {#each history.status_history as change}
                <li>
                  <div class="what">
                    {change.from_status ? `${change.from_status} → ${change.to_status}` : `created as ${change.to_status}`}
                  </div>
                  <div class="when">Revision {change.revision_number} · {formatTimestamp(change.timestamp)}</div>
                  {#if change.reason}<div class="reason">{change.reason}</div>{/if}
                </li>
              {/each}
            </ol>
          {:else}
            <p class="history-note">No status transitions recorded.</p>
          {/if}
        </section>

        <section class="section">
          <h3>Webhook delivery</h3>
          {#if webhookEvents.length}
            {#each webhookEvents as event (event.id)}
              <div class="revision">
                <div class="row" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap">
                  <strong>{event.event}</strong>
                  <span class="badge">rev {event.revision_number}</span>
                  <span class="status-badge {event.delivered ? 'tone-sent' : 'tone-pending'}">
                    {event.delivered ? '✓ delivered' : '◷ pending / retrying'}
                  </span>
                  <span class="file-meta">{event.attempts_count} attempt(s)</span>
                </div>
                {#if event.last_error}<p class="error-text">Last error: {event.last_error}</p>{/if}
                <div class="when file-meta">Created {formatTimestamp(event.created_at)}{#if event.delivered_at} · delivered {formatTimestamp(event.delivered_at)}{/if}</div>
                {#if event.attempts?.length}
                  <ul class="timeline" style="margin-top:8px">
                    {#each event.attempts as attempt}
                      <li>
                        <div class="what">Attempt {attempt.attempt_number}: {attempt.status}{#if attempt.http_status} (HTTP {attempt.http_status}){/if}</div>
                        <div class="when">{formatTimestamp(attempt.started_at)} → {formatTimestamp(attempt.finished_at)}</div>
                        {#if attempt.error}<div class="reason">{attempt.error}</div>{/if}
                      </li>
                    {/each}
                  </ul>
                {/if}
                <details style="margin-top:8px">
                  <summary class="history-note" style="cursor:pointer">Payload</summary>
                  <pre class="meta-json" style="margin-top:6px">{JSON.stringify(event.payload, null, 2)}</pre>
                </details>
              </div>
            {/each}
          {:else}
            <p class="history-note">No webhook events. Either no webhook URL was configured or no events have occurred yet.</p>
          {/if}
        </section>
      {/if}
    </div>
  </aside>
</div>

<Modal open={rejectOpen} title="Reject this message" subtitle="A reason is mandatory and is recorded in history and sent to the producer's webhook." onclose={closeReject} busy={busy === 'reject'}>
  <div class="field">
    <label for="reject-reason">Rejection reason</label>
    <textarea id="reject-reason" bind:value={rejectReason} placeholder="Explain exactly what needs to change…" disabled={busy === 'reject'}></textarea>
  </div>
  {#if rejectError}<p class="error-text" role="alert">{rejectError}</p>{/if}
  <div class="modal-actions">
    <button class="btn" type="button" on:click={closeReject} disabled={busy === 'reject'}>Keep pending</button>
    <button class="btn danger" type="button" on:click={submitReject} disabled={busy === 'reject' || !rejectReason.trim()}>
      {busy === 'reject' ? 'Rejecting…' : 'Reject message'}
    </button>
  </div>
</Modal>

<Modal open={cancelOpen} title="Cancel this message?" subtitle="Cancelling is terminal. The message and all history are retained, but it cannot be approved, handed off or sent." onclose={closeCancel} busy={busy === 'cancel'}>
  <div class="field">
    <label for="cancel-reason">Reason (optional)</label>
    <input id="cancel-reason" bind:value={cancelReason} placeholder="e.g. superseded by a newer draft" disabled={busy === 'cancel'} />
  </div>
  <div class="modal-actions">
    <button class="btn" type="button" on:click={closeCancel} disabled={busy === 'cancel'}>Keep message</button>
    <button class="btn danger" type="button" on:click={submitCancel} disabled={busy === 'cancel'}>
      {busy === 'cancel' ? 'Cancelling…' : 'Cancel message'}
    </button>
  </div>
</Modal>

<Modal open={sentOpen} title="Confirm the message was sent" subtitle="This is the only action that marks a message sent. The outbox never sent anything itself." onclose={closeSent} busy={busy === 'sent'}>
  <p class="modal-sub">
    Confirm that you personally pressed Send in {channelInfo(message?.channel || 'email').label}.
    Opening a handoff link, copying text, or downloading an attachment does not count.
  </p>
  <label class="checkbox-row">
    <input type="checkbox" bind:checked={sentChecked} disabled={busy === 'sent'} />
    <span>I actually sent this message to <strong>{message?.destination}</strong> from my own {channelInfo(message?.channel || 'email').label} client.</span>
  </label>
  {#if sentError}<p class="error-text" role="alert">{sentError}</p>{/if}
  <div class="modal-actions">
    <button class="btn" type="button" on:click={closeSent} disabled={busy === 'sent'}>Not yet</button>
    <button class="btn success" type="button" on:click={submitSent} disabled={busy === 'sent' || !sentChecked}>
      {busy === 'sent' ? 'Recording…' : 'Yes, mark as sent'}
    </button>
  </div>
</Modal>
