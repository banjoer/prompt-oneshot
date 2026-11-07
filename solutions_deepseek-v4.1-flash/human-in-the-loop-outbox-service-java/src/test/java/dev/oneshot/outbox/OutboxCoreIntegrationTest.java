package dev.oneshot.outbox;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;

class OutboxCoreIntegrationTest extends AbstractIntegrationTest {

    // ---------------------------------------------------------------- system

    @Test
    void healthInfoDocsAndOpenApiAreComplete() {
        ResponseEntity<Map<String, Object>> health = get("/api/health");
        assertThat(health.getStatusCode().value()).isEqualTo(200);
        assertThat(health.getBody().get("status")).isEqualTo("ok");
        assertThat(map(health.getBody().get("database"))).containsEntry("journal_mode", "wal");

        ResponseEntity<Map<String, Object>> info = get("/api/info");
        assertThat(info.getStatusCode().value()).isEqualTo(200);
        assertThat(info.getBody()).containsEntry("allow_private_urls", true);
        assertThat(info.getBody()).containsEntry("built_by", "DeepSeek V4.1 Flash");
        assertThat((String) info.getBody().get("built_at")).isNotBlank();
        assertThat((String) info.getBody().get("attachment_dir")).endsWith("attachments");

        ResponseEntity<String> openapi = getText("/openapi.json");
        assertThat(openapi.getStatusCode().value()).isEqualTo(200);
        JsonNode spec = json(openapi.getBody());
        assertThat(spec.get("openapi").asText()).startsWith("3.");
        for (String path : List.of("/api/messages", "/api/messages/{id}", "/api/messages/{id}/approve",
                "/api/messages/{id}/reject", "/api/messages/{id}/cancel", "/api/messages/{id}/mark-sent",
                "/api/messages/{id}/history", "/api/messages/{id}/handoff",
                "/api/messages/{id}/attachments", "/api/messages/{id}/attachments/{attachment_id}",
                "/api/messages/{id}/webhook-events", "/api/destinations", "/api/destinations/label",
                "/api/health", "/api/info", "/api/docs", "/openapi.json")) {
            assertThat(spec.get("paths").has(path)).as("openapi path " + path).isTrue();
        }
        assertThat(spec.get("components").get("schemas").has("ErrorEnvelope")).isTrue();

        ResponseEntity<String> docs = getText("/api/docs");
        assertThat(docs.getStatusCode().value()).isEqualTo(200);
        assertThat(docs.getBody()).contains("Human-in-the-Loop Outbox API", "fetch('/openapi.json')");

        ResponseEntity<String> spa = getText("/");
        assertThat(spa.getStatusCode().value()).isEqualTo(200);
        assertThat(spa.getBody()).contains("<div id=\"app\">");
        assertThat(spa.getBody()).doesNotContain("TODO");
    }

    @Test
    void unknownRoutesAndMethodErrorsUseConsistentJson() {
        ResponseEntity<Map<String, Object>> missing = get("/api/messages/msg_000000000000");
        assertThat(missing.getStatusCode().value()).isEqualTo(404);
        assertThat(errorCode(missing)).isEqualTo("not_found");

        ResponseEntity<Map<String, Object>> noRoute = get("/api/nope");
        assertThat(noRoute.getStatusCode().value()).isEqualTo(404);
        assertThat(noRoute.getBody()).containsKey("error");

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<Map<String, Object>> method = rest.exchange(base() + "/api/messages",
                HttpMethod.DELETE, new HttpEntity<>(headers), new org.springframework.core.ParameterizedTypeReference<>() {});
        assertThat(method.getStatusCode().value()).isEqualTo(405);
        assertThat(errorCode(method)).isEqualTo("method_not_allowed");
    }

    // ------------------------------------------------------------- submission

