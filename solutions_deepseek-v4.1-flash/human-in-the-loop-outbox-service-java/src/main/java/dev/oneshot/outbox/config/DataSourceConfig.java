package dev.oneshot.outbox.config;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

import javax.sql.DataSource;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

@Configuration
public class DataSourceConfig {

    @Bean
    @Primary
    public DataSource dataSource(OutboxProperties properties) throws IOException {
        Path dataDir = Path.of(properties.getDataDir()).toAbsolutePath().normalize();
        Path attachmentDir = Path.of(properties.getAttachmentDir()).toAbsolutePath().normalize();
        Files.createDirectories(dataDir);
        Files.createDirectories(attachmentDir);
        properties.setDataDir(dataDir.toString());
        properties.setAttachmentDir(attachmentDir.toString());

        HikariConfig config = new HikariConfig();
        config.setPoolName("outbox-sqlite");
        // One connection keeps SQLite's single-writer model predictable and avoids
        // SQLITE_BUSY races while still allowing WAL-backed readers in other tools.
        config.setMaximumPoolSize(1);
        config.setMinimumIdle(1);
        config.setConnectionTimeout(10_000);
        config.setJdbcUrl("jdbc:sqlite:" + dataDir.resolve("outbox.db")
                + "?busy_timeout=5000&journal_mode=WAL&synchronous=NORMAL&foreign_keys=on");
        config.setConnectionInitSql("PRAGMA foreign_keys=ON");
        return new HikariDataSource(config);
    }
}
