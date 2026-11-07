package dev.oneshot.outbox.attachments;

import dev.oneshot.outbox.config.OutboxProperties;
import dev.oneshot.outbox.model.AttachmentRecord;
import dev.oneshot.outbox.repo.AttachmentRepository;
import dev.oneshot.outbox.util.Filenames;
import dev.oneshot.outbox.util.Times;
import dev.oneshot.outbox.web.ApiException;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

@Service
public class AttachmentService {
    private final OutboxProperties properties;
    private final AttachmentStorage storage;
    private final UrlDownloader downloader;
    private final AttachmentRepository repository;

    public AttachmentService(OutboxProperties properties, AttachmentStorage storage,
                             UrlDownloader downloader, AttachmentRepository repository) {
        this.properties = properties;
        this.storage = storage;
        this.downloader = downloader;
        this.repository = repository;
    }

    /** Stages bytes on disk and returns unpersisted attachment records. */
    public List<AttachmentRecord> stageMultipart(String messageId, List<MultipartFile> files) {
        List<AttachmentRecord> staged = new ArrayList<>();
        if (files == null) return staged;
        try {
            for (MultipartFile file : files) {
                if (file == null) continue;
                String rawName = file.getOriginalFilename();
                if ((rawName == null || rawName.isBlank()) && file.getSize() == 0) continue;
                long size = file.getSize();
                if (size > properties.getMaxAttachmentBytes()) {
                    throw ApiException.tooLarge("Attachment '" + Filenames.sanitize(rawName)
                            + "' is " + size + " bytes; the per-file limit is "
                            + properties.getMaxAttachmentBytes() + " bytes.");
                }
                byte[] bytes = file.getBytes();
                if (bytes.length > properties.getMaxAttachmentBytes()) {
                    throw ApiException.tooLarge("Attachment exceeds the configured per-file limit of "
                            + properties.getMaxAttachmentBytes() + " bytes.");
                }
                staged.add(storeBytes(messageId, bytes, rawName, sanitizeMime(file.getContentType()),
                        "multipart", null));
            }
            return staged;
        } catch (IOException ex) {
            discardStaged(staged);
            throw ApiException.badRequest("Could not read an uploaded attachment: " + ex.getMessage());
        } catch (RuntimeException ex) {
            discardStaged(staged);
            throw ex;
        }
    }

    /** Downloads a URL once, verifying every redirect, and stages the resulting file. */
    public AttachmentRecord stageDownload(String messageId, String url, String explicitFilename) {
        UrlDownloader.Downloaded downloaded = downloader.download(url, properties.getMaxAttachmentBytes());
        String filename = explicitFilename != null && !explicitFilename.isBlank()
                ? explicitFilename : downloaded.filename();
        return storeBytes(messageId, downloaded.bytes(), filename, downloaded.mimeType(),
                "url_download", downloaded.sourceUrl());
    }

    private AttachmentRecord storeBytes(String messageId, byte[] bytes, String filename, String mimeType,
                                         String sourceType, String sourceUrl) {
        String safeName = Filenames.sanitize(filename);
        String storageName;
        try {
            storageName = storage.save(bytes, safeName);
        } catch (IOException ex) {
            throw new IllegalStateException("Could not store attachment bytes", ex);
        }
        return new AttachmentRecord(
                Times.newId("att_"), messageId, safeName, Filenames.sanitizeMimeType(mimeType),
                bytes.length, storageName, Times.nowIso(), sourceType, sourceUrl);
    }

    private static String sanitizeMime(String value) {
        return Filenames.sanitizeMimeType(value);
    }

    public void persist(AttachmentRecord attachment) {
        repository.insert(attachment);
    }

    public void discardStaged(List<AttachmentRecord> staged) {
        if (staged == null) return;
        for (AttachmentRecord attachment : staged) {
            storage.delete(attachment.storageName());
        }
    }

    public AttachmentRecord require(String messageId, String attachmentId) {
        AttachmentRecord attachment = repository.findById(messageId, attachmentId);
        if (attachment == null) {
            throw ApiException.notFound("Attachment " + attachmentId + " was not found for message " + messageId + ".");
        }
        return attachment;
    }

    public Path requirePath(AttachmentRecord attachment) {
        try {
            return storage.path(attachment.storageName());
        } catch (IOException ex) {
            throw ApiException.notFound("The stored bytes for attachment " + attachment.id()
                    + " are missing. The attachment record is retained for audit purposes.");
        }
    }

    public byte[] zipForZipDownload(List<AttachmentRecord> attachments) {
        Set<String> used = new HashSet<>();
        try (ByteArrayOutputStream out = new ByteArrayOutputStream();
             ZipOutputStream zip = new ZipOutputStream(out)) {
            for (AttachmentRecord attachment : attachments) {
                String name = uniqueName(attachment.originalFilename(), used);
                zip.putNextEntry(new ZipEntry(name));
                zip.write(storage.load(attachment.storageName()));
                zip.closeEntry();
            }
            zip.finish();
            return out.toByteArray();
        } catch (IOException ex) {
            throw ApiException.notFound("One or more attachment files are missing from local storage.");
        }
    }

    private static String uniqueName(String original, Set<String> used) {
        String name = Filenames.sanitize(original);
        if (used.add(name)) return name;
        String base = name;
        String ext = "";
        int dot = name.lastIndexOf('.');
        if (dot > 0) {
            base = name.substring(0, dot);
            ext = name.substring(dot);
        }
        int n = 2;
        while (!used.add(base + "-" + n + ext)) n++;
        return base + "-" + n + ext;
    }

    public long perFileLimit() { return properties.getMaxAttachmentBytes(); }
    public long perMessageLimit() { return properties.getMaxMessageAttachmentBytes(); }
}
