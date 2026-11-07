package dev.oneshot.outbox.model;

public record DestinationLabel(
        long id,
        String channel,
        String normalizedDestination,
        String label,
        String createdAt,
        String updatedAt
) {}

