package dev.oneshot.outbox.security;

import dev.oneshot.outbox.config.OutboxProperties;
import dev.oneshot.outbox.web.ApiException;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class UrlGuardTest {

    private UrlGuard guard(boolean allowPrivate) {
        OutboxProperties properties = new OutboxProperties();
        properties.setAllowPrivateUrls(allowPrivate);
        return new UrlGuard(properties);
    }

    @Test
    void blocksLoopbackPrivateLinkLocalReservedAndMetadataTargets() {
        UrlGuard guard = guard(false);
        List<String> blocked = List.of(
                "http://127.0.0.1/",
                "http://127.8.9.10/",
                "http://localhost/",
                "foo.localhost",
                "http://10.1.2.3/",
                "http://172.16.5.4/",
                "http://192.168.0.1/",
                "http://169.254.169.254/latest/meta-data/",
                "http://100.64.0.1/",
                "http://198.18.0.1/",
                "http://192.0.2.5/",
                "http://240.0.0.1/",
                "http://0.0.0.0/",
                "http://[::1]/",
                "http://[fc00::1]/",
                "http://[fe80::1]/",
                "http://[::ffff:127.0.0.1]/",
                "http://metadata.google.internal/computeMetadata/v1/",
                "http://instance-data/latest/"
        );
        for (String url : blocked) {
            String candidate = url.startsWith("http") ? url : "http://" + url + "/";
            assertThatThrownBy(() -> guard.validate(candidate, "Webhook"))
                    .as(candidate)
                    .isInstanceOf(ApiException.class)
                    .satisfies(ex -> {
                        ApiException api = (ApiException) ex;
                        assertThat(api.getStatus()).isEqualTo(400);
                        assertThat(api.getCode()).isEqualTo("unsafe_url");
                    });
        }
    }

    @Test
    void acceptsPublicAddressesAndBlocksBadShapes() {
        UrlGuard guard = guard(false);
        assertThatCode(() -> guard.validate("http://8.8.8.8/path?q=1", "Download"))
                .doesNotThrowAnyException();
        assertThatCode(() -> guard.validate("https://93.184.216.34:8443/file", "Download"))
                .doesNotThrowAnyException();

        assertThatThrownBy(() -> guard.validate("ftp://8.8.8.8/file", "Download"))
                .isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> guard.validate("file:///etc/passwd", "Download"))
                .isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> guard.validate("http://user:pass@8.8.8.8/", "Download"))
                .isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> guard.validate("http:///nohost", "Download"))
                .isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> guard.validate("", "Download"))
                .isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> guard.validate("http://8.8.8.8:0/", "Download"))
                .isInstanceOf(ApiException.class);
    }

    @Test
    void explicitLocalTestingOverrideAllowsLoopback() {
        UrlGuard guard = guard(true);
        assertThatCode(() -> guard.validate("http://127.0.0.1:9002/hook", "Webhook"))
                .doesNotThrowAnyException();
        assertThat(guard.isAllowPrivate()).isTrue();
    }
}
