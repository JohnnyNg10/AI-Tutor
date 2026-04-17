# V3 跳过处理机制实现文档

**需求编号**: 需求池相关条目  
**PRD章节**: 2.4节 跳过处理机制  
**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

实现题目跳过处理机制，处理两种跳过场景：
- **太简单**：学生觉得题目过于简单，浪费时间
- **太难了**：学生觉得题目难度过高，感到挫败

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/algorithms/skip_handler.py` | 跳过处理器核心 | ~450行 |
| `backend/api/skip.py` | 跳过处理API | ~300行 |

---

## 3. 架构设计

### 3.1 跳过处理流程

```
┌─────────────────────────────────────────────────────────────┐
│                      学生点击"跳过"                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      选择跳过原因                            │
│              ┌─────────────┐    ┌─────────────┐             │
│              │   太简单    │    │   太难了    │             │
│              └─────────────┘    └─────────────┘             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      算法处理                                │
│  ┌─────────────────────────┐  ┌─────────────────────────┐   │
│  │ 太简单：                │  │ 太难了：                │   │
│  │ - Actual = 1.0          │  │ - Actual = 0.0          │   │
│  │ - θ += 0.1              │  │ - θ -= 0.05             │   │
│  │ - BKT掌握度提升         │  │ - 不确定性增加          │   │
│  └─────────────────────────┘  └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      Advisor介入                             │
│  ┌─────────────────────────┐  ┌─────────────────────────┐   │
│  │ "看来这些基础难不倒你!  │  │ "这道题涉及的放缩法确   │   │
│  │  我们直接跳过这一阶..." │  │  实超前，别灰心..."     │   │
│  └─────────────────────────┘  └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      下一题推荐策略                          │
│  ┌─────────────────────────┐  ┌─────────────────────────┐   │
│  │ 推荐更高难度题目        │  │ 推荐更简单题目          │   │
│  │ (upgrade策略)           │  │ (downgrade策略)         │   │
│  └─────────────────────────┘  └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 硬指标实现

### 4.1 跳过处理硬指标

| 跳过类型 | Actual Score | θ调整 | BKT影响 | 实现位置 |
|---------|-------------|-------|---------|---------|
| 太简单 | 1.0 | +0.1 | 掌握度提升 | `handle_too_easy()` |
| 太难了 | 0.0 | -0.05 | 不确定性增加 | `handle_too_hard()` |

### 4.2 Advisor话术硬指标

| 跳过类型 | 话术示例 | 实现位置 |
|---------|---------|---------|
| 太简单 | "看来这些基础难不倒你!我们直接跳过这一阶..." | `ADVISOR_MESSAGES` |
| 太难了 | "这道题涉及的{kp}确实超前，别灰心..." | `ADVISOR_MESSAGES` |

### 4.3 下一题推荐策略

| 跳过类型 | 策略 | 难度范围 | 语气 | 实现位置 |
|---------|------|---------|------|---------|
| 太简单 | upgrade | [θ, θ+0.5] | motivating | `_determine_next_recommendation()` |
| 太难了 | downgrade | [θ-0.5, θ] | encouraging | `_determine_next_recommendation()` |

---

## 5. 核心类设计

```python
SkipHandler              # 跳过处理器
├── handle_skip()        # 通用跳过处理
├── handle_too_easy()    # 太简单处理
├── handle_too_hard()    # 太难处理
├── _calculate_actual_score()      # 计算Actual Score
├── _calculate_theta_delta()       # 计算θ调整
├── _generate_advisor_message()    # 生成Advisor话术
├── _determine_next_recommendation() # 决定下一题策略
├── get_skip_statistics()          # 获取跳过统计
└── generate_calibration_suggestion() # 生成校准建议
```

---

## 6. API接口

### 6.1 通用跳过处理

```http
POST /skip/handle
```

**请求体：**
```json
{
  "question_id": "q001",
  "skip_reason": "too_easy",
  "current_theta": 0.5,
  "knowledge_points": ["等差数列"]
}
```

**响应：**
```json
{
  "success": true,
  "skip_reason": "too_easy",
  "actual_score": 1.0,
  "theta_delta": 0.1,
  "new_theta": 0.6,
  "advisor_message": "看来这些基础难不倒你！...",
  "next_recommendation": {
    "strategy": "upgrade",
    "difficulty_range": [0.6, 1.1],
    "tone": "motivating"
  }
}
```

