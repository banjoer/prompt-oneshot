package dev.oneshot.outbox;

import dev.oneshot.outbox.support.TestHttpServer;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.core.ParameterizedTypeReference;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;

class OutboxReliabilityIntegrationTest extends AbstractIntegrationTest {

    // -------------------------------------------------------------- attachments

    @Test
    void multipartStoresSanitizedFileAndDownloadNeverMarksSent() {
        ResponseEntity<Map<String, Object>> created = postMultipart("/api/messages", Map.of(
                "channel", "email",
                "destination", "files@example.com",
                "subject", "With file",
                "body", "See the attached file."),
                files(new NamedBytes("../../evil.txt", "Outbox attachment fixture.\nThis file is intentionally small.\n")));
        assertThat(created.getStatusCode().value()).isEqualTo(201);
        Map<String, Object> message = created.getBody();
        String messageId = id(message);
        assertThat(message).containsEntry("attachment_count", 1);
        List<Map<String, Object>> attachmentViews = (List<Map<String, Object>>) message.get("attachments");
        assertThat(attachmentViews).hasSize(1);
        assertThat(attachmentViews.get(0).get("filename")).isEqualTo("evil.txt");
        assertThat(attachmentViews.get(0).get("source_type")).isEqualTo("multipart");
        String attachmentId = (String) attachmentViews.get(0).get("id");

        ResponseEntity<byte[]> download = getBytes("/api/messages/" + messageId + "/attachments/" + attachmentId);
        assertThat(download.getStatusCode().value()).isEqualTo(200);
        assertThat(new String(download.getBody(), StandardCharsets.UTF_8)).contains("Outbox attachment fixture");
        assertThat(download.getHeaders().getFirst("Content-Disposition")).contains("evil.txt");
        assertThat(download.getHeaders().getFirst("X-Content-Type-Options")).isEqualTo("nosniff");

        // Downloading and listing must not change the status.
        assertThat(get("/api/messages/" + messageId).getBody()).containsEntry("status", "pending");
        postEmpty("/api/messages/" + messageId + "/approve");
        ResponseEntity<byte[]> afterApprove = getBytes("/api/messages/" + messageId + "/attachments/" + attachmentId);
        assertThat(afterApprove.getStatusCode().value()).isEqualTo(200);
        assertThat(get("/api/messages/" + messageId).getBody()).containsEntry("status", "approved");

        ResponseEntity<Map<String, Object>> list = get("/api/messages/" + messageId + "/attachments");
        assertThat((Integer) list.getBody().get("total")).isEqualTo(1);

        assertThat(get("/api/messages/" + messageId + "/attachments/att_000000000000").getStatusCode().value())
                .isEqualTo(404);
        assertThat(get("/api/messages/" + messageId + "/attachments/..%2F..%2Fetc%2Fpasswd")
                .getStatusCode().value()).isIn(400, 404);
    }

    @Test
    void zipDownloadContainsAllAttachments() {
        ResponseEntity<Map<String, Object>> created = postMultipart("/api/messages", Map.of(
                "channel", "email",
                "destination", "zip@example.com",
                "body", "Two files"),
                files(new NamedBytes("one.txt", "first"), new NamedBytes("two.txt", "second")));
        assertThat(created.getStatusCode().value()).isEqualTo(201);
        String messageId = id(created.getBody());
        ResponseEntity<byte[]> zip = getBytes("/api/messages/" + messageId + "/attachments.zip");
        assertThat(zip.getStatusCode().value()).isEqualTo(200);
        assertThat(zip.getBody()).isNotEmpty();
        assertThat(zip.getBody()[0]).isEqualTo((byte) 0x50);
        assertThat(zip.getBody()[1]).isEqualTo((byte) 0x4b);
        assertThat(zip.getHeaders().getFirst("Content-Disposition")).contains(".zip");
    }

