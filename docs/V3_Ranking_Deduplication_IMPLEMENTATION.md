# V3 IRT段位与题目多样化实现文档

**需求编号**: 需求9, 需求32  
**需求名称**: 
- 需求9: 将底层枯燥的IRT θ值转化为学生易懂的游戏化成长段位趋势图
- 需求32: 防止算法陷入局部最优，避免连续向用户推送相同考点的题目

**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

实现两个核心功能：
1. **IRT段位系统**: 将θ值[-3, +3]映射为游戏化段位，展示成长趋势
2. **题目多样化**: 防止连续推送相同知识点，避免认知疲劳

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/services/irt_ranking_service.py` | IRT段位服务 | ~350行 |
| `backend/algorithms/question_deduplication.py` | 题目去重服务 | ~350行 |
| `backend/api/ranking.py` | 段位与多样化API | ~280行 |

---

## 3. IRT段位系统（需求9）

### 3.1 段位定义（硬指标）

| θ范围 | 段位 | 名称 | 颜色 | 图标 |
|-------|------|------|------|------|
| [-3.0, -2.0) | Novice | 见习生 | #8C8C8C | 🌱 |
| [-2.0, -1.0) | Explorer | 探索者 | #52C41A | 🔍 |
| [-1.0, 0.0) | Apprentice | 学徒 | #1890FF | 📚 |
| [0.0, 1.0) | Practitioner | 实践者 | #722ED1 | ⚔️ |
| [1.0, 2.0) | Expert | 专家 | #FA8C16 | ⭐ |
| [2.0, 2.5) | Master | 大师 | #EB2F96 | 🏆 |
| [2.5, 3.0] | Grandmaster | 宗师 | #F5222D | 👑 |

### 3.2 段位变化检测

```python
# 升级检测
if new_rank_index > old_rank_index:
    return {
        'change_type': 'promotion',
        'message': '恭喜！你已从【见习生】晋升为【探索者】！',
        'should_animate': True
    }

# 降级检测
if new_rank_index < old_rank_index:
    return {
        'change_type': 'demotion',
        'message': '别灰心，继续努力！',
        'should_animate': True
    }
```

---

## 4. 题目多样化（需求32）

### 4.1 滑动窗口检查

```python
SLIDING_WINDOW_SIZE = 2
KNOWLEDGE_OVERLAP_THRESHOLD = 0.5  # 50%重叠视为相同考点

# 检查第i题与第i+1题
for i in range(len(questions) - 1):
    overlap = calculate_knowledge_overlap(
        questions[i].knowledge_points,
        questions[i+1].knowledge_points
    )
    if overlap >= 0.5:
        # 发现违规，记录并处理
```

### 4.2 重排算法

```python
# 1. 按主要知识点分类
categorized = categorize_by_knowledge_point(questions)

# 2. 优先选择与最近历史不同的知识点
for each position:
    best = select_max_diversity_score(remaining_questions)
    reordered.append(best)
    update_recent_history(best.knowledge_points)
```

### 4.3 惩罚逻辑

```python
# 对连续相同知识点的题目降低20%分数
if knowledge_overlap >= 0.5:
    score *= 0.8
```

---

## 5. API接口

### 5.1 获取当前段位

```http
GET /ranking/current
```

**响应：**
```json
{
  "success": true,
  "user_id": 1,
  "current_theta": 0.5,
  "current_rank": {
    "tier": "practitioner",
    "name": "Practitioner",
    "name_cn": "实践者",
    "color": "#722ED1",
    "icon": "⚔️",
    "description": "理论与实践结合，解题能力稳步提升"
  },
  "progress_to_next": 50.0,
  "next_rank": {
    "name_cn": "专家",
    "icon": "⭐"
  },
  "total_study_days": 30
}
```

### 5.2 获取段位趋势

```http
GET /ranking/trend?days=30
```

### 5.3 检查段位变化

```http
POST /ranking/check-change?old_theta=0.5&new_theta=1.2
```

**响应（升级）：**
```json
{
  "has_changed": true,
  "change_type": "promotion",
  "from_rank": {"name_cn": "实践者", "icon": "⚔️"},
  "to_rank": {"name_cn": "专家", "icon": "⭐"},
  "message": "恭喜！你已从【实践者】晋升为【专家】！",
  "should_animate": true
}
```

### 5.4 队列多样化

```http
POST /ranking/diversify-queue
```

**请求体：**
```json
{
  "questions": [
    {"question_id": "q1", "knowledge_points": ["等差数列"], "difficulty": 0.5},
    {"question_id": "q2", "knowledge_points": ["等差数列"], "difficulty": 0.6},
    {"question_id": "q3", "knowledge_points": ["等比数列"], "difficulty": 0.5}
  ]
}
```

**响应：**
```json
{
  "success": true,
  "original_count": 3,
  "diversified_count": 3,
  "violations_fixed": 1,
  "questions": [
    {"question_id": "q1", "knowledge_points": ["等差数列"], ...},
    {"question_id": "q3", "knowledge_points": ["等比数列"], ...},
    {"question_id": "q2", "knowledge_points": ["等差数列"], ...}
  ]
}
```

---

## 6. 硬指标实现

### 6.1 段位映射

| θ范围 | 段位 | 实现位置 |
|-------|------|---------|
| [-3, -2) | 见习生 | `theta_to_rank()` |
| [-2, -1) | 探索者 | `theta_to_rank()` |
| [-1, 0) | 学徒 | `theta_to_rank()` |
| [0, 1) | 实践者 | `theta_to_rank()` |
| [1, 2) | 专家 | `theta_to_rank()` |
| [2, 2.5) | 大师 | `theta_to_rank()` |
| [2.5, 3] | 宗师 | `theta_to_rank()` |

### 6.2 多样化算法

| 参数 | 值 | 实现位置 |
|-----|-----|---------|
| 滑动窗口大小 | 2 | `SLIDING_WINDOW_SIZE` |
| 知识点重叠阈值 | 50% | `KNOWLEDGE_OVERLAP_THRESHOLD` |
| 惩罚系数 | 0.8 | `apply_diversity_penalty()` |

---

## 7. 验收标准

### 7.1 需求9验收

- [x] θ值[-3, +3]正确映射到7个段位
- [x] 段位趋势历史数据查询
- [x] 升级/降级动画触发
- [x] 段位进度计算正确

### 7.2 需求32验收

- [x] 滑动窗口检查（窗口大小=2）
- [x] 相同知识点检测（重叠度>=50%）
- [x] 队列重排算法
- [x] 多样性惩罚逻辑（-20%分数）

---

## 8. Git提交记录

```bash
git add backend/services/irt_ranking_service.py
git add backend/algorithms/question_deduplication.py
git add backend/api/ranking.py
git add docs/V3_Ranking_Deduplication_IMPLEMENTATION.md

git commit -m "feat: Implement IRT ranking and question deduplication (Req 9,32)

- Add IRT ranking service with 7 tiers (Novice to Grandmaster)
- Add theta to rank mapping [-3, +3] with color/icon
- Add rank change detection with animation trigger
- Add question deduplication with sliding window (size=2)
- Add knowledge overlap check (threshold=50%)
- Add queue reordering algorithm
- Add diversity penalty logic (-20% score)
- Add ranking and deduplication API endpoints

Closes requirements #9, #32"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