    @Test
    void submissionReturnsStableIdAndCompleteDetail() {
        Map<String, Object> payload = emailPayload("alex@example.com");
        payload.put("expires_at", "2030-01-01T00:00:00Z");
        ResponseEntity<Map<String, Object>> created = postJson("/api/messages", payload);
        assertThat(created.getStatusCode().value()).isEqualTo(201);
        assertThat(created.getHeaders().getFirst("Location")).startsWith("/api/messages/msg_");
        Map<String, Object> body = created.getBody();
        assertThat((String) body.get("id")).matches("^msg_[a-f0-9]{12}$");
        assertThat(body).containsEntry("status", "pending");
        assertThat(body).containsEntry("revision_number", 1);
        assertThat((String) body.get("created_at")).endsWith("Z");
        assertThat(body).containsEntry("subject", "Q4 report draft");
        assertThat(map(body.get("metadata"))).containsEntry("ticket", "OPS-142");
        assertThat(body).containsEntry("attachment_count", 0);
        assertThat(strings(body.get("allowed_actions"))).contains("approve", "reject", "cancel");

        String id = id(body);
        ResponseEntity<Map<String, Object>> detail = get("/api/messages/" + id);
        assertThat(detail.getStatusCode().value()).isEqualTo(200);
        assertThat(detail.getBody()).containsEntry("id", id);
        assertThat((String) detail.getBody().get("body")).contains("Q4 report");

        Map<String, Object> listed = get("/api/messages?status=pending&destination=alex").getBody();
        assertThat((Integer) listed.get("total")).isGreaterThanOrEqualTo(1);
        assertThat((List<?>) listed.get("items")).isNotEmpty();
    }

    @Test
    void submissionValidatesShapesDestinationsAndExpiry() {
        List<Map<String, Object>> invalid = new ArrayList<>();

        Map<String, Object> badChannel = emailPayload("a@example.com");
        badChannel.put("channel", "sms");
        invalid.add(badChannel);

        Map<String, Object> badEmail = emailPayload("not-an-email");
        invalid.add(badEmail);

        Map<String, Object> emptyBody = emailPayload("a@example.com");
        emptyBody.put("body", "   ");
        invalid.add(emptyBody);

        Map<String, Object> bothExpiry = emailPayload("a@example.com");
        bothExpiry.put("expires_at", "2030-01-01T00:00:00Z");
        bothExpiry.put("ttl_seconds", 60);
        invalid.add(bothExpiry);

        Map<String, Object> pastExpiry = emailPayload("a@example.com");
        pastExpiry.put("expires_at", "2001-01-01T00:00:00Z");
        invalid.add(pastExpiry);

        Map<String, Object> zeroTtl = emailPayload("a@example.com");
        zeroTtl.put("ttl_seconds", 0);
        invalid.add(zeroTtl);

        Map<String, Object> arrayMetadata = emailPayload("a@example.com");
        arrayMetadata.put("metadata", List.of("nope"));
        invalid.add(arrayMetadata);

        Map<String, Object> badReferences = emailPayload("a@example.com");
        badReferences.put("references", "https://example.com");
        invalid.add(badReferences);

        Map<String, Object> badWebhook = emailPayload("a@example.com");
        badWebhook.put("webhook_url", "ftp://example.com/hook");
        invalid.add(badWebhook);

        Map<String, Object> badWhatsApp = new LinkedHashMap<>();
        badWhatsApp.put("channel", "whatsapp");
        badWhatsApp.put("destination", "not a number");
        badWhatsApp.put("body", "hello");
        invalid.add(badWhatsApp);

        Map<String, Object> badTelegram = new LinkedHashMap<>();
        badTelegram.put("channel", "telegram");
        badTelegram.put("destination", "bad username!");
        badTelegram.put("body", "hello");
        invalid.add(badTelegram);

        for (Map<String, Object> payload : invalid) {
            ResponseEntity<Map<String, Object>> response = postJson("/api/messages", payload);
            assertThat(response.getStatusCode().value())
                    .as("payload %s", payload).isEqualTo(400);
            assertThat(errorCode(response)).isIn("validation_error", "unsafe_url");
            assertThat(errorMessage(response)).isNotBlank();
        }

        // Unsupported media type and malformed JSON.
        HttpHeaders textHeaders = new HttpHeaders();
        textHeaders.setContentType(MediaType.TEXT_PLAIN);
        ResponseEntity<Map<String, Object>> unsupported = rest.exchange(base() + "/api/messages",
                HttpMethod.POST, new HttpEntity<>("hello", textHeaders),
                new org.springframework.core.ParameterizedTypeReference<>() {});
        assertThat(unsupported.getStatusCode().value()).isEqualTo(415);
        assertThat(errorCode(unsupported)).isEqualTo("unsupported_media_type");

        HttpHeaders jsonHeaders = new HttpHeaders();
        jsonHeaders.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<Map<String, Object>> malformed = rest.exchange(base() + "/api/messages",
                HttpMethod.POST, new HttpEntity<>("{\"channel\":", jsonHeaders),
                new org.springframework.core.ParameterizedTypeReference<>() {});
        assertThat(malformed.getStatusCode().value()).isEqualTo(400);
        assertThat(errorCode(malformed)).isEqualTo("malformed_request");
    }

