package dev.oneshot.outbox.util;

import java.nio.charset.StandardCharsets;

/** Strict RFC 3986 percent encoding (never leaves '+' for a space). */
public final class Percent {
    private Percent() {}

    private static final char[] HEX = "0123456789ABCDEF".toCharArray();

    public static String encode(String value) {
        if (value == null) return "";
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        StringBuilder out = new StringBuilder(bytes.length + 16);
        for (byte raw : bytes) {
            int b = raw & 0xff;
            if ((b >= 'A' && b <= 'Z') || (b >= 'a' && b <= 'z') || (b >= '0' && b <= '9')
                    || b == '-' || b == '.' || b == '_' || b == '~') {
                out.append((char) b);
            } else {
                out.append('%').append(HEX[b >> 4]).append(HEX[b & 0x0f]);
            }
        }
        return out.toString();
    }
}
