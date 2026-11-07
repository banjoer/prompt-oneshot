package dev.oneshot.outbox.model;

public record WebhookAttempt(
        long id,
        String eventId,
        int attemptNumber,
        String status,
        Integer httpStatus,
        String error,
        String startedAt,
        String finishedAt
) {}

