package dev.oneshot.outbox.attachments;

import dev.oneshot.outbox.config.OutboxProperties;
import dev.oneshot.outbox.util.Filenames;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.UUID;

/** Local attachment bytes, stored under the configured attachment directory only. */
@Component
public class LocalAttachmentStorage implements AttachmentStorage {
    private final Path root;

    public LocalAttachmentStorage(OutboxProperties properties) throws IOException {
        this.root = Path.of(properties.getAttachmentDir()).toAbsolutePath().normalize();
        Files.createDirectories(root);
    }

    public Path root() {
        return root;
    }

    @Override
    public synchronized String save(byte[] bytes, String originalFilename) throws IOException {
        String storageName = "att_" + UUID.randomUUID().toString().replace("-", "")
                + Filenames.safeExtension(Filenames.sanitize(originalFilename));
        Path target = resolveInsideRoot(storageName);
        try (InputStream in = new java.io.ByteArrayInputStream(bytes)) {
            Files.copy(in, target, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        }
        return storageName;
    }

    @Override
    public Path path(String storageName) throws IOException {
        Path path = resolveInsideRoot(storageName);
        if (!Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)) {
            throw new java.nio.file.NoSuchFileException("Attachment file missing: " + storageName);
        }
        return path;
    }

    @Override
    public byte[] load(String storageName) throws IOException {
        return Files.readAllBytes(path(storageName));
    }

    @Override
    public void delete(String storageName) {
        try {
            Files.deleteIfExists(resolveInsideRoot(storageName));
        } catch (Exception ignored) {
            // Best-effort cleanup; the database record is the source of truth.
        }
    }

    private Path resolveInsideRoot(String storageName) {
        if (storageName == null || storageName.isBlank()) {
            throw new IllegalArgumentException("Storage name must not be empty.");
        }
        String name = storageName;
        if (name.contains("/") || name.contains("\\") || name.contains("..")
                || name.startsWith(".") || Path.of(name).isAbsolute()) {
            throw new IllegalArgumentException("Unsafe storage reference rejected.");
        }
        Path path = root.resolve(name).normalize();
        if (!path.startsWith(root) || path.equals(root)) {
            throw new IllegalArgumentException("Unsafe storage reference rejected.");
        }
        return path;
    }
}