### 6.2 太简单跳过

```http
POST /skip/too-easy
```

### 6.3 太难了跳过

```http
POST /skip/too-hard
```

### 6.4 跳过统计

```http
GET /skip/statistics
```

**响应：**
```json
{
  "success": true,
  "total_skips": 10,
  "too_easy_count": 7,
  "too_hard_count": 2,
  "other_count": 1,
  "too_easy_ratio": 0.7,
  "too_hard_ratio": 0.2
}
```

### 6.5 系统校准建议

```http
GET /skip/calibration-suggestion?current_theta=0.5
```

**响应：**
```json
{
  "success": true,
  "should_adjust": true,
  "suggestion": "学生频繁跳过简单题，建议提升初始能力估计",
  "theta_adjustment": 0.2,
  "difficulty_bias": "increase"
}
```

---

## 7. 验收标准

### 7.1 功能验收

- [x] 太简单跳过处理正确（Actual=1.0, θ+=0.1）
- [x] 太难了跳过处理正确（Actual=0.0, θ-=0.05）
- [x] Advisor话术生成正确
- [x] 下一题推荐策略正确
- [x] 跳过历史记录正常
- [x] 跳过模式检测正常

### 7.2 测试用例

```python
# 测试1：太简单跳过
result = handler.handle_too_easy(user_id=1, question_id="q001", current_theta=0.5)
assert result.actual_score == 1.0
assert result.theta_delta == 0.1
assert "难不倒你" in result.advisor_message

# 测试2：太难了跳过
result = handler.handle_too_hard(user_id=1, question_id="q002", current_theta=0.5)
assert result.actual_score == 0.0
assert result.theta_delta == -0.05
assert "别灰心" in result.advisor_message

# 测试3：下一题策略
result = handler.handle_too_easy(user_id=1, question_id="q001", current_theta=0.5)
assert result.next_recommendation['strategy'] == 'upgrade'

result = handler.handle_too_hard(user_id=1, question_id="q002", current_theta=0.5)
assert result.next_recommendation['strategy'] == 'downgrade'
```

---

## 8. 系统校准功能

### 8.1 跳过模式检测

```python
# 频繁跳过简单题
if too_easy_ratio > 0.7:
    pattern = 'frequent_easy_skip'
    suggestion = '系统可能低估学生能力，建议提升初始θ估计'

# 频繁跳过难题
if too_hard_ratio > 0.7:
    pattern = 'frequent_hard_skip'
    suggestion = '系统可能高估学生能力，建议降低初始θ估计'
```

### 8.2 自动校准建议

| 模式 | 建议调整 | θ调整量 | 难度偏移 |
|-----|---------|---------|---------|
| frequent_easy_skip | 提升能力估计 | +0.2 | increase |
| frequent_hard_skip | 降低能力估计 | -0.2 | decrease |

---

## 9. Git提交记录

```bash
# 待提交
git add backend/algorithms/skip_handler.py
git add backend/api/skip.py
git add docs/V3_Skip_Handler_IMPLEMENTATION.md

git commit -m "feat: Implement skip handler mechanism (PRD 2.4)

- Add SkipHandler with too_easy/too_hard processing
- Add Actual Score calculation (1.0/0.0)
- Add theta adjustment (+0.1/-0.05)
- Add Advisor message generation
- Add next question recommendation strategy
- Add skip pattern detection and calibration
- Add skip handling API endpoints

Closes skip handling requirement"
```

---

## 10. 实现总结

### 10.1 完成功能

1. **跳过处理器** (`skip_handler.py`)
   - 太简单/太难了两种跳过处理
   - Actual Score计算
   - 能力值θ调整
   - BKT影响计算
   - Advisor话术生成
   - 下一题推荐策略

2. **跳过处理API** (`skip.py`)
   - 通用跳过处理接口
   - 太简单/太难了专用接口
   - 跳过统计接口
   - 跳过历史接口
   - 系统校准建议接口

### 10.2 技术亮点

- 严格遵循PRD硬指标实现
- 支持跳过模式检测和系统校准
- 完整的Advisor话术库
- 智能的下一题推荐策略
- 跳过历史记录和分析

### 10.3 后续优化方向

1. 接入LLM生成更自然的Advisor话术
2. 增加更多跳过原因类型
3. 实现跳过预测（提前识别可能跳过的题目）
4. 添加跳过效果反馈机制

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
