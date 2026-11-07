<script>
  import { tick } from 'svelte';

  export let open = false;
  export let title = '';
  export let subtitle = '';
  export let onclose = () => {};
  export let busy = false;
  export let labelledBy = 'modal-title-' + Math.random().toString(36).slice(2);

  let dialog;
  let previousFocus = null;

  $: if (open) {
    openChanged(true);
  } else {
    openChanged(false);
  }

  let wasOpen = false;
  function openChanged(isOpen) {
    if (isOpen === wasOpen) return;
    wasOpen = isOpen;
    if (isOpen) {
      previousFocus = document.activeElement;
      tick().then(() => {
        const focusable = dialog?.querySelector(
          'input:not([type="hidden"]), textarea, select, button:not(:disabled)'
        );
        focusable?.focus();
      });
    } else if (previousFocus instanceof HTMLElement) {
      previousFocus.focus();
      previousFocus = null;
    }
  }

  function handleKeydown(event) {
    if (!open) return;
    if (event.key === 'Escape' && !busy) {
      event.preventDefault();
      onclose();
      return;
    }
    if (event.key !== 'Tab' || !dialog) return;
    const nodes = [...dialog.querySelectorAll(
      'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'
    )].filter((el) => el.offsetParent !== null);
    if (nodes.length === 0) return;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function backdropClick(event) {
    if (event.target === event.currentTarget && !busy) onclose();
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
  <div class="modal-backdrop" role="presentation" on:click={backdropClick} on:keydown={() => {}}>
    <div class="modal" bind:this={dialog} role="dialog" aria-modal="true" aria-labelledby={labelledBy}>
      <h2 id={labelledBy}>{title}</h2>
      {#if subtitle}<p class="modal-sub">{subtitle}</p>{/if}
      <slot />
    </div>
  </div>
{/if}
