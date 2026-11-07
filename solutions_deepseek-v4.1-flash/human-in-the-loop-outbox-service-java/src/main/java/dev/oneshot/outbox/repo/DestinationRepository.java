package dev.oneshot.outbox.repo;

import dev.oneshot.outbox.model.Channel;
import dev.oneshot.outbox.model.DestinationLabel;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class DestinationRepository {
    private final JdbcTemplate jdbc;

    public DestinationRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public static final RowMapper<DestinationLabel> MAPPER = (rs, n) -> new DestinationLabel(
            rs.getLong("id"), rs.getString("channel"), rs.getString("normalized_destination"),
            rs.getString("label"), rs.getString("created_at"), rs.getString("updated_at"));

    public List<DestinationLabel> all() {
        return jdbc.query("SELECT * FROM destination_labels ORDER BY channel ASC, lower(label) ASC", MAPPER);
    }

    public DestinationLabel find(Channel channel, String normalizedDestination) {
        List<DestinationLabel> rows = jdbc.query(
                "SELECT * FROM destination_labels WHERE channel = ? AND normalized_destination = ?",
                MAPPER, channel.wire(), normalizedDestination);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public List<DestinationLabel> findConflictingLabel(Channel channel, String normalizedDestination, String label) {
        return jdbc.query("""
                SELECT * FROM destination_labels
                WHERE channel = ? AND lower(label) = lower(?) AND normalized_destination <> ?
                """, MAPPER, channel.wire(), label, normalizedDestination);
    }

    public void upsert(Channel channel, String normalizedDestination, String label, String nowIso) {
        jdbc.update("""
                INSERT INTO destination_labels (channel, normalized_destination, label, created_at, updated_at)
                VALUES (?,?,?,?,?)
                ON CONFLICT(channel, normalized_destination)
                DO UPDATE SET label = excluded.label, updated_at = excluded.updated_at
                """, channel.wire(), normalizedDestination, label, nowIso, nowIso);
    }

    public int delete(Channel channel, String normalizedDestination) {
        return jdbc.update("DELETE FROM destination_labels WHERE channel = ? AND normalized_destination = ?",
                channel.wire(), normalizedDestination);
    }

    /** One row per distinct channel + normalized destination discovered from messages. */
    public List<DiscoveredRow> discovered() {
        return jdbc.query("""
                SELECT channel, normalized_destination, destination, created_at
                FROM messages ORDER BY created_at DESC, id DESC
                """, (rs, n) -> new DiscoveredRow(
                Channel.parse(rs.getString("channel")), rs.getString("normalized_destination"),
                rs.getString("destination"), rs.getString("created_at")));
    }

    public record DiscoveredRow(Channel channel, String normalizedDestination, String destination,
                                String createdAt) {}
}
