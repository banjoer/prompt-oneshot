package dev.oneshot.outbox.web;

import dev.oneshot.outbox.config.DatabaseInitializer;
import dev.oneshot.outbox.config.OutboxProperties;
import dev.oneshot.outbox.service.WebhookService;
import dev.oneshot.outbox.util.Times;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.lang.management.ManagementFactory;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class SystemController {
    private final OutboxProperties properties;
    private final DatabaseInitializer database;
    private final WebhookService webhooks;
    private final Instant startedAt = Instant.now();

    @Value("${server.port:8000}")
    private int port;

    public SystemController(OutboxProperties properties, DatabaseInitializer database, WebhookService webhooks) {
        this.properties = properties;
        this.database = database;
        this.webhooks = webhooks;
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> db = new LinkedHashMap<>(database.status());
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("status", "ok");
        out.put("time", Times.nowIso());
        out.put("database", db);
        out.put("pending_webhooks", webhooks.pendingCount());
        return out;
    }

    @GetMapping("/info")
    public Map<String, Object> info() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("service", "human-in-the-loop-outbox");
        out.put("version", "1.0.0");
        out.put("runtime", "Java " + System.getProperty("java.version") + " / Spring Boot");
        out.put("started_at", Times.iso(startedAt));
        out.put("uptime_seconds", Duration.between(startedAt, Instant.now()).toSeconds());
        out.put("port", port);
        out.put("data_dir", properties.getDataDir());
        out.put("attachment_dir", properties.getAttachmentDir());
        out.put("max_attachment_bytes", properties.getMaxAttachmentBytes());
        out.put("max_message_attachment_bytes", properties.getMaxMessageAttachmentBytes());
        out.put("expiration_interval_seconds", properties.getExpirationIntervalSeconds());
        out.put("webhook_timeout_seconds", properties.getWebhookTimeoutSeconds());
        out.put("webhook_max_attempts", properties.getWebhookMaxAttempts());
        out.put("webhook_backoff_base_seconds", properties.getWebhookBackoffBaseSeconds());
        out.put("download_timeout_seconds", properties.getDownloadTimeoutSeconds());
        out.put("max_redirects", properties.getMaxRedirects());
        out.put("allow_private_urls", properties.isAllowPrivateUrls());
        out.put("handoff_url_max_chars", properties.getHandoffUrlMaxChars());
        out.put("built_at", properties.getBuiltAt());
        out.put("built_by", properties.getBuiltBy());
        out.put("schema", database.status());
        out.put("auth", "none (local single-user deployment)");
        out.put("provider_integrations", "none — handoff links only");
        out.put("jvm", Map.of(
                "version", System.getProperty("java.version"),
                "vendor", System.getProperty("java.vendor"),
                "pid", ManagementFactory.getRuntimeMXBean().getPid()));
        return out;
    }
}
