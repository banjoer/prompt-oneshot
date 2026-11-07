package dev.oneshot.outbox.service;

import dev.oneshot.outbox.attachments.AttachmentService;
import dev.oneshot.outbox.channel.ChannelRegistry;
import dev.oneshot.outbox.channel.NormalizedDestination;
import dev.oneshot.outbox.config.OutboxProperties;
import dev.oneshot.outbox.model.AttachmentRecord;
import dev.oneshot.outbox.model.Channel;
import dev.oneshot.outbox.model.MessageRecord;
import dev.oneshot.outbox.model.MessageStatus;
import dev.oneshot.outbox.model.RevisionRecord;
import dev.oneshot.outbox.model.StatusChange;
import dev.oneshot.outbox.repo.MessageRepository;
import dev.oneshot.outbox.repo.RevisionRepository;
import dev.oneshot.outbox.security.UrlGuard;
import dev.oneshot.outbox.util.Json;
import dev.oneshot.outbox.util.Times;
import dev.oneshot.outbox.web.ApiException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.multipart.MultipartFile;

import java.net.URI;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** Domain logic for submission, listing, revisions and lifecycle transitions. */
@Service
public class MessageService {
    private final MessageRepository messages;
    private final RevisionRepository revisions;
    private final AttachmentService attachments;
    private final ChannelRegistry channels;
    private final ExpirationService expiration;
    private final WebhookService webhooks;
    private final UrlGuard guard;
    private final Json json;
    private final MessagePresenter presenter;
    private final TransactionTemplate transactions;
    private final OutboxProperties properties;

    public MessageService(MessageRepository messages, RevisionRepository revisions, AttachmentService attachments,
                          ChannelRegistry channels, ExpirationService expiration, WebhookService webhooks,
                          UrlGuard guard, Json json, MessagePresenter presenter,
                          TransactionTemplate transactions, OutboxProperties properties) {
        this.messages = messages;
        this.revisions = revisions;
        this.attachments = attachments;
        this.channels = channels;
        this.expiration = expiration;
        this.webhooks = webhooks;
        this.guard = guard;
        this.json = json;
        this.presenter = presenter;
        this.transactions = transactions;
        this.properties = properties;
    }

    // ---------------------------------------------------------------- create

    public Map<String, Object> create(SubmitCommand cmd) {
        Instant nowInstant = Times.now();
        String now = Times.iso(nowInstant);
        Channel channel = Channel.parse(cmd.channel());
        String body = requireBody(cmd.body());
        String subject = cleanSubject(cmd.subject());
        NormalizedDestination destination = channels.normalize(channel, cmd.destination());
        String expiresAt = resolveCreateExpiry(cmd, nowInstant);
        String source = cleanOptional(cmd.source(), 200, "source");
        String metadata = serializeMetadata(cmd.metadata(), true);
        String destinationLabel = cleanDestinationLabel(cmd.destinationLabel());
        String webhookUrl = cleanWebhook(cmd.webhookUrl());

        Set<String> references = new LinkedHashSet<>(validateReferences(cmd.references()));
        String messageId = Times.newId("msg_");
        List<AttachmentRecord> staged = new ArrayList<>();
        try {
            if (cmd.attachments() != null) {
                for (SubmitCommand.UrlAttachment spec : cmd.attachments()) {
                    if (spec == null) throw ApiException.badRequest("attachments entries must be objects.");
                    String kind = spec.kind() == null ? "" : spec.kind().trim().toLowerCase(Locale.ROOT);
                    if ("url_reference".equals(kind)) {
                        references.add(validateReference(spec.url(), "attachments[].url"));
                    } else if ("url_download".equals(kind)) {
                        staged.add(attachments.stageDownload(messageId, spec.url(), spec.filename()));
                    } else {
                        throw ApiException.badRequest(
                                "attachments[].kind must be 'url_reference' or 'url_download'.");
                    }
                }
            }
            staged.addAll(attachments.stageMultipart(messageId, safeFiles(cmd.files())));
            ensureReferenceLimit(references);
            ensureMessageSize(null, staged);

            MessageRecord message = new MessageRecord(messageId, channel, destination.destination(),
                    destination.normalized(), destinationLabel, subject, body, MessageStatus.PENDING,
                    now, now, expiresAt, webhookUrl, null, null, 1, source, metadata);
            final List<AttachmentRecord> stagedFinal = staged;
            final List<String> referenceList = new ArrayList<>(references);
            transactions.executeWithoutResult(status -> {
                messages.insert(message);
                long revisionId = revisions.insertFromMessage(message);
                int position = 0;
                for (AttachmentRecord attachment : stagedFinal) {
                    attachments.persist(attachment);
                    revisions.linkAttachment(revisionId, attachment.id(), position++);
                }
                for (int i = 0; i < referenceList.size(); i++) {
                    revisions.insertReference(revisionId, i, referenceList.get(i));
                }
                messages.insertStatusHistory(messageId, null, "pending", "submitted", 1, now);
            });
        } catch (RuntimeException ex) {
            attachments.discardStaged(staged);
            throw ex;
        }
        return detail(messageId);
    }

