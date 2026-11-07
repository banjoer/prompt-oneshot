package dev.oneshot.outbox.service;

import dev.oneshot.outbox.model.AttachmentRecord;
import dev.oneshot.outbox.model.DestinationLabel;
import dev.oneshot.outbox.model.MessageRecord;
import dev.oneshot.outbox.repo.DestinationRepository;
import dev.oneshot.outbox.repo.RevisionRepository;
import dev.oneshot.outbox.util.Json;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Builds the stable API representation of messages and attachments. */
@Component
public class MessagePresenter {
    private final RevisionRepository revisions;
    private final DestinationRepository destinations;
    private final Json json;

    public MessagePresenter(RevisionRepository revisions, DestinationRepository destinations, Json json) {
        this.revisions = revisions;
        this.destinations = destinations;
        this.json = json;
    }

    public Map<String, Object> detail(MessageRecord m) {
        List<AttachmentRecord> attachments =
                revisions.attachmentsForMessageRevision(m.id(), m.revisionNumber());
        List<String> references =
                revisions.referencesForMessageRevision(m.id(), m.revisionNumber());
        DestinationLabel managed = destinations.find(m.channel(), m.normalizedDestination());
        String managedLabel = managed == null ? null : managed.label();
        String displayLabel = managedLabel != null ? managedLabel : m.destinationLabel();

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", m.id());
        out.put("channel", m.channel().wire());
        out.put("destination", m.destination());
        out.put("normalized_destination", m.normalizedDestination());
        out.put("destination_label", m.destinationLabel());
        out.put("managed_label", managedLabel);
        out.put("display_label", displayLabel);
        out.put("subject", m.subject());
        out.put("body", m.body());
        out.put("status", m.status().wire());
        out.put("status_terminal", m.status().isTerminal());
        out.put("created_at", m.createdAt());
        out.put("updated_at", m.updatedAt());
        out.put("expires_at", m.expiresAt());
        out.put("expired", isExpired(m));
        out.put("webhook_url", m.webhookUrl());
        out.put("rejection_reason", m.rejectionReason());
        out.put("rejection_at", m.rejectionAt());
        out.put("revision_number", m.revisionNumber());
        out.put("source", m.source());
        out.put("metadata", metadata(m.metadata()));
        out.put("attachment_count", attachments.size());
        out.put("attachments", attachments.stream().map(a -> attachmentView(m.id(), a)).toList());
        out.put("references", references);
        out.put("allowed_actions", m.status().allowedActions());
        return out;
    }

    public Map<String, Object> summary(MessageRecord m) {
        List<AttachmentRecord> attachments =
                revisions.attachmentsForMessageRevision(m.id(), m.revisionNumber());
        DestinationLabel managed = destinations.find(m.channel(), m.normalizedDestination());
        String managedLabel = managed == null ? null : managed.label();

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", m.id());
        out.put("channel", m.channel().wire());
        out.put("destination", m.destination());
        out.put("normalized_destination", m.normalizedDestination());
        out.put("destination_label", m.destinationLabel());
        out.put("managed_label", managedLabel);
        out.put("display_label", managedLabel != null ? managedLabel : m.destinationLabel());
        out.put("subject", m.subject());
        out.put("body_preview", preview(m.body()));
        out.put("status", m.status().wire());
        out.put("status_terminal", m.status().isTerminal());
        out.put("created_at", m.createdAt());
        out.put("updated_at", m.updatedAt());
        out.put("expires_at", m.expiresAt());
        out.put("expired", isExpired(m));
        out.put("revision_number", m.revisionNumber());
        out.put("source", m.source());
        out.put("attachment_count", attachments.size());
        out.put("rejection_reason", m.rejectionReason());
        out.put("allowed_actions", m.status().allowedActions());
        return out;
    }

    public Map<String, Object> attachmentView(String messageId, AttachmentRecord a) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", a.id());
        out.put("filename", a.originalFilename());
        out.put("original_filename", a.originalFilename());
        out.put("mime_type", a.mimeType());
        out.put("size_bytes", a.sizeBytes());
        out.put("created_at", a.createdAt());
        out.put("source_type", a.sourceType());
        out.put("source_url", a.sourceUrl());
        out.put("storage_reference", a.storageName());
        out.put("storage_name", a.storageName());
        out.put("download_url", "/api/messages/" + messageId + "/attachments/" + a.id());
        return out;
    }

    public Map<String, Object> revisionView(dev.oneshot.outbox.model.RevisionRecord r) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("revision_number", r.revisionNumber());
        out.put("channel", r.channel().wire());
        out.put("destination", r.destination());
        out.put("normalized_destination", r.normalizedDestination());
        out.put("destination_label", r.destinationLabel());
        out.put("subject", r.subject());
        out.put("body", r.body());
        out.put("metadata", metadata(r.metadata()));
        out.put("expires_at", r.expiresAt());
        out.put("status", r.status().wire());
        out.put("rejection_reason", r.rejectionReason());
        out.put("rejection_at", r.rejectionAt());
        out.put("created_at", r.createdAt());
        out.put("attachments", r.attachments().stream()
                .map(a -> attachmentView(r.messageId(), a)).toList());
        out.put("references", r.references());
        return out;
    }

    @SuppressWarnings("unchecked")
    public Object metadata(String raw) {
        if (raw == null || raw.isBlank()) return null;
        try {
            return json.mapper().readValue(raw, Object.class);
        } catch (Exception ex) {
            return raw;
        }
    }

    public static boolean isExpired(MessageRecord m) {
        if (m.expiresAt() == null) return false;
        return m.expiresAt().compareTo(dev.oneshot.outbox.util.Times.nowIso()) <= 0;
    }

    private static String preview(String body) {
        if (body == null) return null;
        String oneLine = body.replaceAll("\\s+", " ").trim();
        return oneLine.length() <= 160 ? oneLine : oneLine.substring(0, 157) + "…";
    }

    public List<String> references(MessageRecord m) {
        return new ArrayList<>(revisions.referencesForMessageRevision(m.id(), m.revisionNumber()));
    }

    public List<AttachmentRecord> attachments(MessageRecord m) {
        return revisions.attachmentsForMessageRevision(m.id(), m.revisionNumber());
    }
}
