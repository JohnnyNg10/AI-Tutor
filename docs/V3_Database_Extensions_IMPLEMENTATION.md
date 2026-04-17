# V3 数据库表扩展实现文档

**需求编号**: 需求34, 35, 36, 37  
**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

实现V3版本数据库表扩展和数据迁移：
- **需求34**: 扩展learning_records表（新增交互行为字段）
- **需求35**: 扩展user_profiles表和user_knowledge_mastery表（新增BKT/IRT参数）
- **需求36**: 创建新表（user_ability_history, user_interaction_logs等）
- **需求37**: 解决V2到V3的数据断层问题

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/database/migrations/v3_schema_extensions.py` | 表结构迁移脚本 | ~450行 |
| `backend/services/data_migration_service.py` | 数据迁移服务 | ~500行 |
| `backend/api/migration.py` | 数据迁移API | ~300行 |

---

## 3. 表结构变更详情

### 3.1 需求34: learning_records表扩展

**新增字段：**

| 字段名 | 类型 | 默认值 | 说明 |
|-------|------|-------|------|
| hint_count | INT | 0 | 提示使用次数 |
| time_spent | INT | NULL | 答题耗时（秒） |
| skip_reason | VARCHAR(20) | NULL | 跳过原因 |
| theta_before | FLOAT | NULL | 答题前能力值 |
| theta_after | FLOAT | NULL | 答题后能力值 |
| mastery_updates | JSON | NULL | 各知识点掌握度更新 |

**SQL:**
```sql
ALTER TABLE learning_records 
ADD COLUMN hint_count INT DEFAULT 0,
ADD COLUMN time_spent INT,
ADD COLUMN skip_reason VARCHAR(20),
ADD COLUMN theta_before FLOAT,
ADD COLUMN theta_after FLOAT,
ADD COLUMN mastery_updates JSON;
```

### 3.2 需求35: user_profiles表扩展

**新增字段：**

| 字段名 | 类型 | 默认值 | 说明 |
|-------|------|-------|------|
| theta | FLOAT | NULL | 当前IRT能力值 |
| theta_se | FLOAT | NULL | 标准误差 |
| theta_ci_lower | FLOAT | NULL | 95%置信区间下限 |
| theta_ci_upper | FLOAT | NULL | 95%置信区间上限 |
| avg_mastery | FLOAT | NULL | 平均掌握度 |
| weak_kp_count | INT | 0 | 薄弱知识点数量 |
| learning_style | VARCHAR(20) | NULL | 学习风格 |
| mastery_strategy | VARCHAR(20) | 'simple' | 掌握度计算策略 |

### 3.3 需求35: user_knowledge_mastery表扩展

**新增BKT参数字段：**

| 字段名 | 类型 | 默认值 | 说明 |
|-------|------|-------|------|
| p_guess | FLOAT | 0.2 | 猜测概率 P(G) |
| p_slip | FLOAT | 0.1 | 失误概率 P(S) |
| p_known | FLOAT | 0.5 | 当前掌握概率 P(L) |
| consecutive_correct | INT | 0 | 连续正确次数 |
| consecutive_wrong | INT | 0 | 连续错误次数 |

### 3.4 需求36: 新表创建

#### user_ability_history表

```sql
CREATE TABLE user_ability_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    theta FLOAT NOT NULL,
    theta_se FLOAT,
    theta_ci_lower FLOAT,
    theta_ci_upper FLOAT,
    avg_mastery FLOAT,
    weak_kp_count INT DEFAULT 0,
    total_questions INT DEFAULT 0,
    correct_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id_created_at (user_id, created_at)
);
```

#### user_interaction_logs表

```sql
CREATE TABLE user_interaction_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    session_id VARCHAR(64),
    question_id VARCHAR(64),
    action_type VARCHAR(50) NOT NULL,
    action_detail JSON,
    hint_level INT,
    time_spent INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id_created_at (user_id, created_at),
    INDEX idx_session_id (session_id)
);
```

#### review_queue_settings表

```sql
CREATE TABLE review_queue_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    question_id VARCHAR(64) NOT NULL,
    error_count INT DEFAULT 1,
    next_review_at DATETIME NOT NULL,
    review_stage INT DEFAULT 0,
    is_mastered BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id_next_review (user_id, next_review_at),
    UNIQUE INDEX idx_user_id_question (user_id, question_id)
);
```

---

## 4. 数据迁移策略（需求37）

### 4.1 迁移流程

```
┌─────────────────────────────────────────────────────────────┐
│                      V2 数据                                 │
│  - user_profiles (旧字段)                                    │
│  - user_knowledge_mastery (旧字段)                           │
│  - learning_records (旧字段)                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      数据迁移                                │
│  1. 计算默认值                                               │
│  2. 填充缺失字段                                             │
│  3. 创建历史记录                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      V3 数据                                 │
│  - user_profiles (扩展字段)                                  │
│  - user_knowledge_mastery (BKT参数)                          │
│  - learning_records (交互行为)                               │
│  - user_ability_history (新增)                               │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 默认值计算规则

