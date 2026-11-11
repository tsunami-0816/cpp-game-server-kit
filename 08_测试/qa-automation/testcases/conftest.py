# -*- coding: utf-8 -*-
"""pytest 全局 fixtures：环境配置、客户端工厂、种子登录账号与用例后清理。

用例独立原则（step08 框架硬规则 3/7）：每条用例自己登录拿 token、自己建房；
fixture teardown 清理本用例产生的 Redis session，不依赖其他用例执行顺序。
"""
import sys
from pathlib import Path

import pytest

_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

from common.config_util import CONFIG  # noqa: E402
from common.db_util import RedisHelper  # noqa: E402
from common.gateway_client import GatewayClient  # noqa: E402
from api import auth_api, battle_api  # noqa: E402


@pytest.fixture(scope="session")
def config():
    return CONFIG


@pytest.fixture(scope="session")
def redis_helper():
    helper = RedisHelper()
    yield helper


@pytest.fixture(scope="session", autouse=True)
def _cleanup_sessions_after_session(redis_helper):
    """整轮测试结束后清理种子 session，回到干净库 + 最小种子状态。"""
    yield
    redis_helper.delete("session:1", "session:2")


@pytest.fixture(scope="function")
def gateway():
    return GatewayClient()


@pytest.fixture(scope="function")
def battle_factory():
    clients = []

    def _factory():
        c = battle_api.new_battle_client()
        clients.append(c)
        return c

    yield _factory
    for c in clients:
        c.close()


@pytest.fixture(scope="function")
def seed_user1(redis_helper):
    result = auth_api.login_seed(0)
    yield result
    redis_helper.delete(RedisHelper.session_key(result.uid))


@pytest.fixture(scope="function")
def seed_user2(redis_helper):
    result = auth_api.login_seed(1)
    yield result
    redis_helper.delete(RedisHelper.session_key(result.uid))
