# 安全约束总览

本文档汇总 Healing Score Agent 的安全边界、风险等级约束和回复规范，供开发者、协作者和审核人员参考。

运行时约束通过 `policy_engine.py` 注入 System Prompt，详见 [system_prompt.md](../app/prompt/system_prompt.md)。

---

## 1. 系统定位与边界

| 项目 | 说明 |
|------|------|
| 定位 | AI 心理支持陪伴助手，提供情绪倾听和现实资源引导 |
| 不是 | 医生、心理咨询师、诊断工具或治疗替代品 |
| 能力 | 风险检测、安全模式切换、带约束的支持性回复 |
| 局限 | 无法替代人工危机干预、无法拨打紧急电话、无法打破保密通知第三方 |

---

## 2. 双层安全机制

### 硬约束（代码强制执行）

| 机制 | 实现位置 | 行为 |
|------|----------|------|
| 关键词规则扫描 | `app/risk/rule_monitor.py` | 检测自杀/自伤/危机信号，含误报过滤 |
| 分数修正 | `app/risk/assessment_engine.py` | 规则命中时上调 SDS 分数 |
| 趋势检测 | `app/risk/trend_detector.py` | 多轮恶化阻止不合理降级 |
| 等级判定 | `app/risk/assessment_engine.py` | 输出 `normal` ~ `critical` |
| 模式映射 | `app/safety/policy_engine.py` | 等级 → 安全模式 |
| 知识模块选择 | `app/safety/policy_engine.py` | 按模式注入不同 reference 文档 |
| 审计日志 | `app/risk/audit.py` | 记录等级/模式/信号，不含用户原文 |
| 输入长度限制 | `app/models/schemas.py` | `user_text` 1–2000 字符 |
| LLM 失败降级 | `app/services/llm_service.py` | 返回通用安全回复 |

### 软约束（Prompt 引导，无输出后验过滤）

以下约束通过 System Prompt 和知识库注入，**依赖 LLM 遵守**，代码不做回复内容校验：

- 禁止医学诊断、药物建议、承诺疗效
- 回复长度和风格要求
- 危机场景必须提及热线号码
- 禁止淡化风险、轻率安慰

---

## 3. 风险等级 → 安全模式

| 风险等级 | 安全模式 | 触发场景（概要） |
|----------|----------|------------------|
| `normal` | `normal_support` | 无明显风险信号 |
| `low` | `supportive_checkin` | 轻度情绪困扰 |
| `medium` | `safety_planning` | 中度风险或持续低落 |
| `high` | `crisis_intervention` | 自杀/自伤意念或高危规则命中 |
| `critical` | `emergency_escalation` | 有具体计划、手段或即时危险 |

---

## 4. 各模式约束矩阵

### normal_support

| 维度 | 内容 |
|------|------|
| 必须行为 | 无特殊要求 |
| 禁止行为 | 无特殊限制 |
| 回复要点 | 普通支持性交流 |
| 知识模块 | 仅 `knowledge.md` 核心知识 |

### supportive_checkin

| 维度 | 内容 |
|------|------|
| 必须行为 | 表达共情与支持 |
| 禁止行为 | 淡化用户感受；急于给出建议 |
| 回复要点 | 温和支持，鼓励继续表达 |
| 知识模块 | emotion-support, meditation-scripts |

### safety_planning

| 维度 | 内容 |
|------|------|
| 必须行为 | 确认用户当前感受；确认当前是否安全；提供现实支持建议；鼓励联系身边可信任的人 |
| 禁止行为 | 轻率安慰；淡化风险；给出医学诊断 |
| 回复要点 | 加入安全确认，引导关注现实支持资源 |
| 知识模块 | emotion-support, cbt-techniques |

### crisis_intervention