    @Test
    void oversizedUploadsReturn413AndCreateNothing() {
        int before = jdbc.queryForObject("SELECT COUNT(*) FROM messages", Integer.class);

        ResponseEntity<Map<String, Object>> tooBig = postMultipart("/api/messages", Map.of(
                "channel", "email", "destination", "big@example.com", "body", "too big"),
                files(new NamedBytes("big.bin", new byte[3000], "application/octet-stream")));
        assertThat(tooBig.getStatusCode().value()).isEqualTo(413);
        assertThat(errorCode(tooBig)).isEqualTo("payload_too_large");

        ResponseEntity<Map<String, Object>> tooBigTotal = postMultipart("/api/messages", Map.of(
                "channel", "email", "destination", "big2@example.com", "body", "three files"),
                files(new NamedBytes("a.bin", new byte[2000], "application/octet-stream"),
                        new NamedBytes("b.bin", new byte[2000], "application/octet-stream"),
                        new NamedBytes("c.bin", new byte[2000], "application/octet-stream")));
        assertThat(tooBigTotal.getStatusCode().value()).isEqualTo(413);

        int after = jdbc.queryForObject("SELECT COUNT(*) FROM messages", Integer.class);
        assertThat(after).isEqualTo(before);
    }

    @Test
    void missingPhysicalFileReturnsClear404AndDoesNotDeleteRecord() throws Exception {
        ResponseEntity<Map<String, Object>> created = postMultipart("/api/messages", Map.of(
                "channel", "email", "destination", "missing@example.com", "body", "file will vanish"),
                files(new NamedBytes("gone.txt", "temporary")));
        assertThat(created.getStatusCode().value()).isEqualTo(201);
        String messageId = id(created.getBody());
        String attachmentId = (String) ((Map<String, Object>) ((List<?>) created.getBody().get("attachments")).get(0)).get("id");

        Path attachmentsDir = Path.of(props.getAttachmentDir());
        try (var files = Files.list(attachmentsDir)) {
            for (Path file : files.toList()) Files.deleteIfExists(file);
        }

        ResponseEntity<Map<String, Object>> download = get("/api/messages/" + messageId + "/attachments/" + attachmentId);
        assertThat(download.getStatusCode().value()).isEqualTo(404);
        assertThat(errorMessage(download)).containsIgnoringCase("missing");
        ResponseEntity<Map<String, Object>> list = get("/api/messages/" + messageId + "/attachments");
        assertThat((Integer) list.getBody().get("total")).isEqualTo(1);
        assertThat(get("/api/messages/" + messageId + "/attachments.zip").getStatusCode().value()).isEqualTo(404);
    }

    // -------------------------------------------------------------- URL fetch

    @Test
    void urlReferencesAreNotFetchedAndDownloadsAreStored() {
        server.on("/sample.txt", (exchange, n) -> TestHttpServer.respondBytes(exchange, 200,
                "remote attachment body".getBytes(StandardCharsets.UTF_8), "text/plain",
                Map.of("Content-Disposition", "attachment; filename=\"server-name.txt\"")));

        Map<String, Object> payload = emailPayload("download@example.com");
        payload.put("references", List.of("https://example.com/spec"));
        payload.put("attachments", List.of(
                Map.of("kind", "url_reference", "url", "https://example.com/other-reference"),
                Map.of("kind", "url_download", "url", server.url("/sample.txt"))));
        ResponseEntity<Map<String, Object>> created = postJson("/api/messages", payload);
        assertThat(created.getStatusCode().value()).isEqualTo(201);
        Map<String, Object> message = created.getBody();
        String messageId = id(message);
        assertThat(message).containsEntry("attachment_count", 1);
        List<String> references = (List<String>) message.get("references");
        assertThat(references).containsExactly("https://example.com/spec", "https://example.com/other-reference");
        List<Map<String, Object>> attachments = (List<Map<String, Object>>) message.get("attachments");
        assertThat(attachments).hasSize(1);
        assertThat(attachments.get(0).get("filename")).isEqualTo("server-name.txt");
        assertThat(attachments.get(0).get("source_type")).isEqualTo("url_download");
        assertThat(attachments.get(0).get("source_url")).isEqualTo(server.url("/sample.txt"));
        assertThat(server.count("/sample.txt")).isEqualTo(1);

        ResponseEntity<byte[]> download = getBytes("/api/messages/" + messageId + "/attachments/"
                + attachments.get(0).get("id"));
        assertThat(new String(download.getBody(), StandardCharsets.UTF_8)).isEqualTo("remote attachment body");
    }

