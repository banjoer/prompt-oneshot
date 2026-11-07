package dev.oneshot.outbox.util;

import java.security.SecureRandom;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.time.temporal.ChronoUnit;
import java.util.HexFormat;

public final class Times {
    private Times() {}

    private static final DateTimeFormatter SECOND_FORMAT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'").withZone(ZoneOffset.UTC);

    /** Current instant truncated to whole seconds, UTC. */
    public static Instant now() {
        return Instant.now().truncatedTo(ChronoUnit.SECONDS);
    }

    public static String iso(Instant instant) {
        if (instant == null) return null;
        return SECOND_FORMAT.format(instant.truncatedTo(ChronoUnit.SECONDS));
    }

    public static String nowIso() {
        return iso(now());
    }

    /**
     * Parse an ISO-8601 instant or offset date-time into a UTC instant.
     * Throws IllegalArgumentException with a friendly message when unparseable.
     */
    public static Instant parse(String value) {
        if (value == null) return null;
        String trimmed = value.trim();
        if (trimmed.isEmpty()) throw new IllegalArgumentException("timestamp must not be empty");
        try {
            return Instant.parse(trimmed).truncatedTo(ChronoUnit.SECONDS);
        } catch (DateTimeParseException ignored) {
            // Fall through to offset date-time.
        }
        try {
            return OffsetDateTime.parse(trimmed).toInstant().truncatedTo(ChronoUnit.SECONDS);
        } catch (DateTimeParseException ex) {
            throw new IllegalArgumentException(
                    "Invalid timestamp '" + value + "'. Use ISO 8601 UTC, for example 2030-01-01T00:00:00Z.");
        }
    }

    public static Instant parseOrNull(String value) {
        if (value == null || value.isBlank()) return null;
        return parse(value);
    }

    public static String human(Instant instant) {
        return instant == null ? null : SECOND_FORMAT.format(instant);
    }

    private static final SecureRandom RANDOM = new SecureRandom();
    private static final HexFormat HEX = HexFormat.of();

    public static String newId(String prefix) {
        byte[] bytes = new byte[6];
        RANDOM.nextBytes(bytes);
        return prefix + HEX.formatHex(bytes);
    }
}