| 维度 | 内容 |
|------|------|
| 必须行为 | 优先表达关切和陪伴感；明确建议联系可信任对象或心理援助热线；回复中须包含至少一个热线号码（12356 或 400-161-9995） |
| 禁止行为 | 轻率安慰；淡化风险；给出医学诊断；使用普通疗愈话术 |
| 回复要点 | 优先安全确认，明确建议寻求现实帮助，避免普通疗愈话术 |
| 知识模块 | crisis-resources, suicide-prevention |

### emergency_escalation

| 维度 | 内容 |
|------|------|
| 必须行为 | 强烈建议立即寻求紧急现实帮助；提供明确的紧急联系方式（120/110 或心理热线）；建议联系身边可信任的人陪同 |
| 禁止行为 | 做任何形式的安抚和拖延；淡化危机的紧急性；给出医学诊断 |
| 回复要点 | 强烈建议立即拨打 120/110 或心理热线，明确给出联系方式 |
| 知识模块 | crisis-resources, suicide-prevention |

---

## 5. 全局禁止项

无论风险等级，AI 回复中**绝对禁止**：

| 禁止项 | 说明 |
|--------|------|
| 医学诊断 | 不对用户做出抑郁症、焦虑症等正式诊断 |
| 药物建议 | 不推荐、不评价具体药物 |
| 承诺疗效 | 不承诺"一定能好"、"保证治愈" |
| 替代专业治疗 | 不说"不需要看医生" |
| 淡化危机 | 不对自杀/自伤风险说"没什么大不了" |
| 激惹性语言 | 不对自杀意念争辩或挑衅 |
| 虚假专业身份 | 不自称医生、咨询师或治疗师 |

---

## 6. 危机场景回复规范

当 `risk_level` 为 `high` 或 `critical` 时：

### 必须包含

1. 表达关切和陪伴（"我很担心你"、"我在这儿陪你"）
2. 至少一个可操作的求助渠道：
   - 心理热线：**12356**（全国统一，24 小时）
   - 希望 24 热线：**400-161-9995**
   - 紧急情况：**120**（急救）/ **110**（报警）
3. 建议联系身边可信任的人

### 禁止使用

- "没事的"、"想开点"、"一切都会好的"等轻率安慰
- 普通正念、呼吸练习等疗愈话术（此时优先安全）
- 长篇心理分析或说教

### 回复长度

- `high`：60–100 字，简洁但信息完整
- `critical`：60–100 字，以紧急求助引导为主

---

## 7. 与代码文件映射

| 文档/配置 | 文件路径 | 作用 |
|-----------|----------|------|
| 安全模式映射 | `app/safety/policy_engine.py` | `LEVEL_TO_MODE` + `MODE_POLICIES` |
| 规则词表 | `app/risk/rule_definitions.py` | 17 条关键词规则 |
| 规则扫描 | `app/risk/rule_monitor.py` | 扫描 + 误报过滤 |
| 综合评估 | `app/risk/assessment_engine.py` | 等级判定 |
| System Prompt | `app/prompt/system_prompt.md` | 回复生成模板 |
| 核心知识 | `app/prompt/knowledge.md` | 所有模式共享 |
| 危机资源 | `app/prompt/references/crisis-resources.md` | high/critical 模式注入 |
| 自杀预防 | `app/prompt/references/suicide-prevention.md` | high/critical 模式注入 |
| 伦理边界 | `app/prompt/references/ethics-guidelines.md` | AI 专用伦理限制 |
| Prompt 组装 | `app/services/llm_service.py` | 注入安全决策到 System Prompt |

---

## 8. 已知局限

1. **无输出后验过滤**：LLM 可能违反 Prompt 约束，需人工抽检
2. **无人工升级通道**：无法自动通知家属或紧急服务
3. **保护因素未降级**：检测到保护因素不会降低风险等级
4. **保密例外未自动化**：高风险时无法在系统中自动打破保密

---

## 9. 相关文档

- [USAGE.md](./USAGE.md) — 安装与 API 调用
- [README.md](../README.md) — 架构与管道说明
