package dev.oneshot.outbox.model;

public record StatusChange(
        long id,
        String messageId,
        String fromStatus,
        String toStatus,
        String reason,
        int revisionNumber,
        String createdAt
) {}

