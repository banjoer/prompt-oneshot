package dev.oneshot.outbox.channel;

import java.util.List;

/** Result of validating and normalizing a destination for a channel. */
public record NormalizedDestination(
        String destination,
        String normalized,
        DestinationKind kind,
        String targetDisplay
) {}

