package dev.oneshot.outbox.attachments;

import dev.oneshot.outbox.config.OutboxProperties;
import dev.oneshot.outbox.security.UrlGuard;
import dev.oneshot.outbox.util.Filenames;
import dev.oneshot.outbox.web.ApiException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Locale;
import java.util.Optional;

/**
 * Fetches remote attachments with manual redirect handling so every hop is
 * revalidated by {@link UrlGuard}. The response is streamed into a bounded buffer;
 * a hostile server cannot make us allocate more than the configured per-file limit.
 */
@Component
public class UrlDownloader {
    private static final Logger log = LoggerFactory.getLogger(UrlDownloader.class);

    private final OutboxProperties properties;
    private final UrlGuard guard;
    private final HttpClient client;

    public UrlDownloader(OutboxProperties properties, UrlGuard guard) {
        this.properties = properties;
        this.guard = guard;
        this.client = HttpClient.newBuilder()
                .followRedirects(HttpClient.Redirect.NEVER)
                .connectTimeout(Duration.ofSeconds(Math.max(1, properties.getDownloadTimeoutSeconds())))
                .build();
    }

    public Downloaded download(String rawUrl, long maxBytes) {
        URI uri = guard.validateDownload(rawUrl);
        int maxRedirects = Math.max(0, properties.getMaxRedirects());
        for (int hop = 0; ; hop++) {
            HttpResponse<InputStream> response;
            HttpRequest request = HttpRequest.newBuilder(uri)
                    .timeout(Duration.ofSeconds(Math.max(1, properties.getDownloadTimeoutSeconds())))
                    .header("User-Agent", "outbox-downloader/1.0")
                    .header("Accept", "*/*")
                    .GET()
                    .build();
            try {
                response = client.send(request, HttpResponse.BodyHandlers.ofInputStream());
            } catch (java.net.http.HttpTimeoutException ex) {
                throw ApiException.badRequest("Downloading " + uri + " timed out after "
                        + properties.getDownloadTimeoutSeconds() + " seconds.");
            } catch (IOException ex) {
                throw ApiException.badRequest("Could not download " + uri + ": " + ex.getMessage());
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                throw ApiException.badRequest("Download was interrupted.");
            }

            int status = response.statusCode();
            if (isRedirect(status)) {
                closeQuietly(response.body());
                if (hop >= maxRedirects) {
                    throw ApiException.badRequest("Download exceeded the maximum of " + maxRedirects + " redirects.");
                }
                Optional<String> location = response.headers().firstValue("location");
                if (location.isEmpty() || location.get().isBlank()) {
                    throw ApiException.badRequest("Download redirect did not include a Location header.");
                }
                URI next;
                try {
                    next = uri.resolve(location.get().trim());
                } catch (IllegalArgumentException ex) {
                    throw ApiException.badRequest("Download redirect Location is invalid.");
                }
                // Revalidate every redirect target, exactly like the first hop.
                uri = guard.validateDownload(next.toString());
                continue;
            }

            if (status < 200 || status >= 300) {
                closeQuietly(response.body());
                throw ApiException.badRequest("Attachment download failed with HTTP " + status + " from " + uri + ".");
            }

            Optional<String> declared = response.headers().firstValue("content-length");
            if (declared.isPresent()) {
                try {
                    if (Long.parseLong(declared.get()) > maxBytes) {
                        closeQuietly(response.body());
                        throw ApiException.tooLarge("Downloaded file exceeds the configured per-file limit of "
                                + maxBytes + " bytes.");
                    }
                } catch (NumberFormatException ignored) {
                    // A malformed Content-Length is not trusted; the streaming cap still applies.
                }
            }

            byte[] bytes = readBounded(response.body(), maxBytes, uri);
            String headerType = response.headers().firstValue("content-type").orElse(null);
            String mime = Filenames.sanitizeMimeType(headerType);
            final URI finalUri = uri;
            String filename = filenameFromHeaders(response).orElseGet(() -> filenameFromUri(finalUri));
            final String finalUrl = uri.toString();
            log.info("Downloaded {} bytes from {} as {}", bytes.length, finalUrl, filename);
            return new Downloaded(bytes, mime, Filenames.sanitize(filename), finalUrl);
        }
    }

    private byte[] readBounded(InputStream stream, long maxBytes, URI uri) {
        try (stream) {
            java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
            byte[] buffer = new byte[8192];
            long total = 0;
            int read;
            while ((read = stream.read(buffer)) != -1) {
                total += read;
                if (total > maxBytes) {
                    throw ApiException.tooLarge("Downloaded file exceeds the configured per-file limit of "
                            + maxBytes + " bytes.");
                }
                out.write(buffer, 0, read);
            }
            return out.toByteArray();
        } catch (IOException ex) {
            throw ApiException.badRequest("Download from " + uri + " ended unexpectedly: " + ex.getMessage());
        }
    }

    private static boolean isRedirect(int status) {
        return status == 301 || status == 302 || status == 303 || status == 307 || status == 308;
    }

    private static Optional<String> filenameFromHeaders(HttpResponse<?> response) {
        Optional<String> disposition = response.headers().firstValue("content-disposition");
        if (disposition.isEmpty()) return Optional.empty();
        String value = disposition.get();
        // RFC 5987 filename*=UTF-8''name
        int star = value.toLowerCase(Locale.ROOT).indexOf("filename*=");
        if (star >= 0) {
            String rest = value.substring(star + "filename*=".length()).trim();
            int semi = rest.indexOf(';');
            if (semi >= 0) rest = rest.substring(0, semi);
            rest = rest.replace("\"", "").trim();
            int quote = rest.indexOf("''");
            if (quote >= 0) {
                try {
                    return Optional.of(java.net.URLDecoder.decode(
                            rest.substring(quote + 2).replace("+", "%2B"), StandardCharsets.UTF_8));
                } catch (IllegalArgumentException ignored) {
                    // Fall through to the plain filename.
                }
            }
        }
        int plain = value.toLowerCase(Locale.ROOT).indexOf("filename=");
        if (plain >= 0) {
            String rest = value.substring(plain + "filename=".length()).trim();
            int semi = rest.indexOf(';');
            if (semi >= 0) rest = rest.substring(0, semi);
            rest = rest.replace("\"", "").trim();
            if (!rest.isEmpty()) return Optional.of(rest);
        }
        return Optional.empty();
    }

    private static String filenameFromUri(URI uri) {
        String path = uri.getPath();
        if (path == null || path.isBlank() || path.endsWith("/")) return "download";
        int slash = path.lastIndexOf('/');
        String name = slash >= 0 ? path.substring(slash + 1) : path;
        try {
            name = java.net.URLDecoder.decode(name.replace("+", "%2B"), StandardCharsets.UTF_8);
        } catch (IllegalArgumentException ignored) {
            // Keep the raw path segment.
        }
        return name.isBlank() ? "download" : name;
    }

    private static void closeQuietly(InputStream stream) {
        try {
            if (stream != null) stream.close();
        } catch (IOException ignored) {
            // Nothing useful to do.
        }
    }

    public record Downloaded(byte[] bytes, String mimeType, String filename, String sourceUrl) {}
}
