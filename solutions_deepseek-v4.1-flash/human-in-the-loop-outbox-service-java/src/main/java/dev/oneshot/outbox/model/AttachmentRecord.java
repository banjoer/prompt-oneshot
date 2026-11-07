package dev.oneshot.outbox.model;

import java.util.List;

public record AttachmentRecord(
        String id,
        String messageId,
        String originalFilename,
        String mimeType,
        long sizeBytes,
        String storageName,
        String createdAt,
        String sourceType,
        String sourceUrl
) {}

