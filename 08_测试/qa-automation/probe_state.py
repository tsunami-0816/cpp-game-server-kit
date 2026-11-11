#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step8 状态探测：二进制时间戳/阈值源码/端口监听/种子用户/Redis 残留。结果落盘 reports/probe_state.txt。"""
import os
import subprocess
import time
from pathlib import Path

ROOT = str(Path(__file__).resolve().parent.parent.parent)
BIN = os.path.join(ROOT, "05_代码/backend/build/bin")
OUT = os.path.join(ROOT, "08_测试/qa-automation/reports/probe_state.txt")
_lines = []


def emit(s=""):
    print(s)
    _lines.append(str(s))


def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    return (p.stdout + p.stderr).strip()


for exe in ["game_gateway", "battle_server", "echo_server", "bench_queue", "stress_client"]:
    p = os.path.join(BIN, exe)
    if os.path.exists(p):
        st = os.stat(p)
        emit(f"bin {exe}: mtime={time.strftime('%H:%M:%S', time.localtime(st.st_mtime))} size={st.st_size}")
    else:
        emit(f"bin {exe}: MISSING")

src = os.path.join(ROOT, "05_代码/backend/src/battle/main_battle.cpp")
with open(src, encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "members.size()" in line:
            emit(f"src threshold line {i}: {line.strip()}")

emit("--- ports ---")
emit(run("ss -ltnp 2>/dev/null | grep -E '8001|3306' || true"))
emit(run("ss -lunp 2>/dev/null | grep 8002 || true"))
emit("--- mysql users ---")
emit(run("mysql -uroot -N -e 'SELECT id,username FROM cpp_game.users ORDER BY id;' 2>&1"))
emit("--- redis keys ---")
emit(run("redis-cli -p 6380 keys '*' 2>&1"))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(_lines) + "\n")
print(f"\nwritten: {OUT}")
