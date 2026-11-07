package dev.oneshot.outbox.channel;

import dev.oneshot.outbox.model.AttachmentRecord;
import dev.oneshot.outbox.model.MessageRecord;

import java.util.List;

public interface ChannelAdapter {
    String channel();

    NormalizedDestination normalize(String destination);

    HandoffPlan handoff(MessageRecord message, List<AttachmentRecord> attachments, int maxUrlChars);
}