    // ----------------------------------------------------------- list/filter

    @Test
    void listingFiltersPaginatesAndSortsWithNoExpiryLast() {
        Map<String, Object> first = emailPayload("alice@example.com");
        first.put("expires_at", "2030-01-01T00:00:00Z");
        String firstId = id(postJson("/api/messages", first).getBody());

        Map<String, Object> second = emailPayload("bob@example.com");
        second.put("expires_at", "2029-01-01T00:00:00Z");
        String secondId = id(postJson("/api/messages", second).getBody());

        Map<String, Object> third = emailPayload("carol@example.com");
        String thirdId = id(postJson("/api/messages", third).getBody());

        Map<String, Object> wa = new LinkedHashMap<>();
        wa.put("channel", "whatsapp");
        wa.put("destination", "+1 (415) 555-0123");
        wa.put("body", "Appointment confirmed");
        String waId = id(postJson("/api/messages", wa).getBody());

        // Deterministic creation timestamps for sort tests.
        jdbc.update("UPDATE messages SET created_at = '2026-01-01T00:00:00Z' WHERE id = ?", firstId);
        jdbc.update("UPDATE messages SET created_at = '2026-01-02T00:00:00Z' WHERE id = ?", secondId);
        jdbc.update("UPDATE messages SET created_at = '2026-01-03T00:00:00Z' WHERE id = ?", thirdId);
        jdbc.update("UPDATE messages SET created_at = '2026-01-04T00:00:00Z' WHERE id = ?", waId);
        postEmpty("/api/messages/" + firstId + "/approve");
        postJson("/api/messages/" + thirdId + "/reject", Map.of("reason", "Wrong recipient"));

        Map<String, Object> approvedOnly = get("/api/messages?status=approved").getBody();
        assertThat((Integer) approvedOnly.get("total")).isEqualTo(1);
        assertThat(((Map<?, ?>) ((List<?>) approvedOnly.get("items")).get(0)).get("id")).isEqualTo(firstId);

        Map<String, Object> emailOnly = get("/api/messages?channel=email").getBody();
        assertThat((Integer) emailOnly.get("total")).isEqualTo(3);

        Map<String, Object> destinationMatch = get("/api/messages?destination=alice").getBody();
        assertThat((Integer) destinationMatch.get("total")).isEqualTo(1);

        Map<String, Object> createdRange = get("/api/messages?created_after=2026-01-02&created_before=2026-01-03").getBody();
        assertThat((Integer) createdRange.get("total")).isEqualTo(2);

        Map<String, Object> soon = get("/api/messages?status=pending&sort=expires_soon&limit=100").getBody();
        List<Map<String, Object>> soonItems = (List<Map<String, Object>>) soon.get("items");
        assertThat(soonItems).isNotEmpty();
        assertThat(soonItems.get(soonItems.size() - 1).get("expires_at")).isNull();

        Map<String, Object> late = get("/api/messages?status=pending&sort=expires_late&limit=100").getBody();
        List<Map<String, Object>> lateItems = (List<Map<String, Object>>) late.get("items");
        assertThat(lateItems.get(lateItems.size() - 1).get("expires_at")).isNull();

        Map<String, Object> oldest = get("/api/messages?sort=oldest&limit=100").getBody();
        assertThat(((Map<?, ?>) ((List<?>) oldest.get("items")).get(0)).get("id")).isEqualTo(firstId);

        Map<String, Object> review = get("/api/messages?status=active&sort=review&limit=100").getBody();
        assertThat(((Map<?, ?>) ((List<?>) review.get("items")).get(0)).get("status")).isIn("pending", "approved", "rejected");

        Map<String, Object> page1 = get("/api/messages?sort=oldest&limit=2&offset=0").getBody();
        Map<String, Object> page2 = get("/api/messages?sort=oldest&limit=2&offset=2").getBody();
        assertThat((Integer) page1.get("limit")).isEqualTo(2);
        assertThat((List<?>) page1.get("items")).hasSize(2);
        assertThat((List<?>) page2.get("items")).hasSize(2);
        assertThat(((Map<?, ?>) ((List<?>) page1.get("items")).get(0)).get("id"))
                .isNotEqualTo(((Map<?, ?>) ((List<?>) page2.get("items")).get(0)).get("id"));

        assertThat(get("/api/messages?limit=101").getStatusCode().value()).isEqualTo(400);
        assertThat(get("/api/messages?limit=0").getStatusCode().value()).isEqualTo(400);
        assertThat(get("/api/messages?sort=sideways").getStatusCode().value()).isEqualTo(400);
        assertThat(get("/api/messages?created_after=not-a-date").getStatusCode().value()).isEqualTo(400);
    }

