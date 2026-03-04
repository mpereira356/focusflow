-- ═══════════════════════════════════════════════════════════
-- FocusFlow — MySQL Schema
-- ═══════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS focusflow
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE focusflow;

-- ─── Users ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username     VARCHAR(80)  NOT NULL UNIQUE,
    email        VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email)
) ENGINE=InnoDB;

-- ─── Tasks ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id          INT UNSIGNED NOT NULL,
    name             VARCHAR(200) NOT NULL,
    description      TEXT,
    duration_minutes INT          NOT NULL DEFAULT 25,
    is_recurring     TINYINT(1)   NOT NULL DEFAULT 1,
    color            VARCHAR(7)   NOT NULL DEFAULT '#4A9EFF',
    icon             VARCHAR(50)  NOT NULL DEFAULT 'timer',
    is_active        TINYINT(1)   NOT NULL DEFAULT 1,
    created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_active (user_id, is_active)
) ENGINE=InnoDB;

-- ─── Task Sessions ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS task_sessions (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    task_id        INT UNSIGNED NOT NULL,
    date           DATE         NOT NULL,
    time_completed INT          NOT NULL DEFAULT 0,
    status         VARCHAR(20)  NOT NULL DEFAULT 'pending',
    started_at     DATETIME,
    ended_at       DATETIME,
    last_tick      DATETIME,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    UNIQUE KEY uq_task_date (task_id, date),
    INDEX idx_task_date (task_id, date)
) ENGINE=InnoDB;
