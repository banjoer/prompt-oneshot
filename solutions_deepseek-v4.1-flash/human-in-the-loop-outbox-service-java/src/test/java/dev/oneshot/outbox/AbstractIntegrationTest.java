package dev.oneshot.outbox;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.oneshot.outbox.support.TestHttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Shared integration harness: random port, isolated SQLite and attachment
 * directories per test run, a loopback fixture server, and JSON/multipart helpers.
 */
@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
                "outbox.allow-private-urls=true",
                "outbox.max-attachment-bytes=2048",
                "outbox.max-message-attachment-bytes=4096",
                "outbox.expiration-interval-seconds=1",
                "outbox.webhook-timeout-seconds=1",
                "outbox.webhook-max-attempts=3",
                "outbox.webhook-backoff-base-seconds=0.05",
                "outbox.download-timeout-seconds=2",
                "outbox.max-redirects=1",
                "outbox.webhook-worker-interval-ms=100",
                "outbox.handoff-url-max-chars=1800",
                "outbox.built-at=2026-11-07T00:00:00Z",
                "outbox.built-by=DeepSeek V4.1 Flash",
                "logging.level.root=WARN",
                "logging.level.dev.oneshot.outbox=WARN"
        })
public abstract class AbstractIntegrationTest {

    private static final Path ROOT = tempRoot();

    @DynamicPropertySource
    static void directories(DynamicPropertyRegistry registry) {
        registry.add("outbox.data-dir", () -> ROOT.resolve("data").toString());
        registry.add("outbox.attachment-dir", () -> ROOT.resolve("data/attachments").toString());
    }

    private static Path tempRoot() {
        try {
            return Files.createTempDirectory("outbox-it-");
        } catch (IOException ex) {
            throw new IllegalStateException(ex);
        }
    }

    @LocalServerPort
    protected int port;

    @Autowired
    protected TestRestTemplate rest;

    @Autowired
    protected JdbcTemplate jdbc;

    @Autowired
    protected ObjectMapper objectMapper;

    @Autowired
    protected dev.oneshot.outbox.config.OutboxProperties props;

    protected TestHttpServer server;

    @BeforeEach
    void cleanState() throws IOException {
        for (String table : List.of("webhook_attempts", "webhook_events", "revision_references",
                "revision_attachments", "attachments", "status_history", "message_revisions",
                "messages", "destination_labels")) {
            jdbc.execute("DELETE FROM " + table);
        }
        jdbc.execute("DELETE FROM sqlite_sequence WHERE name IN ('message_revisions','status_history','webhook_attempts','destination_labels')");
        try (var files = Files.list(ROOT.resolve("data/attachments"))) {
            files.forEach(path -> {
                try { Files.deleteIfExists(path); } catch (IOException ignored) { }
            });
        } catch (IOException ignored) {
            // Directory is created by the application.
        }
        server = new TestHttpServer();
    }

    @AfterEach
    void stopServer() {
        if (server != null) server.close();
    }

    // ------------------------------------------------------------- HTTP helpers

    protected String base() {
        return "http://127.0.0.1:" + port;
    }

    protected ResponseEntity<Map<String, Object>> get(String path) {
        return rest.exchange(base() + path, HttpMethod.GET, null,
                new ParameterizedTypeReference<>() {});
    }

    protected ResponseEntity<Map<String, Object>> postJson(String path, Map<String, Object> body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        return rest.exchange(base() + path, HttpMethod.POST, new HttpEntity<>(body, headers),
                new ParameterizedTypeReference<>() {});
    }

