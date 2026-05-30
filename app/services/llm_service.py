
### 封装llm，runnable组件 reply_step，后面可改流式输出stream()
'''memory_step:
        input:
            user_text
            score_result
            session_id
            persistent_score
            risk_level
        output:
            reply
            score_result
            persistent_score
            risk_level
            evidence

'''
import os
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.config import settings
from app.prompt.knowledge_loader import KnowledgeBase
from app.services.memory_service import _conversation_memory

_kb: KnowledgeBase | None = None

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompt")

with open(os.path.join(_TEMPLATE_DIR, "system_prompt.md"), "r", encoding="utf-8") as _f:
    REPLY_SYSTEM_PROMPT_TEMPLATE = _f.read()


def _get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb



_llm_client: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.api_key,
            base_url=settings.base_url,
            temperature=0.7,
            max_tokens=512,
        )
    assert _llm_client is not None
    return _llm_client


def _call_llm(prompt: str, system: str = "") -> str:
    try:
        llm = _get_llm()
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


def generate_supportive_reply(
    user_text: str,
    risk_level: str,
    persistent_score: float,
    evidence: list[str],
    conversation_history: str = "",
    safety_decision=None,
    risk_assessment=None,
) -> str:
    # 优先使用 SafetyDecision 中的约束来生成 extra_instruction
    if safety_decision is not None:
        safety_mode = safety_decision.mode
        extra_instruction = safety_decision.response_constraints
    else:
        safety_mode = risk_level
        extra_instruction = ""

    if safety_mode in ("crisis_intervention", "high"):
        if not extra_instruction:
            extra_instruction = (
                "当前用户表现出高风险。"
                "请优先表达关切和陪伴感，明确建议其尽快联系现实中的可信任对象、心理援助热线或医疗资源。"
                "不要做轻率安慰，不要淡化风险，不要给出医学诊断。"
            )
        refs = ["crisis-resources", "suicide-prevention"]
    elif safety_mode in ("safety_planning", "medium"):
        if not extra_instruction:
            extra_instruction = (
                "当前用户表现出中等风险。"
                "请表达理解与支持，并鼓励其继续描述当前最困扰的问题。"
            )
        refs = ["emotion-support", "cbt-techniques"]
    elif safety_mode in ("supportive_checkin", "low"):
        if not extra_instruction:
            extra_instruction = "当前用户风险较低。请给出温和、支持性、开放式的回应。"
        refs = ["emotion-support", "meditation-scripts"]
    elif safety_mode in ("normal_support", "normal"):
        if not extra_instruction:
            extra_instruction = "当前用户无抑郁症风险，请正常交流"
        refs = []
    else:
        extra_instruction = extra_instruction or "请给出温和、支持性的回应。"
        refs = []

    # 将 safety_decision 的 forbid/require 注入 extra_instruction
    if safety_decision is not None:
        if safety_decision.forbidden_actions:
            extra_instruction += " 禁止行为: " + "; ".join(safety_decision.forbidden_actions) + "。"
        if safety_decision.required_actions:
            extra_instruction += " 必须行为: " + "; ".join(safety_decision.required_actions) + "。"

    kb = _get_kb()
    prompt_knowledge = kb.generate_prompt(include_refs=refs)

    # 将历史对话拼接到当前用户消息之前
    if conversation_history:
        prompt = f"{conversation_history}\n\n[当前用户消息]\n{user_text}"
    else:
        prompt = user_text

    system_prompt = REPLY_SYSTEM_PROMPT_TEMPLATE.format(
        risk_level=risk_level,
        persistent_score=persistent_score,
        evidence="; ".join(evidence),
        extra_instruction=extra_instruction,
        prompt_knowledge=prompt_knowledge,
    ).strip()

    return _call_llm(prompt, system=system_prompt)


def _format_evidence(details: dict) -> list[str]:
    evidence = []
    text_features = details.get("text_features_extracted", {})
    if text_features:
        feature_labels = {
            "anhedonia": "快感缺失", "depressed": "情绪低落", "sleep": "睡眠问题",
            "fatigue": "疲劳", "appetite": "食欲变化", "guilt": "内疚感",
            "concentrate": "注意力困难", "movement": "运动迟缓"
        }
        for k in ["anhedonia", "depressed", "sleep", "fatigue", "appetite", "guilt", "concentrate", "movement"]:
            v = text_features.get(k, 0)
            evidence.append(f"{feature_labels.get(k, k)}: {v}/3分")

    audio_summary = details.get("audio_features_summary")
    if isinstance(audio_summary, dict):
        evidence.append(
            f"音频特征: 基频均值 {audio_summary.get('pitch_mean_hz', 'N/A')}Hz, "
            f"能量均值 {audio_summary.get('energy_mean', 'N/A')}"
        )

    return evidence if evidence else ["评估数据不足"]

def _reply_with_memory(inputs: dict) -> dict:
    session_id = inputs.get("session_id", "default")
    history = _conversation_memory.get_history_text(session_id)
    evidence = _format_evidence(inputs["score_result"]["details"])

    safety_decision = inputs.get("safety_decision")
    risk_assessment = inputs.get("risk_assessment")

    reply = generate_supportive_reply(
        user_text=inputs["user_text"],
        risk_level=inputs["risk_level"],
        persistent_score=float(inputs["persistent_score"]),
        evidence=evidence,
        conversation_history=history,
        safety_decision=safety_decision,
        risk_assessment=risk_assessment,
    )

    _conversation_memory.add_turn(session_id, inputs["user_text"], reply)

    return {
        "reply": reply,
        "score_result": inputs["score_result"],
        "persistent_score": inputs["persistent_score"],
        "risk_level": inputs["risk_level"],
        "evidence": evidence,
        "risk_assessment": risk_assessment,
        "safety_decision": safety_decision,
    }


### 构建runnable组件
reply_step = RunnableLambda(_reply_with_memory)