    @Test
    void redirectsAreFollowedOnceAndLoopIsRejected() {
        server.on("/target.txt", (exchange, n) -> TestHttpServer.respondBytes(exchange, 200,
                "redirected".getBytes(StandardCharsets.UTF_8), "text/plain", null));
        server.on("/redirect", (exchange, n) -> TestHttpServer.respond(exchange, 302, null, null,
                Map.of("Location", "/target.txt")));
        server.on("/loop", (exchange, n) -> TestHttpServer.respond(exchange, 302, null, null,
                Map.of("Location", "/loop")));

        Map<String, Object> payload = emailPayload("redirect@example.com");
        payload.put("attachments", List.of(Map.of("kind", "url_download", "url", server.url("/redirect"))));
        ResponseEntity<Map<String, Object>> created = postJson("/api/messages", payload);
        assertThat(created.getStatusCode().value()).isEqualTo(201);
        assertThat(server.count("/target.txt")).isEqualTo(1);

        Map<String, Object> loopPayload = emailPayload("loop@example.com");
        loopPayload.put("attachments", List.of(Map.of("kind", "url_download", "url", server.url("/loop"))));
        ResponseEntity<Map<String, Object>> loop = postJson("/api/messages", loopPayload);
        assertThat(loop.getStatusCode().value()).isEqualTo(400);
        assertThat(errorMessage(loop)).containsIgnoringCase("redirect");

        Map<String, Object> badScheme = emailPayload("scheme@example.com");
        badScheme.put("attachments", List.of(Map.of("kind", "url_download", "url", "ftp://example.com/file")));
        assertThat(postJson("/api/messages", badScheme).getStatusCode().value()).isEqualTo(400);

        Map<String, Object> badKind = emailPayload("kind@example.com");
        badKind.put("attachments", List.of(Map.of("kind", "wat", "url", "https://example.com/file")));
        assertThat(postJson("/api/messages", badKind).getStatusCode().value()).isEqualTo(400);
    }

    // ---------------------------------------------------------------- webhooks

    private List<Map<String, Object>> events(String messageId) {
        ResponseEntity<Map<String, Object>> response = get("/api/messages/" + messageId + "/webhook-events");
        assertThat(response.getStatusCode().value()).isEqualTo(200);
        return (List<Map<String, Object>>) response.getBody().get("items");
    }

    @Test
    void webhookEventsAreEmittedOnlyForRealEventsAndOnce() {
        server.on("/hook", (exchange, n) -> TestHttpServer.webhookSink(exchange, n, 0, new AtomicInteger()));
        Map<String, Object> payload = emailPayload("hooks@example.com");
        payload.put("webhook_url", server.url("/hook"));
        String messageId = id(postJson("/api/messages", payload).getBody());

        // Submission is not a supported webhook event.
        assertThat(events(messageId)).isEmpty();

        postJson("/api/messages/" + messageId + "/reject", Map.of("reason", "Wrong recipient"));
        await(Duration.ofSeconds(5), "message.rejected delivery",
                () -> events(messageId).stream().anyMatch(e -> "message.rejected".equals(e.get("event")) && (Boolean) e.get("delivered")));
        postJson("/api/messages/" + messageId + "/reject", Map.of("reason", "Again"));
        assertThat(events(messageId).stream().filter(e -> "message.rejected".equals(e.get("event"))).count())
                .isEqualTo(1);

        Map<String, Object> rejectedEvent = events(messageId).stream()
                .filter(e -> "message.rejected".equals(e.get("event"))).findFirst().orElseThrow();
        Map<String, Object> payloadBody = (Map<String, Object>) rejectedEvent.get("payload");
        assertThat(payloadBody).containsEntry("event", "message.rejected")
                .containsEntry("message_id", messageId)
                .containsEntry("status", "rejected")
                .containsEntry("rejection_reason", "Wrong recipient");
        assertThat(payloadBody.get("revision_number")).isEqualTo(1);
        assertThat((String) payloadBody.get("timestamp")).endsWith("Z");
        assertThat((List<?>) rejectedEvent.get("attempts")).hasSize(1);

        patchJson("/api/messages/" + messageId, Map.of("subject", "Revised subject"));
        await(Duration.ofSeconds(5), "message.revised delivery",
                () -> events(messageId).stream().anyMatch(e -> "message.revised".equals(e.get("event")) && (Boolean) e.get("delivered")));
        assertThat(events(messageId).stream().filter(e -> "message.revised".equals(e.get("event"))).count()).isEqualTo(1);

        postEmpty("/api/messages/" + messageId + "/approve");
        postJson("/api/messages/" + messageId + "/mark-sent", Map.of("confirmed", true));
        await(Duration.ofSeconds(5), "approved and sent events",
                () -> events(messageId).stream().filter(e -> Boolean.TRUE.equals(e.get("delivered"))).count() >= 4);
        assertThat(events(messageId).stream().map(e -> (String) e.get("event")))
                .contains("message.rejected", "message.revised", "message.approved", "message.sent");
    }

