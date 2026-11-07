package dev.oneshot.outbox.config;

import dev.oneshot.outbox.util.Times;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/**
 * Idempotent schema initialization and forward-only migrations.
 *
 * Every migration runs once and is recorded in schema_migrations. The application
 * startup is safe to repeat; existing data is never dropped.
 */
@Component
public class DatabaseInitializer {
    private static final Logger log = LoggerFactory.getLogger(DatabaseInitializer.class);

    private final JdbcTemplate jdbc;

    public DatabaseInitializer(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    private static final List<String> V1 = List.of(
            """
            CREATE TABLE IF NOT EXISTS messages (
              id TEXT PRIMARY KEY,
              channel TEXT NOT NULL,
              destination TEXT NOT NULL,
              normalized_destination TEXT NOT NULL,
              destination_label TEXT,
              subject TEXT,
              body TEXT NOT NULL,
              status TEXT NOT NULL CHECK (status IN
                ('pending','approved','sent','rejected','stale','cancelled')),
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              expires_at TEXT,
              webhook_url TEXT,
              rejection_reason TEXT,
              rejection_at TEXT,
              revision_number INTEGER NOT NULL DEFAULT 1,
              source TEXT,
              metadata TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS message_revisions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
              revision_number INTEGER NOT NULL,
              channel TEXT NOT NULL,
              destination TEXT NOT NULL,
              normalized_destination TEXT NOT NULL,
              destination_label TEXT,
              subject TEXT,
              body TEXT NOT NULL,
              metadata TEXT,
              expires_at TEXT,
              rejection_reason TEXT,
              rejection_at TEXT,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE (message_id, revision_number)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS attachments (
              id TEXT PRIMARY KEY,
              message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
              original_filename TEXT NOT NULL,
              mime_type TEXT NOT NULL,
              size_bytes INTEGER NOT NULL,
              storage_name TEXT NOT NULL,
              created_at TEXT NOT NULL,
              source_type TEXT NOT NULL CHECK (source_type IN ('multipart','url_download')),
              source_url TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS revision_attachments (
              revision_id INTEGER NOT NULL REFERENCES message_revisions(id) ON DELETE CASCADE,
              attachment_id TEXT NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
              position INTEGER NOT NULL,
              PRIMARY KEY (revision_id, attachment_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS revision_references (
              revision_id INTEGER NOT NULL REFERENCES message_revisions(id) ON DELETE CASCADE,
              position INTEGER NOT NULL,
              url TEXT NOT NULL,
              PRIMARY KEY (revision_id, position)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS status_history (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
              from_status TEXT,
              to_status TEXT NOT NULL,
              reason TEXT,
              revision_number INTEGER NOT NULL,
              created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS destination_labels (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              channel TEXT NOT NULL,
              normalized_destination TEXT NOT NULL,
              label TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (channel, normalized_destination)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS webhook_events (
              id TEXT PRIMARY KEY,
              message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
              event TEXT NOT NULL,
              revision_number INTEGER NOT NULL,
              payload TEXT NOT NULL,
              created_at TEXT NOT NULL,
              delivered_at TEXT,
              attempts_count INTEGER NOT NULL DEFAULT 0,
              next_attempt_at TEXT,
              last_error TEXT,
              UNIQUE (message_id, event, revision_number)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS webhook_attempts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id TEXT NOT NULL REFERENCES webhook_events(id) ON DELETE CASCADE,
              attempt_number INTEGER NOT NULL,
              status TEXT NOT NULL,
              http_status INTEGER,
              error TEXT,
              started_at TEXT NOT NULL,
              finished_at TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status)",
            "CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel)",
            "CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_messages_expires ON messages(expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_messages_destination ON messages(channel, normalized_destination)",
            "CREATE INDEX IF NOT EXISTS idx_revisions_message ON message_revisions(message_id, revision_number)",
            "CREATE INDEX IF NOT EXISTS idx_history_message ON status_history(message_id, id)",
            "CREATE INDEX IF NOT EXISTS idx_webhook_message ON webhook_events(message_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_webhook_pending ON webhook_events(delivered_at, next_attempt_at)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_label_per_channel ON destination_labels(channel, lower(label))"
    );

    @PostConstruct
    public void initialize() {
        jdbc.execute("PRAGMA journal_mode=WAL");
        jdbc.execute("PRAGMA foreign_keys=ON");
        jdbc.execute("PRAGMA synchronous=NORMAL");
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  version INTEGER PRIMARY KEY,
                  applied_at TEXT NOT NULL
                )
                """);
        apply(1, V1);
        Integer version = jdbc.queryForObject("SELECT COALESCE(MAX(version), 0) FROM schema_migrations", Integer.class);
        log.info("SQLite schema ready at version {}", version);
    }

    private void apply(int version, List<String> statements) {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM schema_migrations WHERE version = ?", Integer.class, version);
        if (count != null && count > 0) return;
        for (String sql : statements) {
            jdbc.execute(sql);
        }
        jdbc.update("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)", version, Times.nowIso());
        log.info("Applied database migration {}", version);
    }

    public Map<String, Object> status() {
        Integer version = jdbc.queryForObject("SELECT COALESCE(MAX(version), 0) FROM schema_migrations", Integer.class);
        return Map.of("schema_version", version == null ? 0 : version,
                "journal_mode", jdbc.queryForObject("PRAGMA journal_mode", String.class));
    }
}
