# Healing Score Agent 使用说明

本文档介绍如何在本地安装、配置、启动和调用 Healing Score Agent 后端服务。

更完整的架构说明见 [README.md](../README.md)，安全约束见 [SAFETY.md](./SAFETY.md)。

---

## 1. 环境要求

- **Python**：3.10 或更高版本（推荐 3.10 / 3.11）
- **操作系统**：Linux / macOS / Windows
- **网络**：调用 LLM API 时需要可访问 `BASE_URL` 对应的服务端点

---

## 2. 安装

```bash
cd healing-score-agent

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

---

## 3. ML 评分模型

评分模块依赖两个本地模型文件，当前已随仓库提交，默认位于：

```
app/models/eatd_rf_model_v1.joblib
app/models/eatd_multimodal_rf_model_v2.joblib
```

若模型文件缺失，调用 `POST /chat/message` 时会在 `scoring_step` 阶段抛出 `FileNotFoundError`；请确认仓库已完整 clone/pull，且以下文件未被误删。

| 模型 | 用途 |
|------|------|
| `eatd_rf_model_v1.joblib` | V1 纯文本 SDS 评分 |
| `eatd_multimodal_rf_model_v2.joblib` | V2 多模态评分（需提供 `audio_path`） |

---

## 4. 环境配置

复制配置模板并填入实际值：

```bash
cp .env.example .env
```

### 推荐配置（DeepSeek 示例）

```env
APP_ENV=dev
HOST=127.0.0.1
PORT=8000

LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
API_KEY=sk-your-api-key-here
BASE_URL=https://api.deepseek.com/v1
```

### 环境变量说明

| 变量 | 是否生效 | 说明 |
|------|----------|------|
| `APP_ENV` | 是 | `dev` 时服务关闭会清理 `data/*.json` 和 `data/*.jsonl`；非 `dev` 则保留 |
| `API_KEY` | 是 | OpenAI 兼容 API 密钥 |
| `BASE_URL` | 是 | OpenAI 兼容 API 地址 |
| `LLM_MODEL` | 是 | 模型名称，用于评分特征提取和回复生成 |
| `LLM_PROVIDER` | 是 | 仅用于 API 响应中的 `model_provider` 字段展示 |
| `HOST` / `PORT` | 否 | 已加载到配置，但启动命令需手动指定 `--host` / `--port` |
| `LOG_LEVEL` | 否 | 当前未接入统一日志模块 |
| `OLLAMA_BASE_URL` | 否 | 当前未接入，LLM 统一走 OpenAI 兼容接口 |
| `DATABASE_URL` | 否 | 当前未接入，持久化使用 `data/` 目录下的 JSON 文件 |

---

## 5. 启动服务

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

启动后可访问：

| 地址 | 说明 |
|------|------|
| `http://127.0.0.1:8000/` | 根路径，返回运行状态 |
| `http://127.0.0.1:8000/health` | 健康检查 |
| `http://127.0.0.1:8000/docs` | FastAPI 自动生成的 Swagger 文档 |

---

## 6. API 调用

### 健康检查

```bash
curl http://127.0.0.1:8000/health
```

响应示例：

```json
{"status": "ok"}
```

### 发送聊天消息

```bash
curl -X POST http://127.0.0.1:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "user_text": "最近总觉得很累，什么都提不起劲",
    "session_id": "demo-session-001"
  }'
```

### 请求字段（`ChatRequest`）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_text` | string | 是 | 用户输入文本，1–2000 字符 |
| `session_id` | string | 否 | 会话 ID，用于多轮对话；默认 `"default"` |
| `audio_path` | string | 否 | 本地音频文件路径，提供时触发 V2 多模态评分 |

### 响应字段（`ChatResponse`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `reply` | string | 支持性回复文本 |
| `risk_level` | string | `normal` / `low` / `medium` / `high` / `critical` |
| `score` | float | EMA 平滑后的持久化 SDS 分数 |
| `evidence` | string[] | 低敏感度判断依据摘要（不含用户原文） |
| `model_provider` | string | LLM 提供商标识 |
| `model_name` | string | 使用的模型名称 |
| `safety_mode` | string? | 安全模式，如 `crisis_intervention` |
| `safety_actions` | string[]? | 当前模式要求的必须行为 |
| `risk_signals` | object[]? | 精简风险信号 `{name, source, severity}` |

响应示例：

```json
{
  "reply": "听起来你已经撑了挺久了，有时候不是不想努力，而是真的有点没力气了。",
  "risk_level": "low",
  "score": 42.5,
  "evidence": ["SDS 评分处于低区间"],
  "model_provider": "deepseek",
  "model_name": "deepseek-chat",
  "safety_mode": "supportive_checkin",
  "safety_actions": ["表达共情与支持"],
  "risk_signals": []
}
```

---

## 7. 多轮对话

同一 `session_id` 下的对话历史会持久化到 `data/conversation_history.json`，并在后续请求中注入 LLM 上下文。

```bash
# 第一轮
curl -X POST http://127.0.0.1:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"user_text": "最近睡不好", "session_id": "user-42"}'

# 第二轮（同一 session）
curl -X POST http://127.0.0.1:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"user_text": "已经持续两周了", "session_id": "user-42"}'
```

风险历史单独存储在 `data/risk_history.json`，审计日志写入 `data/risk_audit.jsonl`。

---

## 8. 多模态评分（可选）

在请求中提供本地音频路径可触发 V2 多模态模型：

```bash
curl -X POST http://127.0.0.1:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "user_text": "最近情绪很低落",
    "session_id": "audio-demo",
    "audio_path": "/path/to/sample.wav"
  }'
```

音频文件需为服务端可读取的本地路径，格式需被 `librosa` 支持。

---

## 9. 运行测试

```bash
pytest tests/ -q
```

测试覆盖规则扫描、风险评估、安全策略、管道集成和 API 端点，不依赖真实 LLM 调用（使用 mock）。

---

## 10. 常见问题

### 模型文件找不到

```
FileNotFoundError: 找不到模型文件，请确保 .joblib 文件在当前目录下！
```

**解决**：正常情况下仓库已包含这两个文件；若本地缺失，请重新拉取仓库，或确认 `app/models/` 中存在 `eatd_rf_model_v1.joblib` 和 `eatd_multimodal_rf_model_v2.joblib`。

### LLM 调用失败

若 API Key 无效或网络不通，系统会返回安全降级回复：

> 我听到了你的分享，感谢你的信任。如果你感到困扰，建议联系身边可信任的人或专业心理援助资源。

**解决**：检查 `.env` 中的 `API_KEY` 和 `BASE_URL`，确认账户余额和网络连通性。

### 服务关闭后数据消失

`APP_ENV=dev` 时，服务 shutdown 会清理 `data/` 下的 JSON/JSONL 文件。生产环境请设置 `APP_ENV=prod`。

### HOST/PORT 环境变量不生效

当前版本需通过 uvicorn 命令行参数指定绑定地址，例如 `--host 0.0.0.0 --port 8080`。

---

## 11. 相关文档

- [README.md](../README.md) — 架构与管道说明
- [SAFETY.md](./SAFETY.md) — 安全约束总览
- [UPDATE_SUMMARY.md](./UPDATE_SUMMARY.md) — 近期文档变更汇总
