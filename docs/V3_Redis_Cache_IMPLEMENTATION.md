# V3 Redis缓存服务实现文档

**需求编号**: 需求40, 需求41  
**需求名称**: 
- 需求40: Redis错题复习队列
- 需求41: Redis知识点掌握度缓存

**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

实现两个核心Redis缓存功能：
1. **错题复习队列**: 使用Redis ZSet管理复习计划，支持艾宾浩斯遗忘曲线
2. **知识点掌握度缓存**: 使用Redis Hash缓存掌握度数据，减少数据库查询

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/services/redis_cache_service.py` | Redis缓存服务核心 | ~550行 |
| `backend/api/redis_cache.py` | Redis缓存API接口 | ~400行 |

---

## 3. Redis数据结构

### 3.1 错题复习队列 (需求40)

**ZSet结构:**
```
Key: ai:tutor:review-q:{user_id}
Score: next_review_timestamp (下次复习时间戳)
Member: question_id (题目ID)
TTL: 30天
```

**详情Hash:**
```
Key: ai:tutor:review-q:{user_id}:detail:{question_id}
Field: data
Value: {
  "question_id": "q001",
  "review_stage": 0,
  "mastery_level": 0.3,
  "added_at": "2024-01-01T12:00:00",
  "next_review_at": "2024-01-02T12:00:00"
}
```

**复习间隔 (艾宾浩斯):**
| 阶段 | 间隔天数 |
|-----|---------|
| 0 | 1天 |
| 1 | 2天 |
| 2 | 4天 |
| 3 | 7天 |
| 4 | 14天 |

### 3.2 知识点掌握度缓存 (需求41)

**Hash结构:**
```
Key: ai:tutor:mastery:{user_id}
Field: knowledge_point_id
Value: {
  "score": 75.0,
  "p_known": 0.75,
  "updated_at": "2024-01-01T12:00:00"
}
TTL: 7天
```

---

## 4. 核心功能

### 4.1 错题复习队列

#### 添加题目到队列
```python
service.add_to_review_queue(
    user_id=1,
    question_id="q001",
    mastery_level=0.3,
    review_stage=0
)
```

#### 获取到期复习
```python
# 使用ZRANGEBYSCORE获取score <= 当前时间的题目
due_items = service.get_due_reviews(user_id=1, limit=10)
```

#### 更新复习阶段
- **答对**: 进入下一阶段，更新下次复习时间
- **答错**: 重置为阶段0，1天后再次复习
- **完成阶段4**: 从队列中移除，标记为已掌握

### 4.2 掌握度缓存

#### 缓存掌握度
```python
service.cache_mastery(
    user_id=1,
    knowledge_point_id="kp001",
    score=75.0,
    p_known=0.75
)
```

#### 批量缓存 (预热)
```python
mastery_data = {
    "kp001": {"score": 75.0, "p_known": 0.75},
    "kp002": {"score": 60.0, "p_known": 0.60}
}
service.batch_cache_mastery(user_id=1, mastery_data=mastery_data)
```

---

## 5. API接口

### 5.1 复习队列API

| 方法 | 端点 | 说明 |
|-----|------|------|
| POST | `/redis-cache/review-queue/add` | 添加题目到复习队列 |
| GET | `/redis-cache/review-queue/due` | 获取到期复习题目 |
| POST | `/redis-cache/review-queue/update` | 更新复习阶段 |
| GET | `/redis-cache/review-queue/stats` | 获取队列统计 |
| DELETE | `/redis-cache/review-queue/{question_id}` | 移除题目 |
| GET | `/redis-cache/review-queue/due-count` | 获取到期数量 |

### 5.2 掌握度缓存API

| 方法 | 端点 | 说明 |
|-----|------|------|
| POST | `/redis-cache/mastery/cache` | 缓存掌握度 |
| GET | `/redis-cache/mastery/{kp_id}` | 获取掌握度 |
| GET | `/redis-cache/mastery` | 获取所有掌握度 |
| POST | `/redis-cache/mastery/batch-cache` | 批量缓存 |
| DELETE | `/redis-cache/mastery/cache` | 使缓存失效 |
| POST | `/redis-cache/mastery/for-recommendation` | 获取推荐用掌握度 |

### 5.3 缓存管理API

| 方法 | 端点 | 说明 |
|-----|------|------|
| POST | `/redis-cache/warm-up` | 缓存预热 |
| GET | `/redis-cache/stats` | 获取缓存统计 |
| GET | `/redis-cache/health` | 健康检查 |

---

## 6. 硬指标实现

### 6.1 复习队列

| 指标 | 值 | 实现位置 |
|-----|-----|---------|
| 复习间隔 | 1/2/4/7/14天 | `REVIEW_INTERVALS` |
| 队列TTL | 30天 | `REVIEW_QUEUE_TTL` |
| 数据结构 | ZSet | `add_to_review_queue()` |

### 6.2 掌握度缓存

| 指标 | 值 | 实现位置 |
|-----|-----|---------|
| 数据结构 | Hash | `cache_mastery()` |
| TTL | 7天 | `MASTERY_TTL` |
| 淘汰策略 | 7天未登录淘汰 | TTL自动过期 |

---

## 7. 使用示例

### 7.1 添加错题到复习队列
```http
POST /redis-cache/review-queue/add
{
  "question_id": "q001",
  "mastery_level": 0.3,
  "review_stage": 0
}

