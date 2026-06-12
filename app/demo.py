"""直接调用 pipeline 的交互式测试脚本，不经过 FastAPI。"""

import sys
import io

# 安全设置 stdout 编码，非 TTY/重定向环境下静默跳过
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from app.services.pipeline_service import run_pipeline
from app.services.memory_service import _conversation_memory, _score_smoother
from app.core.lifecycle import register_shutdown_cleanup


def demo(user_text: str, session_id: str = "test_session"):
    print("=" * 60)
    print(f"用户输入: {user_text}")

    # 打印当前注入给 LLM 的对话历史
    history = _conversation_memory.get_history_text(session_id)
    if history:
        print("-" * 40)
        print("[本轮注入LLM的对话历史]")
        print(history)
        print("-" * 40)
    else:
        print("(首轮对话，无历史记录)")

    result = run_pipeline(user_text=user_text, session_id=session_id)

    print(f"回复: {result['reply']}")

    print("-" * 26, "EVIDENCES", "-" * 26)
    print(f"风险等级: {result['risk_level']}")
    print(f"persistent_score: {result['score']}")
    print(f"证据: {result['evidence']}")
    print(f"模型: {result['model_provider']} / {result['model_name']}")
    print("=" * 60)
    return result


if __name__ == "__main__":
    import uuid

    # dev 模式退出时自动清理 data/ 目录
    register_shutdown_cleanup()

    session_id = str(uuid.uuid4())[:8]
    print(f"会话已开始 (session: {session_id})，输入 'quit' 结束对话\n")

    while True:
        try:
            user_text = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n对话结束。")
            break

        if not user_text:
            continue
        if user_text.lower() == "quit":
            print("对话结束。")
            # 退出前清理本次测试会话
            _conversation_memory.clear(session_id)
            _score_smoother.reset(session_id)
            break

        demo(user_text, session_id=session_id)
        print()