| 表 | 字段 | 默认值计算规则 |
|-----|------|---------------|
| user_profiles | theta | 0.0（新用户默认值） |
| user_profiles | theta_se | 1.0（标准误差） |
| user_profiles | theta_ci_lower/upper | -2.0 / 2.0（95%置信区间） |
| user_knowledge_mastery | p_known | 根据mastery_level映射 |
| user_knowledge_mastery | p_guess/p_slip | 0.2 / 0.1（BKT硬指标） |
| learning_records | hint_count | 0（无法 retroactively 计算） |
| learning_records | theta_before/after | 根据is_correct推断 |

---

## 5. API接口

### 5.1 执行表结构迁移

```http
POST /migration/schema
```

**响应：**
```json
{
  "success": true,
  "message": "数据库表结构迁移完成",
  "details": {
    "extend_learning_records": true,
    "extend_user_profiles": true,
    "extend_user_knowledge_mastery": true,
    "create_user_ability_history": true,
    "create_user_interaction_logs": true,
    "create_review_queue_settings": true
  }
}
```

### 5.2 执行数据迁移

```http
POST /migration/data
```

**响应：**
```json
{
  "success": true,
  "message": "数据迁移完成",
  "results": {
    "user_profiles": {
      "total": 100,
      "migrated": 100,
      "failed": 0
    },
    "user_knowledge_mastery": {
      "total": 500,
      "migrated": 500,
      "failed": 0
    }
  }
}
```

### 5.3 获取迁移状态

```http
GET /migration/status
```

**响应：**
```json
{
  "success": true,
  "schema_migrated": true,
  "data_migrated": true,
  "pending_tables": [],
  "consistency_issues": []
}
```

---

## 6. 验收标准

### 6.1 表结构验收

- [x] learning_records表新增6个字段
- [x] user_profiles表新增8个字段
- [x] user_knowledge_mastery表新增5个字段
- [x] user_ability_history表创建成功
- [x] user_interaction_logs表创建成功
- [x] review_queue_settings表创建成功

### 6.2 数据迁移验收

- [x] 老用户数据自动填充默认值
- [x] mastery_level正确映射到p_known
- [x] 数据一致性检查通过
- [x] 迁移过程可回滚

---

## 7. Git提交记录

```bash
git add backend/database/migrations/v3_schema_extensions.py
git add backend/services/data_migration_service.py
git add backend/api/migration.py
git add docs/V3_Database_Extensions_IMPLEMENTATION.md

git commit -m "feat: Implement V3 database schema extensions (Req 34-37)

- Add learning_records table extensions (hint_count, time_spent, etc.)
- Add user_profiles table extensions (theta, BKT/IRT params)
- Add user_knowledge_mastery table extensions (p_guess, p_slip, p_known)
- Create new tables: user_ability_history, user_interaction_logs, review_queue_settings
- Add data migration service for V2 to V3 compatibility
- Add migration API endpoints

Closes requirements #34, #35, #36, #37"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
