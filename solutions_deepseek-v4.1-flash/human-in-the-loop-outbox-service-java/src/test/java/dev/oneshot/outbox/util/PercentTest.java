package dev.oneshot.outbox.util;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class PercentTest {
    @Test
    void encodesUtf8SpecialCharactersAndNewlinesWithoutPlusForSpace() {
        assertThat(Percent.encode("a b\nc+d&é✓"))
                .isEqualTo("a%20b%0Ac%2Bd%26%C3%A9%E2%9C%93");
        assertThat(Percent.encode("AZaz09-._~")).isEqualTo("AZaz09-._~");
        assertThat(Percent.encode("?subject=Q4 & report")).isEqualTo("%3Fsubject%3DQ4%20%26%20report");
        assertThat(Percent.encode("")).isEmpty();
        assertThat(Percent.encode(null)).isEmpty();
    }

    @Test
    void timestampUtilitiesNormalizeToUtcSeconds() {
        assertThat(Times.iso(Times.parse("2030-01-01T01:00:00+01:00")))
                .isEqualTo("2030-01-01T00:00:00Z");
        assertThat(Times.iso(Times.parse("2030-01-01T00:00:00.987Z")))
                .isEqualTo("2030-01-01T00:00:00Z");
        assertThat(Times.iso(Times.parse("2030-01-01T00:00:00Z")))
                .isEqualTo("2030-01-01T00:00:00Z");
    }
}
