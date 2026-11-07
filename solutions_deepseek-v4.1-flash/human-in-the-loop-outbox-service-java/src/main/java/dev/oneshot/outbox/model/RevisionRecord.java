package dev.oneshot.outbox.model;

import java.util.List;

public record RevisionRecord(
        long id,
        String messageId,
        int revisionNumber,
        Channel channel,
        String destination,
        String normalizedDestination,
        String destinationLabel,
        String subject,
        String body,
        String metadata,
        String expiresAt,
        String rejectionReason,
        String rejectionAt,
        MessageStatus status,
        String createdAt,
        List<AttachmentRecord> attachments,
        List<String> references
) {}

