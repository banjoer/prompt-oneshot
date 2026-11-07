package dev.oneshot.outbox.attachments;

import java.io.IOException;
import java.nio.file.Path;

/** Small storage abstraction so attachment persistence is not tied to HTTP handlers. */
public interface AttachmentStorage {
    String save(byte[] bytes, String originalFilename) throws IOException;

    Path path(String storageName) throws IOException;

    byte[] load(String storageName) throws IOException;

    void delete(String storageName);
}
