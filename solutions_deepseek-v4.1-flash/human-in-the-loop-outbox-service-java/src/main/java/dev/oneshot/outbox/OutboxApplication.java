/*
 * Human-in-the-Loop Outbox Service — Java / Spring Boot edition.
 *
 * Built 2026-11-07 01:20 UTC by DeepSeek V4.1 Flash (opencode-go / deepseek-v4.1-flash).
 *
 * Local, single-process review-and-handoff outbox. Producers submit messages over
 * REST, a human reviews them in the Svelte SPA, and the human sends them through
 * their own email / WhatsApp / Telegram client using prepared handoff links.
 * The service never integrates with provider APIs and never sends by itself.
 */
package dev.oneshot.outbox;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@ConfigurationPropertiesScan
@EnableScheduling
public class OutboxApplication {
    public static void main(String[] args) {
        SpringApplication.run(OutboxApplication.class, args);
    }
}
