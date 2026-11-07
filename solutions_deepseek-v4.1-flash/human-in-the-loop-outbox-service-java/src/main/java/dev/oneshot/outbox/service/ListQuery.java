package dev.oneshot.outbox.service;

public record ListQuery(
        String status,
        String channel,
        String destination,
        String createdAfter,
        String createdBefore,
        String expiresAfter,
        String expiresBefore,
        String sort,
        Integer limit,
        Integer offset
) {}
