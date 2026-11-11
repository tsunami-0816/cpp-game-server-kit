#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step8 环境自检：Python 版本 / 测试依赖 / 中间件连通 / 编译产物。只读探测，不改环境。"""
import importlib
import os
import shutil
import socket
import subprocess
import sys

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, ok, detail))
    print(f"[{'OK' if ok else 'MISS'}] {name}: {detail}")


def mod_version(mod, attr="__version__"):
    try:
        m = importlib.import_module(mod)
        return getattr(m, attr, "installed")
    except Exception as e:
        return None


# 1. Python
check("python", sys.version_info >= (3, 8), sys.version.split()[0])

# 2. 测试/协议依赖
for mod, label in [("pytest", "pytest"), ("google.protobuf", "protobuf"),
                   ("redis", "redis-py"), ("requests", "requests"),
                   ("yaml", "pyyaml"), ("allure", "allure-pytest")]:
    v = mod_version(mod)
    check(label, v is not None, str(v) if v else "not installed")

# 3. 可执行工具
for tool in ["allure", "jmeter", "mysql", "redis-cli", "cmake", "g++"]:
    check(f"tool:{tool}", shutil.which(tool) is not None, shutil.which(tool) or "not on PATH")

# 4. 中间件端口连通
for host, port, label in [("127.0.0.1", 8001, "gateway TCP"),
                           ("127.0.0.1", 8002, "battle UDP(探测端口)"),
                           ("127.0.0.1", 3306, "MySQL"),
                           ("127.0.0.1", 6380, "Redis")]:
    if label.startswith("battle"):
        check(label, True, "UDP 无连接，以 ss 监听为准")
        continue
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        check(label, True, f"{host}:{port} reachable")
    except OSError as e:
        check(label, False, f"{host}:{port} {e}")

# 5. 编译产物
bin_dir = os.path.join(os.path.dirname(__file__), "..", "..",
                       "05_代码", "backend", "build", "bin")
bin_dir = os.path.abspath(bin_dir)
for exe in ["game_gateway", "battle_server", "echo_server", "bench_queue", "stress_client"]:
    p = os.path.join(bin_dir, exe)
    check(f"bin:{exe}", os.path.exists(p), p if os.path.exists(p) else "missing")

# 6. protobuf 生成的 python 模块
scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
sys.path.insert(0, scripts_dir)
try:
    import game_pb2  # noqa
    check("game_pb2.py", True, os.path.join(scripts_dir, "game_pb2.py"))
except Exception as e:
    check("game_pb2.py", False, str(e))

print("\n=== 汇总 ===")
missing = [n for n, ok, _ in CHECKS if not ok]
print(f"total={len(CHECKS)} missing={len(missing)}")
if missing:
    print("missing:", ", ".join(missing))
sys.exit(1 if missing else 0)
