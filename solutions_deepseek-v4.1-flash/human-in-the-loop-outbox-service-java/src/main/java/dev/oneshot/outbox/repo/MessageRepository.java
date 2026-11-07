package dev.oneshot.outbox.repo;

import dev.oneshot.outbox.model.Channel;
import dev.oneshot.outbox.model.MessageRecord;
import dev.oneshot.outbox.model.MessageStatus;
import dev.oneshot.outbox.model.StatusChange;
import dev.oneshot.outbox.util.Times;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.util.ArrayList;
import java.util.List;

@Repository
public class MessageRepository {
    private final JdbcTemplate jdbc;

    public MessageRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public static final RowMapper<MessageRecord> MAPPER = (rs, rowNum) -> new MessageRecord(
            rs.getString("id"),
            Channel.parse(rs.getString("channel")),
            rs.getString("destination"),
            rs.getString("normalized_destination"),
            rs.getString("destination_label"),
            rs.getString("subject"),
            rs.getString("body"),
            MessageStatus.fromDb(rs.getString("status")),
            rs.getString("created_at"),
            rs.getString("updated_at"),
            rs.getString("expires_at"),
            rs.getString("webhook_url"),
            rs.getString("rejection_reason"),
            rs.getString("rejection_at"),
            rs.getInt("revision_number"),
            rs.getString("source"),
            rs.getString("metadata")
    );

