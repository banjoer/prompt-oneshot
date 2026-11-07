package dev.oneshot.outbox.service;

import dev.oneshot.outbox.channel.ChannelRegistry;
import dev.oneshot.outbox.channel.NormalizedDestination;
import dev.oneshot.outbox.model.Channel;
import dev.oneshot.outbox.model.DestinationLabel;
import dev.oneshot.outbox.repo.DestinationRepository;
import dev.oneshot.outbox.util.Times;
import dev.oneshot.outbox.web.ApiException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
public class DestinationService {
    private final DestinationRepository repository;
    private final ChannelRegistry channels;

    public DestinationService(DestinationRepository repository, ChannelRegistry channels) {
        this.repository = repository;
        this.channels = channels;
    }

    public List<Map<String, Object>> list() {
        List<DestinationRepository.DiscoveredRow> rows = repository.discovered();
        Map<String, Aggregate> grouped = new LinkedHashMap<>();
        for (DestinationRepository.DiscoveredRow row : rows) {
            String key = row.channel().wire() + "|" + row.normalizedDestination();
            Aggregate aggregate = grouped.get(key);
            if (aggregate == null) {
                // Rows are newest first, so the first spelling becomes the display value.
                aggregate = new Aggregate(row.channel(), row.normalizedDestination(), row.destination(),
                        row.createdAt(), 0);
                grouped.put(key, aggregate);
            }
            aggregate.messageCount++;
        }
        List<DestinationLabel> labels = repository.all();
        for (DestinationLabel label : labels) {
            String key = label.channel() + "|" + label.normalizedDestination();
            Aggregate aggregate = grouped.get(key);
            if (aggregate == null) {
                aggregate = new Aggregate(labelledChannel(label.channel()), label.normalizedDestination(),
                        label.normalizedDestination(), null, 0);
                grouped.put(key, aggregate);
            }
            aggregate.label = label.label();
        }
        List<Map<String, Object>> items = new ArrayList<>();
        for (Aggregate a : grouped.values()) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("channel", a.channel.wire());
            item.put("destination", a.destination);
            item.put("normalized_destination", a.normalizedDestination);
            item.put("label", a.label);
            item.put("message_count", a.messageCount);
            item.put("last_used_at", a.lastUsedAt);
            items.add(item);
        }
        items.sort(Comparator
                .comparing((Map<String, Object> m) -> (String) m.get("channel"))
                .thenComparing(m -> (String) m.get("label") == null ? "~" : ((String) m.get("label")).toLowerCase(Locale.ROOT))
                .thenComparing(m -> (String) m.get("normalized_destination")));
        return items;
    }

    @Transactional
    public Map<String, Object> putLabel(String channelRaw, String destinationRaw, String labelRaw) {
        Channel channel = Channel.parse(channelRaw);
        NormalizedDestination normalized = channels.normalize(channel, destinationRaw);
        String label = cleanLabel(labelRaw);
        if (!repository.findConflictingLabel(channel, normalized.normalized(), label).isEmpty()) {
            throw ApiException.conflict("The label '" + label + "' is already used by another "
                    + channel.wire() + " destination. Labels must be unique within a channel.");
        }
        String now = Times.nowIso();
        try {
            repository.upsert(channel, normalized.normalized(), label, now);
        } catch (DataIntegrityViolationException ex) {
            throw ApiException.conflict("The label '" + label + "' is already used by another "
                    + channel.wire() + " destination. Labels must be unique within a channel.");
        }
        DestinationLabel saved = repository.find(channel, normalized.normalized());
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("channel", channel.wire());
        out.put("destination", normalized.destination());
        out.put("normalized_destination", normalized.normalized());
        out.put("label", saved == null ? label : saved.label());
        out.put("created_at", saved == null ? now : saved.createdAt());
        out.put("updated_at", saved == null ? now : saved.updatedAt());
        return out;
    }

    @Transactional
    public Map<String, Object> deleteLabel(String channelRaw, String destinationRaw) {
        Channel channel = Channel.parse(channelRaw);
        NormalizedDestination normalized = channels.normalize(channel, destinationRaw);
        DestinationLabel existing = repository.find(channel, normalized.normalized());
        if (existing == null) {
            throw ApiException.notFound("No label is assigned to " + channel.wire() + " destination '"
                    + destinationRaw + "'.");
        }
        repository.delete(channel, normalized.normalized());
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("removed", true);
        out.put("channel", channel.wire());
        out.put("destination", normalized.destination());
        out.put("normalized_destination", normalized.normalized());
        out.put("label", existing.label());
        return out;
    }

    public String cleanLabel(String raw) {
        if (raw == null || raw.isBlank()) {
            throw ApiException.badRequest("label must be a non-empty string.");
        }
        String label = raw.trim().replaceAll("\\s+", " ");
        if (label.length() > 80) {
            throw ApiException.badRequest("label is too long (maximum 80 characters).");
        }
        for (int i = 0; i < label.length(); i++) {
            char ch = label.charAt(i);
            if (ch < 0x20 || ch == 0x7f) {
                throw ApiException.badRequest("label must not contain control characters.");
            }
        }
        return label;
    }

    private static Channel labelledChannel(String channel) {
        return Channel.parse(channel);
    }

    private static final class Aggregate {
        final Channel channel;
        final String normalizedDestination;
        final String destination;
        final String lastUsedAt;
        int messageCount;
        String label;

        Aggregate(Channel channel, String normalizedDestination, String destination,
                  String lastUsedAt, int messageCount) {
            this.channel = channel;
            this.normalizedDestination = normalizedDestination;
            this.destination = destination;
            this.lastUsedAt = lastUsedAt;
            this.messageCount = messageCount;
        }
    }
}
