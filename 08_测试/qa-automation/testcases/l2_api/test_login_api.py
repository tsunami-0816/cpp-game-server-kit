# -*- coding: utf-8 -*-
"""L2 接口集成：网关登录链路（TCP 8001，4B 头 + protobuf）。

四象限：正向（user1/user2）/ 反向（不存在、密码错）/ 边界（空用户名、空密码）。
断言不只看 code，同时校验 uid、token 格式、msg 与失败时 token 为空。
"""
import pytest

from common.assert_util import assert_code, is_token_format
from api import auth_api


@pytest.mark.l2
@pytest.mark.p0
def test_login_user1_success():
    r = auth_api.login("user1", "123456")
    assert_code(r.code, 0, f"msg={r.msg}")
    assert r.uid == 1
    assert is_token_format(r.token)
    assert r.msg == "ok"


@pytest.mark.l2
@pytest.mark.p0
def test_login_user2_success():
    r = auth_api.login("user2", "123456")
    assert_code(r.code, 0, f"msg={r.msg}")
    assert r.uid == 2
    assert is_token_format(r.token)


@pytest.mark.l2
@pytest.mark.p1
def test_login_user_not_found():
    r = auth_api.login("nobody_xyz", "123456")
    assert_code(r.code, 1001)
    assert r.token == ""
    assert r.uid == 0


@pytest.mark.l2
@pytest.mark.p1
def test_login_wrong_password():
    r = auth_api.login("user1", "wrongpass")
    assert_code(r.code, 1002)
    assert r.token == ""


@pytest.mark.l2
@pytest.mark.p1
def test_login_empty_username_is_rejected():
    r = auth_api.login("", "123456")
    assert_code(r.code, 1001)
    assert r.token == ""


@pytest.mark.l2
@pytest.mark.p1
def test_login_empty_password_is_rejected():
    r = auth_api.login("user1", "")
    assert_code(r.code, 1002)
    assert r.token == ""


@pytest.mark.l2
@pytest.mark.p1
def test_login_sql_injection_probe_rejected():
    """用户名带注入串经预处理占位符传递，应按字面量查不到用户 → 1001，不得绕过。"""
    r = auth_api.login("' OR '1'='1", "anything")
    assert_code(r.code, 1001)
    assert r.token == ""


@pytest.mark.l2
@pytest.mark.p1
def test_login_response_fast_on_local_loopback():
    """M4 口径：本机回环登录端到端 < 50ms（单次采样，趋势性指标见 perf_report）。"""
    r = auth_api.login("user1", "123456")
    assert_code(r.code, 0)
    assert r.rt_ms < 50, f"登录耗时 {r.rt_ms:.1f}ms 超过 50ms"
