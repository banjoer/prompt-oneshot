package dev.oneshot.outbox.service;

import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;

public record SubmitCommand(
        String channel,
        String destination,
        String subject,
        String body,
        boolean expiresAtPresent,
        String expiresAt,
        Long ttlSeconds,
        String webhookUrl,
        String source,
        Map<String, Object> metadata,
        String destinationLabel,
        List<String> references,
        List<UrlAttachment> attachments,
        List<MultipartFile> files
) {
    public record UrlAttachment(String kind, String url, String filename) {}
}
