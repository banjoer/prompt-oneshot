export const STATUS = {
  pending: { label: 'Pending', icon: '◷', tone: 'pending', note: 'Waiting for review' },
  approved: { label: 'Approved', icon: '✓', tone: 'approved', note: 'Ready for handoff' },
  rejected: { label: 'Rejected', icon: '✕', tone: 'rejected', note: 'Returned for revision' },
  sent: { label: 'Sent', icon: '➤', tone: 'sent', note: 'Terminal — confirmed by a human' },
  stale: { label: 'Stale', icon: '△', tone: 'stale', note: 'Terminal — expired before sending' },
  cancelled: { label: 'Cancelled', icon: '⊘', tone: 'cancelled', note: 'Terminal — withdrawn by a reviewer' }
};

export const CHANNELS = {
  email: { label: 'Email', icon: '✉' },
  whatsapp: { label: 'WhatsApp', icon: '✆' },
  telegram: { label: 'Telegram', icon: '➤' }
};

export function statusInfo(status) {
  return STATUS[status] || { label: status || 'Unknown', icon: '?', tone: 'neutral', note: '' };
}

export function channelInfo(channel) {
  return CHANNELS[channel] || { label: channel || 'Unknown', icon: '•' };
}

export function isTerminal(status) {
  return status === 'sent' || status === 'stale' || status === 'cancelled';
}

export function formatTimestamp(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    timeZoneName: 'short'
  }).format(date);
}

export function formatDate(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'short', day: '2-digit'
  }).format(date);
}

export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function remaining(expiresAt, now = Date.now()) {
  if (!expiresAt) return null;
  const target = new Date(expiresAt).getTime();
  if (Number.isNaN(target)) return null;
  const ms = target - now;
  if (ms <= 0) return 'expired';
  const minutes = Math.floor(ms / 60000);
  if (minutes < 1) return 'less than a minute left';
  if (minutes < 60) return `${minutes}m left`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours}h ${minutes % 60}m left`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h left`;
}

export function timezoneLabel() {
  try {
    const parts = new Intl.DateTimeFormat(undefined, { timeZoneName: 'short' }).formatToParts(new Date());
    return parts.find((part) => part.type === 'timeZoneName')?.value || '';
  } catch {
    return '';
  }
}

export async function copyText(text) {
  if (text === null || text === undefined) return false;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(String(text));
      return true;
    }
  } catch {
    // Fall through to the legacy path.
  }
  try {
    const area = document.createElement('textarea');
    area.value = String(text);
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(area);
    return ok;
  } catch {
    return false;
  }
}
