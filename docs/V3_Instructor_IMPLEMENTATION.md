# V3 Instructor教学交互实现文档

**需求编号**: 需求16（完善）  
**PRD章节**: 2.1节 模型对话、2.2节 分等级提示系统  
**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

实现Instructor Agent教学交互系统，包括：
- 分等级提示系统 (L0-L4)
- 引导式教学（情感感知响应）
- 与Hint Button状态机联动
- 与Advisor指令集联动

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/algorithms/hint_generator.py` | 提示生成器 | ~450行 |
| `backend/algorithms/sentiment_analyzer.py` | 情感分析器 | ~420行 |
| `backend/agents/instructor_agent.py` | Instructor Agent核心 | ~550行 |
| `backend/api/instructor.py` | Instructor API接口 | ~350行 |

---

## 3. 架构设计

### 3.1 提示等级系统 (L0-L4)

```
┌─────────────────────────────────────────────────────────────┐
│                    提示等级定义                              │
├─────────────────────────────────────────────────────────────┤
│  L0-自主    │ 学生直接提交答案    │ 仅批改,不干预    │ 1.0  │
│  L1-方向    │ "有点思路但卡住了"  │ 解题方向提示     │ 0.8  │
│  L2-公式    │ "需要公式提醒"      │ 相关公式定理     │ 0.6  │
│  L3-步骤    │ "教教我"            │ 关键推导步骤     │ 0.4  │
│  L4-答案    │ "看答案"            │ 完整解答         │ 0.1  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 核心类设计

```python
HintGenerator              # 提示生成器
├── generate_l0_hint()     # L0: 自主解答
├── generate_l1_hint()     # L1: 解题方向
├── generate_l2_hint()     # L2: 公式提醒
├── generate_l3_hint()     # L3: 关键步骤
└── generate_l4_hint()     # L4: 完整解答

SentimentAnalyzer          # 情感分析器
├── analyze()              # 分析单条消息
├── analyze_batch()        # 批量分析
├── detect_learning_style() # 检测学习风格
└── generate_instructor_strategy() # 生成教学策略

InstructorAgent            # Instructor Agent核心
├── respond_to_hint_button_click()   # 响应Hint Button
├── respond_to_user_message()        # 响应用户消息
├── respond_to_advisor_instruction() # 响应Advisor指令
└── _apply_teaching_mode()           # 应用教学模式
```

---

## 4. 硬指标实现

### 4.1 提示等级硬指标

| 等级 | 触发条件 | Instructor行为 | Actual权重 | 实现位置 |
|-----|---------|---------------|-----------|---------|
| L0 | 直接提交答案 | 仅批改 | 1.0 | `generate_l0_hint()` |
| L1 | "有点思路但卡住了" | 解题方向提示 | 0.8 | `generate_l1_hint()` |
| L2 | "需要公式提醒" | 相关公式定理 | 0.6 | `generate_l2_hint()` |
| L3 | "教教我" | 关键推导步骤 | 0.4 | `generate_l3_hint()` |
| L4 | "看答案" | 完整解答 | 0.1 | `generate_l4_hint()` |

### 4.2 情感检测硬指标

| 用户表达 | 检测关键词 | 系统画像更新 | Instructor响应策略 | 实现位置 |
|---------|-----------|-------------|-------------------|---------|
| 困难感知 | "好难"、"太难了" | 难度感知+1 | 分解步骤 | `analyze()` |
| 信心充足 | "能克服"、"简单" | 学习风格="进取型" | 减少提示 | `analyze()` |
| 步骤困惑 | "看不懂"、"跳太快" | 需要详细解释 | 展开步骤 | `analyze()` |

### 4.3 教学模式硬指标

| 模式 | 触发条件 | Instructor行为约束 | 实现位置 |
|-----|---------|-------------------|---------|
| SCAFFOLD | P(L) < 0.4 | 分步讲解,每步确认 | `_apply_teaching_mode()` |
| CHALLENGE | P(L) > 0.8 | 仅方向提示,自主推导 | `_apply_teaching_mode()` |
| ENCOURAGE | 连续3题错误 | 情感支持,逐步引导 | `_apply_teaching_mode()` |

---

## 5. API接口

### 5.1 Hint Button点击

```http
POST /instructor/hint-button
```

**请求体：**
```json
{
  "question_id": "q001",
  "question_content": "已知等差数列...",
  "knowledge_points": ["等差数列"],
  "current_state": "initial"
}
```

**响应：**
```json
{
  "success": true,
  "content": "这道题主要考察等差数列...",
  "hint_level": 1,
  "actual_weight": 0.8,
  "next_button_text": "还需要公式支持",
  "latex_formulas": []
}
```