    protected ResponseEntity<Map<String, Object>> postEmpty(String path) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        return rest.exchange(base() + path, HttpMethod.POST, new HttpEntity<>(headers),
                new ParameterizedTypeReference<>() {});
    }

    protected ResponseEntity<Map<String, Object>> patchJson(String path, Map<String, Object> body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        return rest.exchange(base() + path, HttpMethod.PATCH, new HttpEntity<>(body, headers),
                new ParameterizedTypeReference<>() {});
    }

    protected ResponseEntity<Map<String, Object>> putJson(String path, Map<String, Object> body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        return rest.exchange(base() + path, HttpMethod.PUT, new HttpEntity<>(body, headers),
                new ParameterizedTypeReference<>() {});
    }

    protected ResponseEntity<Map<String, Object>> delete(String path) {
        return rest.exchange(base() + path, HttpMethod.DELETE, null,
                new ParameterizedTypeReference<>() {});
    }

    protected ResponseEntity<Map<String, Object>> postMultipart(String path, Map<String, String> fields,
                                                                List<NamedBytes> files) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        fields.forEach(form::add);
        for (NamedBytes file : files) {
            form.add("attachments", new ByteArrayResource(file.bytes()) {
                @Override
                public String getFilename() { return file.filename(); }
            });
        }
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        return rest.exchange(base() + path, HttpMethod.POST, new HttpEntity<>(form, headers),
                new ParameterizedTypeReference<>() {});
    }

    protected ResponseEntity<byte[]> getBytes(String path) {
        return rest.exchange(base() + path, HttpMethod.GET, null, byte[].class);
    }

    protected ResponseEntity<String> getText(String path) {
        return rest.exchange(base() + path, HttpMethod.GET, null, String.class);
    }

    protected record NamedBytes(String filename, byte[] bytes, String contentType) {
        public NamedBytes(String filename, String text) {
            this(filename, text.getBytes(StandardCharsets.UTF_8), "text/plain");
        }
    }

    // --------------------------------------------------------------- fixtures

    protected Map<String, Object> emailPayload(String destination) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("channel", "email");
        body.put("destination", destination);
        body.put("subject", "Q4 report draft");
        body.put("body", "Hi Alex,\n\nPlease review the attached Q4 report before Friday.\n\nThanks,\nSam");
        body.put("source", "report-agent");
        body.put("metadata", Map.of("ticket", "OPS-142"));
        return body;
    }

    protected Map<String, Object> createEmail(String destination) {
        ResponseEntity<Map<String, Object>> response = postJson("/api/messages", emailPayload(destination));
        assertThat(response.getStatusCode().value()).isEqualTo(201);
        return response.getBody();
    }

    protected String id(Map<String, Object> message) {
        return (String) message.get("id");
    }

    protected String errorCode(ResponseEntity<Map<String, Object>> response) {
        Map<String, Object> error = (Map<String, Object>) response.getBody().get("error");
        return (String) error.get("code");
    }

    protected String errorMessage(ResponseEntity<Map<String, Object>> response) {
        Map<String, Object> error = (Map<String, Object>) response.getBody().get("error");
        return (String) error.get("message");
    }

    protected void await(Duration timeout, String description, Supplier<Boolean> condition) {
        long deadline = System.nanoTime() + timeout.toNanos();
        while (System.nanoTime() < deadline) {
            if (Boolean.TRUE.equals(condition.get())) return;
            try {
                Thread.sleep(40);
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                throw new AssertionError("interrupted while waiting for " + description, ex);
            }
        }
        throw new AssertionError("timed out waiting for " + description);
    }

    protected int rowCount(String table, String where, Object... args) {
        Integer value = jdbc.queryForObject("SELECT COUNT(*) FROM " + table + " WHERE " + where,
                Integer.class, args);
        return value == null ? 0 : value;
    }

    protected List<String> statusTransitions(String messageId, String toStatus) {
        return jdbc.queryForList("""
                SELECT from_status || '->' || to_status FROM status_history
                WHERE message_id = ? AND to_status = ?
                """, String.class, messageId, toStatus);
    }

    protected JsonNode json(String text) {
        try {
            return objectMapper.readTree(text);
        } catch (Exception ex) {
            throw new AssertionError("Invalid JSON: " + text, ex);
        }
    }

    protected static List<NamedBytes> files(NamedBytes... entries) {
        return new ArrayList<>(List.of(entries));
    }

    @SuppressWarnings("unchecked")
    protected static Map<String, Object> map(Object value) {
        return (Map<String, Object>) value;
    }

    @SuppressWarnings("unchecked")
    protected static List<String> strings(Object value) {
        return (List<String>) value;
    }
}
