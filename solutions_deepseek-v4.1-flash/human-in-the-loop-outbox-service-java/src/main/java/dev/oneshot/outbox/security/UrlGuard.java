package dev.oneshot.outbox.security;

import dev.oneshot.outbox.config.OutboxProperties;
import dev.oneshot.outbox.web.ApiException;
import org.springframework.stereotype.Component;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.UnknownHostException;
import java.util.ArrayList;
import java.util.List;

/**
 * Central SSRF gate for caller-supplied attachment-download and webhook URLs.
 *
 * It rejects non-HTTP(S) URLs, credentials in URLs, and any host that resolves to
 * loopback, private, link-local, multicast, unspecified, carrier-grade-NAT,
 * documentation/reserved ranges, IPv6 unique-local space, or well-known cloud
 * metadata names. Redirects are revalidated by the callers before each hop.
 *
 * ALLOW_PRIVATE_URLS=1 is an explicit local-testing override and is reported
 * through /api/info so it is never silently on.
 */
@Component
public class UrlGuard {
    private final boolean allowPrivate;

    private static final List<String> METADATA_HOSTS = List.of(
            "metadata.google.internal",
            "metadata.goog",
            "instance-data",
            "metadata",
            "metadata.azure.com"
    );

    public UrlGuard(OutboxProperties properties) {
        this.allowPrivate = properties.isAllowPrivateUrls();
    }

    public boolean isAllowPrivate() {
        return allowPrivate;
    }

    public URI validate(String rawUrl, String purpose) {
        if (rawUrl == null || rawUrl.isBlank()) {
            throw ApiException.badRequest(purpose + " URL must not be empty.");
        }
        if (rawUrl.length() > 2048) {
            throw ApiException.badRequest(purpose + " URL is too long (maximum 2048 characters).");
        }
        URI uri;
        try {
            uri = new URI(rawUrl.trim());
        } catch (URISyntaxException ex) {
            throw ApiException.badRequest(purpose + " URL is not valid: " + ex.getMessage());
        }
        String scheme = uri.getScheme();
        if (scheme == null || !(scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https"))) {
            throw ApiException.forbiddenUrl(purpose + " URL must use http or https.");
        }
        if (uri.getUserInfo() != null) {
            throw ApiException.forbiddenUrl(purpose + " URL must not contain credentials.");
        }
        String host = uri.getHost();
        if (host == null || host.isBlank()) {
            throw ApiException.badRequest(purpose + " URL must include a host.");
        }
        if (host.startsWith("[") && host.endsWith("]")) {
            host = host.substring(1, host.length() - 1);
        }
        int port = uri.getPort();
        if (port == 0) {
            throw ApiException.badRequest(purpose + " URL has an invalid port.");
        }
        if (allowPrivate) {
            return uri;
        }
        String lowerHost = host.toLowerCase();
        if (lowerHost.equals("localhost") || lowerHost.endsWith(".localhost")
                || METADATA_HOSTS.contains(lowerHost) || lowerHost.endsWith(".internal")) {
            throw blocked(purpose, host);
        }
        InetAddress[] addresses;
        try {
            addresses = InetAddress.getAllByName(host);
        } catch (UnknownHostException ex) {
            throw ApiException.badRequest(purpose + " URL host could not be resolved: " + host);
        }
        if (addresses.length == 0) {
            throw ApiException.badRequest(purpose + " URL host could not be resolved: " + host);
        }
        List<String> blockedAddresses = new ArrayList<>();
        for (InetAddress address : addresses) {
            if (isBlocked(address)) blockedAddresses.add(address.getHostAddress());
        }
        if (!blockedAddresses.isEmpty()) {
            throw blocked(purpose, host + " -> " + String.join(", ", blockedAddresses));
        }
        return uri;
    }

    public URI validateWebhook(String rawUrl) {
        return validate(rawUrl, "Webhook");
    }

    public URI validateDownload(String rawUrl) {
        return validate(rawUrl, "Attachment download");
    }

    private ApiException blocked(String purpose, String detail) {
        return ApiException.forbiddenUrl(
                purpose + " URL points at a loopback, private, link-local, multicast, reserved, or metadata "
                        + "address and is blocked (" + detail + "). Use ALLOW_PRIVATE_URLS=1 only for local testing.");
    }

    static boolean isBlocked(InetAddress address) {
        if (address.isAnyLocalAddress() || address.isLoopbackAddress() || address.isLinkLocalAddress()
                || address.isSiteLocalAddress() || address.isMulticastAddress()) {
            return true;
        }
        byte[] bytes = address.getAddress();
        if (address instanceof Inet4Address && bytes.length == 4) {
            int b0 = bytes[0] & 0xff;
            int b1 = bytes[1] & 0xff;
            // 0.0.0.0/8
            if (b0 == 0) return true;
            // 100.64.0.0/10 (carrier-grade NAT)
            if (b0 == 100 && b1 >= 64 && b1 <= 127) return true;
            // 127.0.0.0/8 (covered by loopback, kept explicit)
            if (b0 == 127) return true;
            // 169.254.0.0/16 (covered by link-local, kept explicit)
            if (b0 == 169 && b1 == 254) return true;
            // 192.0.0.0/24, 192.0.2.0/24 (IETF protocol assignments / TEST-NET-1)
            if (b0 == 192 && b1 == 0 && (bytes[2] & 0xff) <= 2) return true;
            // 198.18.0.0/15 (benchmarking)
            if (b0 == 198 && (b1 == 18 || b1 == 19)) return true;
            // 198.51.100.0/24 (TEST-NET-2), 203.0.113.0/24 (TEST-NET-3)
            if (b0 == 198 && b1 == 51 && (bytes[2] & 0xff) == 100) return true;
            if (b0 == 203 && b1 == 0 && (bytes[2] & 0xff) == 113) return true;
            // 240.0.0.0/4 (reserved) and broadcast
            if (b0 >= 240) return true;
        } else if (bytes.length == 16) {
            int b0 = bytes[0] & 0xff;
            // IPv6 unique local addresses fc00::/7
            if ((b0 & 0xfe) == 0xfc) return true;
            // IPv6 documentation 2001:db8::/32
            if (b0 == 0x20 && (bytes[1] & 0xff) == 0x01 && (bytes[2] & 0xff) == 0x0d && (bytes[3] & 0xff) == 0xb8) {
                return true;
            }
            // IPv4-mapped addresses are normalized by the JDK to Inet4Address, but guard anyway.
            boolean mapped = true;
            for (int i = 0; i < 10; i++) {
                if (bytes[i] != 0) { mapped = false; break; }
            }
            if (mapped && (bytes[10] & 0xff) == 0xff && (bytes[11] & 0xff) == 0xff) {
                byte[] v4 = new byte[]{bytes[12], bytes[13], bytes[14], bytes[15]};
                try {
                    return isBlocked(InetAddress.getByAddress(v4));
                } catch (UnknownHostException ignored) {
                    return true;
                }
            }
        }
        return false;
    }
}
