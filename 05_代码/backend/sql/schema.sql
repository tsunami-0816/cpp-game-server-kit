-- T-24: MySQL schema + 种子数据
CREATE DATABASE IF NOT EXISTS cpp_game DEFAULT CHARSET utf8mb4;
USE cpp_game;

CREATE TABLE IF NOT EXISTS users (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(64)  NOT NULL UNIQUE,
    password_hash VARCHAR(128) NOT NULL,
    salt          VARCHAR(32)  NOT NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 种子数据：user1 / 123456, user2 / 123456
-- password_hash = sha256(salt + password) hex
INSERT IGNORE INTO users(username, password_hash, salt) VALUES
('user1', '55baa6968eec5d9d7117c507fb2aa381cfd9c85e018733020b7ad58a21f7388c', 'salt1'),
('user2', '63e48047827db95821f831780355ecaf617d1ca69474c4a39f8902d24fa3a5e6', 'salt2');
