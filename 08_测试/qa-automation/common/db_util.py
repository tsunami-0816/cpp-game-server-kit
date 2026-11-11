# -*- coding: utf-8 -*-
"""中间件只读断言辅助：Redis(redis-py) + MySQL(mysql CLI 子进程，避免额外装驱动)。"""
import subprocess

import redis

from .config_util import CONFIG


class RedisHelper:
    def __init__(self):
        cfg = CONFIG["redis"]
        self.client = redis.Redis(host=cfg["host"], port=cfg["port"],
                                  db=cfg.get("db", 0), decode_responses=True)

    @staticmethod
    def session_key(uid: int) -> str:
        return f"session:{uid}"

    def get_session(self, uid: int):
        return self.client.get(self.session_key(uid))

    def session_ttl(self, uid: int) -> int:
        return self.client.ttl(self.session_key(uid))

    def keys(self, pattern: str = "*"):
        return self.client.keys(pattern)

    def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        return self.client.delete(*keys)

    def ping(self) -> bool:
        return self.client.ping()


def mysql_query(sql: str) -> list:
    """只读 SELECT；返回行列表（每行是 tab 分隔字符串）。"""
    cfg = CONFIG["mysql"]
    cmd = ["mysql", "-uroot", "-N", "-B", "-e", sql, cfg["database"]]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if p.returncode != 0:
        raise RuntimeError(f"mysql 查询失败: {p.stderr.strip()}")
    return [ln for ln in p.stdout.splitlines() if ln.strip()]
