package dev.oneshot.outbox.service;

import dev.oneshot.outbox.channel.ChannelAdapter;
import dev.oneshot.outbox.channel.ChannelRegistry;
import dev.oneshot.outbox.channel.HandoffPlan;
import dev.oneshot.outbox.config.OutboxProperties;
import dev.oneshot.outbox.model.AttachmentRecord;
import dev.oneshot.outbox.model.MessageRecord;
import dev.oneshot.outbox.model.MessageStatus;
import dev.oneshot.outbox.repo.MessageRepository;
import dev.oneshot.outbox.repo.RevisionRepository;
import dev.oneshot.outbox.web.ApiException;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class HandoffService {
    private final MessageRepository messages;
    private final RevisionRepository revisions;
    private final ChannelRegistry channels;
    private final ExpirationService expiration;
    private final MessagePresenter presenter;
    private final OutboxProperties properties;

    public HandoffService(MessageRepository messages, RevisionRepository revisions, ChannelRegistry channels,
                          ExpirationService expiration, MessagePresenter presenter, OutboxProperties properties) {
        this.messages = messages;
        this.revisions = revisions;
        this.channels = channels;
        this.expiration = expiration;
        this.presenter = presenter;
        this.properties = properties;
    }

    public Map<String, Object> handoff(String messageId) {
        expiration.expireDue();
        MessageRecord message = messages.findById(messageId);
        if (message == null) throw ApiException.notFound("Message " + messageId + " was not found.");
        if (MessagePresenter.isExpired(message) && !message.status().isTerminal()) {
            expiration.expireOne(messageId);
            message = messages.findById(messageId);
        }
        if (message == null) throw ApiException.notFound("Message " + messageId + " was not found.");
        if (message.status() != MessageStatus.APPROVED) {
            throw ApiException.transition(
                    "Handoff is only available for approved messages. Current status: " + message.status().wire() + ".",
                    message.status().wire(), message.status().allowedActions());
        }
        if (MessagePresenter.isExpired(message)) {
            throw ApiException.transition("This message expired and cannot be handed off.",
                    MessageStatus.STALE.wire(), MessageStatus.STALE.allowedActions());
        }

        ChannelAdapter adapter = channels.get(message.channel());
        final MessageRecord finalMessage = message;
        List<AttachmentRecord> attachments = revisions.attachmentsForMessageRevision(
                finalMessage.id(), finalMessage.revisionNumber());
        List<String> references = revisions.referencesForMessageRevision(
                finalMessage.id(), finalMessage.revisionNumber());
        HandoffPlan plan = adapter.handoff(message, attachments, properties.getHandoffUrlMaxChars());

        Map<String, Object> capabilities = new LinkedHashMap<>();
        capabilities.put("prefill_recipient", plan.prefillRecipient());
        capabilities.put("prefill_subject", plan.prefillSubject());
        capabilities.put("prefill_body", plan.prefillBody());
        capabilities.put("attachments_supported", false);

        List<String> warnings = new ArrayList<>(plan.warnings());
        warnings.add("The service never contacts a provider. You send the message yourself.");

        Map<String, Object> copy = new LinkedHashMap<>();
        copy.put("subject", message.subject());
        copy.put("body", message.body());

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("message_id", message.id());
        out.put("channel", message.channel().wire());
        out.put("destination", message.destination());
        out.put("normalized_destination", message.normalizedDestination());
        out.put("destination_label", message.destinationLabel());
        out.put("display_label", presenter.detail(message).get("display_label"));
        out.put("target_display", plan.targetDisplay());
        out.put("handoff_url", plan.handoffUrl());
        out.put("capabilities", capabilities);
        out.put("manual_actions", plan.manualActions());
        out.put("warnings", warnings);
        out.put("copy", copy);
        out.put("subject", message.subject());
        out.put("body", message.body());
        out.put("attachments", attachments.stream()
                .map(a -> presenter.attachmentView(finalMessage.id(), a)).toList());
        out.put("references", references);
        out.put("transport_note", plan.transportNote());
        out.put("status", message.status().wire());
        out.put("revision_number", message.revisionNumber());
        out.put("handoff_url_length", plan.handoffUrl().length());
        out.put("handoff_url_max_chars", properties.getHandoffUrlMaxChars());
        out.put("download_all_url", attachments.isEmpty() ? null
                : "/api/messages/" + message.id() + "/attachments.zip");
        return out;
    }
}
