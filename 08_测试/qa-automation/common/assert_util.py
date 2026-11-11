# -*- coding: utf-8 -*-
"""统一断言工具：不只断 code，关键字段一并校验（step08 框架硬规则 4）。"""
import re

_TOKEN_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def is_token_format(token: str) -> bool:
    """登录 token：32 字节随机数的 hex 编码 = 64 位十六进制字符。"""
    return bool(token) and bool(_TOKEN_RE.match(token))


def assert_code(actual: int, expected: int, msg: str = "") -> None:
    assert actual == expected, f"code 期望 {expected}，实际 {actual} {msg}"


def assert_login_ok(result, expect_uid: int) -> None:
    assert_code(result.code, 0, f"msg={result.msg}")
    assert result.uid == expect_uid, f"uid 期望 {expect_uid}，实际 {result.uid}"
    assert is_token_format(result.token), f"token 格式非法: len={len(result.token)}"


def assert_members_contain(members: list, uids: list) -> None:
    for uid in uids:
        assert uid in members, f"成员列表 {members} 缺少 uid={uid}"
