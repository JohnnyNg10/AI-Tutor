# V3 交互日志表分区归档实现文档

**需求编号**: 行号40  
**需求名称**: 防止新引入的 user_interaction_logs 表无限制膨胀撑爆数据库磁盘  

**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

防止交互日志表无限制膨胀：
- 按时间分区存储日志
- 自动归档旧数据
- 自动删除过期数据
- 磁盘空间监控

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/services/log_partitioning_service.py` | 日志分区服务 | ~450行 |
| `backend/api/log_partitioning.py` | 日志分区API | ~250行 |

---

## 3. 分区策略

### 3.1 分区配置

| 配置项 | 值 | 说明 |
|-------|-----|------|
| PARTITION_DAYS | 7 | 每个分区7天 |
| MAX_ACTIVE_PARTITIONS | 4 | 最多4个活跃分区 |
| ARCHIVE_AFTER_DAYS | 30 | 30天后归档 |
| DELETE_AFTER_DAYS | 90 | 90天后删除 |
| MAX_PARTITION_SIZE_MB | 500 | 单个分区最大500MB |

### 3.2 分区命名

```
log_YYYY_MM_DD

例如：
- log_2026_04_17 (2026年4月17日开始)
- log_2026_04_24 (2026年4月24日开始)
```

### 3.3 分区生命周期

```
创建分区（7天）
    ↓
活跃使用（最近28天）
    ↓
归档（30天后）
    ↓
删除（90天后）
```

---

## 4. 核心功能

### 4.1 自动分区切换

```python
# 检查是否需要切换分区
def _should_switch_partition(current):
    # 分区已满（10万条或500MB）
    if record_count >= 100000 or size_mb >= 500:
        return True
    
    # 时间到期
    if now >= end_date:
        return True
    
    return False
```

### 4.2 自动归档

```python
# 归档30天前的分区
cutoff_date = now - 30 days
for partition in partitions:
    if partition.end_date < cutoff_date:
        archive_partition(partition)
```

### 4.3 磁盘监控

| 状态 | 阈值 | 建议 |
|-----|------|------|
| normal | < 3GB | 磁盘空间充足 |
| warning | 3-5GB | 磁盘空间正常，建议定期监控 |
| warning | 5-8GB | 磁盘空间紧张，建议归档旧分区 |
| critical | > 8GB | 磁盘空间严重不足，立即处理 |

---

## 5. API接口

| 端点 | 说明 |
|-----|------|
| `GET /log-partitioning/current-partition` | 获取当前分区 |
| `POST /log-partitioning/write-log` | 写入日志 |
| `GET /log-partitioning/statistics` | 分区统计 |
| `POST /log-partitioning/archive` | 归档旧分区 |
| `POST /log-partitioning/delete-expired` | 删除过期分区 |
| `GET /log-partitioning/disk-space` | 磁盘空间检查 |

---

## 6. 硬指标

| 指标 | 值 |
|-----|-----|
| 分区周期 | 7天 |
| 归档时间 | 30天 |
| 删除时间 | 90天 |
| 单分区最大 | 500MB / 10万条 |
| 活跃分区数 | 最多4个 |

---

## 7. Git提交记录

```bash
git add backend/services/log_partitioning_service.py
git add backend/api/log_partitioning.py
git add docs/V3_LogPartitioning_IMPLEMENTATION.md

git commit -m "feat: Implement log partitioning and archiving (Row 40)

- Add time-based log partitioning (7 days per partition)
- Add automatic partition switching when full or expired
- Add automatic archiving after 30 days
- Add automatic deletion after 90 days
- Add disk space monitoring with warning/critical thresholds
- Add API endpoints for partition management

对应飞书需求池行号40:
- 防止user_interaction_logs表无限制膨胀
- 分区存储+自动归档+自动清理"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
