# Healing Score Agent

一个用于"疗愈对话 + 风险评分"的后端原型项目。

## 1. 项目简介

本项目用于从 0 开始实践一个简单的心理支持对话 Agent 原型，目标是逐步完成这样一条基础链路：

**用户输入文本 -> 风险评分 -> 支持性回复 -> 后续扩展到本地 LLM / 微信接入 / 数据存储**

当前版本重点不在"临床可用"，而在于：

- 熟悉 Python 后端项目搭建
- 熟悉 Git 和 GitHub 的基本协作流程
- 学习最小可运行 Agent / pipeline 的组织方式
- 为后续接入本地模型、评分模块和微信消息链路做准备

## 2. 当前已实现功能

- 使用 FastAPI 启动本地后端服务
- 提供健康检查接口：`GET /health`
- 提供聊天接口：`POST /chat/message`
- 基于 ML 模型的自适应抑郁风险评分（`UnifiedDepressionEngine`）
- 基于 EMA 的对话记忆分数平滑（`memory_service`，a=0.85 b=0.15）
- 基于关键词的危机检测与分数修正（`crisis_service`）
- 根据风险等级调用 Ollama 生成不同风格的支持性回复
- 注入心理健康领域知识库作为 LLM System Prompt（`system_prompts/`）

## 3. 系统架构

```
用户输入 (文本 + 可选音频 + session_id)
       │
       ▼
┌──────────────────────────────────────────────────┐
│              Pipeline Service                     │
│        (LangChain LCEL chain)                     │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │  1. scoring_step (scoring_service)           │ │
│  │  ┌───────────────────────────────────────┐  │ │
│  │  │  UnifiedDepressionEngine              │  │ │
│  │  │                                        │  │ │
│  │  │  V1: 纯文本 RF 模型 (8维Qwen特征)     │  │ │
│  │  │  V2: 多模态 RF 模型 (8维文本+17维音频) │  │ │
│  │  └───────────────────────────────────────┘  │ │
│  │              │                               │ │
│  │              ▼                               │ │
│  │  predicted_sds_score / risk_level(中文)      │ │
│  └─────────────────────────────────────────────┘ │
│              │                                    │
│              ▼                                    │
│  ┌─────────────────────────────────────────────┐ │
│  │  2. memory_step (memory_service)             │ │
│  │                                              │ │
│  │  EMA 平滑:                                   │ │
│  │  首轮: persistent_score = instant_score      │ │
│  │  后续: persistent_score = 0.85×旧 + 0.15×新  │ │
│  └─────────────────────────────────────────────┘ │
│              │                                    │
│              ▼                                    │
│  ┌─────────────────────────────────────────────┐ │
│  │  3. crisis_step (crisis_service)             │ │
│  │                                              │ │
│  │  关键词安全检测:                              │ │
│  │  高危 (不想活/自杀/想死等) → score = 95.0    │ │
│  │  中危 (失眠/绝望/撑不下去等)                  │ │
│  │    & score < 60 → score = 60.0               │ │
│  │                                              │ │
│  │  persistent_score → risk_level 映射:          │ │
│  │  ≥73→high  63-72→medium                      │ │
│  │  53-62→low  <53→normal                       │ │
│  └─────────────────────────────────────────────┘ │
│              │                                    │
│              ▼                                    │
│  ┌─────────────────────────────────────────────┐ │
│  │  4. reply_step (LLM Service / Ollama)        │ │
│  │                                              │ │
│  │  根据 risk_level 生成不同风格的回复:          │ │
│  │  high    → 危机干预 + 求助引导               │ │
│  │  medium  → 共情支持 + CBT 技术               │ │
│  │  low     → 温和开放式回应                     │ │
│  │  normal  → 正常交流                           │ │
│  │                                              │ │
│  │  注入知识库 System Prompt                     │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
       │
       ▼
   ChatResponse
   (reply, risk_level, score, evidence, model_provider, model_name)
```

## 4. 项目结构

