package dev.oneshot.outbox.web;

import com.fasterxml.jackson.databind.JsonNode;
import dev.oneshot.outbox.service.PatchCommand;
import dev.oneshot.outbox.service.SubmitCommand;
import dev.oneshot.outbox.util.Json;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Parses JSON and multipart payloads into commands, with strict shape validation. */
@Component
public class RequestMapper {
    private final Json json;

    public RequestMapper(Json json) {
        this.json = json;
    }

    // ------------------------------------------------------------- submit JSON

    public SubmitCommand submitJson(JsonNode body) {
        if (body == null || !body.isObject()) {
            throw ApiException.badRequest("The request body must be a JSON object.");
        }
        return new SubmitCommand(
                text(body, "channel"),
                text(body, "destination"),
                text(body, "subject"),
                text(body, "body"),
                body.has("expires_at"),
                text(body, "expires_at"),
                longValue(body.get("ttl_seconds"), "ttl_seconds"),
                text(body, "webhook_url"),
                text(body, "source"),
                metadataJson(body),
                text(body, "destination_label"),
                referencesJson(body.get("references")),
                attachmentsJson(body.get("attachments")),
                null
        );
    }

    // ---------------------------------------------------------- submit multipart

    public SubmitCommand submitMultipart(Map<String, String[]> params, MultipartFile[] files) {
        return new SubmitCommand(
                param(params, "channel"),
                param(params, "destination"),
                param(params, "subject"),
                param(params, "body"),
                params.containsKey("expires_at"),
                param(params, "expires_at"),
                parseLong(param(params, "ttl_seconds"), "ttl_seconds"),
                param(params, "webhook_url"),
                param(params, "source"),
                metadataForm(params.get("metadata")),
                param(params, "destination_label"),
                allParams(params, "references"),
                null,
                files == null ? List.of() : List.of(files)
        );
    }

    // -------------------------------------------------------------- patch JSON

    public PatchCommand patchJson(JsonNode body) {
        if (body == null || !body.isObject()) {
            throw ApiException.badRequest("The request body must be a JSON object.");
        }
        if (body.has("status")) {
            throw ApiException.badRequest("status cannot be changed through PATCH. Use the explicit approve, "
                    + "reject, cancel, or mark-sent operations.");
        }
        return new PatchCommand(
                body.has("channel"), text(body, "channel"),
                body.has("destination"), text(body, "destination"),
                body.has("subject"), text(body, "subject"),
                body.has("body"), text(body, "body"),
                body.has("expires_at"), text(body, "expires_at"),
                longValue(body.get("ttl_seconds"), "ttl_seconds"),
                body.has("metadata"), metadataJson(body),
                body.has("destination_label"), text(body, "destination_label"),
                body.has("references"), referencesJson(body.get("references")),
                attachmentsJson(body.get("attachments")),
                null
        );
    }

    // ----------------------------------------------------------- patch multipart

    public PatchCommand patchMultipart(Map<String, String[]> params, MultipartFile[] files) {
        if (params.containsKey("status")) {
            throw ApiException.badRequest("status cannot be changed through PATCH. Use the explicit approve, "
                    + "reject, cancel, or mark-sent operations.");
        }
        return new PatchCommand(
                params.containsKey("channel"), param(params, "channel"),
                params.containsKey("destination"), param(params, "destination"),
                params.containsKey("subject"), param(params, "subject"),
                params.containsKey("body"), param(params, "body"),
                params.containsKey("expires_at"), param(params, "expires_at"),
                parseLong(param(params, "ttl_seconds"), "ttl_seconds"),
                params.containsKey("metadata"), metadataForm(params.get("metadata")),
                params.containsKey("destination_label"), param(params, "destination_label"),
                params.containsKey("references"), allParams(params, "references"),
                null,
                files == null ? List.of() : List.of(files)
        );
    }

    // ----------------------------------------------------------------- helpers

    private static String text(JsonNode body, String field) {
        JsonNode node = body.get(field);
        if (node == null || node.isNull()) return null;
        if (!node.isTextual()) {
            throw ApiException.badRequest(field + " must be a string.");
        }
        return node.asText();
    }

    private static Long longValue(JsonNode node, String field) {
        if (node == null || node.isNull()) return null;
        if (node.isIntegralNumber() && node.canConvertToLong()) return node.asLong();
        if (node.isTextual() && node.asText().trim().matches("-?[0-9]+")) {
            try {
                return Long.parseLong(node.asText().trim());
            } catch (NumberFormatException ignored) {
                // Fall through to the error below.
            }
        }
        throw ApiException.badRequest(field + " must be an integer.");
    }

    private static Long parseLong(String value, String field) {
        if (value == null || value.isBlank()) return null;
        try {
            return Long.parseLong(value.trim());
        } catch (NumberFormatException ex) {
            throw ApiException.badRequest(field + " must be an integer.");
        }
    }

    private Map<String, Object> metadataJson(JsonNode body) {
        if (!body.has("metadata")) return null;
        JsonNode node = body.get("metadata");
        if (node == null || node.isNull()) return null;
        if (!node.isObject()) throw ApiException.badRequest("metadata must be a JSON object.");
        return toMap(node);
    }

    private Map<String, Object> metadataForm(String[] values) {
        if (values == null || values.length == 0) return null;
        String raw = values[0];
        if (raw == null || raw.isBlank()) return null;
        JsonNode node;
        try {
            node = json.readTree(raw);
        } catch (IllegalArgumentException ex) {
            throw ApiException.badRequest("metadata must be a valid JSON object.");
        }
        if (!node.isObject()) throw ApiException.badRequest("metadata must be a JSON object.");
        return toMap(node);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> toMap(JsonNode node) {
        return json.mapper().convertValue(node, LinkedHashMap.class);
    }

    private static List<String> referencesJson(JsonNode node) {
        if (node == null || node.isNull()) return List.of();
        if (!node.isArray()) throw ApiException.badRequest("references must be an array of URL strings.");
        List<String> out = new ArrayList<>();
        for (JsonNode item : node) {
            if (!item.isTextual()) throw ApiException.badRequest("references must contain only URL strings.");
            out.add(item.asText());
        }
        return out;
    }

    private static List<SubmitCommand.UrlAttachment> attachmentsJson(JsonNode node) {
        if (node == null || node.isNull()) return null;
        if (!node.isArray()) throw ApiException.badRequest("attachments must be an array of objects.");
        List<SubmitCommand.UrlAttachment> out = new ArrayList<>();
        for (JsonNode item : node) {
            if (!item.isObject()) throw ApiException.badRequest("attachments entries must be objects.");
            String kind = text(item, "kind");
            String url = text(item, "url");
            String filename = text(item, "filename");
            if (kind == null || kind.isBlank()) {
                throw ApiException.badRequest("attachments[].kind is required (url_reference or url_download).");
            }
            if (url == null || url.isBlank()) {
                throw ApiException.badRequest("attachments[].url is required.");
            }
            out.add(new SubmitCommand.UrlAttachment(kind, url, filename));
        }
        return out;
    }

    private static String param(Map<String, String[]> params, String key) {
        String[] values = params.get(key);
        return values == null || values.length == 0 ? null : values[0];
    }

    private static boolean has(Map<String, String[]> params, String key) {
        return params.containsKey(key);
    }

    private static List<String> allParams(Map<String, String[]> params, String key) {
        List<String> out = new ArrayList<>();
        String[] values = params.get(key);
        if (values != null) out.addAll(List.of(values));
        String[] arrayValues = params.get(key + "[]");
        if (arrayValues != null) out.addAll(List.of(arrayValues));
        return out;
    }
}
