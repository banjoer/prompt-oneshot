package dev.oneshot.outbox.repo;

import dev.oneshot.outbox.model.WebhookAttempt;
import dev.oneshot.outbox.model.WebhookEvent;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class WebhookRepository {
    private final JdbcTemplate jdbc;

    public WebhookRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public static final RowMapper<WebhookEvent> EVENT_MAPPER = (rs, n) -> new WebhookEvent(
            rs.getString("id"), rs.getString("message_id"), rs.getString("event"),
            rs.getInt("revision_number"), rs.getString("payload"), rs.getString("created_at"),
            rs.getString("delivered_at"), rs.getInt("attempts_count"),
            rs.getString("next_attempt_at"), rs.getString("last_error"));

    /** Idempotent: the unique key (message_id, event, revision_number) prevents duplicates. */
    public boolean insertEventIfAbsent(String id, String messageId, String event, int revisionNumber,
                                       String payload, String createdAt) {
        int rows = jdbc.update("""
                INSERT OR IGNORE INTO webhook_events
                  (id, message_id, event, revision_number, payload, created_at, attempts_count, next_attempt_at)
                VALUES (?,?,?,?,?,?,0,?)
                """, id, messageId, event, revisionNumber, payload, createdAt, createdAt);
        return rows > 0;
    }

    public List<WebhookEvent> findByMessage(String messageId) {
        return jdbc.query("""
                SELECT * FROM webhook_events WHERE message_id = ? ORDER BY created_at ASC, id ASC
                """, EVENT_MAPPER, messageId);
    }

    public WebhookEvent findById(String eventId) {
        List<WebhookEvent> rows = jdbc.query("SELECT * FROM webhook_events WHERE id = ?", EVENT_MAPPER, eventId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public List<WebhookAttempt> attempts(String eventId) {
        return jdbc.query("""
                SELECT * FROM webhook_attempts WHERE event_id = ? ORDER BY attempt_number ASC, id ASC
                """, (rs, n) -> new WebhookAttempt(
                rs.getLong("id"), rs.getString("event_id"), rs.getInt("attempt_number"),
                rs.getString("status"), (Integer) rs.getObject("http_status"), rs.getString("error"),
                rs.getString("started_at"), rs.getString("finished_at")), eventId);
    }

    /** The oldest event still eligible for an attempt; used by the single delivery worker. */
    public WebhookEvent nextDue(String nowIso, int maxAttempts) {
        List<WebhookEvent> rows = jdbc.query("""
                SELECT e.* FROM webhook_events e
                JOIN messages m ON m.id = e.message_id
                WHERE e.delivered_at IS NULL
                  AND e.attempts_count < ?
                  AND (e.next_attempt_at IS NULL OR e.next_attempt_at <= ?)
                  AND m.webhook_url IS NOT NULL AND m.webhook_url <> ''
                ORDER BY COALESCE(e.next_attempt_at, e.created_at) ASC, e.created_at ASC
                LIMIT 1
                """, EVENT_MAPPER, maxAttempts, nowIso);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public String webhookUrlFor(String messageId) {
        List<String> urls = jdbc.queryForList(
                "SELECT webhook_url FROM messages WHERE id = ?", String.class, messageId);
        return urls.isEmpty() ? null : urls.get(0);
    }

    public void recordAttempt(String eventId, int attemptNumber, String status, Integer httpStatus,
                              String error, String startedAt, String finishedAt) {
        jdbc.update("""
                INSERT INTO webhook_attempts (event_id, attempt_number, status, http_status, error, started_at, finished_at)
                VALUES (?,?,?,?,?,?,?)
                """, eventId, attemptNumber, status, httpStatus, error, startedAt, finishedAt);
    }

    public void markDelivered(String eventId, int nextAttemptNumber, Integer httpStatus, String finishedAt) {
        jdbc.update("""
                UPDATE webhook_events SET delivered_at = ?, attempts_count = ?, next_attempt_at = NULL, last_error = NULL
                WHERE id = ?
                """, finishedAt, nextAttemptNumber, eventId);
    }

    public void markAttemptFailed(String eventId, int attemptNumber, Integer httpStatus, String error,
                                  String nextAttemptAt) {
        jdbc.update("""
                UPDATE webhook_events SET attempts_count = ?, next_attempt_at = ?, last_error = ?
                WHERE id = ?
                """, attemptNumber, nextAttemptAt, error, eventId);
    }

    public int countPending(String nowIso, int maxAttempts) {
        Integer value = jdbc.queryForObject("""
                SELECT COUNT(*) FROM webhook_events e
                JOIN messages m ON m.id = e.message_id
                WHERE e.delivered_at IS NULL AND e.attempts_count < ?
                  AND (e.next_attempt_at IS NULL OR e.next_attempt_at <= ?)
                  AND m.webhook_url IS NOT NULL AND m.webhook_url <> ''
                """, Integer.class, maxAttempts, nowIso);
        return value == null ? 0 : value;
    }
}
