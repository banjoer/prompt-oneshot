package dev.oneshot.outbox.model;

public record MessageRecord(
        String id,
        Channel channel,
        String destination,
        String normalizedDestination,
        String destinationLabel,
        String subject,
        String body,
        MessageStatus status,
        String createdAt,
        String updatedAt,
        String expiresAt,
        String webhookUrl,
        String rejectionReason,
        String rejectionAt,
        int revisionNumber,
        String source,
        String metadata
) {}

