package dev.oneshot.outbox.channel;

import dev.oneshot.outbox.model.Channel;
import dev.oneshot.outbox.web.ApiException;
import org.springframework.stereotype.Component;

import java.util.EnumMap;
import java.util.List;
import java.util.Map;

@Component
public class ChannelRegistry {
    private final Map<Channel, ChannelAdapter> adapters = new EnumMap<>(Channel.class);

    public ChannelRegistry(List<ChannelAdapter> adapters) {
        for (ChannelAdapter adapter : adapters) {
            this.adapters.put(Channel.parse(adapter.channel()), adapter);
        }
        for (Channel channel : Channel.values()) {
            if (!this.adapters.containsKey(channel)) {
                throw new IllegalStateException("No adapter registered for channel " + channel.wire());
            }
        }
    }

    public ChannelAdapter get(Channel channel) {
        ChannelAdapter adapter = adapters.get(channel);
        if (adapter == null) throw ApiException.badRequest("Unsupported channel: " + channel.wire());
        return adapter;
    }

    public NormalizedDestination normalize(Channel channel, String destination) {
        return get(channel).normalize(destination);
    }
}
