package dev.oneshot.outbox.model;

import dev.oneshot.outbox.web.ApiException;

import java.util.List;
import java.util.Locale;

public enum MessageStatus {
    PENDING("pending"),
    APPROVED("approved"),
    SENT("sent"),
    REJECTED("rejected"),
    STALE("stale"),
    CANCELLED("cancelled");

    private final String wire;

    MessageStatus(String wire) { this.wire = wire; }

    public String wire() { return wire; }

    public boolean isTerminal() {
        return this == SENT || this == STALE || this == CANCELLED;
    }

    public static MessageStatus parse(String value) {
        if (value == null || value.isBlank()) {
            throw ApiException.badRequest("status must not be empty.");
        }
        String normalized = value.trim().toLowerCase(Locale.ROOT);
        for (MessageStatus status : values()) {
            if (status.wire.equals(normalized)) return status;
        }
        throw ApiException.badRequest("Invalid status '" + value + "'.");
    }

    public static MessageStatus fromDb(String value) {
        for (MessageStatus status : values()) {
            if (status.wire.equals(value)) return status;
        }
        throw new IllegalStateException("Unknown status in database: " + value);
    }

    public List<String> allowedActions() {
        return switch (this) {
            case PENDING -> List.of("approve", "reject", "cancel", "patch");
            case APPROVED -> List.of("mark_sent", "cancel", "handoff");
            case REJECTED -> List.of("cancel", "patch");
            case SENT, STALE, CANCELLED -> List.of();
        };
    }
}
