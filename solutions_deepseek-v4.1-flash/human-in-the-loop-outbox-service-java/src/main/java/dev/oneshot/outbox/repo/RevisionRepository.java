package dev.oneshot.outbox.repo;

import dev.oneshot.outbox.model.AttachmentRecord;
import dev.oneshot.outbox.model.Channel;
import dev.oneshot.outbox.model.MessageRecord;
import dev.oneshot.outbox.model.MessageStatus;
import dev.oneshot.outbox.model.RevisionRecord;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class RevisionRepository {
    private final JdbcTemplate jdbc;

    public RevisionRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public static final RowMapper<AttachmentRecord> ATTACHMENT_MAPPER = (rs, n) -> new AttachmentRecord(
            rs.getString("id"), rs.getString("message_id"), rs.getString("original_filename"),
            rs.getString("mime_type"), rs.getLong("size_bytes"), rs.getString("storage_name"),
            rs.getString("created_at"), rs.getString("source_type"), rs.getString("source_url"));

    public long insertFromMessage(MessageRecord m) {
        return insertFromMessage(m, m.createdAt());
    }

    public long insertFromMessage(MessageRecord m, String revisionCreatedAt) {
        jdbc.update("""
                INSERT INTO message_revisions (message_id, revision_number, channel, destination,
                  normalized_destination, destination_label, subject, body, metadata, expires_at,
                  rejection_reason, rejection_at, status, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, m.id(), m.revisionNumber(), m.channel().wire(), m.destination(),
                m.normalizedDestination(), m.destinationLabel(), m.subject(), m.body(), m.metadata(),
                m.expiresAt(), m.rejectionReason(), m.rejectionAt(), m.status().wire(), revisionCreatedAt);
        Long id = jdbc.queryForObject("SELECT last_insert_rowid()", Long.class);
        return id == null ? 0 : id;
    }

    public void linkAttachment(long revisionId, String attachmentId, int position) {
        jdbc.update("INSERT INTO revision_attachments (revision_id, attachment_id, position) VALUES (?,?,?)",
                revisionId, attachmentId, position);
    }

    public void insertReference(long revisionId, int position, String url) {
        jdbc.update("INSERT INTO revision_references (revision_id, position, url) VALUES (?,?,?)",
                revisionId, position, url);
    }

    public void updateRejection(String messageId, int revisionNumber, String reason, String at) {
        jdbc.update("""
                UPDATE message_revisions SET rejection_reason = ?, rejection_at = ?
                WHERE message_id = ? AND revision_number = ?
                """, reason, at, messageId, revisionNumber);
    }

    public List<RevisionRecord> findByMessage(String messageId) {
        List<RevisionRecord> revisions = jdbc.query("""
                SELECT * FROM message_revisions WHERE message_id = ? ORDER BY revision_number ASC
                """, (rs, n) -> new RevisionRecord(
                rs.getLong("id"), rs.getString("message_id"), rs.getInt("revision_number"),
                Channel.parse(rs.getString("channel")), rs.getString("destination"),
                rs.getString("normalized_destination"), rs.getString("destination_label"),
                rs.getString("subject"), rs.getString("body"), rs.getString("metadata"),
                rs.getString("expires_at"), rs.getString("rejection_reason"), rs.getString("rejection_at"),
                MessageStatus.fromDb(rs.getString("status")), rs.getString("created_at"),
                null, null), messageId);
        return revisions.stream()
                .map(r -> new RevisionRecord(r.id(), r.messageId(), r.revisionNumber(), r.channel(),
                        r.destination(), r.normalizedDestination(), r.destinationLabel(), r.subject(),
                        r.body(), r.metadata(), r.expiresAt(), r.rejectionReason(), r.rejectionAt(),
                        r.status(), r.createdAt(), attachments(r.id()), references(r.id())))
                .toList();
    }

    public List<AttachmentRecord> attachments(long revisionId) {
        return jdbc.query("""
                SELECT a.* FROM attachments a
                JOIN revision_attachments ra ON ra.attachment_id = a.id
                WHERE ra.revision_id = ? ORDER BY ra.position ASC
                """, ATTACHMENT_MAPPER, revisionId);
    }

    public List<String> references(long revisionId) {
        return jdbc.queryForList(
                "SELECT url FROM revision_references WHERE revision_id = ? ORDER BY position ASC",
                String.class, revisionId);
    }

    public List<AttachmentRecord> attachmentsForMessageRevision(String messageId, int revisionNumber) {
        return jdbc.query("""
                SELECT a.* FROM attachments a
                JOIN revision_attachments ra ON ra.attachment_id = a.id
                JOIN message_revisions r ON r.id = ra.revision_id
                WHERE r.message_id = ? AND r.revision_number = ?
                ORDER BY ra.position ASC
                """, ATTACHMENT_MAPPER, messageId, revisionNumber);
    }

    public List<String> referencesForMessageRevision(String messageId, int revisionNumber) {
        return jdbc.queryForList("""
                SELECT rr.url FROM revision_references rr
                JOIN message_revisions r ON r.id = rr.revision_id
                WHERE r.message_id = ? AND r.revision_number = ?
                ORDER BY rr.position ASC
                """, String.class, messageId, revisionNumber);
    }
}