    // ------------------------------------------------------------- lifecycle

    @Test
    void approveHandoffMarkSentAndTerminalRules() {
        Map<String, Object> created = createEmail("lifecycle@example.com");
        String messageId = id(created);
        assertThat(postEmpty("/api/messages/" + messageId + "/mark-sent").getStatusCode().value()).isEqualTo(409);

        ResponseEntity<Map<String, Object>> approved = postEmpty("/api/messages/" + messageId + "/approve");
        assertThat(approved.getStatusCode().value()).isEqualTo(200);
        assertThat(approved.getBody()).containsEntry("status", "approved");

        ResponseEntity<Map<String, Object>> handoff = get("/api/messages/" + messageId + "/handoff");
        assertThat(handoff.getStatusCode().value()).isEqualTo(200);
        assertThat((String) handoff.getBody().get("handoff_url")).startsWith("mailto:lifecycle@example.com?");

        // Reading the handoff must not change status.
        assertThat(get("/api/messages/" + messageId).getBody()).containsEntry("status", "approved");

        ResponseEntity<Map<String, Object>> sent = postJson("/api/messages/" + messageId + "/mark-sent",
                Map.of("confirmed", true));
        assertThat(sent.getStatusCode().value()).isEqualTo(200);
        assertThat(sent.getBody()).containsEntry("status", "sent");
        assertThat(statusTransitions(messageId, "sent")).containsExactly("approved->sent");

        assertThat(postJson("/api/messages/" + messageId + "/mark-sent", Map.of("confirmed", true))
                .getStatusCode().value()).isEqualTo(409);
        assertThat(postEmpty("/api/messages/" + messageId + "/approve").getStatusCode().value()).isEqualTo(409);
        assertThat(postEmpty("/api/messages/" + messageId + "/cancel").getStatusCode().value()).isEqualTo(409);
        assertThat(patchJson("/api/messages/" + messageId, Map.of("body", "changed"))
                .getStatusCode().value()).isEqualTo(409);

        assertThat(postJson("/api/messages/" + messageId + "/mark-sent", Map.of("confirmed", true))
                .getStatusCode().value()).isEqualTo(409);

        String pendingAgain = id(createEmail("confirm@example.com"));
        assertThat(postJson("/api/messages/" + pendingAgain + "/mark-sent", Map.of("confirmed", false))
                .getStatusCode().value()).isEqualTo(400);
    }

