package dev.oneshot.outbox.util;

import java.util.Locale;
import java.util.Set;

/** Filename hardening shared by multipart uploads and URL downloads. */
public final class Filenames {
    private Filenames() {}

    private static final Set<String> RESERVED = Set.of(
            "CON", "PRN", "AUX", "NUL",
            "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
            "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
    );

    public static String sanitize(String raw) {
        if (raw == null) return "attachment";
        String name = raw.trim();
        // Strip any client-supplied path (both separators) and query fragments.
        int slash = Math.max(name.lastIndexOf('/'), name.lastIndexOf('\\'));
        if (slash >= 0) name = name.substring(slash + 1);
        int query = name.indexOf('?');
        if (query >= 0) name = name.substring(0, query);
        int hash = name.indexOf('#');
        if (hash >= 0) name = name.substring(0, hash);
        StringBuilder cleaned = new StringBuilder(name.length());
        for (int i = 0; i < name.length(); i++) {
            char ch = name.charAt(i);
            if (ch < 0x20 || ch == 0x7f) continue;
            if ("<>:\"|?*".indexOf(ch) >= 0) {
                cleaned.append('_');
            } else {
                cleaned.append(ch);
            }
        }
        name = cleaned.toString().replaceAll("\\s+", " ").trim();
        while (name.endsWith(".") || name.endsWith(" ")) {
            name = name.substring(0, name.length() - 1);
        }
        if (name.isEmpty() || name.equals(".") || name.equals("..")) name = "attachment";
        if (name.startsWith(".")) name = "_" + name;
        String base = name;
        int dot = name.lastIndexOf('.');
        if (dot > 0) base = name.substring(0, dot);
        String upper = base.toUpperCase(Locale.ROOT);
        if (RESERVED.contains(upper)) name = "_" + name;
        if (name.length() > 180) {
            int extDot = name.lastIndexOf('.');
            String ext = extDot > 0 && name.length() - extDot <= 16 ? name.substring(extDot) : "";
            int keep = Math.max(1, 180 - ext.length());
            name = name.substring(0, keep) + ext;
        }
        return name;
    }

    /** Only a simple, lowercase extension is used for generated storage names. */
    public static String safeExtension(String originalFilename) {
        if (originalFilename == null) return "";
        int dot = originalFilename.lastIndexOf('.');
        if (dot < 0 || dot == originalFilename.length() - 1) return "";
        String ext = originalFilename.substring(dot + 1).toLowerCase(Locale.ROOT);
        if (ext.length() > 10 || !ext.matches("[a-z0-9]+")) return "";
        return "." + ext;
    }

    public static String sanitizeMimeType(String raw) {
        if (raw == null) return "application/octet-stream";
        String type = raw;
        int semi = type.indexOf(';');
        if (semi >= 0) type = type.substring(0, semi);
        type = type.trim().toLowerCase(Locale.ROOT);
        if (type.isEmpty() || type.length() > 120) return "application/octet-stream";
        // RFC 6838 restricted-name plus a slash; reject control characters and nonsense.
        if (!type.matches("[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+")) {
            return "application/octet-stream";
        }
        return type;
    }
}
