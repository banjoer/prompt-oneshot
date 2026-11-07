package dev.oneshot.outbox.channel;

import dev.oneshot.outbox.util.Percent;
import dev.oneshot.outbox.web.ApiException;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;

@Component
public class TelegramAdapter implements ChannelAdapter {
    private static final Pattern USERNAME = Pattern.compile("[A-Za-z][A-Za-z0-9_]{3,31}");
    private static final Pattern INVITE = Pattern.compile("[A-Za-z0-9_-]{6,64}");

    @Override
    public String channel() { return "telegram"; }

    @Override
    public NormalizedDestination normalize(String destination) {
        if (destination == null || destination.isBlank()) {
            throw ApiException.badRequest("A Telegram destination is required.");
        }
        String trimmed = destination.trim();
        if (trimmed.toLowerCase(Locale.ROOT).startsWith("group:")) {
            String name = trimmed.substring("group:".length()).trim().replaceAll("\\s+", " ");
            if (name.isEmpty()) {
                throw ApiException.badRequest("Telegram group destination must include a group name, e.g. group:Ops Room.");
            }
            if (name.length() > 120) {
                throw ApiException.badRequest("Telegram group name is too long (maximum 120 characters).");
            }
            return new NormalizedDestination("group:" + name, "group:" + name.toLowerCase(Locale.ROOT),
                    DestinationKind.GROUP, "Telegram group: " + name);
        }

        String username = null;
        String path = null;
        String lower = trimmed.toLowerCase(Locale.ROOT);
        for (String prefix : List.of("https://t.me/", "http://t.me/", "https://telegram.me/",
                "http://telegram.me/", "https://www.t.me/", "t.me/", "telegram.me/")) {
            if (lower.startsWith(prefix)) {
                path = trimmed.substring(prefix.length());
                break;
            }
        }
        if (path != null) {
            int query = path.indexOf('?');
            if (query >= 0) path = path.substring(0, query);
            int hash = path.indexOf('#');
            if (hash >= 0) path = path.substring(0, hash);
            path = path.replaceAll("/+$", "");
            if (path.startsWith("+")) {
                return privateInvite(path.substring(1), trimmed);
            }
            if (path.toLowerCase(Locale.ROOT).startsWith("joinchat/")) {
                return privateInvite(path.substring("joinchat/".length()), trimmed);
            }
            if (path.toLowerCase(Locale.ROOT).startsWith("c/")) {
                return privateGroup(path.substring(2), trimmed);
            }
            int slash = path.indexOf('/');
            if (slash > 0) path = path.substring(0, slash);
            username = path;
        } else if (trimmed.startsWith("@")) {
            username = trimmed.substring(1);
        } else {
            username = trimmed;
        }

        if (username == null || !USERNAME.matcher(username).matches()) {
            throw ApiException.badRequest("Invalid Telegram destination '" + trimmed
                    + "'. Use @username, https://t.me/username, or group:<name>. "
                    + "Private invites such as t.me/+hash are supported as a manual fallback.");
        }
        String normalized = username.toLowerCase(Locale.ROOT);
        return new NormalizedDestination("@" + normalized, normalized, DestinationKind.INDIVIDUAL,
                "@" + normalized);
    }

    private NormalizedDestination privateInvite(String hash, String original) {
        String clean = hash.trim();
        if (!INVITE.matcher(clean).matches()) {
            throw ApiException.badRequest("Invalid Telegram invite destination '" + original
                    + "'. Expected a t.me/+invite hash.");
        }
        return new NormalizedDestination(original, "invite:" + clean.toLowerCase(Locale.ROOT),
                DestinationKind.PRIVATE_INVITE, "Telegram private invite");
    }

    private NormalizedDestination privateGroup(String path, String original) {
        String clean = path.trim().replaceAll("/+$", "");
        if (clean.isEmpty() || clean.length() > 64 || !clean.matches("[A-Za-z0-9_/-]+")) {
            throw ApiException.badRequest("Invalid Telegram private group destination '" + original + "'.");
        }
        return new NormalizedDestination(original, "private:" + clean.toLowerCase(Locale.ROOT),
                DestinationKind.PRIVATE_INVITE, "Telegram private group");
    }

