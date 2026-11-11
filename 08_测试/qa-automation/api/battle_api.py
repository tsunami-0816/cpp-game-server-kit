# -*- coding: utf-8 -*-
"""战斗服业务高阶封装。"""
from common.battle_client import BattleClient


def new_battle_client() -> BattleClient:
    return BattleClient()
