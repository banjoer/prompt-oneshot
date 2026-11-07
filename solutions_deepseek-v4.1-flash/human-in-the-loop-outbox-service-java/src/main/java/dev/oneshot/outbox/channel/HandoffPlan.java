package dev.oneshot.outbox.channel;

import java.util.List;

/** Structured handoff data produced by a channel adapter and consumed by the SPA. */
public record HandoffPlan(
        String handoffUrl,
        boolean prefillRecipient,
        boolean prefillSubject,
        boolean prefillBody,
        String targetDisplay,
        List<String> manualActions,
        List<String> warnings,
        String transportNote
) {}