### 5.2 响应用户消息

```http
POST /instructor/respond
```

**请求体：**
```json
{
  "question_id": "q001",
  "question_content": "已知等差数列...",
  "knowledge_points": ["等差数列"],
  "user_message": "这道题好难，我完全没思路",
  "advisor_instruction": null
}
```

**响应：**
```json
{
  "success": true,
  "content": "🤗 **别担心**...",
  "hint_level": 2,
  "actual_weight": 0.6,
  "teaching_mode": "encourage",
  "sentiment": "difficult_perceived",
  "sentiment_confidence": 0.9
}
```

### 5.3 生成指定等级提示

```http
POST /instructor/generate-hint
```

**请求体：**
```json
{
  "level": 2,
  "question_content": "已知等差数列...",
  "knowledge_points": ["等差数列"]
}
```

### 5.4 情感分析

```http
POST /instructor/analyze-sentiment
```

**请求体：**
```json
{
  "message": "这道题好难，我完全没思路"
}
```

**响应：**
```json
{
  "success": true,
  "sentiment": "difficult_perceived",
  "confidence": 0.9,
  "keywords": ["好难", "没思路"],
  "learning_style": null,
  "suggested_strategy": "break_down_steps"
}
```

---

## 6. 验收标准

### 6.1 功能验收

- [x] L0-L4提示等级生成正确
- [x] 情感分析检测准确
- [x] Hint Button状态机联动正常
- [x] Advisor指令响应正确
- [x] 教学模式切换正常

### 6.2 测试用例

```python
# 测试1：L1方向提示
hint = generator.generate_hint(L1, question, kps)
assert "方向" in hint.content or "思路" in hint.content
assert hint.actual_weight == 0.8

# 测试2：L2公式提示
hint = generator.generate_hint(L2, question, ["等差数列"])
assert "公式" in hint.content
assert len(hint.latex_formulas) > 0

# 测试3：情感分析
result = analyzer.analyze("这道题好难")
assert result.sentiment == SentimentType.DIFFICULT_PERCEIVED
assert "好难" in result.keywords

# 测试4：教学模式
response = instructor.respond_to_advisor_instruction(
    instruction={'instruction': 'MODE_SCAFFOLD'}
)
assert response.teaching_mode == TeachingMode.SCAFFOLD
```

---

## 7. 依赖关系

### 7.1 前置依赖

- ✅ Hint Button状态机（需求16基础）
- ✅ Advisor Agent指令集（PRD 3.2）
- ✅ 公式数据库（LaTeX格式）

### 7.2 后续依赖

- ⏳ 跳过处理机制
- ⏳ 解题思路批改

---

## 8. Git提交记录

```bash
# 待提交
git add backend/algorithms/hint_generator.py
git add backend/algorithms/sentiment_analyzer.py
git add backend/agents/instructor_agent.py
git add backend/api/instructor.py
git add docs/V3_Instructor_IMPLEMENTATION.md

git commit -m "feat: Implement Instructor teaching interaction (PRD 2.1-2.2)

- Add HintGenerator with L0-L4 hint levels
- Add SentimentAnalyzer for learning state detection
- Add InstructorAgent core with teaching modes
- Add instructor API endpoints
- Support SCAFFOLD/CHALLENGE/ENCOURAGE modes
- Integrate with Hint Button state machine
- Integrate with Advisor instruction system

Closes requirement #16 (enhancement)"
```

---

## 9. 实现总结

### 9.1 完成功能

1. **提示生成器** (`hint_generator.py`)
   - L0-L4五个等级的提示生成
   - 公式数据库（LaTeX格式）
   - 引导性问题生成

2. **情感分析器** (`sentiment_analyzer.py`)
   - 困难感知检测
   - 信心充足检测
   - 步骤困惑检测
   - 学习风格识别

3. **Instructor Agent** (`instructor_agent.py`)
   - 响应Hint Button点击
   - 响应用户消息（情感感知）
   - 响应Advisor指令
   - 三种教学模式（SCAFFOLD/CHALLENGE/ENCOURAGE）

4. **API接口** (`instructor.py`)
   - Hint Button处理接口
   - 用户消息响应接口
   - 提示生成接口
   - 情感分析接口

### 9.2 技术亮点

- 严格遵循PRD硬指标实现
- 情感分析与教学策略联动
- 与Hint Button状态机无缝集成
- 支持Advisor指令控制
- 完整的LaTeX公式支持

### 9.3 后续优化方向

1. 接入LLM生成更自然的提示内容
2. 增加更多情感类型检测
3. 实现个性化提示模板
4. 添加提示效果反馈机制

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
