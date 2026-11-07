package dev.oneshot.outbox.support;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

/** Tiny loopback HTTP fixture server used for webhook and attachment-download tests. */
public class TestHttpServer implements AutoCloseable {

    @FunctionalInterface
    public interface Handler {
        void handle(HttpExchange exchange, int requestNumber) throws IOException;
    }

    private final HttpServer server;
    private final Map<String, Handler> handlers = new ConcurrentHashMap<>();
    private final Map<String, AtomicInteger> counts = new ConcurrentHashMap<>();
    private final List<String> requestBodies = new CopyOnWriteArrayList<>();

    public TestHttpServer() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.setExecutor(Executors.newCachedThreadPool());
        server.createContext("/", exchange -> {
            String path = exchange.getRequestURI().getPath();
            counts.computeIfAbsent(path, key -> new AtomicInteger()).incrementAndGet();
            byte[] body = exchange.getRequestBody().readAllBytes();
            if (body.length > 0) requestBodies.add(new String(body, StandardCharsets.UTF_8));
            Handler handler = handlers.get(path);
            if (handler == null) {
                respond(exchange, 404, "not found", "text/plain", null);
                return;
            }
            try {
                handler.handle(exchange, counts.get(path).get());
            } catch (RuntimeException ex) {
                respond(exchange, 500, "fixture failure: " + ex.getMessage(), "text/plain", null);
            }
        });
        server.start();
    }

    public String baseUrl() {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    public String url(String path) {
        return baseUrl() + path;
    }

    public void on(String path, Handler handler) {
        handlers.put(path, handler);
    }

    public int count(String path) {
        AtomicInteger value = counts.get(path);
        return value == null ? 0 : value.get();
    }

    public List<String> requestBodies() {
        return requestBodies;
    }

    public static void respond(HttpExchange exchange, int status, String body, String contentType,
                               Map<String, String> headers) throws IOException {
        byte[] bytes = body == null ? new byte[0] : body.getBytes(StandardCharsets.UTF_8);
        if (contentType != null) exchange.getResponseHeaders().set("Content-Type", contentType);
        if (headers != null) headers.forEach((key, value) -> exchange.getResponseHeaders().set(key, value));
        if (bytes.length == 0) {
            exchange.sendResponseHeaders(status, -1);
        } else {
            exchange.sendResponseHeaders(status, bytes.length);
            try (OutputStream out = exchange.getResponseBody()) {
                out.write(bytes);
            }
        }
        exchange.close();
    }

    public static void respondBytes(HttpExchange exchange, int status, byte[] bytes, String contentType,
                                    Map<String, String> headers) throws IOException {
        if (contentType != null) exchange.getResponseHeaders().set("Content-Type", contentType);
        if (headers != null) headers.forEach((key, value) -> exchange.getResponseHeaders().set(key, value));
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(bytes);
        }
        exchange.close();
    }

    public static void webhookSink(HttpExchange exchange, int requestNumber, int failFirst,
                                   AtomicInteger delivered) throws IOException {
        if (requestNumber <= failFirst) {
            respond(exchange, 500, "synthetic failure", "text/plain", null);
            return;
        }
        delivered.incrementAndGet();
        respond(exchange, 204, null, null, null);
    }

    @Override
    public void close() {
        server.stop(0);
    }
}