    @Override
    public HandoffPlan handoff(dev.oneshot.outbox.model.MessageRecord message,
                               List<dev.oneshot.outbox.model.AttachmentRecord> attachments,
                               int maxUrlChars) {
        String normalized = message.normalizedDestination();
        if (normalized.startsWith("group:")) {
            String name = message.destination().substring("group:".length()).trim();
            List<String> warnings = new ArrayList<>();
            warnings.add("Telegram does not offer a public link that preselects a group or prefills a group message.");
            warnings.add("Open Telegram, choose the group named below, then paste the copied body.");
            warnings.add("Opening Telegram or downloading attachments does not change the message status.");
            List<String> manual = new ArrayList<>();
            manual.add("Open Telegram Desktop, Telegram Web, or the Telegram app.");
            manual.add("Select the group \"" + name + "\" in Telegram yourself.");
            manual.add("Use Copy body, then paste the message into the group chat.");
            if (!attachments.isEmpty()) {
                manual.add("Download the " + attachments.size()
                        + " attachment(s) and attach them manually in Telegram.");
            }
            manual.add("Press Send in Telegram yourself.");
            return new HandoffPlan("https://web.telegram.org/", false, false, false,
                    "Telegram group: " + name, manual, warnings,
                    "Manual group fallback — no group preselection and no text prefill is possible.");
        }
        if (normalized.startsWith("invite:") || normalized.startsWith("private:")) {
            String url;
            if (normalized.startsWith("invite:")) {
                url = "https://t.me/+" + normalized.substring("invite:".length());
            } else {
                url = "https://web.telegram.org/";
            }
            List<String> warnings = new ArrayList<>();
            warnings.add("This Telegram chat is private. The link can only open or request to join it; "
                    + "it cannot preselect the chat or prefill a message.");
            warnings.add("Use Copy body and paste the message into the private chat yourself.");
            warnings.add("Opening the invite or downloading attachments does not change the message status.");
            List<String> manual = new ArrayList<>();
            manual.add("Open the Telegram invite link and join/open the intended private chat yourself.");
            manual.add("Use Copy body, then paste the message into the chat.");
            if (!attachments.isEmpty()) {
                manual.add("Download the " + attachments.size()
                        + " attachment(s) and attach them manually in Telegram.");
            }
            manual.add("Press Send in Telegram yourself.");
            return new HandoffPlan(url, false, false, false,
                    message.destination(), manual, warnings,
                    "Manual private-chat fallback — no recipient preselection or text prefill is possible.");
        }

        String username = normalized;
        String body = message.body() == null ? "" : message.body();
        String full = "https://t.me/" + username + "?text=" + Percent.encode(body);
        String bare = "https://t.me/" + username;
        List<String> warnings = new ArrayList<>();
        warnings.add("Some Telegram clients ignore ?text= on username links. If the draft is empty, use Copy body.");
        warnings.add("The service cannot verify that this username belongs to the intended person.");
        warnings.add("Opening this link or downloading attachments does not change the message status.");
        if (message.subject() != null && !message.subject().isBlank()) {
            warnings.add("Telegram has no subject line. Only the body is used; the subject is available to copy.");
        }
        String url;
        boolean prefillBody = true;
        if (full.length() > maxUrlChars) {
            url = bare;
            prefillBody = false;
            warnings.add("The body is too long for a safe t.me URL. Use Copy body and paste it into Telegram.");
        } else {
            url = full;
        }
        List<String> manual = new ArrayList<>();
        manual.add("Open the prepared t.me link to start a chat with @" + username + ".");
        manual.add("If the text was not prefilled, use Copy body and paste it into Telegram.");
        if (!attachments.isEmpty()) {
            manual.add("Download the " + attachments.size()
                    + " attachment(s) and attach them manually in Telegram; t.me links cannot attach files.");
        }
        manual.add("Press Send in Telegram yourself.");
        return new HandoffPlan(url, true, false, prefillBody, "@" + username, manual, warnings,
                "t.me deep link — recipient username is preselected; text is prefilled when supported "
                        + "and the URL stays within the safe length limit.");
    }
}