    // ----------------------------------------------------------------- reads

    public Map<String, Object> detail(String id) {
        expiration.expireDue();
        MessageRecord message = require(id);
        return presenter.detail(message);
    }

    public Map<String, Object> list(ListQuery query) {
        expiration.expireDue();
        List<MessageStatus> statuses = parseStatuses(query.status());
        Channel channel = query.channel() == null || query.channel().isBlank()
                ? null : Channel.parse(query.channel());
        String createdAfter = bound(query.createdAfter(), false, "created_after");
        String createdBefore = bound(query.createdBefore(), true, "created_before");
        String expiresAfter = bound(query.expiresAfter(), false, "expires_after");
        String expiresBefore = bound(query.expiresBefore(), true, "expires_before");
        if (createdAfter != null && createdBefore != null && createdAfter.compareTo(createdBefore) > 0) {
            throw ApiException.badRequest("created_after must not be later than created_before.");
        }
        if (expiresAfter != null && expiresBefore != null && expiresAfter.compareTo(expiresBefore) > 0) {
            throw ApiException.badRequest("expires_after must not be later than expires_before.");
        }
        String sort = query.sort() == null || query.sort().isBlank() ? "newest" : query.sort().trim();
        if (!List.of("newest", "oldest", "expires_soon", "expires_late", "review").contains(sort)) {
            throw ApiException.badRequest("sort must be one of newest, oldest, expires_soon, expires_late, review.");
        }
        int limit = query.limit() == null ? 20 : query.limit();
        if (limit < 1 || limit > 100) throw ApiException.badRequest("limit must be between 1 and 100.");
        int offset = query.offset() == null ? 0 : query.offset();
        if (offset < 0) throw ApiException.badRequest("offset must be zero or greater.");

        List<MessageRecord> rows = messages.list(statuses, channel, query.destination(),
                createdAfter, createdBefore, expiresAfter, expiresBefore, sort, limit, offset);
        int total = messages.count(statuses, channel, query.destination(),
                createdAfter, createdBefore, expiresAfter, expiresBefore);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", rows.stream().map(presenter::summary).toList());
        out.put("total", total);
        out.put("limit", limit);
        out.put("offset", offset);
        out.put("sort", sort);
        return out;
    }

