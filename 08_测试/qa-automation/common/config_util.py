# -*- coding: utf-8 -*-
"""读取 config/config.yaml 测试环境配置。"""
from pathlib import Path
import yaml

_CONFIG = Path(__file__).resolve().parent.parent / "config" / "config.yaml"


def load_config() -> dict:
    with open(_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG = load_config()
