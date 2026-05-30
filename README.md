# Healing Score Agent

一个心理支持对话 Agent 的后端原型，核心能力是：接收用户输入文本，评估风险等级，产出带安全约束的支持性回复。

## 项目定位

目前这还是一个学习型项目，目标不是临床可用，而是：

- 把"风险检测 → 安全决策 → 生成回复"这条链路做得结构清晰、可解释、可扩展
- 为后续接入本地模型、微信端、数据库打底
- 积累在实际场景中怎么处理"AI 回复安全"问题的经验

## 核心链路

```
用户输入
  → SDS 评分 (ML 模型)
  → EMA 记忆平滑
  → 关键词危机检测
  → 规则风险信号扫描
  → 趋势检测 (多轮历史)
  → 统一风险评估
  → 安全策略决策
  → LLM 回复生成 (DeepSeek)
```

这条链路的关键设计是：**回复层不自己做安全判断，而是执行上层传下来的安全策略**。

## 风险评估体系

系统不只看一个分数，而是综合三类信号：

**即时信号（规则扫描）**
- 直接高危：自杀意念、自伤意念、有方法、有时间、有准备、无法保证安全、他伤风险
- 中风险辅助：绝望感、自觉负担、社交孤立、严重失眠、功能受损、濒临崩溃
- 保护因素：有支持系统、主动求助、未来牵挂、有自助方式
- 误报过滤：识别否定（"我没有想自杀"）、转述（"朋友说他想死"）、假设、过去已解决等上下文

**趋势信号（多轮历史）**
- 快速恶化：最近 3 轮 SDS 连续上升或等级跳跃
- 反复高危：近几轮中自杀/自伤信号反复出现
- 长期高位：连续多轮处于中等及以上风险
- 保护因素减少：之前的支持/求助信号近期消失

**SDS 分数**：来自 ML 模型（随机森林），EMA 平滑后的抑郁症状严重度评分

等级判定逻辑：**计划/手段/时间等直接信号优先于 SDS 分数，趋势信号阻止不合理的快速降级**。

| 信号组合 | 最终等级 |
|---|---|
| 自杀意念 + 方法 | critical |
| 方法 + 时间/准备 | critical |
| 有方法/准备/不能保证安全 | high |
| 自杀意念 | high |
| ≥3 个中风险信号 + 高 SDS | high |
| 反复高危趋势 | medium/high（不降级） |
| 长期高位趋势 | medium/high（不降级） |
| SDS 高分无其他信号 | medium |
| 所有高危信号被否定 | normal |

## 安全策略层

根据风险评估结果，生成结构化的安全策略决策，回复层执行：

| 风险等级 | 安全模式 | 回复约束 |
|---|---|---|
| normal | normal_support | 普通交流 |
| low | supportive_checkin | 温和支持，鼓励表达 |
| medium | safety_planning | 安全确认 + 现实支持引导 |
| high | crisis_intervention | 优先安全，建议热线/医疗，禁用普通疗愈话术 |
| critical | emergency_escalation | 强烈建议立即寻求紧急帮助 |

高危回复的硬约束：不做轻率安慰、不给医学诊断、不淡化风险、不承诺保密。

## API

`POST /chat/message`

响应除了原有的 `reply/risk_level/score/evidence` 外，还新增了可选字段：

```json
{
  "reply": "...",
  "risk_level": "high",
  "score": 88.0,
  "evidence": ["SDS 评分处于高区间", "命中direct_high_risk规则: suicide_ideation"],
  "safety_mode": "crisis_intervention",
  "safety_actions": ["优先表达关切和陪伴感", "明确建议联系热线"],
  "risk_signals": [
    {"name": "suicide_ideation", "source": "rule", "severity": 0.95, "confidence": 0.95}
  ],
  "assessment_version": "risk-assessment-v1",
  "policy_version": "safety-policy-v1"
}
```

`evidence` 字段已改为低敏摘要，不再暴露用户原文或内部评分细节。

## 项目结构

```text
app/
├── main.py                     # FastAPI 入口
├── api/
│   ├── routes_chat.py          # POST /chat/message
│   ├── routes_health.py        # GET /health
│   └── routes_admin.py         # 管理接口（占位）
├── core/
│   ├── config.py               # 环境变量配置
│   ├── logger.py               # 日志
│   └── safety.py               # 旧版关键词检测（保留为底层词表）
├── models/
│   ├── schemas.py              # ChatRequest/Response + RiskSignalBrief
│   ├── scoring_engine.py       # 双模型自适应 SDS 评分引擎
│   └── *.joblib                # 模型文件
├── services/
│   ├── pipeline_service.py     # 管道编排（6 步链）
│   ├── scoring_service.py      # ML 评分
│   ├── memory_service.py       # EMA 记忆 + 对话历史持久化
│   ├── crisis_service.py       # 关键词检测 + 等级映射（保留）
│   └── llm_service.py          # LLM 回复生成
├── risk/                       # 风险评估模块（新增）
│   ├── schemas.py              # RiskSignal / RiskAssessment
│   ├── rule_definitions.py     # 规则词表定义
│   ├── rule_monitor.py         # 规则扫描引擎（含误报过滤）
│   ├── trend_detector.py       # 趋势检测引擎
│   ├── risk_state_memory.py    # 风险历史存储（与对话历史分离）
│   ├── assessment_engine.py    # 综合评估引擎
│   └── audit.py                # 审计日志（JSONL）
├── safety/                     # 安全策略模块（新增）
│   ├── schemas.py              # SafetyDecision
│   └── policy_engine.py        # 策略引擎
└── prompt/                     # 心理知识库 + System Prompt 模板
    ├── knowledge.md
    ├── system_prompt.md
    ├── knowledge_loader.py
    └── references/             # 9 个专业参考模块
```

## 测试

103 个测试，覆盖 11 个测试文件：

- 规则监测（21 个）：高危/中危/保护/误报信号检测
- 风险评估引擎（16 个）：等级判定、信号组合、边界情况
- 趋势检测（20 个）：四种趋势信号 + 趋势影响评估
- 安全策略引擎（22 个）：模式映射、危机约束、结构验证
- 管道安全（17 个）：API 兼容性、安全行为场景、回复约束
- 风险状态记忆（10 个）：CRUD、窗口查询、趋势统计

```bash
pytest tests/ -q  # 103 passed
```

## 配置

通过 `.env` 文件：

| 变量 | 说明 |
|---|---|
| `API_KEY` | DeepSeek API Key |
| `BASE_URL` | DeepSeek API 地址 |
| `HOST` / `PORT` | 服务地址/端口（默认 127.0.0.1:8000） |