    public Map<String, Object> history(String id) {
        expiration.expireDue();
        MessageRecord message = require(id);
        List<RevisionRecord> revisionRows = revisions.findByMessage(id);
        List<StatusChange> changes = messages.history(id);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", id);
        out.put("current_revision", message.revisionNumber());
        out.put("current_status", message.status().wire());
        out.put("created_at", message.createdAt());
        out.put("revisions", revisionRows.stream().map(presenter::revisionView).toList());
        out.put("status_history", changes.stream().map(change -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", change.id());
            item.put("from_status", change.fromStatus());
            item.put("to_status", change.toStatus());
            item.put("reason", change.reason());
            item.put("revision_number", change.revisionNumber());
            item.put("timestamp", change.createdAt());
            item.put("created_at", change.createdAt());
            return item;
        }).toList());
        return out;
    }

    public Map<String, Object> attachments(String id) {
        expiration.expireDue();
        MessageRecord message = require(id);
        List<AttachmentRecord> rows = presenter.attachments(message);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("items", rows.stream().map(a -> presenter.attachmentView(id, a)).toList());
        out.put("total", rows.size());
        return out;
    }

    public MessageRecord ensureExists(String id) {
        expiration.expireDue();
        return require(id);
    }

    public List<AttachmentRecord> activeAttachments(String id) {
        expiration.expireDue();
        return presenter.attachments(require(id));
    }

    // ------------------------------------------------------------- lifecycle

    public Map<String, Object> approve(String id) {
        MessageRecord current = transitionLoad(id);
        if (current.status() != MessageStatus.PENDING) {
            throw ApiException.transition("Only pending messages can be approved. Current status: "
                    + current.status().wire() + ".", current.status().wire(), current.status().allowedActions());
        }
        String now = Times.nowIso();
        Boolean changed = transactions.execute(status -> {
            int rows = messages.casStatus(id, MessageStatus.PENDING, MessageStatus.APPROVED, now,
                    current.rejectionReason(), current.rejectionAt(), true);
            if (rows != 1) return false;
            messages.insertStatusHistory(id, "pending", "approved", null, current.revisionNumber(), now);
            webhooks.enqueue(withStatus(current, MessageStatus.APPROVED, now),
                    "message.approved", Map.of("previous_status", "pending"));
            return true;
        });
        if (!Boolean.TRUE.equals(changed)) throw conflictAfterRace(id);
        webhooks.wake();
        return detail(id);
    }

    public Map<String, Object> reject(String id, String rawReason) {
        String reason = cleanReason(rawReason);
        MessageRecord current = transitionLoad(id);
        if (current.status() != MessageStatus.PENDING) {
            throw ApiException.transition("Only pending messages can be rejected. Current status: "
                    + current.status().wire() + ".", current.status().wire(), current.status().allowedActions());
        }
        String now = Times.nowIso();
        Boolean changed = transactions.execute(status -> {
            int rows = messages.casStatus(id, MessageStatus.PENDING, MessageStatus.REJECTED, now,
                    reason, now, true);
            if (rows != 1) return false;
            revisions.updateRejection(id, current.revisionNumber(), reason, now);
            messages.insertStatusHistory(id, "pending", "rejected", reason, current.revisionNumber(), now);
            webhooks.enqueue(withStatus(current, MessageStatus.REJECTED, now, reason, now),
                    "message.rejected", Map.of("rejection_reason", reason, "previous_status", "pending"));
            return true;
        });
        if (!Boolean.TRUE.equals(changed)) throw conflictAfterRace(id);
        webhooks.wake();
        return detail(id);
    }

    public Map<String, Object> cancel(String id, String rawReason) {
        String reason = rawReason == null || rawReason.isBlank() ? null : cleanReason(rawReason);
        MessageRecord current = transitionLoad(id);
        if (current.status() != MessageStatus.PENDING
                && current.status() != MessageStatus.APPROVED
                && current.status() != MessageStatus.REJECTED) {
            throw ApiException.transition("This message cannot be cancelled from status "
                    + current.status().wire() + ".", current.status().wire(), current.status().allowedActions());
        }
        String now = Times.nowIso();
        boolean guardExpiry = current.status() != MessageStatus.REJECTED;
        MessageRecord before = current;
        Boolean changed = transactions.execute(status -> {
            int rows = messages.casStatus(id, before.status(), MessageStatus.CANCELLED, now,
                    before.rejectionReason(), before.rejectionAt(), guardExpiry);
            if (rows != 1) return false;
            messages.insertStatusHistory(id, before.status().wire(), "cancelled", reason,
                    before.revisionNumber(), now);
            webhooks.enqueue(withStatus(before, MessageStatus.CANCELLED, now),
                    "message.cancelled", Map.of("previous_status", before.status().wire()));
            return true;
        });
        if (!Boolean.TRUE.equals(changed)) throw conflictAfterRace(id);
        webhooks.wake();
        return detail(id);
    }

    public Map<String, Object> markSent(String id) {
        MessageRecord current = transitionLoad(id);
        if (current.status() != MessageStatus.APPROVED) {
            throw ApiException.transition("Only approved messages can be marked sent. Current status: "
                    + current.status().wire() + ".", current.status().wire(), current.status().allowedActions());
        }
        String now = Times.nowIso();
        Boolean changed = transactions.execute(status -> {
            int rows = messages.casStatus(id, MessageStatus.APPROVED, MessageStatus.SENT, now,
                    current.rejectionReason(), current.rejectionAt(), true);
            if (rows != 1) return false;
            messages.insertStatusHistory(id, "approved", "sent",
                    "marked sent after explicit confirmation", current.revisionNumber(), now);
            webhooks.enqueue(withStatus(current, MessageStatus.SENT, now),
                    "message.sent", Map.of("previous_status", "approved"));
            return true;
        });
        if (!Boolean.TRUE.equals(changed)) throw conflictAfterRace(id);
        webhooks.wake();
        return detail(id);
    }

    // ----------------------------------------------------------------- patch

    public Map<String, Object> patch(String id, PatchCommand cmd) {
        MessageRecord current = transitionLoad(id);
        if (current.status() != MessageStatus.PENDING && current.status() != MessageStatus.REJECTED) {
            throw ApiException.transition("Only pending or rejected messages can be revised. Current status: "
                    + current.status().wire() + ".", current.status().wire(), current.status().allowedActions());
        }
        Instant nowInstant = Times.now();
        String now = Times.iso(nowInstant);

        Channel channel = cmd.channelPresent() ? Channel.parse(cmd.channel()) : current.channel();
        String destinationRaw = cmd.destinationPresent() ? requireNonBlank(cmd.destination(), "destination")
                : current.destination();
        NormalizedDestination destination = channels.normalize(channel, destinationRaw);
        String body = cmd.bodyPresent() ? requireBody(cmd.body()) : current.body();
        String subject = cmd.subjectPresent() ? cleanSubject(cmd.subject()) : current.subject();
        String metadata = cmd.metadataPresent() ? serializeMetadata(cmd.metadata(), true) : current.metadata();
        String destinationLabel = cmd.destinationLabelPresent()
                ? cleanDestinationLabel(cmd.destinationLabel()) : current.destinationLabel();
        String expiresAt = resolvePatchExpiry(cmd, current, nowInstant);
        if (expiresAt != null && !Instant.parse(expiresAt).isAfter(nowInstant)) {
            throw ApiException.badRequest("expires_at must be in the future for a message returned to pending.");
        }

        Set<String> references = cmd.referencesPresent()
                ? new LinkedHashSet<>(validateReferences(cmd.references()))
                : new LinkedHashSet<>(presenter.references(current));
        List<AttachmentRecord> staged = new ArrayList<>();
        List<AttachmentRecord> existing = presenter.attachments(current);
        try {
            if (cmd.attachments() != null) {
                for (SubmitCommand.UrlAttachment spec : cmd.attachments()) {
                    if (spec == null) throw ApiException.badRequest("attachments entries must be objects.");
                    String kind = spec.kind() == null ? "" : spec.kind().trim().toLowerCase(Locale.ROOT);
                    if ("url_reference".equals(kind)) {
                        references.add(validateReference(spec.url(), "attachments[].url"));
                    } else if ("url_download".equals(kind)) {
                        staged.add(attachments.stageDownload(id, spec.url(), spec.filename()));
                    } else {
                        throw ApiException.badRequest(
                                "attachments[].kind must be 'url_reference' or 'url_download'.");
                    }
                }
            }
            staged.addAll(attachments.stageMultipart(id, safeFiles(cmd.files())));
            ensureReferenceLimit(references);
            ensureMessageSize(current, staged);

            final List<AttachmentRecord> stagedFinal = staged;
            final List<AttachmentRecord> existingFinal = existing;
            final List<String> referenceList = new ArrayList<>(references);
            final String channelWire = channel.wire();
            final String bodyFinal = body;
            final String subjectFinal = subject;
            final String metadataFinal = metadata;
            final String destinationLabelFinal = destinationLabel;
            final String expiresFinal = expiresAt;
            Boolean changed = transactions.execute(status -> {
                int rows = messages.updateContent(id, current.revisionNumber(), channel,
                        destination.destination(), destination.normalized(), destinationLabelFinal,
                        subjectFinal, bodyFinal, metadataFinal, expiresFinal, now);
                if (rows != 1) return false;
                MessageRecord updated = messages.findById(id);
                long revisionId = revisions.insertFromMessage(updated, now);
                int position = 0;
                for (AttachmentRecord attachment : existingFinal) {
                    revisions.linkAttachment(revisionId, attachment.id(), position++);
                }
                for (AttachmentRecord attachment : stagedFinal) {
                    attachments.persist(attachment);
                    revisions.linkAttachment(revisionId, attachment.id(), position++);
                }
                for (int i = 0; i < referenceList.size(); i++) {
                    revisions.insertReference(revisionId, i, referenceList.get(i));
                }
                if (current.status() == MessageStatus.REJECTED) {
                    messages.insertStatusHistory(id, "rejected", "pending", "revised", updated.revisionNumber(), now);
                }
                webhooks.enqueue(updated, "message.revised", Map.of(
                        "previous_status", current.status().wire(),
                        "previous_revision_number", current.revisionNumber(),
                        "channel", channelWire));
                return true;
            });
            if (!Boolean.TRUE.equals(changed)) {
                attachments.discardStaged(staged);
                throw ApiException.conflict(
                        "The message changed before this revision could be applied. Reload and try again.");
            }
        } catch (RuntimeException ex) {
            attachments.discardStaged(staged);
            throw ex;
        }
        webhooks.wake();
        return detail(id);
    }

    // --------------------------------------------------------------- helpers

    private MessageRecord require(String id) {
        MessageRecord message = messages.findById(id);
        if (message == null) throw ApiException.notFound("Message " + id + " was not found.");
        return message;
    }

    private MessageRecord transitionLoad(String id) {
        expiration.expireDue();
        MessageRecord message = require(id);
        if ((message.status() == MessageStatus.PENDING || message.status() == MessageStatus.APPROVED)
                && message.expiresAt() != null) {
            if (message.expiresAt().compareTo(Times.nowIso()) <= 0) {
                expiration.expireOne(id);
                message = require(id);
            }
        }
        return message;
    }

    private ApiException conflictAfterRace(String id) {
        expiration.expireOne(id);
        MessageRecord latest = messages.findById(id);
        if (latest == null) return ApiException.notFound("Message " + id + " was not found.");
        return ApiException.transition("The message changed concurrently and this transition no longer applies. "
                        + "Current status: " + latest.status().wire() + ".",
                latest.status().wire(), latest.status().allowedActions());
    }

    private static MessageRecord withStatus(MessageRecord m, MessageStatus status, String updatedAt) {
        return withStatus(m, status, updatedAt, m.rejectionReason(), m.rejectionAt());
    }

    private static MessageRecord withStatus(MessageRecord m, MessageStatus status, String updatedAt,
                                            String rejectionReason, String rejectionAt) {
        return new MessageRecord(m.id(), m.channel(), m.destination(), m.normalizedDestination(),
                m.destinationLabel(), m.subject(), m.body(), status, m.createdAt(), updatedAt,
                m.expiresAt(), m.webhookUrl(), rejectionReason, rejectionAt, m.revisionNumber(),
                m.source(), m.metadata());
    }

    private String resolveCreateExpiry(SubmitCommand cmd, Instant now) {
        boolean hasAbsolute = cmd.expiresAtPresent() && cmd.expiresAt() != null && !cmd.expiresAt().isBlank();
        if (hasAbsolute && cmd.ttlSeconds() != null) {
            throw ApiException.badRequest("expires_at and ttl_seconds are mutually exclusive; provide only one.");
        }
        if (cmd.ttlSeconds() != null) {
            validateTtl(cmd.ttlSeconds());
            return Times.iso(now.plusSeconds(cmd.ttlSeconds()));
        }
        if (hasAbsolute) {
            Instant value = Times.parse(cmd.expiresAt());
            if (!value.isAfter(now)) {
                throw ApiException.badRequest("expires_at must be in the future.");
            }
            return Times.iso(value);
        }
        return null;
    }

    private String resolvePatchExpiry(PatchCommand cmd, MessageRecord current, Instant now) {
        if (cmd.ttlSeconds() != null && cmd.expiresAtPresent()) {
            throw ApiException.badRequest("expires_at and ttl_seconds are mutually exclusive; provide only one.");
        }
        if (cmd.ttlSeconds() != null) {
            validateTtl(cmd.ttlSeconds());
            return Times.iso(now.plusSeconds(cmd.ttlSeconds()));
        }
        if (cmd.expiresAtPresent()) {
            if (cmd.expiresAt() == null || cmd.expiresAt().isBlank()) return null;
            Instant value = Times.parse(cmd.expiresAt());
            if (!value.isAfter(now)) {
                throw ApiException.badRequest("expires_at must be in the future.");
            }
            return Times.iso(value);
        }
        return current.expiresAt();
    }

    private static void validateTtl(Long ttl) {
        if (ttl == null || ttl <= 0) {
            throw ApiException.badRequest("ttl_seconds must be a positive integer.");
        }
        if (ttl > 315_360_000L) {
            throw ApiException.badRequest("ttl_seconds is unreasonably large (maximum 315,360,000 seconds).");
        }
    }

    private String cleanWebhook(String raw) {
        if (raw == null || raw.isBlank()) return null;
        return guard.validateWebhook(raw.trim()).toString();
    }

    private String bodyOf(String raw) {
        return raw;
    }

    private String requireBody(String raw) {
        if (raw == null || raw.isBlank()) {
            throw ApiException.badRequest("body is required and must be a non-empty string.");
        }
        if (raw.length() > 200_000) {
            throw ApiException.badRequest("body is too long (maximum 200,000 characters).");
        }
        for (int i = 0; i < raw.length(); i++) {
            char ch = raw.charAt(i);
            if (ch == 0 || (ch < 0x20 && ch != '\n' && ch != '\r' && ch != '\t')) {
                throw ApiException.badRequest("body contains unsupported control characters.");
            }
        }
        return raw;
    }

    private String cleanSubject(String raw) {
        if (raw == null) return null;
        String subject = raw.trim();
        if (subject.isEmpty()) return null;
        if (subject.length() > 500) throw ApiException.badRequest("subject is too long (maximum 500 characters).");
        if (subject.contains("\n") || subject.contains("\r")) {
            throw ApiException.badRequest("subject must be a single line.");
        }
        return subject;
    }

    private String requireNonBlank(String value, String field) {
        if (value == null || value.isBlank()) throw ApiException.badRequest(field + " must not be empty.");
        return value;
    }

    private String cleanOptional(String value, int max, String field) {
        if (value == null || value.isBlank()) return null;
        String cleaned = value.trim();
        if (cleaned.length() > max) {
            throw ApiException.badRequest(field + " is too long (maximum " + max + " characters).");
        }
        return cleaned;
    }

    private String cleanDestinationLabel(String value) {
        if (value == null || value.isBlank()) return null;
        String label = value.trim().replaceAll("\\s+", " ");
        if (label.length() > 80) {
            throw ApiException.badRequest("destination_label is too long (maximum 80 characters).");
        }
        return label;
    }

    private String cleanReason(String raw) {
        if (raw == null || raw.isBlank()) {
            throw ApiException.badRequest("A non-empty rejection reason is required.");
        }
        String reason = raw.trim();
        if (reason.length() > 2000) {
            throw ApiException.badRequest("reason is too long (maximum 2000 characters).");
        }
        if (reason.indexOf('\0') >= 0) {
            throw ApiException.badRequest("reason must not contain NUL characters.");
        }
        return reason;
    }

    private String serializeMetadata(Map<String, Object> metadata, boolean allowNull) {
        if (metadata == null) {
            if (allowNull) return null;
            return "{}";
        }
        String serialized = json.write(metadata);
        if (serialized.length() > 20_000) {
            throw ApiException.badRequest("metadata is too large (maximum 20,000 serialized characters).");
        }
        return serialized;
    }

    private List<String> validateReferences(List<String> references) {
        if (references == null) return List.of();
        if (references.size() > 50) throw ApiException.badRequest("At most 50 references are allowed.");
        List<String> out = new ArrayList<>();
        for (String reference : references) {
            out.add(validateReference(reference, "references[]"));
        }
        return out;
    }

    private String validateReference(String raw, String field) {
        if (raw == null || raw.isBlank()) throw ApiException.badRequest(field + " must be a non-empty URL.");
        String value = raw.trim();
        if (value.length() > 2048) throw ApiException.badRequest(field + " is too long (maximum 2048 characters).");
        try {
            URI uri = new URI(value);
            String scheme = uri.getScheme();
            if (scheme == null || !(scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https"))
                    || uri.getHost() == null) {
                throw ApiException.badRequest(field + " must be an absolute http or https URL.");
            }
            if (uri.getUserInfo() != null) {
                throw ApiException.badRequest(field + " must not contain credentials.");
            }
            return value;
        } catch (java.net.URISyntaxException ex) {
            throw ApiException.badRequest(field + " is not a valid URL: " + ex.getMessage());
        }
    }

    private void ensureReferenceLimit(Set<String> references) {
        if (references.size() > 50) {
            throw ApiException.badRequest("At most 50 references are allowed per message.");
        }
    }

    private void ensureMessageSize(MessageRecord current, List<AttachmentRecord> staged) {
        long total = 0;
        if (current != null) {
            for (AttachmentRecord attachment : presenter.attachments(current)) {
                total += attachment.sizeBytes();
            }
        }
        for (AttachmentRecord attachment : staged) total += attachment.sizeBytes();
        if (total > properties.getMaxMessageAttachmentBytes()) {
            attachments.discardStaged(staged);
            throw ApiException.tooLarge("The message attachments total " + total
                    + " bytes; the per-message limit is " + properties.getMaxMessageAttachmentBytes() + " bytes.");
        }
    }

    private static List<MultipartFile> safeFiles(List<MultipartFile> files) {
        return files == null ? List.of() : files;
    }

    private List<MessageStatus> parseStatuses(String raw) {
        if (raw == null || raw.isBlank() || raw.equalsIgnoreCase("all")) return null;
        if (raw.equalsIgnoreCase("active") || raw.equalsIgnoreCase("non_terminal")
                || raw.equalsIgnoreCase("non-terminal")) {
            return List.of(MessageStatus.PENDING, MessageStatus.APPROVED, MessageStatus.REJECTED);
        }
        Set<MessageStatus> statuses = new LinkedHashSet<>();
        for (String part : raw.split(",")) {
            if (part.isBlank()) continue;
            statuses.add(MessageStatus.parse(part));
        }
        if (statuses.isEmpty()) throw ApiException.badRequest("status filter must not be empty.");
        return List.copyOf(statuses);
    }

    private static String bound(String raw, boolean endOfDay, String field) {
        if (raw == null || raw.isBlank()) return null;
        String value = raw.trim();
        if (value.matches("\\d{4}-\\d{2}-\\d{2}")) {
            return value + (endOfDay ? "T23:59:59Z" : "T00:00:00Z");
        }
        try {
            return Times.iso(Times.parse(value));
        } catch (IllegalArgumentException ex) {
            throw ApiException.badRequest("Invalid " + field + ": " + ex.getMessage());
        }
    }
}
