#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直连依赖 OSV 漏洞直查（替代不可用的 pip-audit -r 隔离解析）。

审计对象 = WSL 测试环境实际安装版本（requirements.txt 为 >= 下限）。
仅覆盖 qa-automation 直连依赖；C++ 运行时依赖为系统库，另在报告中列版本。
"""
import json
import urllib.request

# 实际安装版本（pip list 实测，2026-11-11）
DEPS = [
    ("pytest", "9.2.0"),
    ("redis", "8.1.0"),
    ("requests", "2.25.1"),
    ("PyYAML", "5.4.1"),
    ("allure-pytest", "2.16.2"),
    ("protobuf", "7.36.2"),
]

URL = "https://api.osv.dev/v1/query"


def query(name, version):
    body = json.dumps({
        "version": version,
        "package": {"name": name, "ecosystem": "PyPI"},
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "vulns": []}
    vulns = []
    for v in data.get("vulns", []) or []:
        aliases = v.get("aliases", [])
        vulns.append({
            "id": v.get("id"),
            "aliases": aliases,
            "summary": (v.get("summary") or "")[:120],
            "severity": [s.get("type") for s in v.get("severity", [])],
            "fixed": [
                ev.get("fixed")
                for aff in v.get("affected", [])
                for ev in aff.get("ranges", [])
                if ev.get("fixed")
            ],
        })
    return {"vulns": vulns}


def main():
    report = {}
    for name, ver in DEPS:
        res = query(name, ver)
        report[f"{name}=={ver}"] = res
        n = len(res.get("vulns", []))
        print(f"== {name}=={ver}: {n} 条公告")
        for v in res.get("vulns", []):
            print(f"   - {v['id']} {v['aliases']} fixed={v['fixed']} :: {v['summary']}")
    with open("08.5_安全扫描/evidence/osv_check.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n证据已落 08.5_安全扫描/evidence/osv_check.json")


if __name__ == "__main__":
    main()
