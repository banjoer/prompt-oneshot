package dev.oneshot.outbox.channel;

import dev.oneshot.outbox.util.Percent;
import dev.oneshot.outbox.web.ApiException;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

@Component
public class WhatsAppAdapter implements ChannelAdapter {

    @Override
    public String channel() { return "whatsapp"; }

    @Override
    public NormalizedDestination normalize(String destination) {
        if (destination == null || destination.isBlank()) {
            throw ApiException.badRequest("A WhatsApp destination is required.");
        }
        String trimmed = destination.trim();
        if (trimmed.toLowerCase(Locale.ROOT).startsWith("group:")) {
            String name = trimmed.substring("group:".length()).trim().replaceAll("\\s+", " ");
            if (name.isEmpty()) {
                throw ApiException.badRequest("WhatsApp group destination must include a group name, e.g. group:Project Alpha.");
            }
            if (name.length() > 120) {
                throw ApiException.badRequest("WhatsApp group name is too long (maximum 120 characters).");
            }
            rejectControlChars(name, "WhatsApp group name");
            return new NormalizedDestination("group:" + name, "group:" + name.toLowerCase(Locale.ROOT),
                    DestinationKind.GROUP, "WhatsApp group: " + name);
        }
        String cleaned = trimmed.replaceAll("[\\s().\\-]", "");
        if (cleaned.startsWith("00")) cleaned = cleaned.substring(2);
        boolean plus = cleaned.startsWith("+");
        String digits = plus ? cleaned.substring(1) : cleaned;
        if (!digits.matches("[0-9]{7,15}")) {
            throw ApiException.badRequest("Invalid WhatsApp destination '" + trimmed
                    + "'. Use an international phone number with 7–15 digits (e.g. +1 415 555 0123) "
                    + "or group:<name> for a group.");
        }
        if (digits.charAt(0) == '0') {
            throw ApiException.badRequest("WhatsApp phone numbers must be international, without a leading 0. "
                    + "Use the country code, e.g. +14155550123.");
        }
        return new NormalizedDestination(trimmed, digits, DestinationKind.INDIVIDUAL, trimmed);
    }

    @Override
    public HandoffPlan handoff(dev.oneshot.outbox.model.MessageRecord message,
                               List<dev.oneshot.outbox.model.AttachmentRecord> attachments,
                               int maxUrlChars) {
        if (message.destination().toLowerCase(Locale.ROOT).startsWith("group:")) {
            String name = message.destination().substring("group:".length()).trim();
            List<String> warnings = new ArrayList<>();
            warnings.add("WhatsApp does not offer a public link that preselects a group or prefills a group message.");
            warnings.add("Open WhatsApp, choose the group named below, then paste the copied body.");
            warnings.add("Opening WhatsApp or downloading attachments does not change the message status.");
            List<String> manual = new ArrayList<>();
            manual.add("Open WhatsApp Web or the WhatsApp app.");
            manual.add("Select the group \"" + name + "\" in WhatsApp yourself.");
            manual.add("Use Copy body, then paste the message into the group chat.");
            if (!attachments.isEmpty()) {
                manual.add("Download the " + attachments.size()
                        + " attachment(s) and attach them manually in WhatsApp.");
            }
            manual.add("Press Send in WhatsApp yourself.");
            return new HandoffPlan("https://web.whatsapp.com/", false, false, false,
                    "WhatsApp group: " + name, manual, warnings,
                    "Manual group fallback — no recipient preselection and no text prefill is possible.");
        }

        String digits = message.normalizedDestination();
        String body = message.body() == null ? "" : message.body();
        String full = "https://wa.me/" + digits + "?text=" + Percent.encode(body);
        String bare = "https://wa.me/" + digits;
        List<String> warnings = new ArrayList<>();
        warnings.add("wa.me opens a chat with this number; you must press Send in WhatsApp yourself.");
        warnings.add("Opening this link or downloading attachments does not change the message status.");
        if (message.subject() != null && !message.subject().isBlank()) {
            warnings.add("WhatsApp has no subject line. Only the body is used; the subject is available to copy.");
        }
        String url;
        boolean prefillBody = true;
        if (full.length() > maxUrlChars) {
            url = bare;
            prefillBody = false;
            warnings.add("The body is too long for a safe wa.me URL. Use Copy body and paste it into WhatsApp.");
        } else {
            url = full;
        }
        List<String> manual = new ArrayList<>();
        manual.add("Open the prepared WhatsApp link to start a chat with the recipient.");
        manual.add("If the chat does not contain the text, use Copy body and paste it in WhatsApp.");
        if (!attachments.isEmpty()) {
            manual.add("Download the " + attachments.size()
                    + " attachment(s) and attach them manually in WhatsApp; wa.me links cannot attach files.");
        }
        manual.add("Press Send in WhatsApp yourself.");
        return new HandoffPlan(url, true, false, prefillBody, message.destination(), manual, warnings,
                "wa.me deep link — recipient is preselected; text is prefilled in the URL when short enough. "
                        + "Attachments are never transferred.");
    }

    private static void rejectControlChars(String value, String label) {
        for (int i = 0; i < value.length(); i++) {
            if (value.charAt(i) < 0x20 || value.charAt(i) == 0x7f) {
                throw ApiException.badRequest(label + " must not contain control characters.");
            }
        }
    }
}
