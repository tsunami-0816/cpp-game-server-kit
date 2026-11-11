# -*- coding: utf-8 -*-
"""登录业务高阶封装。"""
from common.gateway_client import GatewayClient, LoginResult
from common.config_util import CONFIG


def gateway() -> GatewayClient:
    return GatewayClient()


def seed_accounts() -> list:
    return CONFIG["accounts"]["seed"]


def login(username: str, password: str) -> LoginResult:
    return GatewayClient().login(username, password)


def login_seed(index: int = 0) -> LoginResult:
    """登录种子账号；index 0=user1(uid1)，1=user2(uid2)。"""
    acc = seed_accounts()[index]
    return GatewayClient().login(acc["username"], acc["password"])