    @Test
    void cancelledAndStaleEventsAreEmitted() {
        server.on("/hook", (exchange, n) -> TestHttpServer.webhookSink(exchange, n, 0, new AtomicInteger()));
        Map<String, Object> payload = emailPayload("cancel-hook@example.com");
        payload.put("webhook_url", server.url("/hook"));
        String messageId = id(postJson("/api/messages", payload).getBody());
        postEmpty("/api/messages/" + messageId + "/cancel");
        await(Duration.ofSeconds(5), "cancelled event",
                () -> events(messageId).stream().anyMatch(e -> "message.cancelled".equals(e.get("event"))
                        && (Boolean) e.get("delivered")));

        Map<String, Object> stalePayload = emailPayload("stale-hook@example.com");
        stalePayload.put("webhook_url", server.url("/hook"));
        stalePayload.put("ttl_seconds", 1);
        String staleId = id(postJson("/api/messages", stalePayload).getBody());
        await(Duration.ofSeconds(6), "stale event",
                () -> events(staleId).stream().anyMatch(e -> "message.stale".equals(e.get("event"))
                        && (Boolean) e.get("delivered")));
    }

    @Test
    void webhookRetriesThenSucceedsAndFailuresNeverRollBack() {
        server.on("/flaky", (exchange, n) -> TestHttpServer.webhookSink(exchange, n, 2, new AtomicInteger()));
        Map<String, Object> payload = emailPayload("retry@example.com");
        payload.put("webhook_url", server.url("/flaky"));
        String messageId = id(postJson("/api/messages", payload).getBody());
        postEmpty("/api/messages/" + messageId + "/approve");
        await(Duration.ofSeconds(8), "webhook retry success", () -> {
            List<Map<String, Object>> items = events(messageId);
            return items.size() == 1 && Boolean.TRUE.equals(items.get(0).get("delivered"));
        });
        Map<String, Object> event = events(messageId).get(0);
        assertThat(event.get("attempts_count")).isEqualTo(3);
        List<Map<String, Object>> attempts = (List<Map<String, Object>>) event.get("attempts");
        assertThat(attempts).hasSize(3);
        assertThat(attempts.get(0).get("status")).isEqualTo("failed");
        assertThat(attempts.get(1).get("status")).isEqualTo("failed");
        assertThat(attempts.get(2).get("status")).isEqualTo("delivered");
        assertThat(get("/api/messages/" + messageId).getBody()).containsEntry("status", "approved");

        server.on("/always-fails", (exchange, n) -> TestHttpServer.webhookSink(exchange, n, 999, new AtomicInteger()));
        Map<String, Object> failing = emailPayload("failing@example.com");
        failing.put("webhook_url", server.url("/always-fails"));
        String failingId = id(postJson("/api/messages", failing).getBody());
        postJson("/api/messages/" + failingId + "/reject", Map.of("reason", "Policy violation"));
        await(Duration.ofSeconds(8), "three failed webhook attempts", () -> {
            List<Map<String, Object>> items = events(failingId);
            return items.size() == 1 && Integer.valueOf(3).equals(items.get(0).get("attempts_count"));
        });
        Map<String, Object> failed = events(failingId).get(0);
        assertThat(failed.get("delivered")).isEqualTo(false);
        assertThat((String) failed.get("last_error")).contains("HTTP 500");
        // The message transition is intact and the API still works.
        assertThat(get("/api/messages/" + failingId).getBody()).containsEntry("status", "rejected");
        assertThat(get("/api/health").getStatusCode().value()).isEqualTo(200);
    }

