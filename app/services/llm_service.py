"""LLM 回复生成服务

reply_step — 管道的最后一步：根据安全策略调用 LLM 生成支持性回复。
"""

import os
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.llm_client import LLMClientManager
from app.prompt.knowledge_loader import KnowledgeBase
from app.services.memory_service import _conversation_memory
from app.services.persona_service import build_persona_instruction

_kb: KnowledgeBase | None = None

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompt")

with open(os.path.join(_TEMPLATE_DIR, "system_prompt.md"), "r", encoding="utf-8") as _f:
    REPLY_SYSTEM_PROMPT_TEMPLATE = _f.read()


def _get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb


def _call_llm(prompt: str, system: str = "") -> str:
    try:
        llm = LLMClientManager.get_reply_client()
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        response = llm.invoke(messages)
        content = response.content
        assert isinstance(content, str)
        return content.strip()
    except Exception as e:
        print(f"⚠️ LLM 回复生成失败，启用安全降级: {e}")
        return (
            "我听到了你的分享，感谢你的信任。"
            "如果你感到困扰，建议联系身边可信任的人或专业心理援助资源。"
        )


def _build_llm_diagnostic_context(details: dict) -> list[str]:
    """构建注入 LLM System Prompt 的内部诊断上下文。"""
    context: list[str] = []
    text_features = details.get("text_features_extracted", {})
    if text_features:
        feature_labels = {
            "anhedonia": "快感缺失", "depressed": "情绪低落", "sleep": "睡眠问题",
            "fatigue": "疲劳", "appetite": "食欲变化", "guilt": "内疚感",
            "concentrate": "注意力困难", "movement": "运动迟缓",
        }
        for key in [
            "anhedonia", "depressed", "sleep", "fatigue",
            "appetite", "guilt", "concentrate", "movement",
        ]:
            value = text_features.get(key, 0)
            context.append(f"{feature_labels.get(key, key)}: {value}/3分")

    audio_summary = details.get("audio_features_summary")
    if isinstance(audio_summary, dict):
        context.append(
            f"音频特征: 基频均值 {audio_summary.get('pitch_mean_hz', 'N/A')}Hz, "
            f"能量均值 {audio_summary.get('energy_mean', 'N/A')}"
        )

    return context if context else ["评估数据不足"]


def generate_supportive_reply(
    user_text: str,
    risk_level: str,
    persistent_score: float,
    llm_diagnostic_context: list[str],
    conversation_history: str = "",
    safety_decision=None,
    persona_instruction: str = "",
) -> str:
    """根据安全策略生成支持性回复。"""
    if safety_decision is None:
        raise ValueError("safety_decision is required for generating supportive reply")

    extra_instruction = safety_decision.response_constraints

    if persona_instruction:
        extra_instruction += "\n\n[Agent 初始化设定]\n" + persona_instruction

    if safety_decision.forbidden_actions:
        extra_instruction += " 禁止行为: " + "; ".join(safety_decision.forbidden_actions) + "。"
    if safety_decision.required_actions:
        extra_instruction += " 必须行为: " + "; ".join(safety_decision.required_actions) + "。"

    kb = _get_kb()
    prompt_knowledge = kb.generate_prompt(
        include_refs=safety_decision.reference_modules,
    )

    if conversation_history:
        prompt = f"{conversation_history}\n\n[当前用户消息]\n{user_text}"
    else:
        prompt = user_text

    system_prompt = REPLY_SYSTEM_PROMPT_TEMPLATE.format(
        risk_level=risk_level,
        persistent_score=persistent_score,
        evidence="; ".join(llm_diagnostic_context),
        extra_instruction=extra_instruction,
        prompt_knowledge=prompt_knowledge,
    ).strip()

    return _call_llm(prompt, system=system_prompt)


def _reply_with_memory(inputs: dict) -> dict:
    session_id = inputs.get("session_id", "default")
    history = _conversation_memory.get_history_text(session_id)
    llm_diagnostic_context = _build_llm_diagnostic_context(
        inputs["score_result"]["details"],
    )

    safety_decision = inputs.get("safety_decision")
    risk_assessment = inputs.get("risk_assessment")
    persona_instruction, safe_profile, profile_warnings = build_persona_instruction(
        inputs.get("agent_profile"),
    )

    # reply_user_text 可以包含引用；user_text 只包含当前输入，供评分和风险扫描使用。
    reply_user_text = inputs.get("reply_user_text") or inputs["user_text"]

    reply = generate_supportive_reply(
        user_text=reply_user_text,
        risk_level=inputs["risk_level"],
        persistent_score=float(inputs["persistent_score"]),
        llm_diagnostic_context=llm_diagnostic_context,
        conversation_history=history,
        safety_decision=safety_decision,
        persona_instruction=persona_instruction,
    )

    _conversation_memory.add_turn(session_id, reply_user_text, reply)

    return {
        "reply": reply,
        "score_result": inputs["score_result"],
        "instant_score": inputs.get("instant_score"),
        "smoothed_score": inputs.get("smoothed_score"),
        "persistent_score": inputs["persistent_score"],
        "risk_adjusted_score": inputs.get("risk_adjusted_score"),
        "risk_level": inputs["risk_level"],
        "risk_assessment": risk_assessment,
        "safety_decision": safety_decision,
        "agent_profile": safe_profile,
        "agent_profile_warnings": profile_warnings,
    }


reply_step = RunnableLambda(_reply_with_memory)
