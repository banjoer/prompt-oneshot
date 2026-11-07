package dev.oneshot.outbox.web;

import dev.oneshot.outbox.service.DestinationService;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/destinations")
public class DestinationController {
    private final DestinationService destinations;

    public DestinationController(DestinationService destinations) {
        this.destinations = destinations;
    }

    @GetMapping
    public Map<String, Object> list() {
        List<Map<String, Object>> items = destinations.list();
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", items);
        out.put("total", items.size());
        return out;
    }

    @PutMapping("/label")
    public Map<String, Object> putLabel(@RequestBody Map<String, Object> body) {
        Object channel = body == null ? null : body.get("channel");
        Object destination = body == null ? null : body.get("destination");
        Object label = body == null ? null : body.get("label");
        if (!(channel instanceof String)) throw ApiException.badRequest("channel is required.");
        if (!(destination instanceof String)) throw ApiException.badRequest("destination is required.");
        if (label != null && !(label instanceof String)) throw ApiException.badRequest("label must be a string.");
        return destinations.putLabel((String) channel, (String) destination, (String) label);
    }

    @DeleteMapping("/label")
    public Map<String, Object> deleteLabel(@RequestParam String channel, @RequestParam String destination) {
        return destinations.deleteLabel(channel, destination);
    }
}
