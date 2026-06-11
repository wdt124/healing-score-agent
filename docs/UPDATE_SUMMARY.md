# 文档与 Prompt 优化变更汇总

**日期**：2026-06-11  
**范围**：使用说明、安全约束文档、System Prompt 及相关知识库文案  
**未改动**：管道逻辑、API Schema、测试结构、风险规则代码

---

## 变更文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `docs/USAGE.md` | 完整使用说明 |
| 新增 | `docs/SAFETY.md` | 安全约束总览 |
| 新增 | `docs/UPDATE_SUMMARY.md` | 本变更汇总 |
| 修改 | `README.md` | 快速开始 + 修正过时描述 |
| 修改 | `app/prompt/system_prompt.md` | 重写 System Prompt |
| 修改 | `app/prompt/knowledge.md` | 精简并强化安全约束 |
| 修改 | `app/prompt/references/crisis-resources.md` | 压缩热线表，聚焦危机脚本 |
| 修改 | `app/prompt/references/ethics-guidelines.md` | 重写为 AI 专用伦理边界 |
| 修改 | `app/safety/policy_engine.py` | 同步 MODE_POLICIES 约束文案 |

---

## 各文件改动摘要

### `docs/USAGE.md`（新增）

- 覆盖环境要求、安装、ML 模型获取、`.env` 配置、启动命令
- 提供 `curl` 健康检查和聊天 API 示例
- 说明 `session_id` 多轮对话、`audio_path` 多模态用法
- 列出环境变量实际生效情况（标注 `HOST`/`PORT`/`DATABASE_URL` 等未接入项）
- 常见问题：模型缺失、LLM 降级、dev 模式数据清理

### `README.md`（修改）

- 新增「快速开始」：3 步安装 + 2 条 curl 示例
- 链接到 `docs/USAGE.md` 和 `docs/SAFETY.md`
- 修正 API 响应示例（移除不存在的 `assessment_version`/`policy_version`，补充 `model_provider`/`model_name`）
- 修正项目结构（移除不存在的 `routes_admin.py`、`logger.py`）
- 更新配置表（`APP_ENV` 值、`LLM_PROVIDER` 说明）

### `docs/SAFETY.md`（新增）

- 系统定位与能力边界
- 硬约束 vs 软约束双层机制说明
- 5 级风险 → 5 种安全模式对照表
- 各模式必须/禁止/回复要点矩阵
- 全局禁止项和危机场景回复规范
- 与代码文件的映射表和已知局限

### `app/prompt/system_prompt.md`（重写）

- 修正错字：「题海专业治疗」→「替代专业治疗」
- 新增优先级规则：`extra_instruction` > 全局约束 > 按等级约束 > 知识库
- 删除固定 50–80 字全局限制，改为按 `risk_level` 分段（normal/low 50–80，medium 80–120，high/critical 60–100）
- 新增 high/critical 危机回复示例（含热线号码和紧急求助引导）
- 重组为 Role → Context → Priority → Style → Constraints → Risk-Level → Examples

### `app/prompt/knowledge.md`（优化）

- PHQ-9 空节标注为「系统未使用」
- 药物表格和疗法证据表改为「仅供背景参考，禁止在回复中引用」
- 删除与 crisis-resources 重复的大段热线列表
- 强化禁止/必须表：新增「淡化危机」「替代专业治疗」等条目

### `app/prompt/references/crisis-resources.md`（优化）

- 保留全国核心热线 + 120/110 紧急号码
- 压缩 12 个省市和港台热线表为一句查询提示
- 删除就医指南、在线平台、跟进时间表等非核心段落
- 保留危机六步法、三问评估、对话脚本、安全计划要点、干预禁区

### `app/prompt/references/ethics-guidelines.md`（重写）

- 从 450 行通用伦理守则精简为 AI 专用伦理边界（约 120 行）
- 聚焦：能力边界、保密例外引导义务、危机关怀、回复质量要求
- 删除双重关系、礼物馈赠、记录保存等与 AI 无关的章节
- 新增伦理决策速查优先级

### `app/safety/policy_engine.py`（文案同步）

- `safety_planning`：新增「确认用户当前是否安全」必须行为
- `crisis_intervention`：新增「回复中须包含至少一个热线号码」必须行为
- `emergency_escalation`：新增「建议联系身边可信任的人陪同」和 120/110 联系方式
- 所有 `response_constraints` 与 `docs/SAFETY.md` 对齐

---

## 三处对齐关系

```
docs/SAFETY.md（人类可读总览）
    ↓ 对齐
app/safety/policy_engine.py（运行时策略注入）
    ↓ 注入 extra_instruction
app/prompt/system_prompt.md（LLM 回复模板）
    ↑ 参考
app/prompt/knowledge.md + references/（知识库内容）
```

- **USAGE** 面向操作者：如何安装、配置、调用 API
- **SAFETY** 面向审核者：约束矩阵、禁止项、危机规范
- **system_prompt** 面向 LLM：优先级、按等级约束、示例话术

---

## 验证结果

```bash
# 已通过（81 个）
pytest tests/test_safety_policy_engine.py tests/test_rule_monitor.py \
       tests/test_trend_detector.py tests/test_risk_state_memory.py \
       tests/test_risk_assessment_engine.py tests/test_api.py -q
# 81 passed

# 未通过（预存问题，与本次改动无关）
pytest tests/test_pipeline_safety.py -q
# ModuleNotFoundError: No module named 'tests.conftest'
```

安全策略相关 18 个测试全部通过，policy_engine 文案变更未破坏现有断言。

### 建议手动验证

```bash
# 启动服务后测试 medium 风险
curl -X POST http://127.0.0.1:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"user_text": "最近每天都想哭，感觉撑不下去了", "session_id": "safety-test"}'

# 观察响应中 safety_mode、safety_actions 和 reply 是否含安全确认
```

---

## 未改动范围

- `app/services/pipeline_service.py` — 管道编排逻辑
- `app/risk/` — 规则扫描、趋势检测、等级判定
- `app/models/schemas.py` — API 请求/响应结构
- `app/services/llm_service.py` — Prompt 组装逻辑（占位符未变）
- 所有测试文件