    @Test
    void rejectRequiresReasonAndPatchCreatesRevisionWithStableIdentity() {
        Map<String, Object> created = createEmail("revise@example.com");
        String messageId = id(created);
        String originalCreatedAt = (String) created.get("created_at");

        ResponseEntity<Map<String, Object>> empty = postJson("/api/messages/" + messageId + "/reject",
                Map.of("reason", "   "));
        assertThat(empty.getStatusCode().value()).isEqualTo(400);
        assertThat(errorMessage(empty)).containsIgnoringCase("reason");

        ResponseEntity<Map<String, Object>> rejected = postJson("/api/messages/" + messageId + "/reject",
                Map.of("reason", "The recipient name is wrong. Address it to Alex Smith, not Alex Doe."));
        assertThat(rejected.getStatusCode().value()).isEqualTo(200);
        assertThat(rejected.getBody()).containsEntry("status", "rejected");
        assertThat(rejected.getBody()).containsEntry("rejection_reason",
                "The recipient name is wrong. Address it to Alex Smith, not Alex Doe.");
        assertThat(rejected.getBody().get("rejection_at")).isNotNull();
        assertThat(statusTransitions(messageId, "rejected")).containsExactly("pending->rejected");

        ResponseEntity<Map<String, Object>> patched = patchJson("/api/messages/" + messageId, Map.of(
                "subject", "Q4 report draft — revised",
                "body", "Hi Alex Smith,\n\nPlease review the attached Q4 report before Friday.\n\nThanks,\nSam"));
        assertThat(patched.getStatusCode().value()).isEqualTo(200);
        assertThat(patched.getBody()).containsEntry("id", messageId);
        assertThat(patched.getBody()).containsEntry("status", "pending");
        assertThat(patched.getBody()).containsEntry("revision_number", 2);
        assertThat(patched.getBody().get("rejection_reason")).isNull();
        assertThat(patched.getBody()).containsEntry("created_at", originalCreatedAt);
        assertThat((String) patched.getBody().get("subject")).contains("revised");

        Map<String, Object> history = get("/api/messages/" + messageId + "/history").getBody();
        List<Map<String, Object>> revisions = (List<Map<String, Object>>) history.get("revisions");
        assertThat(revisions).hasSize(2);
        assertThat(revisions.get(0).get("revision_number")).isEqualTo(1);
        assertThat(revisions.get(0).get("rejection_reason"))
                .isEqualTo("The recipient name is wrong. Address it to Alex Smith, not Alex Doe.");
        assertThat(revisions.get(0).get("subject")).isEqualTo("Q4 report draft");
        assertThat(revisions.get(1).get("revision_number")).isEqualTo(2);
        assertThat(revisions.get(1).get("rejection_reason")).isNull();
        List<Map<String, Object>> statuses = (List<Map<String, Object>>) history.get("status_history");
        assertThat(statuses).anySatisfy(change -> {
            assertThat(change.get("from_status")).isEqualTo("rejected");
            assertThat(change.get("to_status")).isEqualTo("pending");
            assertThat(change.get("revision_number")).isEqualTo(2);
        });

        assertThat(patchJson("/api/messages/" + messageId, Map.of("status", "approved"))
                .getStatusCode().value()).isEqualTo(400);

        assertThat(postEmpty("/api/messages/" + messageId + "/approve").getStatusCode().value()).isEqualTo(200);
        assertThat(patchJson("/api/messages/" + messageId, Map.of("body", "cannot edit"))
                .getStatusCode().value()).isEqualTo(409);
    }

    @Test
    void cancelAllowedFromPendingApprovedRejectedAndIsTerminal() {
        String pendingId = id(createEmail("cancel1@example.com"));
        assertThat(postEmpty("/api/messages/" + pendingId + "/cancel").getBody()).containsEntry("status", "cancelled");

        String approvedId = id(createEmail("cancel2@example.com"));
        postEmpty("/api/messages/" + approvedId + "/approve");
        assertThat(postJson("/api/messages/" + approvedId + "/cancel", Map.of("reason", "superseded"))
                .getBody()).containsEntry("status", "cancelled");

        String rejectedId = id(createEmail("cancel3@example.com"));
        postJson("/api/messages/" + rejectedId + "/reject", Map.of("reason", "wrong tone"));
        assertThat(postEmpty("/api/messages/" + rejectedId + "/cancel").getBody()).containsEntry("status", "cancelled");

        for (String messageId : List.of(pendingId, approvedId, rejectedId)) {
            assertThat(postEmpty("/api/messages/" + messageId + "/approve").getStatusCode().value()).isEqualTo(409);
            assertThat(postEmpty("/api/messages/" + messageId + "/mark-sent").getStatusCode().value()).isEqualTo(409);
            assertThat(patchJson("/api/messages/" + messageId, Map.of("body", "new"))
                    .getStatusCode().value()).isEqualTo(409);
            Map<String, Object> detail = get("/api/messages/" + messageId).getBody();
            assertThat(detail).containsEntry("status", "cancelled");
            assertThat((String) detail.get("body")).isNotBlank();
        }
    }

    @Test
    void concurrentApprovalsProduceOneSuccessAndOneHistoryRow() throws Exception {
        String messageId = id(createEmail("race@example.com"));
        ExecutorService pool = Executors.newFixedThreadPool(2);
        CountDownLatch ready = new CountDownLatch(2);
        CountDownLatch start = new CountDownLatch(1);
        List<Future<Integer>> futures = new ArrayList<>();
        try {
            for (int i = 0; i < 2; i++) {
                futures.add(pool.submit(() -> {
                    ready.countDown();
                    start.await(5, TimeUnit.SECONDS);
                    return postEmpty("/api/messages/" + messageId + "/approve").getStatusCode().value();
                }));
            }
            assertThat(ready.await(5, TimeUnit.SECONDS)).isTrue();
            start.countDown();
            List<Integer> statuses = new ArrayList<>();
            for (Future<Integer> future : futures) statuses.add(future.get(10, TimeUnit.SECONDS));
            assertThat(statuses).containsExactlyInAnyOrder(200, 409);
        } finally {
            pool.shutdownNow();
        }
        assertThat(rowCount("status_history", "message_id = ? AND to_status = 'approved'", messageId)).isEqualTo(1);
        assertThat(get("/api/messages/" + messageId).getBody()).containsEntry("status", "approved");
    }

