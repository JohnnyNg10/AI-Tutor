# V3 计算失误处理与Session管理实现文档

**需求编号**: 需求17, 需求27  
**需求名称**: 
- 需求17: 复用V2的错误诊断能力，避免在"纯计算失误"时错误扣除学生的Actual权重
- 需求27: 在Redis中维护当前Session的临时状态

**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

实现两个核心功能：
1. **计算失误识别**: 区分纯计算失误vs逻辑/公式错误，保护Actual权重
2. **Session管理**: 维护Agent对话的临时状态，支持多轮对话

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/algorithms/calculation_error_handler.py` | 计算失误处理器 | ~350行 |
| `backend/services/session_service.py` | Session服务 | ~400行 |
| `backend/api/calculation_error.py` | 计算失误API | ~250行 |
| `backend/api/session.py` | Session API | ~350行 |

---

## 3. 计算失误处理（需求17）

### 3.1 错误类型分类

| 错误类型 | 描述 | 权重保护 |
|---------|------|---------|
| CALCULATION_ERROR | 纯计算失误，思路和方法正确 | ✅ 保护 |
| LOGIC_ERROR | 逻辑错误，解题思路存在问题 | ❌ 不保护 |
| FORMULA_ERROR | 公式错误，公式记忆或应用不当 | ❌ 不保护 |
| CONCEPT_ERROR | 概念错误，对知识点的理解有误 | ❌ 不保护 |
| UNKNOWN_ERROR | 错误类型不明确 | ❌ 不保护 |

### 3.2 权重保护机制

```python
# 纯计算失误时，不应用hint惩罚
if is_calculation_error and confidence > 0.7:
    effective_hint_penalty = 0.0  # 完全保护
    protection_applied = True
else:
    effective_hint_penalty = hint_penalty  # 正常扣权重
    protection_applied = False
```

### 3.3 轻提示生成

纯计算失误时的轻提示示例：
- "你的思路完全正确，但仔细检查一下计算过程哦！"
- "方法是对的，再检查一下数值计算是否有小错误？"
- "解题方向正确，注意一下计算细节！"

---

## 4. Session管理（需求27）

### 4.1 Redis数据结构

**Session Hash:**
```
Key: ai:tutor:session:{session_id}
Fields:
  - session_id: Session ID
  - user_id: 用户ID
  - question_id: 题目ID
  - hint_level: 当前提示等级
  - conversation_summary: 对话摘要
  - last_message: 最后消息
  - message_count: 消息计数
  - created_at: 创建时间
  - updated_at: 更新时间
  - metadata: 元数据（JSON）
TTL: 7200秒（2小时）
```

**用户Session列表 (ZSet):**
```
Key: ai:tutor:user-sessions:{user_id}
Score: timestamp
Member: session_id
```

### 4.2 Session生命周期

```
创建Session
    ↓
活跃状态（2小时TTL）
    ↓
用户交互 → 更新状态 → 刷新TTL
    ↓
过期自动删除 / 手动删除
```

---

## 5. API接口

### 5.1 计算失误处理API

#### 诊断错误
```http
POST /calculation-error/diagnose
```

**请求体：**
```json
{
  "student_answer": "10",
  "correct_answer": "12",
  "solution_steps": [],
  "error_analysis": "学生在最后一步计算时出现符号错误"
}
```

**响应：**
```json
{
  "success": true,
  "error_type": "calculation_error",
  "is_calculation_error": true,
  "confidence": 0.85,
  "description": "纯计算失误，思路和方法正确",
  "suggested_hint": "你的思路完全正确，但仔细检查一下计算过程哦！",
  "should_preserve_weight": true
}
```

#### 计算受保护的分数
```http
POST /calculation-error/calculate-score
```

**响应（保护生效）：**
```json
{
  "success": true,
  "final_score": 1.0,
  "base_score": 1.0,
  "hint_penalty": 0.4,
  "effective_hint_penalty": 0.0,
  "protection_applied": true,
  "protection_reason": "检测到纯计算失误，保护Actual权重"
}
```

### 5.2 Session管理API

#### 创建Session
```http
POST /session/create
```

**请求体：**
```json
{
  "question_id": "q001"
}
```

#### 获取Session状态
```http
GET /session/{session_id}
```

**响应：**
```json
{
  "success": true,
  "session_id": "1_q001_1234567890",
  "user_id": 1,
  "question_id": "q001",
  "hint_level": 2,
  "conversation_summary": "user: 这道题怎么做？\nassistant: 让我来帮你分析...",
  "last_message": "让我来帮你分析...",
  "message_count": 2,
  "created_at": "2024-01-01T12:00:00",
  "updated_at": "2024-01-01T12:05:00"
}
```

#### 添加消息
```http
POST /session/{session_id}/message
```

**请求体：**
```json
{
  "role": "user",
  "message": "我明白了，谢谢！"
}
```

#### 获取对话上下文
```http
GET /session/{session_id}/context?max_messages=5
```

---

## 6. 硬指标实现

### 6.1 计算失误检测

| 指标 | 值 | 实现位置 |
|-----|-----|---------|
| 置信度阈值 | 0.7 | `is_calculation_error()` |
| 保护条件 | 纯计算失误 + 置信度>0.7 | `calculate_actual_score_with_protection()` |
| 惩罚系数 | 0.0（完全保护） | `calculate_actual_score_with_protection()` |

### 6.2 Session管理

| 指标 | 值 | 实现位置 |
|-----|-----|---------|
| Session TTL | 7200秒（2小时） | `SESSION_TTL` |
| 对话摘要长度限制 | 500字符 | `add_message_to_summary()` |
| 上下文消息数 | 默认5条 | `get_conversation_context()` |

---

## 7. 验收标准

### 7.1 需求17验收

- [x] 错误类型分类（计算/逻辑/公式/概念）
- [x] 纯计算失误检测（关键词匹配）
- [x] 权重保护机制（不降低Actual Score）
- [x] 轻提示生成（不触发L1-L4降权重）

### 7.2 需求27验收

- [x] Session Hash结构（题号、hint_level、对话摘要）
- [x] Session创建与获取
- [x] Session状态更新
- [x] 对话上下文维护
- [x] Session TTL管理
- [x] 多轮对话支持

---

## 8. Git提交记录

```bash
git add backend/algorithms/calculation_error_handler.py
git add backend/services/session_service.py
git add backend/api/calculation_error.py
git add backend/api/session.py
git add docs/V3_Calculation_Error_Session_IMPLEMENTATION.md

git commit -m "feat: Implement calculation error handling and session management (Req 17,27)

- Add error type classification (calculation/logic/formula/concept)
- Add calculation error detection with keyword matching
- Add Actual Score weight protection for calculation errors
- Add light hint generation without L1-L4 penalty
- Add Redis Session Hash structure
- Add Session lifecycle management (create/get/update/delete)
- Add conversation context maintenance
- Add Session TTL management (2 hours)
- Add calculation error and session API endpoints

Closes requirements #17, #27"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
