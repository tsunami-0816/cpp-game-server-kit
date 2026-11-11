#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python 轻量压测：网关登录接口（MySQL 查用户 + Redis 写 session 主路径）。

三档并发 10/20/50，每档持续指定秒数；输出平均 RT / P95 RT / TPS / 错误率。
短连接：每次登录新建 TCP（贴近真实登录场景）。结果落 reports/perf_login.json。

用法:
    python3 perf_test.py [--dur 10] [--levels 10,20,50]
"""
import argparse
import concurrent.futures
import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.gateway_client import GatewayClient  # noqa: E402

QA_ROOT = Path(__file__).resolve().parent
REPORT = QA_ROOT / "reports" / "perf_login.json"
ACCOUNTS = [("user1", "123456"), ("user2", "123456")]


def percentile(xs, p):
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def load_level(concurrency: int, duration: float) -> dict:
    deadline = time.time() + duration
    rts, lock = [], threading.Lock()
    ok = biz_fail = exc = 0

    def worker(idx: int):
        nonlocal ok, biz_fail, exc
        gc = GatewayClient()
        i = idx
        while time.time() < deadline:
            user, pw = ACCOUNTS[i % len(ACCOUNTS)]
            i += 1
            t0 = time.time()
            try:
                r = gc.login(user, pw, timeout=3.0)
                rt = (time.time() - t0) * 1000
                with lock:
                    rts.append(rt)
                    if r.code == 0:
                        ok += 1
                    else:
                        biz_fail += 1
            except Exception:
                with lock:
                    exc += 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = [pool.submit(worker, i) for i in range(concurrency)]
        for f in futs:
            f.result()

    total = ok + biz_fail + exc
    return {
        "concurrency": concurrency,
        "duration_s": duration,
        "total_requests": total,
        "success": ok,
        "business_fail": biz_fail,
        "exception": exc,
        "error_rate": round((biz_fail + exc) / total, 4) if total else 1.0,
        "tps": round(total / duration, 1) if duration else 0,
        "avg_rt_ms": round(sum(rts) / len(rts), 2) if rts else 0,
        "p95_rt_ms": round(percentile(rts, 0.95), 2),
        "max_rt_ms": round(max(rts), 2) if rts else 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dur", type=float, default=10.0)
    ap.add_argument("--levels", default="10,20,50")
    args = ap.parse_args()
    levels = [int(x) for x in args.levels.split(",")]

    results = []
    print(f"=== 登录接口压测（每档 {args.dur}s）===")
    for n in levels:
        print(f"-- 并发 {n} ...")
        res = load_level(n, args.dur)
        results.append(res)
        print(f"   TPS={res['tps']} avg={res['avg_rt_ms']}ms "
              f"P95={res['p95_rt_ms']}ms err={res['error_rate']} "
              f"(ok={res['success']} bizFail={res['business_fail']} exc={res['exception']})")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"target": "gateway login TCP 8001",
                                  "results": results}, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print(f"\n报告已保存: {REPORT}")


if __name__ == "__main__":
    main()
