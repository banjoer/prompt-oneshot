package dev.oneshot.outbox.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * All runtime configuration, populated from environment variables through
 * application.yml. Directories are resolved to absolute paths when the app starts.
 */
@ConfigurationProperties(prefix = "outbox")
public class OutboxProperties {

    private String dataDir = "./data";
    private String attachmentDir = "./data/attachments";
    private long maxAttachmentBytes = 10L * 1024 * 1024;
    private long maxMessageAttachmentBytes = 25L * 1024 * 1024;
    private int expirationIntervalSeconds = 30;
    private int webhookTimeoutSeconds = 5;
    private int webhookMaxAttempts = 3;
    private double webhookBackoffBaseSeconds = 1;
    private int downloadTimeoutSeconds = 10;
    private int maxRedirects = 3;
    private boolean allowPrivateUrls = false;
    private int handoffUrlMaxChars = 1800;
    private long webhookWorkerIntervalMs = 300;
    private String builtAt = "";
    private String builtBy = "DeepSeek V4.1 Flash";

    public String getDataDir() { return dataDir; }
    public void setDataDir(String dataDir) { this.dataDir = dataDir; }

    public String getAttachmentDir() { return attachmentDir; }
    public void setAttachmentDir(String attachmentDir) { this.attachmentDir = attachmentDir; }

    public long getMaxAttachmentBytes() { return maxAttachmentBytes; }
    public void setMaxAttachmentBytes(long maxAttachmentBytes) { this.maxAttachmentBytes = maxAttachmentBytes; }

    public long getMaxMessageAttachmentBytes() { return maxMessageAttachmentBytes; }
    public void setMaxMessageAttachmentBytes(long v) { this.maxMessageAttachmentBytes = v; }

    public int getExpirationIntervalSeconds() { return expirationIntervalSeconds; }
    public void setExpirationIntervalSeconds(int v) { this.expirationIntervalSeconds = v; }

    public int getWebhookTimeoutSeconds() { return webhookTimeoutSeconds; }
    public void setWebhookTimeoutSeconds(int webhookTimeoutSeconds) { this.webhookTimeoutSeconds = webhookTimeoutSeconds; }

    public int getWebhookMaxAttempts() { return webhookMaxAttempts; }
    public void setWebhookMaxAttempts(int webhookMaxAttempts) { this.webhookMaxAttempts = webhookMaxAttempts; }

    public double getWebhookBackoffBaseSeconds() { return webhookBackoffBaseSeconds; }
    public void setWebhookBackoffBaseSeconds(double v) { this.webhookBackoffBaseSeconds = v; }

    public int getDownloadTimeoutSeconds() { return downloadTimeoutSeconds; }
    public void setDownloadTimeoutSeconds(int downloadTimeoutSeconds) { this.downloadTimeoutSeconds = downloadTimeoutSeconds; }

    public int getMaxRedirects() { return maxRedirects; }
    public void setMaxRedirects(int maxRedirects) { this.maxRedirects = maxRedirects; }

    public boolean isAllowPrivateUrls() { return allowPrivateUrls; }
    public void setAllowPrivateUrls(boolean allowPrivateUrls) { this.allowPrivateUrls = allowPrivateUrls; }

    public int getHandoffUrlMaxChars() { return handoffUrlMaxChars; }
    public void setHandoffUrlMaxChars(int handoffUrlMaxChars) { this.handoffUrlMaxChars = handoffUrlMaxChars; }

    public long getWebhookWorkerIntervalMs() { return webhookWorkerIntervalMs; }
    public void setWebhookWorkerIntervalMs(long v) { this.webhookWorkerIntervalMs = v; }

    public String getBuiltAt() { return builtAt; }
    public void setBuiltAt(String builtAt) { this.builtAt = builtAt; }

    public String getBuiltBy() { return builtBy; }
    public void setBuiltBy(String builtBy) { this.builtBy = builtBy; }
}
