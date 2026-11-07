package dev.oneshot.outbox.util;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

@Component
public class Json {
    private final ObjectMapper mapper;

    public Json(ObjectMapper mapper) {
        this.mapper = mapper;
    }

    public ObjectMapper mapper() { return mapper; }

    public String write(Object value) {
        try {
            return mapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Unable to serialize JSON", ex);
        }
    }

    public JsonNode readTree(String value) {
        try {
            return mapper.readTree(value);
        } catch (JsonProcessingException ex) {
            throw new IllegalArgumentException("Invalid JSON: " + ex.getOriginalMessage());
        }
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> readMap(String value) {
        if (value == null || value.isBlank()) return null;
        try {
            return mapper.readValue(value, LinkedHashMap.class);
        } catch (JsonProcessingException ex) {
            throw new IllegalArgumentException("Invalid JSON object: " + ex.getOriginalMessage());
        }
    }

    public ObjectNode objectNode() {
        return mapper.createObjectNode();
    }
}
