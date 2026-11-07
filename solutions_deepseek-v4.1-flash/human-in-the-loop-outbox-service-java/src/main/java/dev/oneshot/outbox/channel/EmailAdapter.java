package dev.oneshot.outbox.channel;

import dev.oneshot.outbox.model.Channel;
import dev.oneshot.outbox.web.ApiException;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;

@Component
public class EmailAdapter implements ChannelAdapter {
    private static final Pattern EMAIL = Pattern.compile(
            "^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\\.)+[A-Za-z]{2,63}$");

    @Override
    public String channel() { return "email"; }

    @Override
    public NormalizedDestination normalize(String destination) {
        if (destination == null || destination.isBlank()) {
            throw ApiException.badRequest("A destination email address is required.");
        }
        String trimmed = destination.trim();
        if (trimmed.length() > 320) {
            throw ApiException.badRequest("Email destination is too long (maximum 320 characters).");
        }
        if (!EMAIL.matcher(trimmed).matches()) {
            throw ApiException.badRequest("Invalid email destination '" + trimmed
                    + "'. Use a single address such as alex@example.com (no display names or lists).");
        }
        if (trimmed.contains("..")) {
            throw ApiException.badRequest("Invalid email destination '" + trimmed
                    + "': consecutive dots are not allowed.");
        }
        return new NormalizedDestination(trimmed, trimmed.toLowerCase(Locale.ROOT),
                DestinationKind.INDIVIDUAL, trimmed);
    }

    @Override
    public HandoffPlan handoff(dev.oneshot.outbox.model.MessageRecord message,
                               List<dev.oneshot.outbox.model.AttachmentRecord> attachments,
                               int maxUrlChars) {
        String body = message.body() == null ? "" : message.body();
        String subject = message.subject() == null ? "" : message.subject();
        String recipient = message.destination();

        String full = "mailto:" + recipient + "?subject=" + dev.oneshot.outbox.util.Percent.encode(subject)
                + "&body=" + dev.oneshot.outbox.util.Percent.encode(body);
        String subjectOnly = "mailto:" + recipient + "?subject=" + dev.oneshot.outbox.util.Percent.encode(subject);
        String recipientOnly = "mailto:" + recipient;

        List<String> warnings = new ArrayList<>();
        warnings.add("mailto: opens your default email client. The service never sends anything.");
        warnings.add("Opening this link or downloading attachments does not change the message status.");
        String url;
        boolean prefillSubject = true;
        boolean prefillBody = true;
        if (full.length() <= maxUrlChars) {
            url = full;
        } else if (subjectOnly.length() <= maxUrlChars) {
            url = subjectOnly;
            prefillBody = false;
            warnings.add("The body is too long for a safe mailto: URL (" + full.length()
                    + " characters). Use Copy body and paste it into the email client.");
        } else {
            url = recipientOnly;
            prefillBody = false;
            prefillSubject = false;
            warnings.add("Subject and body are too long for a safe mailto: URL. Use Copy subject and Copy body, "
                    + "then paste them into the email client.");
        }

        List<String> manual = new ArrayList<>();
        manual.add("Open the prepared mailto: link, or compose a new email in your email client.");
        if (!attachments.isEmpty()) {
            manual.add("Download the " + attachments.size()
                    + " attachment(s) below and attach them manually: mailto: links cannot carry files.");
        }
        manual.add("Review the recipient, subject, body, and files in your email client, then press Send yourself.");

        return new HandoffPlan(url, true, prefillSubject, prefillBody,
                recipient, manual, warnings,
                "mailto: link — recipient, subject and body are prefilled where length permits. "
                        + "Attachments are never transferred by mailto:.");
    }
}
