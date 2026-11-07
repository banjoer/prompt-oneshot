package dev.oneshot.outbox.repo;

import dev.oneshot.outbox.model.AttachmentRecord;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class AttachmentRepository {
    private final JdbcTemplate jdbc;

    public AttachmentRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(AttachmentRecord a) {
        jdbc.update("""
                INSERT INTO attachments (id, message_id, original_filename, mime_type, size_bytes,
                  storage_name, created_at, source_type, source_url)
                VALUES (?,?,?,?,?,?,?,?,?)
                """, a.id(), a.messageId(), a.originalFilename(), a.mimeType(), a.sizeBytes(),
                a.storageName(), a.createdAt(), a.sourceType(), a.sourceUrl());
    }

    public AttachmentRecord findById(String messageId, String attachmentId) {
        List<AttachmentRecord> rows = jdbc.query("""
                SELECT * FROM attachments WHERE id = ? AND message_id = ?
                """, RevisionRepository.ATTACHMENT_MAPPER, attachmentId, messageId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public long sumSizeForMessage(String messageId) {
        Long sum = jdbc.queryForObject(
                "SELECT COALESCE(SUM(size_bytes),0) FROM attachments WHERE message_id = ?",
                Long.class, messageId);
        return sum == null ? 0 : sum;
    }

    public int countForMessage(String messageId) {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM attachments WHERE message_id = ?", Integer.class, messageId);
        return count == null ? 0 : count;
    }
}