```text
healing-score-agent/
├── app/
│   ├── main.py                     # FastAPI 应用入口
│   ├── api/
│   │   ├── routes_chat.py          # POST /chat/message
│   │   ├── routes_health.py        # GET /health
│   │   └── routes_admin.py         # 管理接口（空占位）
│   ├── core/
│   │   ├── config.py               # 配置管理（环境变量 + pydantic）
│   │   ├── logger.py               # 日志
│   │   └── safety.py               # 高危/中危关键词检测
│   ├── models/
│   │   ├── schemas.py              # Pydantic 请求/响应模型
│   │   ├── scoring_engine.py       # 双模型自适应打分引擎（UnifiedDepressionEngine）
│   │   └── database.py             # SQLAlchemy 数据库模型（空占位）
│   ├── services/
│   │   ├── pipeline_service.py     # LangChain LCEL 流程编排（scoring→memory→crisis→reply）
│   │   ├── scoring_service.py      # ML 评分引擎封装（纯评分，不含安全检测）
│   │   ├── memory_service.py       # EMA 对话记忆平滑（persistent_score）
│   │   ├── crisis_service.py       # 关键词安全检测 + risk_level 映射
│   │   └── llm_service.py          # Ollama LLM 回复生成（含知识库注入）
│   ├── system_prompts/
│   │   ├── SKILL.md                # 心理健康助手角色定义（YAML frontmatter + Markdown）
│   │   ├── skill_loader.py         # 知识库加载器（KnowledgeBase）
│   │   ├── loader_test.py          # skill_loader 测试
│   │   └── references/             # 可注入的专业参考模块
│   │       ├── cbt-techniques.md
│   │       ├── crisis-resources.md
│   │       ├── diagnostic-criteria.md
│   │       ├── emotion-support.md
│   │       ├── ethics-guidelines.md
│   │       ├── meditation-scripts.md
│   │       ├── psychiatric-fundamentals.md
│   │       ├── suicide-prevention.md
│   │       └── therapy-modalities.md
│   ├── repos/
│   │   └── conversation_repo.py    # 对话数据访问层（空占位）
│   └── utils/
│       ├── text_clean.py           # 文本清洗（空占位）
│       └── json_parser.py          # LLM 输出 JSON 解析（空占位）
├── tests/
│   ├── conftest.py                 # 测试配置
│   ├── test_api.py                 # API 接口测试
│   ├── test_scoring.py             # 评分模块测试
│   └── test_pipeline.py            # Pipeline 集成测试
├── scripts/                        # 脚本（均为空占位）
│   ├── init_db.py
│   ├── demo_client.py
│   └── run_local.sh
├── docs/                           # 文档（均为空占位）
│   ├── api_spec.md
│   ├── architecture.md
│   ├── deployment.md
│   └── roadmap.md
├── .env.example
└── requirements.txt
```

## 5. 评分系统

### 5.1 Pipeline 评分链路

1. **ML 评分**（`scoring_service`）：`UnifiedDepressionEngine` 提取文本/音频特征，输出 `predicted_sds_score`（instant_score）
2. **EMA 记忆平滑**（`memory_service`）：将 instant_score 与历史 persistent_score 加权融合，平滑单次波动
3. **危机检测**（`crisis_service`）：
   - 高危关键词（不想活/自杀/想死等）→ 强制 persistent_score = 95.0
   - 中危关键词（失眠/绝望/撑不下去等）且 score < 60 → 上浮至 60.0
   - 根据最终 persistent_score 映射 `risk_level`（high/medium/low/normal）

### 5.2 双模型自适应路由

| 模型 | 输入 | 特征维度 | 路由条件 |
|------|------|----------|----------|
| V1 (纯文本) | 仅文本 | 8维语义特征（Qwen dashscope API 提取） | 仅传入文本 |
| V2 (多模态) | 文本 + 音频 | 8维文本 + 17维声学特征（librosa 提取） | 传入音频路径 |

文本 8 维特征：anhedonia / depressed / sleep / fatigue / appetite / guilt / concentrate / movement（0-3 分制）

音频 17 维特征：基频均值/标准差 + 能量均值/标准差 + MFCC 1-13 均值

### 5.3 风险等级划分

| SDS 分数 | 风险等级 |
|-----------|----------|
| ≥ 73 | high (重度) |
| 63-72 | medium (中度) |
| 53-62 | low (轻度) |
| < 53 | normal (正常) |

## 6. 配置

通过 `.env` 文件或环境变量配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_ENV` | `dev` | 运行环境 |
| `HOST` | `127.0.0.1` | 服务地址 |
| `PORT` | `8000` | 服务端口 |
| `DATABASE_URL` | `sqlite:///./data/app.db` | 数据库连接 |
| `LLM_PROVIDER` | `ollama` | LLM 提供商 |
| `LLM_MODEL` | `qwen2.5:1.5b` | LLM 模型名 |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 服务地址 |
| `DASHSCOPE_API_KEY` | (无) | 阿里云 DashScope API Key（Qwen 特征提取） |
| `LOG_LEVEL` | `INFO` | 日志级别 |
