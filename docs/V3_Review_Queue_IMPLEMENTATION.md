# V3 错题复习队列实现文档

**需求编号**: 需求11, 需求12  
**需求名称**: 
- 需求11: 将传统的错题复习清单游戏化，基于遗忘曲线体现错题的"治愈"过程
- 需求12: 复习错题时拒绝死记硬背原题，由Advisor抽取变式题进行能力验证

**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

实现错题复习系统的两个核心功能：
1. **游戏化复习**: 基于艾宾浩斯遗忘曲线的5阶段复习，视觉表现从"生锈"到"闪亮"
2. **变式题推荐**: 不展示原题，而是推荐同知识点的变式题进行能力验证

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/services/review_queue_service.py` | 错题复习队列服务 | ~500行 |
| `backend/api/review.py` | 错题复习API | ~350行 |

---

## 3. 核心功能实现

### 3.1 需求11: 错题复习游戏化

#### 复习阶段（艾宾浩斯遗忘曲线）

| 阶段 | 间隔天数 | 视觉状态 | 颜色 | 图标 |
|-----|---------|---------|------|------|
| 初始 | 0 | rusty（生锈） | #FF4D4F | 🔴 |
| 1 | 1 | rusty（生锈） | #FF4D4F | 🔴 |
| 2 | 2 | tarnished（暗淡） | #FF7875 | 🟠 |
| 3 | 4 | polishing（打磨中） | #FFC53D | 🟡 |
| 4 | 7 | shiny（发亮） | #95DE64 | 🟢 |
| 5 | 14 | gleaming（闪亮） | #52C41A | ✨ |
| Mastered | - | mastered（已攻克） | #FFD700 | 🏆 |

#### 状态流转

```
错题加入队列
    ↓
[生锈] 1天后首次复习
    ↓ (答对)
[暗淡] 2天后第二次复习
    ↓ (答对)
[打磨中] 4天后第三次复习
    ↓ (答对)
[发亮] 7天后第四次复习
    ↓ (答对)
[闪亮] 14天后第五次复习
    ↓ (答对)
[已攻克] 🏆 金色标签
```

### 3.2 需求12: 变式题推荐

#### 变式题抽取逻辑

```python
# 1. 获取原题知识点
knowledge_points = original_question['knowledge_points']

# 2. Chroma向量检索同知识点题目
candidates = chroma_service.search_by_knowledge_points(knowledge_points)

# 3. 过滤：排除原题、难度匹配 |S - θ| <= 0.5
variations = [
    c for c in candidates
    if c.question_id != original_question_id
    and abs(c.difficulty - user_theta) <= 0.5
]

# 4. 返回最匹配的变式题
return variations[0]
```

---

## 4. API接口

### 4.1 获取到期复习题

```http
GET /review/due?limit=10
```

**响应：**
```json
{
  "success": true,
  "total": 3,
  "questions": [
    {
      "question_id": "q001",
      "original_question": {
        "id": "q001",
        "content": "原题内容...",
        "knowledge_points": ["等差数列"]
      },
      "variation_question": {
        "question_id": "q101",
        "content": "变式题内容...",
        "difficulty": 0.6,
        "is_variation": true
      },
      "review_stage": 2,
      "visual_status": "tarnished",
      "color": "#FF7875",
      "icon": "🟠",
      "is_mastered": false
    }
  ]
}
```

### 4.2 更新复习状态

```http
POST /review/update
```

**请求体：**
```json
{
  "question_id": "q001",
  "is_correct": true
}
```

**响应（答对，推进到下一阶段）：**
```json
{
  "success": true,
  "message": "答对了！下次复习在2天后",
  "is_mastered": false,
  "stage": 3,
  "visual_status": "polishing",
  "color": "#FFC53D",
  "icon": "🟡"
}
```

**响应（完成所有阶段）：**
```json
{
  "success": true,
  "message": "恭喜！该错题已攻克",
  "is_mastered": true,
  "stage": 6,
  "visual_status": "mastered",
  "color": "#FFD700",
  "icon": "🏆"
}
```

### 4.3 获取复习进度

```http
GET /review/progress
```

**响应：**
```json
{
  "success": true,
  "total_questions": 10,
  "mastered_count": 3,
  "in_progress_count": 5,
  "rusty_count": 2,
  "healing_progress": 30.0
}
```

### 4.4 获取变式题

```http
GET /review/variation/q001
```

**响应：**
```json
{
  "success": true,
  "original_question_id": "q001",
  "variation_question": {
    "question_id": "q101",
    "content": "变式题内容...",
    "difficulty": 0.6,
    "knowledge_points": ["等差数列"],
    "similarity": 0.85,
    "is_variation": true
  },
  "message": "成功获取变式题"
}
```

---

## 5. 硬指标实现

### 5.1 复习间隔（艾宾浩斯遗忘曲线）

```python
REVIEW_INTERVALS = [1, 2, 4, 7, 14]  # 天数
```

### 5.2 变式题难度匹配

| 条件 | 值 | 说明 |
|-----|-----|------|
| 难度匹配 | \|S - θ\| <= 0.5 | 变式题难度与用户能力匹配 |
| 知识点匹配 | 相同 | 变式题必须与原题同知识点 |

### 5.3 视觉状态颜色

| 状态 | 颜色值 | 含义 |
|-----|--------|------|
| rusty | #FF4D4F | 生锈（红色） |
| tarnished | #FF7875 | 暗淡（橙红） |
| polishing | #FFC53D | 打磨中（黄色） |
| shiny | #95DE64 | 发亮（浅绿） |
| gleaming | #52C41A | 闪亮（绿色） |
| mastered | #FFD700 | 已攻克（金色） |

---

## 6. 数据存储

### 6.1 Redis数据结构

**Review Queue (ZSet):**
```
Key: ai:tutor:review-q:{user_id}
Score: next_review_timestamp
Member: question_id
```

**Review Metadata (Hash):**
```
Key: ai:tutor:review-meta:{user_id}:{question_id}
Fields:
  - stage: 当前阶段 (0-5)
  - error_count: 错误次数
  - added_at: 加入时间
  - is_mastered: 是否已攻克 (0/1)
```

**Mastered Set:**
```
Key: ai:tutor:mastered:{user_id}
Members: question_ids
```

---

## 7. 验收标准

### 7.1 需求11验收

- [x] 5种复习阶段（1/2/4/7/14天）
- [x] 6种视觉表现（生锈→暗淡→打磨→发亮→闪亮→已攻克）
- [x] 颜色由红转绿的游戏化表现
- [x] 完成14天复习后标记Mastered
- [x] 答错后重置到第1阶段

### 7.2 需求12验收

- [x] 基于RAG抽取变式题
- [x] 变式题与原题同知识点
- [x] 难度匹配 |S - θ| <= 0.5
- [x] 不直接展示原题
- [x] 支持原题对比查看

---

## 8. Git提交记录

```bash
git add backend/services/review_queue_service.py
git add backend/api/review.py
git add docs/V3_Review_Queue_IMPLEMENTATION.md

git commit -m "feat: Implement review queue with gamification and variation questions (Req 11-12)

- Add review queue service with 5-stage review intervals (1/2/4/7/14 days)
- Add visual status mapping (rusty -> mastered) with color transitions
- Add variation question recommendation using RAG
- Add difficulty matching |S - theta| <= 0.5
- Add review progress tracking and healing metrics
- Add review queue API endpoints

Closes requirements #11, #12"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
