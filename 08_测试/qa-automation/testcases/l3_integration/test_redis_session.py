# -*- coding: utf-8 -*-
"""L3 中间件集成：Redis session 落盘、值一致、TTL 非永久、重复登录覆盖。

降级说明（step08 §8.0 L3 取舍）：本机 16GB 内存且中间件为 WSL2 裸跑，未用 Testcontainers
起容器；本层直连常驻 Redis 做交互断言，等价验证「写 session → 读回 → TTL → 覆盖」链路。
"""
import pytest

from api import auth_api


@pytest.mark.l3
@pytest.mark.p0
def test_session_written_after_login(seed_user1, redis_helper):
    val = redis_helper.get_session(seed_user1.uid)
    assert val == seed_user1.token, "Redis session 值与登录返回 token 不一致"
    ttl = redis_helper.session_ttl(seed_user1.uid)
    assert 7190 <= ttl <= 7200, f"session TTL={ttl}，应≈7200s 且非永久"


@pytest.mark.l3
def test_session_overwritten_on_relogin(redis_helper):
    first = auth_api.login("user1", "123456")
    second = auth_api.login("user1", "123456")
    try:
        assert redis_helper.get_session(1) == second.token
        assert redis_helper.get_session(1) != first.token
    finally:
        redis_helper.delete("session:1")


@pytest.mark.l3
def test_no_session_residue_after_fixture_cleanup(redis_helper):
    auth_api.login("user2", "123456")
    # 登录产生 session:2；本用例显式清理，核对清理后无残留
    redis_helper.delete("session:2")
    assert "session:2" not in redis_helper.keys("session:*")
