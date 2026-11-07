package dev.oneshot.outbox.service;

import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;

public record PatchCommand(
        boolean channelPresent,
        String channel,
        boolean destinationPresent,
        String destination,
        boolean subjectPresent,
        String subject,
        boolean bodyPresent,
        String body,
        boolean expiresAtPresent,
        String expiresAt,
        Long ttlSeconds,
        boolean metadataPresent,
        Map<String, Object> metadata,
        boolean destinationLabelPresent,
        String destinationLabel,
        boolean referencesPresent,
        List<String> references,
        List<SubmitCommand.UrlAttachment> attachments,
        List<MultipartFile> files
) {}