    public void insert(MessageRecord m) {
        jdbc.update("""
                INSERT INTO messages (id, channel, destination, normalized_destination, destination_label,
                  subject, body, status, created_at, updated_at, expires_at, webhook_url, rejection_reason,
                  rejection_at, revision_number, source, metadata)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                m.id(), m.channel().wire(), m.destination(), m.normalizedDestination(), m.destinationLabel(),
                m.subject(), m.body(), m.status().wire(), m.createdAt(), m.updatedAt(), m.expiresAt(),
                m.webhookUrl(), m.rejectionReason(), m.rejectionAt(), m.revisionNumber(), m.source(), m.metadata());
    }

    public MessageRecord findById(String id) {
        List<MessageRecord> rows = jdbc.query("SELECT * FROM messages WHERE id = ?", MAPPER, id);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public List<MessageRecord> findDueForExpiration(String nowIso) {
        return jdbc.query("""
                SELECT * FROM messages
                WHERE status IN ('pending','approved') AND expires_at IS NOT NULL AND expires_at <= ?
                ORDER BY expires_at ASC
                """, MAPPER, nowIso);
    }

    /**
     * Compare-and-set status change. Returns the number of rows changed (0 or 1).
     * Expiration is part of the approve guard so an expired message can never be approved.
     */
    public int casStatus(String id, MessageStatus expected, MessageStatus next, String nowIso,
                         String rejectionReason, String rejectionAt, boolean requireNotExpired) {
        String expiryGuard = requireNotExpired
                ? " AND (expires_at IS NULL OR expires_at > ?)"
                : "";
        List<Object> args = new ArrayList<>();
        args.add(next.wire());
        args.add(nowIso);
        args.add(rejectionReason);
        args.add(rejectionAt);
        args.add(id);
        args.add(expected.wire());
        if (requireNotExpired) args.add(nowIso);
        return jdbc.update("""
                UPDATE messages SET status = ?, updated_at = ?, rejection_reason = ?, rejection_at = ?
                WHERE id = ? AND status = ?
                """ + expiryGuard, args.toArray());
    }

    public int expireCas(String id, MessageStatus expected, String nowIso) {
        return jdbc.update("""
                UPDATE messages SET status = 'stale', updated_at = ?
                WHERE id = ? AND status = ? AND expires_at IS NOT NULL AND expires_at <= ?
                """, nowIso, id, expected.wire(), nowIso);
    }

    public int updateContent(String id, int expectedRevision, Channel channel, String destination,
                             String normalizedDestination, String destinationLabel, String subject,
                             String body, String metadata, String expiresAt, String nowIso) {
        return jdbc.update("""
                UPDATE messages SET channel = ?, destination = ?, normalized_destination = ?,
                  destination_label = ?, subject = ?, body = ?, metadata = ?, expires_at = ?,
                  status = 'pending', rejection_reason = NULL, rejection_at = NULL,
                  revision_number = revision_number + 1, updated_at = ?
                WHERE id = ? AND revision_number = ? AND status IN ('pending','rejected')
                """, channel.wire(), destination, normalizedDestination, destinationLabel, subject, body,
                metadata, expiresAt, nowIso, id, expectedRevision);
    }

    public void insertStatusHistory(String messageId, String from, String to, String reason,
                                    int revisionNumber, String at) {
        jdbc.update("""
                INSERT INTO status_history (message_id, from_status, to_status, reason, revision_number, created_at)
                VALUES (?,?,?,?,?,?)
                """, messageId, from, to, reason, revisionNumber, at);
    }

    public List<StatusChange> history(String messageId) {
        return jdbc.query("""
                SELECT * FROM status_history WHERE message_id = ? ORDER BY id ASC
                """, (rs, n) -> new StatusChange(
                rs.getLong("id"), rs.getString("message_id"), rs.getString("from_status"),
                rs.getString("to_status"), rs.getString("reason"), rs.getInt("revision_number"),
                rs.getString("created_at")), messageId);
    }

    public List<MessageRecord> list(List<MessageStatus> statuses, Channel channel, String destination,
                                    String createdAfter, String createdBefore,
                                    String expiresAfter, String expiresBefore,
                                    String sort, int limit, int offset) {
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        List<Object> args = new ArrayList<>();
        if (statuses != null && !statuses.isEmpty()) {
            where.append(" AND m.status IN (");
            for (int i = 0; i < statuses.size(); i++) {
                if (i > 0) where.append(',');
                where.append('?');
                args.add(statuses.get(i).wire());
            }
            where.append(')');
        }
        if (channel != null) {
            where.append(" AND m.channel = ?");
            args.add(channel.wire());
        }
        if (destination != null && !destination.isBlank()) {
            String like = "%" + destination.trim().toLowerCase() + "%";
            where.append(" AND (lower(m.destination) LIKE ? OR lower(m.normalized_destination) LIKE ?"
                    + " OR lower(COALESCE(m.destination_label,'')) LIKE ?"
                    + " OR lower(COALESCE(l.label,'')) LIKE ?)");
            args.add(like);
            args.add(like);
            args.add(like);
            args.add(like);
        }
        if (createdAfter != null) { where.append(" AND m.created_at >= ?"); args.add(createdAfter); }
        if (createdBefore != null) { where.append(" AND m.created_at <= ?"); args.add(createdBefore); }
        if (expiresAfter != null) { where.append(" AND m.expires_at IS NOT NULL AND m.expires_at >= ?"); args.add(expiresAfter); }
        if (expiresBefore != null) { where.append(" AND m.expires_at IS NOT NULL AND m.expires_at <= ?"); args.add(expiresBefore); }

        String order = switch (sort == null ? "newest" : sort) {
            case "oldest" -> " ORDER BY m.created_at ASC, m.id ASC";
            case "expires_soon" -> " ORDER BY CASE WHEN m.expires_at IS NULL THEN 1 ELSE 0 END ASC, m.expires_at ASC, m.created_at DESC";
            case "expires_late" -> " ORDER BY CASE WHEN m.expires_at IS NULL THEN 1 ELSE 0 END ASC, m.expires_at DESC, m.created_at DESC";
            case "review" -> " ORDER BY CASE m.status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 WHEN 'rejected' THEN 2 ELSE 3 END ASC, m.created_at DESC, m.id DESC";
            default -> " ORDER BY m.created_at DESC, m.id DESC";
        };

        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(limit);
        pageArgs.add(offset);
        return jdbc.query("SELECT m.* FROM messages m LEFT JOIN destination_labels l"
                        + " ON l.channel = m.channel AND l.normalized_destination = m.normalized_destination"
                        + where + order + " LIMIT ? OFFSET ?",
                MAPPER, pageArgs.toArray());
    }

    public int count(List<MessageStatus> statuses, Channel channel, String destination,
                     String createdAfter, String createdBefore, String expiresAfter, String expiresBefore) {
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        List<Object> args = new ArrayList<>();
        if (statuses != null && !statuses.isEmpty()) {
            where.append(" AND m.status IN (");
            for (int i = 0; i < statuses.size(); i++) {
                if (i > 0) where.append(',');
                where.append('?');
                args.add(statuses.get(i).wire());
            }
            where.append(')');
        }
        if (channel != null) {
            where.append(" AND m.channel = ?");
            args.add(channel.wire());
        }
        if (destination != null && !destination.isBlank()) {
            String like = "%" + destination.trim().toLowerCase() + "%";
            where.append(" AND (lower(m.destination) LIKE ? OR lower(m.normalized_destination) LIKE ?"
                    + " OR lower(COALESCE(m.destination_label,'')) LIKE ?"
                    + " OR lower(COALESCE(l.label,'')) LIKE ?)");
            args.add(like);
            args.add(like);
            args.add(like);
            args.add(like);
        }
        if (createdAfter != null) { where.append(" AND m.created_at >= ?"); args.add(createdAfter); }
        if (createdBefore != null) { where.append(" AND m.created_at <= ?"); args.add(createdBefore); }
        if (expiresAfter != null) { where.append(" AND m.expires_at IS NOT NULL AND m.expires_at >= ?"); args.add(expiresAfter); }
        if (expiresBefore != null) { where.append(" AND m.expires_at IS NOT NULL AND m.expires_at <= ?"); args.add(expiresBefore); }
        Integer count = jdbc.queryForObject("SELECT COUNT(*) FROM messages m LEFT JOIN destination_labels l"
                + " ON l.channel = m.channel AND l.normalized_destination = m.normalized_destination"
                + where, Integer.class, args.toArray());
        return count == null ? 0 : count;
    }

    public int totalCount() {
        Integer count = jdbc.queryForObject("SELECT COUNT(*) FROM messages", Integer.class);
        return count == null ? 0 : count;
    }

    public String now() {
        return Times.nowIso();
    }
}
