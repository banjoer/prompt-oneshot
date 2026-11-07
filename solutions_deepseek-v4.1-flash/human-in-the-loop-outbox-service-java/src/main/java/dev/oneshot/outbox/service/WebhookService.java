package dev.oneshot.outbox.service;

import dev.oneshot.outbox.config.OutboxProperties;
import dev.oneshot.outbox.model.MessageRecord;
import dev.oneshot.outbox.model.WebhookEvent;
import dev.oneshot.outbox.repo.WebhookRepository;
import dev.oneshot.outbox.security.UrlGuard;
import dev.oneshot.outbox.util.Json;
import dev.oneshot.outbox.util.Times;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Persists webhook events with the state change and delivers them asynchronously.
 * Failures never roll back the state change; every attempt is recorded.
 */
@Service
public class WebhookService {
    private static final Logger log = LoggerFactory.getLogger(WebhookService.class);

    private final WebhookRepository repository;
    private final OutboxProperties properties;
    private final Json json;
    private final UrlGuard guard;
    private final HttpClient client;
    private final AtomicBoolean wake = new AtomicBoolean(false);

    public WebhookService(WebhookRepository repository, OutboxProperties properties, Json json, UrlGuard guard) {
        this.repository = repository;
        this.properties = properties;
        this.json = json;
        this.guard = guard;
        this.client = HttpClient.newBuilder()
                .followRedirects(HttpClient.Redirect.NEVER)
                .connectTimeout(Duration.ofSeconds(Math.max(1, properties.getWebhookTimeoutSeconds())))
                .build();
    }

    /**
     * Inserts the event in the caller's transaction. The idempotency key
     * (message_id, event, revision_number) makes repeated transitions safe.
     */
    @Transactional
    public void enqueue(MessageRecord message, String event, Map<String, Object> extraDetails) {
        if (message.webhookUrl() == null || message.webhookUrl().isBlank()) return;
        String now = Times.nowIso();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("event", event);
        payload.put("message_id", message.id());
        payload.put("status", message.status().wire());
        payload.put("revision_number", message.revisionNumber());
        payload.put("timestamp", now);
        payload.put("channel", message.channel().wire());
        payload.put("destination", message.destination());
        payload.put("destination_label", message.destinationLabel());
        if (message.expiresAt() != null) payload.put("expires_at", message.expiresAt());
        if (extraDetails != null) {
            for (Map.Entry<String, Object> entry : extraDetails.entrySet()) {
                if (!payload.containsKey(entry.getKey())) payload.put(entry.getKey(), entry.getValue());
            }
        }
        String id = Times.newId("wh_");
        boolean inserted = repository.insertEventIfAbsent(id, message.id(), event,
                message.revisionNumber(), json.write(payload), now);
        if (inserted) {
            wake.set(true);
            log.info("Queued webhook {} for {} revision {}", event, message.id(), message.revisionNumber());
        }
    }

    public void wake() {
        wake.set(true);
    }

    @Scheduled(fixedDelayString = "${outbox.webhook-worker-interval-ms:300}")
    public void deliverDue() {
        if (wake.compareAndSet(true, false)) {
            // The scheduled poll would also pick the event up; this simply makes it prompt.
        }
        int processed = 0;
        while (processed < 10) {
            WebhookEvent event = repository.nextDue(Times.nowIso(), properties.getWebhookMaxAttempts());
            if (event == null) return;
            try {
                deliverOne(event);
            } catch (Exception ex) {
                log.error("Webhook worker failed for event {}", event.id(), ex);
            }
            processed++;
        }
    }

    public void deliverOne(WebhookEvent event) {
        String url = repository.webhookUrlFor(event.messageId());
        int attemptNumber = event.attemptsCount() + 1;
        String startedAt = Times.nowIso();
        if (url == null || url.isBlank()) {
            repository.recordAttempt(event.id(), attemptNumber, "skipped", null,
                    "Message has no webhook URL.", startedAt, Times.nowIso());
            repository.markAttemptFailed(event.id(), attemptNumber, null,
                    "Message has no webhook URL.", null);
            return;
        }

        int httpStatus = 0;
        String error = null;
        try {
            URI target = guard.validateWebhook(url);
            HttpRequest request = HttpRequest.newBuilder(target)
                    .timeout(Duration.ofSeconds(Math.max(1, properties.getWebhookTimeoutSeconds())))
                    .header("Content-Type", "application/json")
                    .header("User-Agent", "outbox-webhook/1.0")
                    .header("Idempotency-Key",
                            event.messageId() + ":" + event.event() + ":" + event.revisionNumber())
                    .POST(HttpRequest.BodyPublishers.ofString(event.payload()))
                    .build();
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            httpStatus = response.statusCode();
            if (httpStatus < 200 || httpStatus >= 300) {
                error = "Webhook endpoint returned HTTP " + httpStatus + ".";
            }
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            error = "Webhook delivery was interrupted.";
        } catch (Exception ex) {
            error = ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage();
        }

        String finishedAt = Times.nowIso();
        if (error == null) {
            repository.recordAttempt(event.id(), attemptNumber, "delivered", httpStatus, null,
                    startedAt, finishedAt);
            repository.markDelivered(event.id(), attemptNumber, httpStatus, finishedAt);
            log.info("Delivered webhook {} ({} attempt {})", event.id(), event.event(), attemptNumber);
            return;
        }

        String trimmed = error.length() > 1000 ? error.substring(0, 1000) : error;
        boolean exhausted = attemptNumber >= properties.getWebhookMaxAttempts();
        String nextAttemptAt = exhausted ? null : nextAttempt(attemptNumber);
        repository.recordAttempt(event.id(), attemptNumber, "failed", httpStatus == 0 ? null : httpStatus,
                trimmed, startedAt, finishedAt);
        repository.markAttemptFailed(event.id(), attemptNumber, httpStatus == 0 ? null : httpStatus,
                trimmed, nextAttemptAt);
        log.warn("Webhook {} attempt {} failed: {}", event.id(), attemptNumber, trimmed);
    }

    private String nextAttempt(int attemptNumber) {
        double base = Math.max(0.05, properties.getWebhookBackoffBaseSeconds());
        double delaySeconds = Math.min(3600, base * Math.pow(2, attemptNumber - 1));
        Instant next = Instant.now().plusMillis((long) Math.ceil(delaySeconds * 1000));
        return Times.iso(next);
    }

    public List<Map<String, Object>> eventsFor(String messageId) {
        return repository.findByMessage(messageId).stream().map(event -> {
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("id", event.id());
            out.put("event", event.event());
            out.put("revision_number", event.revisionNumber());
            out.put("created_at", event.createdAt());
            out.put("delivered_at", event.deliveredAt());
            out.put("delivered", event.deliveredAt() != null);
            out.put("attempts_count", event.attemptsCount());
            out.put("next_attempt_at", event.nextAttemptAt());
            out.put("last_error", event.lastError());
            out.put("payload", json.mapper().valueToTree(json.readTree(event.payload())));
            out.put("attempts", repository.attempts(event.id()).stream().map(attempt -> {
                Map<String, Object> a = new LinkedHashMap<>();
                a.put("attempt_number", attempt.attemptNumber());
                a.put("status", attempt.status());
                a.put("http_status", attempt.httpStatus());
                a.put("error", attempt.error());
                a.put("started_at", attempt.startedAt());
                a.put("finished_at", attempt.finishedAt());
                return a;
            }).toList());
            return out;
        }).toList();
    }

    public int pendingCount() {
        return repository.countPending(Times.nowIso(), properties.getWebhookMaxAttempts());
    }
}
