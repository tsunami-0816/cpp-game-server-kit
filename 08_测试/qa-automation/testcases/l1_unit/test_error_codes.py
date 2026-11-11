# -*- coding: utf-8 -*-
"""L1 单元：错误码分支与源码/契约一致（纯源码走查，不联网）。"""
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[4] / "05_代码" / "backend" / "src"


def read(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


@pytest.mark.l1
def test_gateway_error_codes_present():
    src = read("gateway/main_gateway.cpp")
    assert "1001" in src and "user not found" in src
    assert "1002" in src and "wrong password" in src


@pytest.mark.l1
def test_battle_error_codes_present():
    src = read("battle/main_battle.cpp")
    assert "1003" in src and "invalid token" in src
    assert "2001" in src and "room not found" in src
    assert "2002" in src and "room full" in src


@pytest.mark.l1
def test_room_capacity_threshold_is_50():
    """Q-014 回归：满员阈值对齐基线 M5 契约 50 人，不再是硬编码 8。"""
    src = read("battle/main_battle.cpp")
    assert "members.size() >= 50" in src
    assert "members.size() >= 8" not in src