    @Test
    void webhookTimeoutIsRecordedWithoutBlockingStateChange() {
        server.on("/slow", (exchange, requestNumber) -> {
            try {
                Thread.sleep(1800);
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
            }
            TestHttpServer.respond(exchange, 204, null, null, null);
        });
        Map<String, Object> payload = emailPayload("slow@example.com");
        payload.put("webhook_url", server.url("/slow"));
        String messageId = id(postJson("/api/messages", payload).getBody());
        long started = System.nanoTime();
        ResponseEntity<Map<String, Object>> approved = postEmpty("/api/messages/" + messageId + "/approve");
        long elapsedMs = (System.nanoTime() - started) / 1_000_000;
        assertThat(approved.getStatusCode().value()).isEqualTo(200);
        // The state transition must not wait for the webhook timeout.
        assertThat(elapsedMs).isLessThan(1500);
        await(Duration.ofSeconds(6), "timeout attempt recorded", () -> {
            List<Map<String, Object>> items = events(messageId);
            return items.size() == 1 && items.get(0).get("last_error") != null;
        });
        assertThat((String) events(messageId).get(0).get("last_error")).isNotBlank();
        assertThat(get("/api/messages/" + messageId).getBody()).containsEntry("status", "approved");
    }

    // -------------------------------------------------------------- expiration

    @Test
    void ttlExpiresPendingMessagesAndRetainsEverything() {
        Map<String, Object> payload = emailPayload("expire@example.com");
        payload.put("ttl_seconds", 1);
        String messageId = id(postJson("/api/messages", payload).getBody());
        sleep(1300);

        Map<String, Object> detail = get("/api/messages/" + messageId).getBody();
        assertThat(detail).containsEntry("status", "stale");
        assertThat(detail).containsEntry("expired", true);
        assertThat((String) detail.get("body")).contains("Q4 report");
        assertThat((List<?>) detail.get("allowed_actions")).isEmpty();
        assertThat(statusTransitions(messageId, "stale")).containsExactly("pending->stale");

        ResponseEntity<Map<String, Object>> approve = postEmpty("/api/messages/" + messageId + "/approve");
        assertThat(approve.getStatusCode().value()).isEqualTo(409);
        assertThat(map(approve.getBody().get("error"))).containsEntry("current_status", "stale");
        assertThat(get("/api/messages/" + messageId + "/handoff").getStatusCode().value()).isEqualTo(409);
        assertThat(patchJson("/api/messages/" + messageId, Map.of("body", "no"))
                .getStatusCode().value()).isEqualTo(409);
    }

    @Test
    void approvedMessagesCanExpireAndNoExpirationStaysActive() {
        Map<String, Object> payload = emailPayload("approved-expire@example.com");
        payload.put("ttl_seconds", 2);
        String messageId = id(postJson("/api/messages", payload).getBody());
        assertThat(postEmpty("/api/messages/" + messageId + "/approve").getBody())
                .containsEntry("status", "approved");
        sleep(2200);
        assertThat(get("/api/messages/" + messageId).getBody()).containsEntry("status", "stale");
        assertThat(postEmpty("/api/messages/" + messageId + "/mark-sent").getStatusCode().value()).isEqualTo(409);

        String foreverId = id(createEmail("forever@example.com"));
        sleep(1300);
        assertThat(get("/api/messages/" + foreverId).getBody()).containsEntry("status", "pending");
    }

