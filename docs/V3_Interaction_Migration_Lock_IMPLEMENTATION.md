# V3 全量交互日志、数据迁移与乐观锁实现文档

**需求编号**: 行号37, 行号38, 行号39  
**需求名称**: 
- 行号37: 全量记录用户在学习过程中的每一个微小交互
- 行号38: 解决系统大版本升级带来的数据断层
- 行号39: 防止学生快速连续交互导致数据库画像更新冲突（并发冲突乐观锁）

**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

### 行号37: 全量交互日志
- 记录所有用户交互（点击、输入、停留等）
- 异步批量写入，避免阻塞
- 为六维雷达图和算法优化提供数据

### 行号38: 数据迁移
- V2→V3数据迁移
- 缺失字段自动填充默认值
- 防止老用户画像字段为空

### 行号39: 乐观锁
- 版本号机制防止并发冲突
- CAS（Compare-And-Swap）更新
- 冲突检测与自动重试

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/services/interaction_logger_service.py` | 交互日志服务 | ~350行 |
| `backend/services/data_migration_service.py` | 数据迁移服务 | ~400行 |
| `backend/services/optimistic_lock_service.py` | 乐观锁服务 | ~350行 |
| `backend/api/interaction_logger.py` | 交互日志API | ~200行 |
| `backend/api/data_migration.py` | 数据迁移API | ~200行 |
| `backend/api/optimistic_lock.py` | 乐观锁API | ~250行 |

---

## 3. 全量交互日志（行号37）

### 3.1 交互类型

| 类型 | 说明 |
|-----|------|
| page_view | 页面浏览 |
| question_start | 开始答题 |
| question_submit | 提交答案 |
| hint_click | 点击提示 |
| skip_click | 点击跳过 |
| favorite_click | 点击收藏 |
| scroll | 滚动 |
| time_spent | 时间统计 |

### 3.2 批量写入

```python
# 批量配置
BATCH_SIZE = 100      # 每100条写入一次
FLUSH_INTERVAL = 5    # 每5秒刷新一次

# 异步写入Redis队列
for log_data in logs_data:
    pipe.lpush(INTERACTION_LOG_QUEUE, json.dumps(log_data))
```

### 3.3 API端点

- `POST /interaction-logger/log` - 记录交互
- `GET /interaction-logger/analyze` - 分析交互模式

---

## 4. 数据迁移（行号38）

### 4.1 V3新增字段默认值

| 表 | 字段 | 默认值 |
|---|------|--------|
| user_profiles | theta | 0.0 |
| user_profiles | theta_se | 1.0 |
| user_knowledge_mastery | p_learn | 0.3 |
| user_knowledge_mastery | p_guess | 0.2 |
| user_knowledge_mastery | p_slip | 0.1 |
| user_knowledge_mastery | p_known | 0.5 |
| learning_records | hint_count | 0 |
| learning_records | time_spent | 0 |

### 4.2 迁移流程

```
检查是否已迁移
    ↓
迁移user_profiles表
    ↓
迁移user_knowledge_mastery表
    ↓
迁移learning_records表
    ↓
初始化V3新表
    ↓
记录迁移完成
```

### 4.3 API端点

- `POST /data-migration/migrate` - 迁移单个用户
- `POST /data-migration/migrate-batch` - 批量迁移

---

## 5. 乐观锁（行号39）

### 5.1 CAS更新流程

```python
# 1. 获取当前版本号
current_version = get_version(entity_type, entity_id)

# 2. 检查版本号是否匹配
if current_version != expected_version:
    # 版本冲突，重试
    retry()

# 3. 版本匹配，执行更新
new_version = increment_version()
store_data(new_data, new_version)
```

### 5.2 配置

| 配置项 | 值 | 说明 |
|-------|-----|------|
| MAX_RETRIES | 3 | 最大重试次数 |
| RETRY_DELAY | 0.1s | 重试间隔 |
| VERSION_TTL | 3600s | 版本号TTL |

### 5.3 API端点

- `POST /optimistic-lock/cas-update` - CAS更新
- `POST /optimistic-lock/update-profile` - 安全更新画像

---

## 6. 硬指标

### 6.1 交互日志

| 指标 | 值 |
|-----|-----|
| 批量大小 | 100条 |
| 刷新间隔 | 5秒 |
| 队列TTL | 30天 |

### 6.2 数据迁移

| 指标 | 值 |
|-----|-----|
| 批量大小 | 100用户 |
| 默认p_known | 0.5 |
| 默认theta | 0.0 |

### 6.3 乐观锁

| 指标 | 值 |
|-----|-----|
| 最大重试 | 3次 |
| 重试间隔 | 0.1秒 |
| 版本TTL | 1小时 |

---

## 7. Git提交记录

```bash
git add backend/services/interaction_logger_service.py
git add backend/services/data_migration_service.py
git add backend/services/optimistic_lock_service.py
git add backend/api/interaction_logger.py
git add backend/api/data_migration.py
git add backend/api/optimistic_lock.py
git add docs/V3_Interaction_Migration_Lock_IMPLEMENTATION.md

git commit -m "feat: Implement interaction logging, data migration and optimistic lock (Row 37,38,39)

- Add full interaction logging with async batch writing
- Add V2 to V3 data migration with default values
- Add optimistic locking with CAS update
- Add conflict detection and automatic retry
- Add API endpoints for all services

对应飞书需求池:
- 行号37: 全量交互日志记录
- 行号38: V2→V3数据迁移
- 行号39: 并发冲突乐观锁"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
