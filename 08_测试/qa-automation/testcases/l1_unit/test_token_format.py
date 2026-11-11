# -*- coding: utf-8 -*-
"""L1 单元：登录 token 格式校验（32 字节随机数 → 64 位 hex）。"""
import pytest

from common.assert_util import is_token_format


@pytest.mark.l1
def test_valid_64_hex_token():
    assert is_token_format("a" * 64)
    assert is_token_format("0123456789abcdef" * 4)


@pytest.mark.l1
@pytest.mark.parametrize("bad", ["", "a" * 63, "a" * 65, "g" * 64, "Z" * 64, "ab-cd" + "e" * 59])
def test_invalid_token_rejected(bad):
    assert not is_token_format(bad)
