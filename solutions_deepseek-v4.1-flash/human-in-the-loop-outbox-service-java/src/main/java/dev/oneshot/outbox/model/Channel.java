package dev.oneshot.outbox.model;

import dev.oneshot.outbox.web.ApiException;

import java.util.Locale;

public enum Channel {
    EMAIL("email"),
    WHATSAPP("whatsapp"),
    TELEGRAM("telegram");

    private final String wire;

    Channel(String wire) { this.wire = wire; }

    public String wire() { return wire; }

    public static Channel parse(String value) {
        if (value == null || value.isBlank()) {
            throw ApiException.badRequest("channel is required and must be one of: email, whatsapp, telegram.");
        }
        String normalized = value.trim().toLowerCase(Locale.ROOT);
        for (Channel channel : values()) {
            if (channel.wire.equals(normalized)) return channel;
        }
        throw ApiException.badRequest("Invalid channel '" + value + "'. Use email, whatsapp, or telegram.");
    }
}