    // ---------------------------------------------------------- destinations

    @Test
    void destinationsAreDiscoveredAndLabelsAreUniquePerChannel() {
        Map<String, Object> first = new LinkedHashMap<>();
        first.put("channel", "whatsapp");
        first.put("destination", "+1 (415) 555-0123");
        first.put("body", "one");
        String firstId = id(postJson("/api/messages", first).getBody());

        Map<String, Object> second = new LinkedHashMap<>();
        second.put("channel", "whatsapp");
        second.put("destination", "+1-415-555-0123");
        second.put("body", "two");
        String secondId = id(postJson("/api/messages", second).getBody());

        Map<String, Object> listed = get("/api/destinations").getBody();
        List<Map<String, Object>> items = (List<Map<String, Object>>) listed.get("items");
        assertThat(items).anySatisfy(item -> {
            assertThat(item.get("channel")).isEqualTo("whatsapp");
            assertThat(item.get("normalized_destination")).isEqualTo("14155550123");
            assertThat(item.get("message_count")).isEqualTo(2);
        });

        ResponseEntity<Map<String, Object>> labelled = putJson("/api/destinations/label", Map.of(
                "channel", "whatsapp", "destination", "+1 (415) 555-0123", "label", "Alex — Client"));
        assertThat(labelled.getStatusCode().value()).isEqualTo(200);
        assertThat(labelled.getBody()).containsEntry("label", "Alex — Client");

        Map<String, Object> detail = get("/api/messages/" + firstId).getBody();
        assertThat(detail).containsEntry("managed_label", "Alex — Client");
        assertThat(detail).containsEntry("display_label", "Alex — Client");

        Map<String, Object> byManagedLabel = get("/api/messages?destination=Client").getBody();
        assertThat((Integer) byManagedLabel.get("total")).isGreaterThanOrEqualTo(2);

        // Same label on another destination in the same channel conflicts.
        Map<String, Object> third = new LinkedHashMap<>();
        third.put("channel", "whatsapp");
        third.put("destination", "+1 415 555 9999");
        third.put("body", "three");
        postJson("/api/messages", third);
        ResponseEntity<Map<String, Object>> conflict = putJson("/api/destinations/label", Map.of(
                "channel", "whatsapp", "destination", "+1 415 555 9999", "label", "Alex — Client"));
        assertThat(conflict.getStatusCode().value()).isEqualTo(409);
        assertThat(errorCode(conflict)).isEqualTo("conflict");

        // Same label is fine in another channel.
        createEmail("label@example.com");
        assertThat(putJson("/api/destinations/label", Map.of(
                "channel", "email", "destination", "label@example.com", "label", "Alex — Client"))
                .getStatusCode().value()).isEqualTo(200);

        assertThat(putJson("/api/destinations/label", Map.of(
                "channel", "whatsapp", "destination", "+1 (415) 555-0123", "label", "  "))
                .getStatusCode().value()).isEqualTo(400);
        assertThat(putJson("/api/destinations/label", Map.of(
                "channel", "whatsapp", "destination", "+1 (415) 555-0123", "label", "x".repeat(81)))
                .getStatusCode().value()).isEqualTo(400);

        ResponseEntity<Map<String, Object>> removed = delete(
                "/api/destinations/label?channel=whatsapp&destination=14155550123");
        assertThat(removed.getStatusCode().value()).isEqualTo(200);
        assertThat(removed.getBody()).containsEntry("removed", true);

        assertThat(get("/api/messages/" + firstId).getBody()).containsEntry("status", "pending");
        assertThat(get("/api/messages/" + secondId).getStatusCode().value()).isEqualTo(200);

        Map<String, Object> after = get("/api/destinations").getBody();
        assertThat((List<Map<String, Object>>) after.get("items")).anySatisfy(item -> {
            if ("14155550123".equals(item.get("normalized_destination"))) {
                assertThat(item.get("label")).isNull();
                assertThat(item.get("message_count")).isEqualTo(2);
            }
        });

        // Reusing the same destination after label removal still works.
        Map<String, Object> fourth = new LinkedHashMap<>();
        fourth.put("channel", "whatsapp");
        fourth.put("destination", "14155550123");
        fourth.put("body", "four");
        assertThat(postJson("/api/messages", fourth).getStatusCode().value()).isEqualTo(201);
    }

