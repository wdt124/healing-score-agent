# Healing Score Agent

一个心理支持对话 Agent 的后端原型，核心能力：接收用户输入文本，评估风险等级，产出带安全约束的支持性回复。

## 快速开始

```bash
# 1. 安装依赖
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 配置环境（填入 API_KEY）
cp .env.example .env

# 3. 确认 ML 模型文件已随仓库位于 app/models/

# 4. 启动服务
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 发送消息
curl -X POST http://127.0.0.1:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"user_text": "最近总觉得很累", "session_id": "demo"}'
```

详细说明见 [docs/USAGE.md](docs/USAGE.md)，安全约束见 [docs/SAFETY.md](docs/SAFETY.md)。

## 项目定位

- 把"风险检测 → 安全决策 → 生成回复"这条链路做得结构清晰、可解释、可扩展
- 为后续接入本地模型、微信端、数据库打底
- 积累在实际场景中怎么处理"AI 回复安全"问题的经验

## 管道链路

```
POST /chat/message
  → scoring_step         ML 评分（双模型自适应：V1 纯文本 / V2 多模态）
  → memory_step          EMA 指数平滑 + 对话历史持久化
  → risk_assessment      规则扫描 → 分数修正 → 趋势检测 → 综合等级判定
  → safety_policy        等级→安全模式映射，产出结构化的 SafetyDecision
  → reply_step           System Prompt 组装 → LLM 调用 → 支持性回复
  → ChatResponse

shutdown → clear_data_files() → 清除 data/*.json/.jsonl（仅 dev）
```

## 风险评估体系

系统综合三类信号：

**即时信号（规则扫描）**
- 直接高危（7 条规则）：suicide_ideation、self_harm_ideation、has_method、has_time、has_preparation、cannot_stay_safe、harm_to_others
- 中风险辅助（6 条规则）：hopelessness、burdensomeness、social_isolation、severe_insomnia、functional_impairment、panic_or_breakdown
- 保护因素（4 条规则）：has_support、help_seeking、future_orientation、coping_strategy
- 误报过滤：识别否定、转述、假设、过去已解决等上下文

**趋势信号（多轮历史）**
- rapid_worsening: 最近 3 轮连续恶化或等级跳跃
- repeated_high_risk_signal: 高危/中危信号反复出现
- sustained_elevated_risk: 连续多轮 medium+
- protective_factor_drop: 保护因素近期消失

**等级判定**：计划/手段等直接信号优先于 SDS 分数，趋势信号阻止不合理快速降级。

## 安全策略层

| 风险等级 | 安全模式 | 回复约束 |
|----------|----------|----------|
| normal | normal_support | 普通交流 |
| low | supportive_checkin | 温和支持，鼓励表达 |
| medium | safety_planning | 安全确认 + 现实支持引导 |
| high | crisis_intervention | 优先安全，建议热线/医疗，禁用普通疗愈话术 |
| critical | emergency_escalation | 强烈建议立即寻求紧急帮助 |

## API

`POST /chat/message`

```json
{
  "reply": "...",
  "risk_level": "high",
  "score": 88.0,
  "evidence": ["SDS 评分处于高区间", "命中direct_high_risk规则: suicide_ideation"],
  "model_provider": "deepseek",
  "model_name": "deepseek-chat",
  "safety_mode": "crisis_intervention",
  "safety_actions": ["优先表达关切和陪伴感", "明确建议联系现实中的可信任对象或心理援助热线"],
  "risk_signals": [{"name": "suicide_ideation", "source": "rule", "severity": 0.95}]
}
```

## 项目结构

```text
app/
├── main.py                     # FastAPI 入口 + shutdown 清理
├── api/
│   ├── routes_chat.py          # POST /chat/message
│   └── routes_health.py        # GET /health
├── core/
│   ├── config.py               # 环境变量配置
│   ├── llm_client.py           # 统一 LLM 客户端管理
│   └── lifecycle.py            # 退出时 data/ 清理
├── memory/
│   └── score_smoother.py       # EMA 分数平滑器
├── models/
│   ├── schemas.py              # ChatRequest/Response
│   ├── scoring_engine.py       # 双模型自适应 SDS 评分引擎
│   └── *.joblib                # ML 模型文件
├── services/
│   ├── pipeline_service.py     # 管道编排 + 响应组装
│   ├── scoring_service.py      # scoring_step
│   ├── memory_service.py       # memory_step (EMA + ConversationMemory)
│   └── llm_service.py          # reply_step (System Prompt + LLM 调用)
├── risk/
│   ├── schemas.py              # RiskSignal / RiskAssessment
│   ├── thresholds.py           # 统一评分阈值
│   ├── rule_definitions.py     # 规则词表定义（4 类规则）
│   ├── rule_monitor.py         # 规则扫描引擎（含误报过滤）
│   ├── trend_detector.py       # 趋势检测引擎
│   ├── assessment_engine.py    # 综合评估引擎（含分数修正）
│   ├── risk_state_memory.py    # 风险历史存储
│   └── audit.py                # 审计日志（JSONL）
├── safety/
│   ├── schemas.py              # SafetyDecision
│   └── policy_engine.py        # 策略引擎
└── prompt/
    ├── knowledge.md            # 核心心理知识
    ├── system_prompt.md        # LLM System Prompt 模板
    ├── knowledge_loader.py     # 知识库加载器
    └── references/             # 9 个专业参考模块
```

## 测试

92 个测试，覆盖 8 个测试文件：

| 测试文件 | 测试数 | 覆盖内容 |
|----------|--------|----------|
| test_rule_monitor.py | 21 | 高危/中危/保护/误报信号检测 |
| test_safety_policy_engine.py | 18 | 模式映射、危机约束、结构验证 |
| test_trend_detector.py | 17 | 四种趋势信号 + 趋势影响评估 |
| test_risk_assessment_engine.py | 16 | 等级判定、信号组合、边界情况 |
| test_pipeline_safety.py | 10 | 管道集成：兼容性、安全行为、回复约束 |
| test_risk_state_memory.py | 5 | 读写、序列化、窗口查询 |
| test_api.py | 3 | HTTP 端点健康检查 |
| conftest.py | — | 共享 fixtures 和 mock factory |

```bash
pytest tests/ -q  # 92 passed
```

## 配置

通过 `.env` 文件：

| 变量 | 说明 |
|------|------|
| `API_KEY` | DeepSeek API Key |
| `BASE_URL` | API 地址 |
| `APP_ENV` | 环境：`dev`（退出清数据）/ `prod`（保留数据） |
| `LLM_MODEL` | 模型名称 |
| `LLM_PROVIDER` | 提供商标识（仅用于 API 响应展示） |
| `HOST` / `PORT` | 已加载但未接入 uvicorn，启动时需命令行指定 |

完整配置说明见 [docs/USAGE.md](docs/USAGE.md)。