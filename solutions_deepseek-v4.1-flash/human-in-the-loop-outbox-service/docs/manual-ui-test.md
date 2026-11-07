# Manual frontend test script

Run the service at `http://127.0.0.1:8000`. Use two browser viewport sizes:

- desktop: **1440 × 900**
- phone: **390 × 844**

At every step check that the page has no horizontal scrollbar, focus is visible, and there are no errors in the browser console.

## Setup

1. Start the service with a clean data directory:
   ```bash
   rm -rf data
   ALLOW_PRIVATE_URLS=1 python3 app.py
   ```
2. In another terminal start the local download fixture:
   ```bash
   python3 -m http.server 9001 --directory fixtures
   ```
3. Optionally start the webhook sink:
   ```bash
   python3 fixtures/webhook_sink.py
   ```
4. Submit one message per channel (see README curl examples), including an email with an attachment, a WhatsApp group, a Telegram group, and a message with a short TTL. Keep IDs in a scratch file.

## 1. Queue and filters

- Load `/`. The header and footer are visible. The footer shows “Built … by DeepSeek V4.1 Flash”.
- Default queue shows active messages only (pending, approved, rejected), pending cards first, then approved, then rejected.
- Each card shows status text (not just colour), channel, destination or label, subject, body preview, created time, expiry/time remaining, revision, attachment count.
- Switch status filter to “All statuses”; terminal cards appear. Switch back to “Active”.
- Filter by channel, destination substring, label, created date range and expiry date range. Apply/Reset work.
- Change sort to oldest, expiring soonest, expiring latest. No-expiration messages appear last for both expiry sorts.
- Use Previous/Next; the “Showing x–y of z” text updates and disabled buttons do not respond.
- Press Refresh; the list reloads with a short loading state.
- At 390 px width there is no horizontal page scrolling; filters wrap and cards stack.

## 2. Detail review

- Click/Enter a pending card. The drawer/sheet opens and focus moves into it.
- Verify full body, subject, destination, managed label (or snapshot), channel, source, metadata table, created/updated/expiry, attachments, references, revision history and status history.
- There are no inputs for editing body, subject, destination or attachments.
- Press Escape; the drawer closes and focus returns to the card.
- Reopen and check the Close button works too.

## 3. Approve and handoff

- On a pending email choose **Approve for handoff**.
- Confirm the status changes to Approved and the handoff panel appears without a page reload.
- Check the capability grid: recipient/subject/body prefilled, attachments carried “No”.
- Check warnings and numbered manual steps. For an attachment, the instruction says to download and attach manually.
- Click **Copy subject** and **Copy body**, then paste into a scratch editor; newlines and special characters survive.
- Click **Open prepared email**. Your mail client opens with the fields prefilled (or the documented shortened link for a very long body). Return to the browser.
- Download an attachment and the ZIP. Return to the browser.
- Refresh or re-fetch the message: it is still **approved**. Opening a link/downloading a file must not mark it sent.

## 4. Mark sent

- Click **Mark as sent…**. A confirmation dialog opens with an unchecked statement.
- Clicking **Yes, mark as sent** without ticking the checkbox shows an inline error and does nothing.
- Tick the checkbox, confirm. Status becomes `sent`, the delivery actions disappear, and status history gains Approved → Sent.
- Repeat mark-sent or cancel on this terminal message through the API; both return `409`.

## 5. Reject and revise

- On another pending message choose **Reject with reason…**.
- Confirm is blocked with an empty reason. Enter a reason and confirm.
- Status becomes Rejected; the rejection reason and timestamp are visible; no delivery actions are offered; Cancel remains.
- Use curl PATCH to revise the message. Refresh the queue and open it again.
- The message is Pending, revision 2; revision 1 is still expandable in history with its rejection reason and original body.
- Status history shows Rejected → Pending.

## 6. Expiration

- Submit an email with `ttl_seconds: 2`; open it before expiry.
- Wait at least 2 seconds, then refresh the queue. The card leaves the Active filter.
- Filter to Stale and open it. Content, attachments and history remain.
- Approve/handoff attempts via API return `409`; the UI shows no pending/approved actions.
- A message without expiration stays active.

## 7. WhatsApp and Telegram handoffs

- Approve the WhatsApp individual message. The Open button opens `wa.me` with the normalized international number and prefilled text.
- Approve the WhatsApp group message. The panel says manual fallback; no preselection is claimed; the group name appears in the manual steps; copy and attachment controls exist.
- Approve the Telegram `@username` message. The link is a `t.me` deep link with text where supported.
- Approve the Telegram group and private-invite messages. The panel shows a manual fallback, names the group (when applicable), and does not claim preselection.

## 8. Destination labels

- Switch to **Destinations**. Known destinations show channel, normalized address, label, message count and last use.
- Assign a label. It appears on the card and in the queue/detail for matching destinations.
- Try to assign the same label (in any case) to another destination in the same channel; a clear conflict error appears and nothing changes.
- Rename the label; works. Remove the label; the destination remains, messages remain intact, and the label can be assigned again.

## 9. Modals, keyboard and reduced motion

- Open Reject, then Cancel, then Mark as sent. Each has a clear title, explanation, Cancel and destructive/primary confirm.
- Tab inside an open modal stays within it; Shift+Tab wraps. Escape closes it and focus returns to the trigger.
- Enable the operating system “reduce motion” setting and reload; transitions/skeletons are effectively disabled.
- Tab through the whole app: visible focus everywhere, labels announced, cards activate with Enter/Space, no focus traps outside modals.

## 10. Empty and error states

- Filter to a channel/date with no matches; a helpful empty state appears with a reset/next action.
- Stop the service and press Refresh; a readable error state with “Try again” appears and the console has no uncaught exceptions.
- Restart and retry; the queue recovers.