    @Test
    void absoluteExpiryAndBackgroundWorkerBothWork() {
        Map<String, Object> payload = emailPayload("absolute@example.com");
        payload.put("expires_at", Instant.now().plusSeconds(1).toString());
        String absoluteId = id(postJson("/api/messages", payload).getBody());
        sleep(1300);
        assertThat(get("/api/messages/" + absoluteId).getBody()).containsEntry("status", "stale");

        Map<String, Object> background = emailPayload("background@example.com");
        background.put("ttl_seconds", 1);
        String backgroundId = id(postJson("/api/messages", background).getBody());
        // No API read: the periodic worker must expire it.
        await(Duration.ofSeconds(5), "background expiration worker", () -> {
            String status = jdbc.queryForObject("SELECT status FROM messages WHERE id = ?", String.class, backgroundId);
            return "stale".equals(status);
        });
        assertThat(statusTransitions(backgroundId, "stale")).hasSize(1);
    }

    @Test
    void staleMessageRetainsAndServesAttachments() {
        ResponseEntity<Map<String, Object>> created = postMultipart("/api/messages", Map.of(
                "channel", "email", "destination", "stale-file@example.com", "body", "has file", "ttl_seconds", "1"),
                files(new NamedBytes("keep.txt", "kept forever")));
        assertThat(created.getStatusCode().value()).isEqualTo(201);
        String messageId = id(created.getBody());
        String attachmentId = (String) ((Map<String, Object>) ((List<?>) created.getBody().get("attachments")).get(0)).get("id");
        sleep(1300);
        assertThat(get("/api/messages/" + messageId).getBody()).containsEntry("status", "stale");
        ResponseEntity<byte[]> download = getBytes("/api/messages/" + messageId + "/attachments/" + attachmentId);
        assertThat(download.getStatusCode().value()).isEqualTo(200);
        assertThat(new String(download.getBody(), StandardCharsets.UTF_8)).isEqualTo("kept forever");
        assertThat(get("/api/messages/" + messageId).getBody()).containsEntry("status", "stale");
    }

    @Test
    void approvalVersusExpirationRaceNeverLeavesMessageApproved() throws Exception {
        Map<String, Object> payload = emailPayload("race-expiry@example.com");
        payload.put("expires_at", Instant.now().plusSeconds(1).toString());
        String messageId = id(postJson("/api/messages", payload).getBody());
        sleep(1100);

        ExecutorService pool = Executors.newFixedThreadPool(2);
        CountDownLatch start = new CountDownLatch(1);
        try {
            Future<Integer> approve = pool.submit(() -> {
                start.await(5, TimeUnit.SECONDS);
                return postEmpty("/api/messages/" + messageId + "/approve").getStatusCode().value();
            });
            Future<Integer> read = pool.submit(() -> {
                start.await(5, TimeUnit.SECONDS);
                return get("/api/messages/" + messageId).getStatusCode().value();
            });
            start.countDown();
            assertThat(approve.get(10, TimeUnit.SECONDS)).isEqualTo(409);
            assertThat(read.get(10, TimeUnit.SECONDS)).isEqualTo(200);
        } finally {
            pool.shutdownNow();
        }
        assertThat(get("/api/messages/" + messageId).getBody()).containsEntry("status", "stale");
        assertThat(statusTransitions(messageId, "approved")).isEmpty();
    }

    // ---------------------------------------------------------------- misc

    @Test
    void malformedTransitionBodiesReturn400() {
        String messageId = id(createEmail("bodies@example.com"));
        ResponseEntity<Map<String, Object>> numericReason = postJson(
                "/api/messages/" + messageId + "/reject", Map.of("reason", 42));
        assertThat(numericReason.getStatusCode().value()).isEqualTo(400);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<Map<String, Object>> badJson = rest.exchange(
                base() + "/api/messages/" + messageId + "/reject", HttpMethod.POST,
                new HttpEntity<>("{bad", headers), new ParameterizedTypeReference<>() {});
        assertThat(badJson.getStatusCode().value()).isEqualTo(400);

        ResponseEntity<Map<String, Object>> missingPatch = rest.exchange(
                base() + "/api/messages/" + messageId, HttpMethod.PATCH,
                new HttpEntity<>(headers), new ParameterizedTypeReference<>() {});
        assertThat(missingPatch.getStatusCode().value()).isEqualTo(400);
    }

    private static void sleep(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new AssertionError("interrupted", ex);
        }
    }
}