响应:
{
  "success": true,
  "message": "已添加到复习队列",
  "question_id": "q001",
  "review_stage": 0,
  "next_review_in_days": 1,
  "next_review_at": "2024-01-02T12:00:00"
}
```

### 7.2 获取到期复习
```http
GET /redis-cache/review-queue/due?limit=10

响应:
{
  "success": true,
  "user_id": 1,
  "due_count": 3,
  "items": [
    {
      "question_id": "q001",
      "review_stage": 0,
      "mastery_level": 0.3,
      "next_review_at": "2024-01-02T12:00:00"
    }
  ]
}
```

### 7.3 缓存掌握度
```http
POST /redis-cache/mastery/cache
{
  "knowledge_point_id": "kp001",
  "score": 75.0,
  "p_known": 0.75
}

响应:
{
  "success": true,
  "message": "掌握度已缓存",
  "knowledge_point_id": "kp001",
  "score": 75.0,
  "p_known": 0.75
}
```

---

## 8. 验收标准

### 8.1 需求40验收

- [x] Redis ZSet结构 (`ai:tutor:review-q:{uid}`)
- [x] 使用next_review_timestamp作为Score
- [x] ZRANGEBYSCORE拉取到期题目
- [x] 5阶段复习间隔 (1/2/4/7/14天)
- [x] 答对进入下一阶段，答错重置
- [x] 完成阶段4后从队列移除

### 8.2 需求41验收

- [x] Redis Hash结构 (`ai:tutor:mastery:{uid}`)
- [x] Field为knowledge_point_id
- [x] Value包含score和p_known
- [x] 7天TTL设置
- [x] 缓存预热支持
- [x] 7天未登录自动淘汰

---

## 9. Git提交记录

```bash
git add backend/services/redis_cache_service.py
git add backend/api/redis_cache.py
git add docs/V3_Redis_Cache_IMPLEMENTATION.md

git commit -m "feat: Implement Redis cache service for review queue and mastery (Req 40,41)

- Add Redis ZSet structure for review queue (ai:tutor:review-q:{uid})
- Add 5-stage review intervals (1/2/4/7/14 days) based on Ebbinghaus curve
- Add ZRANGEBYSCORE for fetching due reviews
- Add Redis Hash structure for mastery cache (ai:tutor:mastery:{uid})
- Add 7-day TTL for mastery cache
- Add cache warm-up and batch operations
- Add review queue and mastery cache API endpoints

Closes requirements #40, #41"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
