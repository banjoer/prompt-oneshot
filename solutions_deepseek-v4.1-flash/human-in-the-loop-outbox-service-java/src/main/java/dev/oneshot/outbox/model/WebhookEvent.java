package dev.oneshot.outbox.model;

public record WebhookEvent(
        String id,
        String messageId,
        String event,
        int revisionNumber,
        String payload,
        String createdAt,
        String deliveredAt,
        int attemptsCount,
        String nextAttemptAt,
        String lastError
) {}

