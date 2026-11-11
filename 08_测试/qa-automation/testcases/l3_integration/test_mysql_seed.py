# -*- coding: utf-8 -*-
"""L3 中间件集成：MySQL 种子数据、哈希/salt 非空、utf8mb4 字符集。

降级说明：未用 Testcontainers 起 MySQL 容器，直连 WSL2 常驻 cpp_game 库做只读断言。
"""
import pytest

from common.db_util import mysql_query


@pytest.mark.l3
@pytest.mark.p0
def test_seed_users_present():
    rows = mysql_query("SELECT id, username FROM users ORDER BY id")
    assert rows == ["1\tuser1", "2\tuser2"]


@pytest.mark.l3
def test_seed_hash_and_salt_nonempty():
    rows = mysql_query(
        "SELECT id, LENGTH(password_hash), LENGTH(salt) FROM users ORDER BY id")
    assert len(rows) == 2
    for row in rows:
        _id, hash_len, salt_len = row.split("\t")
        assert int(hash_len) == 64, "sha256 hex 应为 64 字符"
        assert int(salt_len) > 0


@pytest.mark.l3
def test_table_collation_utf8mb4():
    rows = mysql_query(
        "SELECT TABLE_COLLATION FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA='cpp_game' AND TABLE_NAME='users'")
    assert rows and rows[0].startswith("utf8mb4"), f"排序规则={rows}"
