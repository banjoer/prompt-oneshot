package dev.oneshot.outbox.web;

import com.fasterxml.jackson.databind.JsonNode;
import dev.oneshot.outbox.attachments.AttachmentService;
import dev.oneshot.outbox.model.AttachmentRecord;
import dev.oneshot.outbox.model.MessageRecord;
import dev.oneshot.outbox.service.HandoffService;
import dev.oneshot.outbox.service.ListQuery;
import dev.oneshot.outbox.service.MessageService;
import dev.oneshot.outbox.service.PatchCommand;
import dev.oneshot.outbox.service.SubmitCommand;
import dev.oneshot.outbox.service.WebhookService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.CacheControl;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/messages")
public class MessageController {
    private final MessageService messages;
    private final HandoffService handoff;
    private final WebhookService webhooks;
    private final AttachmentService attachments;
    private final RequestMapper mapper;

    public MessageController(MessageService messages, HandoffService handoff, WebhookService webhooks,
                             AttachmentService attachments, RequestMapper mapper) {
        this.messages = messages;
        this.handoff = handoff;
        this.webhooks = webhooks;
        this.attachments = attachments;
        this.mapper = mapper;
    }

    // ---------------------------------------------------------------- submit

    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> createJson(@RequestBody JsonNode body) {
        SubmitCommand command = mapper.submitJson(body);
        Map<String, Object> created = messages.create(command);
        return created(created);
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<Map<String, Object>> createMultipart(
            HttpServletRequest request,
            @RequestParam(value = "attachments", required = false) MultipartFile[] files) {
        SubmitCommand command = mapper.submitMultipart(request.getParameterMap(), files);
        Map<String, Object> created = messages.create(command);
        return created(created);
    }

    // ------------------------------------------------------------------ reads

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String channel,
            @RequestParam(required = false) String destination,
            @RequestParam(name = "created_after", required = false) String createdAfter,
            @RequestParam(name = "created_before", required = false) String createdBefore,
            @RequestParam(name = "expires_after", required = false) String expiresAfter,
            @RequestParam(name = "expires_before", required = false) String expiresBefore,
            @RequestParam(required = false) String sort,
            @RequestParam(required = false) Integer limit,
            @RequestParam(required = false) Integer offset) {
        return messages.list(new ListQuery(status, channel, destination, createdAfter, createdBefore,
                expiresAfter, expiresBefore, sort, limit, offset));
    }

    @GetMapping("/{id}")
    public Map<String, Object> get(@PathVariable String id) {
        return messages.detail(id);
    }

    @GetMapping("/{id}/history")
    public Map<String, Object> history(@PathVariable String id) {
        return messages.history(id);
    }

    @GetMapping("/{id}/handoff")
    public Map<String, Object> handoff(@PathVariable String id) {
        return handoff.handoff(id);
    }

    @GetMapping("/{id}/attachments")
    public Map<String, Object> attachments(@PathVariable String id) {
        return messages.attachments(id);
    }

    @GetMapping("/{id}/attachments/{attachmentId}")
    public ResponseEntity<Resource> downloadAttachment(@PathVariable String id,
                                                       @PathVariable String attachmentId) {
        messages.ensureExists(id);
        AttachmentRecord attachment = attachments.require(id, attachmentId);
        Path path = attachments.requirePath(attachment);
        MediaType mediaType;
        try {
            mediaType = MediaType.parseMediaType(attachment.mimeType());
        } catch (Exception ex) {
            mediaType = MediaType.APPLICATION_OCTET_STREAM;
        }
        ContentDisposition disposition = ContentDisposition.attachment()
                .filename(attachment.originalFilename(), StandardCharsets.UTF_8).build();
        return ResponseEntity.ok()
                .contentType(mediaType)
                .header(HttpHeaders.CONTENT_DISPOSITION, disposition.toString())
                .header("X-Content-Type-Options", "nosniff")
                .cacheControl(CacheControl.noStore())
                .body(new FileSystemResource(path));
    }

    @GetMapping("/{id}/attachments.zip")
    public ResponseEntity<Resource> downloadAll(@PathVariable String id) {
        messages.ensureExists(id);
        List<AttachmentRecord> rows = messages.activeAttachments(id);
        if (rows.isEmpty()) throw ApiException.notFound("This message has no attachments to download.");
        byte[] zip = attachments.zipForZipDownload(rows);
        ContentDisposition disposition = ContentDisposition.attachment()
                .filename(id + "-attachments.zip", StandardCharsets.UTF_8).build();
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .header(HttpHeaders.CONTENT_DISPOSITION, disposition.toString())
                .header("X-Content-Type-Options", "nosniff")
                .body(new ByteArrayResource(zip));
    }

    @GetMapping("/{id}/webhook-events")
    public Map<String, Object> webhookEvents(@PathVariable String id) {
        messages.ensureExists(id);
        List<Map<String, Object>> items = webhooks.eventsFor(id);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", items);
        out.put("total", items.size());
        return out;
    }

    // ------------------------------------------------------------- transitions

    @PostMapping("/{id}/approve")
    public Map<String, Object> approve(@PathVariable String id) {
        return messages.approve(id);
    }

    @PostMapping("/{id}/reject")
    public Map<String, Object> reject(@PathVariable String id,
                                      @RequestBody(required = false) Map<String, Object> body) {
        return messages.reject(id, stringField(body, "reason"));
    }

    @PostMapping("/{id}/cancel")
    public Map<String, Object> cancel(@PathVariable String id,
                                      @RequestBody(required = false) Map<String, Object> body) {
        return messages.cancel(id, stringField(body, "reason"));
    }

    @PostMapping("/{id}/mark-sent")
    public Map<String, Object> markSent(@PathVariable String id,
                                        @RequestBody(required = false) Map<String, Object> body) {
        if (body != null && body.containsKey("confirmed")) {
            Object confirmed = body.get("confirmed");
            if (!(confirmed instanceof Boolean) || !((Boolean) confirmed)) {
                throw ApiException.badRequest("mark-sent requires {\"confirmed\": true} when a confirmation field is sent.");
            }
        }
        return messages.markSent(id);
    }

    // ------------------------------------------------------------------ patch

    @PatchMapping(value = "/{id}", consumes = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> patchJson(@PathVariable String id, @RequestBody JsonNode body) {
        PatchCommand command = mapper.patchJson(body);
        return messages.patch(id, command);
    }

    @PatchMapping(value = "/{id}", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map<String, Object> patchMultipart(
            @PathVariable String id,
            HttpServletRequest request,
            @RequestParam(value = "attachments", required = false) MultipartFile[] files) {
        PatchCommand command = mapper.patchMultipart(request.getParameterMap(), files);
        return messages.patch(id, command);
    }

    // ----------------------------------------------------------------- helpers

    private static ResponseEntity<Map<String, Object>> created(Map<String, Object> body) {
        Object id = body.get("id");
        return ResponseEntity.status(201)
                .header(HttpHeaders.LOCATION, "/api/messages/" + id)
                .body(body);
    }

    private static String stringField(Map<String, Object> body, String field) {
        if (body == null) return null;
        Object value = body.get(field);
        if (value == null) return null;
        if (!(value instanceof String text)) {
            throw ApiException.badRequest(field + " must be a string.");
        }
        return text;
    }
}