    // --------------------------------------------------------------- handoff

    @Test
    void emailHandoffEncodesContentAndExplainsManualAttachments() {
        ResponseEntity<Map<String, Object>> created = postMultipart("/api/messages", Map.of(
                "channel", "email",
                "destination", "alex@example.com",
                "subject", "Q4 report draft",
                "body", "Hi Alex,\n\nSpecial: café & tea.\nThanks,\nSam"),
                files(new NamedBytes("sample.txt", "Outbox attachment fixture.\n")));
        assertThat(created.getStatusCode().value()).isEqualTo(201);
        String messageId = id(created.getBody());
        postEmpty("/api/messages/" + messageId + "/approve");

        Map<String, Object> handoff = get("/api/messages/" + messageId + "/handoff").getBody();
        String url = (String) handoff.get("handoff_url");
        assertThat(url).startsWith("mailto:alex@example.com?");
        assertThat(url).contains("subject=Q4%20report%20draft", "%0A", "caf%C3%A9%20%26%20tea");
        Map<String, Object> capabilities = (Map<String, Object>) handoff.get("capabilities");
        assertThat(capabilities).containsEntry("prefill_recipient", true)
                .containsEntry("prefill_subject", true)
                .containsEntry("prefill_body", true)
                .containsEntry("attachments_supported", false);
        assertThat((List<String>) handoff.get("manual_actions"))
                .anyMatch(action -> action.toLowerCase().contains("attach")
                        && action.toLowerCase().contains("mailto"));
        assertThat((List<String>) handoff.get("warnings"))
                .anyMatch(warning -> warning.toLowerCase().contains("never sends"));
        assertThat(map(handoff.get("copy"))).containsEntry("subject", "Q4 report draft");
        assertThat((List<?>) handoff.get("attachments")).hasSize(1);
    }

    @Test
    void overlongEmailBodyUsesShortMailtoAndWarnings() {
        Map<String, Object> payload = emailPayload("long@example.com");
        payload.put("body", "Réview ".repeat(400));
        String messageId = id(postJson("/api/messages", payload).getBody());
        postEmpty("/api/messages/" + messageId + "/approve");
        Map<String, Object> handoff = get("/api/messages/" + messageId + "/handoff").getBody();
        String url = (String) handoff.get("handoff_url");
        assertThat(url.length()).isLessThanOrEqualTo(1800);
        assertThat(url).startsWith("mailto:long@example.com?subject=");
        assertThat(((Map<?, ?>) handoff.get("capabilities")).get("prefill_body")).isEqualTo(false);
        assertThat((List<String>) handoff.get("warnings"))
                .anyMatch(warning -> warning.toLowerCase().contains("too long"));
    }

