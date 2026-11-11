# -*- coding: utf-8 -*-
"""L1 单元：密码哈希口径 = sha256(salt + password) hex，与 schema.sql 种子常量对账。

不连数据库：种子哈希常量取自 sql/schema.sql（基线 §3.2 降级方案：sha256+salt，生产换 bcrypt）。
"""
import hashlib

import pytest

# 取自 05_代码/backend/sql/schema.sql 种子 INSERT
SEED = [
    ("user1", "salt1", "123456",
     "55baa6968eec5d9d7117c507fb2aa381cfd9c85e018733020b7ad58a21f7388c"),
    ("user2", "salt2", "123456",
     "63e48047827db95821f831780355ecaf617d1ca69474c4a39f8902d24fa3a5e6"),
]


def sha256_hex(salt: str, password: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


@pytest.mark.l1
@pytest.mark.parametrize("username,salt,password,expect_hash", SEED)
def test_seed_hash_matches_scheme(username, salt, password, expect_hash):
    assert sha256_hex(salt, password) == expect_hash, f"{username} 哈希口径不一致"


@pytest.mark.l1
def test_wrong_password_produces_different_hash():
    good = sha256_hex("salt1", "123456")
    bad = sha256_hex("salt1", "wrongpass")
    assert good != bad


@pytest.mark.l1
def test_hash_is_not_plaintext():
    h = sha256_hex("salt1", "123456")
    assert "123456" not in h
    assert len(h) == 64
