#!/usr/bin/env python3
"""
step6.5 Protobuf 契约对账脚本（本项目无 HTTP/OpenAPI，契约载体为 proto/game.proto）。

对账两个方向：
  1. 臆造消息：C++ / Python 代码引用了 proto 未定义的消息名 → 报红
  2. 死契约：proto 定义了但服务端与客户端都未引用的消息名 → 告警（不阻塞）

用法：
  python scripts/proto_contract_check.py [项目根目录]
退出码：0 = 无臆造消息；1 = 存在臆造消息。
"""
import re
import sys
from pathlib import Path

MESSAGE_RE = re.compile(r"^\s*message\s+(\w+)\s*\{", re.MULTILINE)
CPP_REF_RE = re.compile(r"game::(\w+)")
PY_REF_RE = re.compile(r"game_pb2\.(\w+)")

CPP_DIRS = ["05_代码/backend/src", "05_代码/backend/include"]
PY_DIR = "scripts"
PROTO_REL = "05_代码/backend/proto/game.proto"
SKIP_PY = {"game_pb2.py", "proto_contract_check.py"}


def _scan(root: Path, rel_dirs, pattern, suffixes):
    refs: dict[str, list[str]] = {}
    for rel in rel_dirs:
        d = root / rel
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if not f.is_file() or f.suffix not in suffixes:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            for m in pattern.finditer(text):
                refs.setdefault(m.group(1), []).append(str(f.relative_to(root)))
    return refs


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    proto = root / PROTO_REL
    if not proto.exists():
        print(f"❌ proto 契约不存在: {proto}")
        return 1

    defined = set(MESSAGE_RE.findall(proto.read_text(encoding="utf-8")))
    cpp_refs = _scan(root, CPP_DIRS, CPP_REF_RE, {".cpp", ".h"})
    py_refs = _scan(root, [PY_DIR], PY_REF_RE, {".py"})
    py_refs = {
        k: v for k, v in py_refs.items()
        if not any(Path(x).name in SKIP_PY for x in v)
    }

    used = set(cpp_refs) | set(py_refs)
    invented = sorted(used - defined)
    dead = sorted(defined - used)

    print(f"=== Protobuf 契约对账（{PROTO_REL}）===")
    print(f"proto 定义消息 {len(defined)} 条；C++ 引用 {len(cpp_refs)} 种；Python 引用 {len(py_refs)} 种\n")

    print("--- 消息定义 ↔ 引用位置 ---")
    for name in sorted(defined):
        cpp = sorted(set(cpp_refs.get(name, [])))
        py = sorted(set(py_refs.get(name, [])))
        mark = "✅" if name in used else "⚠️ 死契约（定义未引用）"
        print(f"  {mark} {name}")
        if cpp:
            print(f"      C++: {', '.join(cpp)}")
        if py:
            print(f"      Py : {', '.join(py)}")

    print("\n--- 臆造消息检查（代码引用但 proto 未定义）---")
    if invented:
        for name in invented:
            locs = sorted(set(cpp_refs.get(name, []) + py_refs.get(name, [])))
            print(f"  ❌ {name}  ← 未在 proto 定义；位置: {', '.join(locs)}")
        print(f"\n❌ 对账失败：{len(invented)} 个臆造消息")
        return 1

    print("  ✅ 0 个臆造消息：代码引用的全部消息均在 proto 契约内")
    if dead:
        print(f"\n⚠️  死契约告警（不阻塞）: {', '.join(dead)}")
    print("\n✅ 契约对账通过")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