    @Test
    void whatsappAndTelegramHandoffsAreHonestAboutFallbacks() {
        Map<String, Object> wa = new LinkedHashMap<>();
        wa.put("channel", "whatsapp");
        wa.put("destination", "+1 (415) 555-0123");
        wa.put("body", "Line one\nLine two & café ✓");
        String waId = id(postJson("/api/messages", wa).getBody());
        postEmpty("/api/messages/" + waId + "/approve");
        Map<String, Object> waHandoff = get("/api/messages/" + waId + "/handoff").getBody();
        String waUrl = (String) waHandoff.get("handoff_url");
        assertThat(waUrl).startsWith("https://wa.me/14155550123?text=");
        assertThat(waUrl).contains("%0A", "%26", "%C3%A9", "%E2%9C%93");
        assertThat(((Map<?, ?>) waHandoff.get("capabilities")).get("prefill_recipient")).isEqualTo(true);

        Map<String, Object> waGroup = new LinkedHashMap<>();
        waGroup.put("channel", "whatsapp");
        waGroup.put("destination", "group:Project Alpha");
        waGroup.put("body", "Standup moved to 10:00.");
        String waGroupId = id(postJson("/api/messages", waGroup).getBody());
        postEmpty("/api/messages/" + waGroupId + "/approve");
        Map<String, Object> groupHandoff = get("/api/messages/" + waGroupId + "/handoff").getBody();
        assertThat(groupHandoff.get("handoff_url")).isEqualTo("https://web.whatsapp.com/");
        assertThat((String) groupHandoff.get("target_display")).contains("Project Alpha");
        assertThat(map(groupHandoff.get("capabilities")))
                .containsEntry("prefill_recipient", false)
                .containsEntry("prefill_subject", false)
                .containsEntry("prefill_body", false)
                .containsEntry("attachments_supported", false);
        assertThat((List<String>) groupHandoff.get("warnings"))
                .anyMatch(w -> w.toLowerCase().contains("does not offer"));
        assertThat((List<String>) groupHandoff.get("manual_actions"))
                .anyMatch(a -> a.toLowerCase().contains("select the group"));

        Map<String, Object> tg = new LinkedHashMap<>();
        tg.put("channel", "telegram");
        tg.put("destination", "@alex_example");
        tg.put("body", "Build finished successfully.");
        String tgId = id(postJson("/api/messages", tg).getBody());
        postEmpty("/api/messages/" + tgId + "/approve");
        Map<String, Object> tgHandoff = get("/api/messages/" + tgId + "/handoff").getBody();
        assertThat((String) tgHandoff.get("handoff_url")).startsWith("https://t.me/alex_example?text=");

        Map<String, Object> tgGroup = new LinkedHashMap<>();
        tgGroup.put("channel", "telegram");
        tgGroup.put("destination", "group:Ops Room");
        tgGroup.put("body", "Deploy is live.");
        String tgGroupId = id(postJson("/api/messages", tgGroup).getBody());
        postEmpty("/api/messages/" + tgGroupId + "/approve");
        Map<String, Object> tgGroupHandoff = get("/api/messages/" + tgGroupId + "/handoff").getBody();
        assertThat(tgGroupHandoff.get("handoff_url")).isEqualTo("https://web.telegram.org/");
        assertThat((List<String>) tgGroupHandoff.get("warnings"))
                .anyMatch(w -> w.toLowerCase().contains("does not offer"));

        Map<String, Object> invite = new LinkedHashMap<>();
        invite.put("channel", "telegram");
        invite.put("destination", "https://t.me/+AbCdEf123456");
        invite.put("body", "Private note");
        String inviteId = id(postJson("/api/messages", invite).getBody());
        postEmpty("/api/messages/" + inviteId + "/approve");
        Map<String, Object> inviteHandoff = get("/api/messages/" + inviteId + "/handoff").getBody();
        assertThat((String) inviteHandoff.get("handoff_url")).startsWith("https://t.me/+");
        assertThat(map(inviteHandoff.get("capabilities")))
                .containsEntry("prefill_recipient", false)
                .containsEntry("prefill_body", false);
        assertThat((List<String>) inviteHandoff.get("manual_actions"))
                .anyMatch(a -> a.toLowerCase().contains("join"));

        // Pending handoff is forbidden.
        Map<String, Object> pending = new LinkedHashMap<>();
        pending.put("channel", "telegram");
        pending.put("destination", "@pending_user");
        pending.put("body", "hello");
        String pendingId = id(postJson("/api/messages", pending).getBody());
        ResponseEntity<Map<String, Object>> pendingHandoff = get("/api/messages/" + pendingId + "/handoff");
        assertThat(pendingHandoff.getStatusCode().value()).isEqualTo(409);
        assertThat(strings(map(pendingHandoff.getBody().get("error")).get("allowed_actions")))
                .contains("approve");
    }

    @Test
    void overlongWhatsAppBodyFallsBackToBareLink() {
        Map<String, Object> wa = new LinkedHashMap<>();
        wa.put("channel", "whatsapp");
        wa.put("destination", "14155550123");
        wa.put("body", "Long message ".repeat(500));
        String messageId = id(postJson("/api/messages", wa).getBody());
        postEmpty("/api/messages/" + messageId + "/approve");
        Map<String, Object> handoff = get("/api/messages/" + messageId + "/handoff").getBody();
        String url = (String) handoff.get("handoff_url");
        assertThat(url).isEqualTo("https://wa.me/14155550123");
        assertThat(((Map<?, ?>) handoff.get("capabilities")).get("prefill_body")).isEqualTo(false);
        assertThat((List<String>) handoff.get("warnings"))
                .anyMatch(w -> w.toLowerCase().contains("too long"));
    }
}
