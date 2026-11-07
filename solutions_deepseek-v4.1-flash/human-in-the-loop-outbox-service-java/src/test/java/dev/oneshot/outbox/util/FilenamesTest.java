package dev.oneshot.outbox.util;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class FilenamesTest {
    @Test
    void stripsPathsControlCharactersAndReservedNames() {
        assertThat(Filenames.sanitize("../../evil.txt")).isEqualTo("evil.txt");
        assertThat(Filenames.sanitize("C:\\temp\\report.pdf")).isEqualTo("report.pdf");
        assertThat(Filenames.sanitize("/absolute/path/note.txt")).isEqualTo("note.txt");
        assertThat(Filenames.sanitize("bad\u0000name\u0007.txt")).isEqualTo("badname.txt");
        assertThat(Filenames.sanitize("CON.txt")).isEqualTo("_CON.txt");
        assertThat(Filenames.sanitize("lpt9.log")).isEqualTo("_lpt9.log");
        assertThat(Filenames.sanitize("..")).isEqualTo("attachment");
        assertThat(Filenames.sanitize(".")).isEqualTo("attachment");
        assertThat(Filenames.sanitize("   ")).isEqualTo("attachment");
        assertThat(Filenames.sanitize(".env")).isEqualTo("_.env");
        assertThat(Filenames.sanitize("name<>:\"|?*.txt")).doesNotContain("<", ">", ":", "\"", "|", "?", "*");
        assertThat(Filenames.sanitize("trailing...")).isEqualTo("trailing");
        assertThat(Filenames.sanitize("a".repeat(400) + ".txt").length()).isLessThanOrEqualTo(180);
    }

    @Test
    void unsafeExtensionsAreNotUsedForGeneratedStorageNames() {
        assertThat(Filenames.safeExtension("report.PDF")).isEqualTo(".pdf");
        assertThat(Filenames.safeExtension("archive.tar.gz")).isEqualTo(".gz");
        assertThat(Filenames.safeExtension("no-extension")).isEmpty();
        assertThat(Filenames.safeExtension("evil./../x")).isEmpty();
        assertThat(Filenames.safeExtension("weird.<script>")).isEmpty();
        assertThat(Filenames.safeExtension(null)).isEmpty();
    }

    @Test
    void mimeTypesAreSanitized() {
        assertThat(Filenames.sanitizeMimeType("text/plain; charset=UTF-8")).isEqualTo("text/plain");
        assertThat(Filenames.sanitizeMimeType("IMAGE/PNG")).isEqualTo("image/png");
        assertThat(Filenames.sanitizeMimeType("not a mime")).isEqualTo("application/octet-stream");
        assertThat(Filenames.sanitizeMimeType("text/plain\nX-Evil: 1")).isEqualTo("application/octet-stream");
        assertThat(Filenames.sanitizeMimeType(null)).isEqualTo("application/octet-stream");
        assertThat(Filenames.sanitizeMimeType("")).isEqualTo("application/octet-stream");
    }
}
