package dev.oneshot.outbox.service;

import dev.oneshot.outbox.model.MessageRecord;
import dev.oneshot.outbox.model.MessageStatus;
import dev.oneshot.outbox.repo.MessageRepository;
import dev.oneshot.outbox.util.Times;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.List;
import java.util.Map;

/**
 * Expiration is checked on every read path and by a periodic worker. The
 * compare-and-set update ensures an approval and an expiration can never both win.
 */
@Service
public class ExpirationService {
    private static final Logger log = LoggerFactory.getLogger(ExpirationService.class);

    private final MessageRepository messages;
    private final WebhookService webhooks;
    private final TransactionTemplate transactions;

    public ExpirationService(MessageRepository messages, WebhookService webhooks,
                             TransactionTemplate transactions) {
        this.messages = messages;
        this.webhooks = webhooks;
        this.transactions = transactions;
    }

    public int expireDue() {
        String now = Times.nowIso();
        List<MessageRecord> due = messages.findDueForExpiration(now);
        int expired = 0;
        for (MessageRecord candidate : due) {
            if (expireOne(candidate.id())) expired++;
        }
        if (expired > 0) {
            log.info("Expired {} message(s)", expired);
        }
        return expired;
    }

    /** Expires a single message if it is still eligible. Returns true when it changed. */
    public boolean expireOne(String messageId) {
        Boolean changed = transactions.execute(status -> {
            String now = Times.nowIso();
            MessageRecord current = messages.findById(messageId);
            if (current == null) return false;
            if (current.status() != MessageStatus.PENDING && current.status() != MessageStatus.APPROVED) {
                return false;
            }
            if (current.expiresAt() == null || current.expiresAt().compareTo(now) > 0) return false;
            int rows = messages.expireCas(messageId, current.status(), now);
            if (rows != 1) return false;
            messages.insertStatusHistory(messageId, current.status().wire(), MessageStatus.STALE.wire(),
                    "expired at " + current.expiresAt(), current.revisionNumber(), now);
            MessageRecord stale = new MessageRecord(current.id(), current.channel(), current.destination(),
                    current.normalizedDestination(), current.destinationLabel(), current.subject(),
                    current.body(), MessageStatus.STALE, current.createdAt(), now, current.expiresAt(),
                    current.webhookUrl(), current.rejectionReason(), current.rejectionAt(),
                    current.revisionNumber(), current.source(), current.metadata());
            webhooks.enqueue(stale, "message.stale", Map.of("expires_at", current.expiresAt()));
            return true;
        });
        return Boolean.TRUE.equals(changed);
    }

    @Scheduled(fixedDelayString = "${outbox.expiration-interval-seconds:30}000",
            initialDelayString = "${outbox.expiration-interval-seconds:30}000")
    public void periodicExpiration() {
        try {
            expireDue();
        } catch (Exception ex) {
            log.error("Periodic expiration failed", ex);
        }
    }
}
