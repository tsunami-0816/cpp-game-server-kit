#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 冒烟回归运行器：读取 p0_cases.json 台账，调用 pytest -m p0 执行并对照清单。

用法（WSL2，qa-automation 目录下）：
    PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python python3 p0_runner.py
退出码：全部 P0 通过=0，否则=1。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# P0 台账主文件在 08_测试/ 根（门禁 steps.yaml 路径约定），qa-automation 为运行目录
CASES = ROOT.parent / "p0_cases.json"


def main() -> int:
    if not CASES.exists():
        print("❌ 缺少 p0_cases.json")
        return 2

    data = json.loads(CASES.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    if not cases:
        print("⚠️  p0_cases.json 用例列表为空")
        return 2

    print(f"=== P0 台账 {len(cases)} 条 ===")
    for c in cases:
        print(f"  {c['id']} [{c['layer']}] {c['name']}")

    env = dict(os.environ)
    env.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-m", "p0", "-q"],
        cwd=ROOT, env=env, capture_output=True, text=True)

    print("\n=== pytest 输出 ===")
    print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip())

    print(f"\n=== P0 回归结论：exit={proc.returncode} ===")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
