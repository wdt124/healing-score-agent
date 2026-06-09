"""应用生命周期管理

提供启动初始化和程序退出时的清理钩子。
在 dev 模式下，退出时自动清理 data/ 目录中的 JSON/JSONL 文件。
"""

import atexit
import os
from app.core.config import settings

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "data"
)


def clear_data_files() -> None:
    """清除 data/ 目录下的持久化数据文件。

    清理目标:
      - conversation_history.json
      - risk_history.json
      - risk_audit.jsonl

    仅在 APP_ENV=dev（默认）时执行；生产环境跳过。
    """
    if settings.app_env != "dev":
        return

    if not os.path.isdir(_DATA_DIR):
        return

    for filename in os.listdir(_DATA_DIR):
        if filename.endswith((".json", ".jsonl")):
            filepath = os.path.join(_DATA_DIR, filename)
            try:
                os.remove(filepath)
            except OSError:
                pass  # 忽略权限错误


def register_shutdown_cleanup() -> None:
    """注册程序退出时的清理钩子。应在 main.py / demo.py 入口调用。"""
    atexit.register(clear_data_files)
