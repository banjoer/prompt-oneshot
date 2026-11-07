package dev.oneshot.outbox.web;

import java.util.List;
import java.util.Map;

/** A structured, client-safe API error. */
public class ApiException extends RuntimeException {
    private final int status;
    private final String code;
    private final Map<String, Object> details;
    private String currentStatus;
    private List<String> allowedActions;

    public ApiException(int status, String code, String message) {
        this(status, code, message, Map.of());
    }

    public ApiException(int status, String code, String message, Map<String, Object> details) {
        super(message);
        this.status = status;
        this.code = code;
        this.details = details == null ? Map.of() : details;
    }

    public static ApiException badRequest(String message) {
        return new ApiException(400, "validation_error", message);
    }

    public static ApiException badRequest(String message, Map<String, Object> details) {
        return new ApiException(400, "validation_error", message, details);
    }

    public static ApiException notFound(String message) {
        return new ApiException(404, "not_found", message);
    }

    public static ApiException conflict(String message) {
        return new ApiException(409, "conflict", message);
    }

    public static ApiException transition(String message, String currentStatus, List<String> allowedActions) {
        ApiException ex = new ApiException(409, "invalid_transition", message);
        ex.currentStatus = currentStatus;
        ex.allowedActions = allowedActions == null ? List.of() : List.copyOf(allowedActions);
        return ex;
    }

    public static ApiException forbiddenUrl(String message) {
        return new ApiException(400, "unsafe_url", message);
    }

    public static ApiException tooLarge(String message) {
        return new ApiException(413, "payload_too_large", message);
    }

    public int getStatus() { return status; }
    public String getCode() { return code; }
    public Map<String, Object> getDetails() { return details; }
    public String getCurrentStatus() { return currentStatus; }
    public List<String> getAllowedActions() { return allowedActions; }
}
