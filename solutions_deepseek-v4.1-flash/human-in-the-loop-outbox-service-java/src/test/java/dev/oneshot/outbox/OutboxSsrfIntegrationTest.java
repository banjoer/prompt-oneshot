package dev.oneshot.outbox;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Separate context with the secure default (ALLOW_PRIVATE_URLS=0). Proves that
 * loopback, private, link-local and metadata destinations are rejected for both
 * webhooks and URL downloads, while references are never fetched at all.
 */
@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
                "outbox.allow-private-urls=false",
                "outbox.expiration-interval-seconds=1000",
                "outbox.webhook-worker-interval-ms=1000",
                "outbox.built-at=2026-11-07T00:00:00Z",
                "outbox.built-by=DeepSeek V4.1 Flash",
                "logging.level.root=WARN",
                "logging.level.dev.oneshot.outbox=WARN"
        })
class OutboxSsrfIntegrationTest {

    private static final Path ROOT = tempRoot();

    @DynamicPropertySource
    static void directories(DynamicPropertyRegistry registry) {
        registry.add("outbox.data-dir", () -> ROOT.resolve("data").toString());
        registry.add("outbox.attachment-dir", () -> ROOT.resolve("data/attachments").toString());
    }

    private static Path tempRoot() {
        try {
            return Files.createTempDirectory("outbox-ssrf-");
        } catch (IOException ex) {
            throw new IllegalStateException(ex);
        }
    }

    @LocalServerPort
    int port;

    @Autowired
    TestRestTemplate rest;

    @Autowired
    JdbcTemplate jdbc;

    @BeforeEach
    void clean() {
        jdbc.execute("DELETE FROM webhook_attempts");
        jdbc.execute("DELETE FROM webhook_events");
        jdbc.execute("DELETE FROM revision_references");
        jdbc.execute("DELETE FROM revision_attachments");
        jdbc.execute("DELETE FROM attachments");
        jdbc.execute("DELETE FROM status_history");
        jdbc.execute("DELETE FROM message_revisions");
        jdbc.execute("DELETE FROM messages");
        jdbc.execute("DELETE FROM destination_labels");
    }

    private String base() {
        return "http://127.0.0.1:" + port;
    }

    private ResponseEntity<Map<String, Object>> post(Map<String, Object> body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        return rest.exchange(base() + "/api/messages", HttpMethod.POST, new HttpEntity<>(body, headers),
                new ParameterizedTypeReference<>() {});
    }

    private Map<String, Object> payload() {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("channel", "email");
        body.put("destination", "ssrf@example.com");
        body.put("body", "check url safety");
        return body;
    }

    private String errorCode(ResponseEntity<Map<String, Object>> response) {
        return (String) ((Map<?, ?>) response.getBody().get("error")).get("code");
    }

    @Test
    void loopbackPrivateAndMetadataUrlsAreBlockedForWebhooksAndDownloads() {
        List<String> blocked = List.of(
                "http://127.0.0.1:9002/hook",
                "http://localhost:9002/hook",
                "http://10.0.0.5/file",
                "http://192.168.1.10/file",
                "http://169.254.169.254/latest/meta-data/",
                "http://0.0.0.0/file",
                "http://[::1]/file",
                "http://[fc00::1]/file",
                "http://metadata.google.internal/computeMetadata/v1/"
        );

        for (String url : blocked) {
            Map<String, Object> webhook = payload();
            webhook.put("webhook_url", url);
            ResponseEntity<Map<String, Object>> response = post(webhook);
            assertThat(response.getStatusCode().value()).as("webhook %s", url).isEqualTo(400);
            assertThat(errorCode(response)).as("webhook %s", url).isEqualTo("unsafe_url");

            Map<String, Object> download = payload();
            download.put("attachments", List.of(Map.of("kind", "url_download", "url", url)));
            ResponseEntity<Map<String, Object>> downloadResponse = post(download);
            assertThat(downloadResponse.getStatusCode().value()).as("download %s", url).isEqualTo(400);
            assertThat(errorCode(downloadResponse)).as("download %s", url).isEqualTo("unsafe_url");
        }

        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM messages", Integer.class)).isZero();
    }

    @Test
    void urlReferencesAreStoredWithoutBeingFetchedOrSsrFChecked() {
        Map<String, Object> body = payload();
        body.put("references", List.of("http://127.0.0.1:9001/never-fetched", "https://example.com/spec"));
        ResponseEntity<Map<String, Object>> response = post(body);
        assertThat(response.getStatusCode().value()).isEqualTo(201);
        assertThat((List<String>) response.getBody().get("references"))
                .containsExactly("http://127.0.0.1:9001/never-fetched", "https://example.com/spec");
        assertThat(response.getBody()).containsEntry("attachment_count", 0);
    }

    @Test
    void infoReportsThatPrivateUrlsAreDisabled() {
        HttpHeaders headers = new HttpHeaders();
        ResponseEntity<Map<String, Object>> info = rest.exchange(base() + "/api/info", HttpMethod.GET,
                new HttpEntity<>(headers), new ParameterizedTypeReference<>() {});
        assertThat(info.getBody()).containsEntry("allow_private_urls", false);
    }
}
