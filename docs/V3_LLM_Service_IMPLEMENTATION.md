# V3 LLM服务实现文档

**需求编号**: 需求16, 18, 24  
**需求名称**: 
- 需求16: 要求大模型根据hint_level参数控制输出颗粒度
- 需求18: 当学生陷入困境时，讲师Agent主动介入下发提示
- 需求24: 规范大模型生成推荐理由的输入上下文

**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

实现统一的大模型服务，支持：
1. **L0-L4提示生成**: 根据等级严格控制输出颗粒度
2. **情感感知响应**: 根据学生情感状态生成支持性提示
3. **推荐理由生成**: 基于上下文变量生成个性化推荐理由

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/services/llm_service.py` | LLM服务核心 | ~450行 |
| `backend/api/llm.py` | LLM API接口 | ~300行 |

---

## 3. 核心功能实现

### 3.1 需求16: L0-L4提示等级约束（硬指标）

| 等级 | 描述 | 约束 | 字数限制 |
|-----|------|------|---------|
| L0 | 仅批改 | 仅提供批改结果，不给出任何提示 | 100字 |
| L1 | 方向提示 | 只输出方向/方法/反问，绝不包含公式 | 200字 |
| L2 | 公式提醒 | 输出公式/定理，绝不包含计算步骤 | 300字 |
| L3 | 关键步骤 | 代入数值，输出第一步，绝不给答案 | 400字 |
| L4 | 完整解答 | 包含所有中间推导的完整解答 | 800字 |

### 3.2 需求18: 情感感知响应

| 情感类型 | 响应策略 |
|---------|---------|
| difficult_perceived | 情感支持→分解难度→L1提示→强调错误是学习机会 |
| confident | 肯定信心→鼓励挑战→减少提示→提醒注意细节 |
| confused | 承认复杂性→详细解释→使用类比→确认理解 |
| frustrated | 情感安抚→强调发现薄弱点→降低难度→额外鼓励 |

### 3.3 需求24: 推荐理由生成

**必须注入的变量：**
- weak_knowledge_points: 薄弱点名称
- days_since_last_error: 距上次做错天数
- difficulty_level: 题目难度评级

**约束：**
- 采用"导师/教练"口吻
- 字数严格控制在30字以内

---

## 4. API接口

### 4.1 生成提示

```http
POST /llm/generate-hint
```

**请求体：**
```json
{
  "hint_level": 1,
  "question_content": "已知等差数列{a_n}中，a_3 = 5，a_7 = 13，求通项公式",
  "knowledge_points": ["等差数列", "通项公式"],
  "student_message": "这道题有点难，我没思路"
}
```

**响应：**
```json
{
  "success": true,
  "hint_level": 1,
  "content": "这道题考察等差数列的基本性质。试着回忆一下，已知两项如何确定首项和公差？",
  "prompt_tokens": 150,
  "completion_tokens": 80,
  "total_tokens": 230,
  "model": "gpt-4",
  "cached": false
}
```

### 4.2 情感响应

```http
POST /llm/emotional-response
```

**请求体：**
```json
{
  "sentiment": "difficult_perceived",
  "confidence": 0.9,
  "question_content": "已知等差数列...",
  "knowledge_points": ["等差数列"]
}
```

### 4.3 推荐理由

```http
POST /llm/recommendation-reason
```

**请求体：**
```json
{
  "weak_knowledge_points": ["等比数列"],
  "question_difficulty": 0.6,
  "user_theta": 0.5,
  "days_since_last_error": 3,
  "question_source": "review"
}
```

**响应：**
```json
{
  "success": true,
  "reason": "距离上次做错放缩法已过3天，测测肌肉记忆还在不？",
  "prompt_tokens": 120,
  "completion_tokens": 25,
  "total_tokens": 145,
  "model": "gpt-4"
}
```

### 4.4 获取提示约束

```http
GET /llm/hint-constraints/1
```

**响应：**
```json
{
  "success": true,
  "constraints": {
    "level": 1,
    "description": "给出解题方向提示",
    "constraints": [
      "只输出解题方向、方法名称或苏格拉底式反问",
      "绝不包含具体公式",
      "绝不包含计算步骤",
      "绝不透露答案"
    ],
    "max_length": 200
  }
}
```

---

## 5. 支持的LLM提供商

| 提供商 | 模型 | 配置方式 |
|-------|------|---------|
| OpenAI | gpt-4 | OPENAI_API_KEY |
| Claude | claude-3-sonnet | ANTHROPIC_API_KEY |
| DashScope | qwen-max | DASHSCOPE_API_KEY |
| SiliconFlow | DeepSeek-V2.5 | SILICONFLOW_API_KEY |

---

## 6. 缓存机制

- **缓存键**: MD5(prompt)
- **缓存时长**: 1小时
- **最大缓存数**: 1000条
- **自动清理**: 过期缓存自动清理

---

## 7. 验收标准

### 7.1 需求16验收

- [x] L1绝不包含公式
- [x] L2绝不包含计算步骤
- [x] L3绝不给出最终答案
- [x] L4包含完整解答
- [x] 字数限制严格执行

### 7.2 需求18验收

- [x] 困难感知→情感支持+L1提示
- [x] 信心充足→鼓励挑战+减少提示
- [x] 步骤困惑→详细解释+类比
- [x] 挫败感→安抚+降低难度

### 7.3 需求24验收

- [x] 注入薄弱知识点变量
- [x] 注入距上次做错天数
- [x] 注入题目难度评级
- [x] 30字以内限制
- [x] 导师/教练口吻

---

## 8. Git提交记录

```bash
git add backend/services/llm_service.py
git add backend/api/llm.py
git add docs/V3_LLM_Service_IMPLEMENTATION.md

git commit -m "feat: Implement LLM service with hint level control (Req 16,18,24)

- Add unified LLM service supporting OpenAI/Claude/DashScope/SiliconFlow
- Add L0-L4 hint generation with strict output constraints
- Add emotional response generation based on sentiment analysis
- Add recommendation reason generation with context variables
- Add response caching mechanism
- Add LLM API endpoints

Closes requirements #16, #18, #24"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
