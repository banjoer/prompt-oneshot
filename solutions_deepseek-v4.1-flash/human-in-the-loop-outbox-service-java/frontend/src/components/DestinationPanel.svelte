<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { channelInfo, formatTimestamp } from '../lib/format.js';

  export let onnotify = () => {};

  let items = [];
  let loading = true;
  let error = '';
  let busyKey = '';
  let editingKey = null;
  let draft = '';
  let rowError = '';

  onMount(load);

  async function load() {
    loading = true;
    error = '';
    try {
      const data = await api.destinations();
      items = data.items || [];
      if (editingKey && !items.some((item) => keyOf(item) === editingKey)) editingKey = null;
    } catch (loadError) {
      error = loadError.message;
    } finally {
      loading = false;
    }
  }

  function keyOf(item) {
    return `${item.channel}|${item.normalized_destination}`;
  }

  function startEdit(item) {
    editingKey = keyOf(item);
    draft = item.label || '';
    rowError = '';
  }

  async function save(item) {
    const label = draft.trim();
    if (!label) {
      rowError = 'A label must not be empty. Use Remove to delete it.';
      return;
    }
    busyKey = keyOf(item);
    rowError = '';
    try {
      await api.putLabel(item.channel, item.destination, label);
      onnotify(`Label saved for ${item.destination}.`, 'ok');
      editingKey = null;
      await load();
    } catch (saveError) {
      rowError = saveError.message;
      onnotify(saveError.message, 'error');
    } finally {
      busyKey = '';
    }
  }

  async function removeLabel(item) {
    busyKey = keyOf(item);
    rowError = '';
    try {
      await api.deleteLabel(item.channel, item.destination);
      onnotify(`Label removed for ${item.destination}. Messages are unchanged.`, 'ok');
      if (editingKey === keyOf(item)) editingKey = null;
      await load();
    } catch (removeError) {
      rowError = removeError.message;
      onnotify(removeError.message, 'error');
    } finally {
      busyKey = '';
    }
  }
</script>

<section aria-labelledby="dest-heading">
  <div class="page-head">
    <div>
      <h2 id="dest-heading">Destinations</h2>
      <p class="sub">
        Destinations are discovered automatically from submitted messages. Labels are reviewer hints only;
        they never change addresses and never delete messages.
      </p>
    </div>
    <div class="page-actions">
      <button class="btn" type="button" on:click={load} disabled={loading}>Refresh</button>
    </div>
  </div>

  {#if error}
    <div class="notice error" role="alert" style="margin-bottom:14px">
      <h3>Could not load destinations</h3>
      <p>{error}</p>
      <div class="actions" style="justify-content:center">
        <button class="btn small" type="button" on:click={load}>Try again</button>
      </div>
    </div>
  {/if}

  {#if rowError}
    <div class="notice error" role="alert" style="margin-bottom:14px; text-align:left">
      <p>{rowError}</p>
    </div>
  {/if}

  {#if loading && items.length === 0}
    <div class="notice"><span class="spinner" aria-hidden="true"></span> Loading known destinations…</div>
  {:else if items.length === 0}
    <div class="notice">
      <h3>No destinations yet</h3>
      <p>Submit a message through the API and its destination will appear here automatically.</p>
    </div>
  {:else}
    <div class="dest-table-wrap">
      <table class="dest-table">
        <caption class="sr-only">Known destinations discovered from messages</caption>
        <thead>
          <tr>
            <th scope="col">Channel</th>
            <th scope="col">Destination</th>
            <th scope="col">Normalized address</th>
            <th scope="col">Label</th>
            <th scope="col">Messages</th>
            <th scope="col">Last used</th>
            <th scope="col"><span class="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {#each items as item (keyOf(item))}
            {@const key = keyOf(item)}
            {@const busy = busyKey === key}
            <tr>
              <td data-label="Channel">{channelInfo(item.channel).icon} {channelInfo(item.channel).label}</td>
              <td data-label="Destination"><span class="dest" style="font-size:0.86rem">{item.destination}</span></td>
              <td data-label="Normalized"><span class="mono" style="font-size:0.76rem; overflow-wrap:anywhere">{item.normalized_destination}</span></td>
              <td class="label-cell" data-label="Label">
                {#if editingKey === key}
                  <div class="label-edit">
                    <input class="inline-input" bind:value={draft} maxlength="80" aria-label={`Label for ${item.destination}`} disabled={busy}
                      on:keydown={(e) => { if (e.key === 'Enter') save(item); if (e.key === 'Escape') editingKey = null; }} />
                    <button class="btn small primary" type="button" on:click={() => save(item)} disabled={busy || !draft.trim()}>
                      {busy ? 'Saving…' : 'Save'}
                    </button>
                    <button class="btn small" type="button" on:click={() => { editingKey = null; rowError = ''; }} disabled={busy}>Cancel</button>
                  </div>
                {:else if item.label}
                  <span class="dest-label">{item.label}</span>
                {:else}
                  <span class="file-meta">No label</span>
                {/if}
              </td>
              <td data-label="Messages">{item.message_count}</td>
              <td data-label="Last used">{item.last_used_at ? formatTimestamp(item.last_used_at) : 'Label only'}</td>
              <td data-label="Actions">
                <div class="actions-cell">
                  {#if editingKey !== key}
                    <button class="btn small" type="button" on:click={() => startEdit(item)} disabled={busy}>
                      {item.label ? 'Rename' : 'Assign label'}
                    </button>
                  {/if}
                  {#if item.label}
                    <button class="btn small danger" type="button" on:click={() => removeLabel(item)} disabled={busy}>
                      {busy ? 'Removing…' : 'Remove'}
                    </button>
                  {/if}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="history-note" style="margin-top:10px">
      A destination can have only one label per channel, and a label can be used only once per channel.
      Removing a label leaves all historical messages untouched; it reappears automatically when the same
      normalized destination is used again.
    </p>
  {/if}
</section>
