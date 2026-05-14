### 封装llm，核心接口 generate_supportive_reply

import requests
from app.core.config import settings
from app.system_prompts.skill_loader import KnowledgeBase

_kb: KnowledgeBase | None = None


def _get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb


def _call_ollama(prompt: str, system: str = "") -> str:
    body: dict = {
        "model": settings.llm_model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        body["system"] = system
    response = requests.post(
        f"{settings.ollama_base_url}/api/generate",
        json=body,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    return data["response"].strip()


def generate_supportive_reply(
    user_text: str,
    risk_level: str,
    score: int,
    evidence: list[str],
) -> str:
    if risk_level == "high":
        extra_instruction = (
            "当前用户表现出较高风险。"
            "请优先表达关切和陪伴感，明确建议其尽快联系现实中的可信任对象、心理援助热线或医疗资源。"
            "不要做轻率安慰，不要淡化风险，不要给出医学诊断。"
        )
        refs = ["crisis-resources", "suicide-prevention"]
    elif risk_level == "medium":
        extra_instruction = (
            "当前用户表现出中等风险。"
            "请表达理解与支持，并鼓励其继续描述当前最困扰的问题。"
        )
        refs = ["emotion-support", "cbt-techniques"]
    else:
        extra_instruction = (
            "当前用户风险较低。"
            "请给出温和、支持性、开放式的回应。"
        )
        refs = ["emotion-support", "meditation-scripts"]

    kb = _get_kb()
    system_prompt = kb.generate_prompt(include_refs=refs)

    prompt = f"""
 用户输入：{user_text}

已知评分结果：
- 风险等级：{risk_level}
- 分数：{score}
- 判断依据：{"; ".join(evidence)}

额外要求：{extra_instruction}

【核心原则】
1. 先表达理解和共情，再做回应
2. 不否定、不评判用户情绪
3. 不说教、不进行长篇分析
4. 以“陪伴者”身份交流，不扮演医生或权威

【表达要求】
- 回复控制在50~80字
- 使用自然口语，不要像机器人
- 避免使用专业术语，如“抑郁症诊断”等
- 不要重复用户原话
- 请直接输出给用户的回复，不要解释推理过程，不要输出项目符号。

【你的目标】
让用户感到被理解、被接住，而不是被分析或被教育
""".strip()

    return _call_ollama(prompt, system=system_prompt)