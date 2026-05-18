# BKT 掌握度量化 & 数据埋点系统 — 开发记录

> 日期：2026-05-18
> 分支：`feat/bkt-knowledge-alignment`

---

## 一、掌握度量化改造

### 1.1 统一 BKT 参数

**问题**：`learning_analytics_service.py` 硬编码 `p_transit = 0.15`，与 `bkt.py` 中 `BKTParams.p_learn = 0.3` 不一致。

**修复**：`learning_analytics_service.py` 改为导入 `BKTParams`，统一使用 `p_learn = 0.3`。

### 1.2 三级 → 四级掌握度

| 级别 | 阈值 | 颜色 | 含义 |
|------|------|------|------|
| 薄弱 (weak) | P(L) < 0.4 | 红色 #EF4444 | 需重新学习 |
| 合格 (qualified) | 0.4 ≤ P(L) < 0.65 | 橙色 #F97316 | 需针对性刷题 |
| 良好 (proficient) | 0.65 ≤ P(L) < 0.85 | 蓝色 #3B82F6 | 需拓展拔高 |
| 精通 (mastered) | P(L) ≥ 0.85 | 绿色 #10B981 | 可进入下一专题 |

**改动文件**：
- `backend/algorithms/bkt.py` — `get_mastery_level()` 四级阈值
- `backend/algorithms/skill_tree.py` — `NodeStatus` 新增 `PROFICIENT`、`QUALIFIED`，阈值常量更新
- `backend/services/cognitive_diagnosis_service.py` — 四级统计输出

### 1.3 Actual Score 融入 BKT — `update_continuous()`

**问题**：原有 `update()` 只接受二元对错，无法利用 `ActualScoreCalculator` 的四因子连续得分（正确性 0.6 + 提示使用 0.25 + 时间效率 0.1 + 跳过行为 0.05）。

**实现**：新增 `update_continuous(p_known, actual_score)` 方法：
- 将 `actual_score ∈ [0,1]` 视为"有效正确程度"
- 分别计算正确/错误两条贝叶斯后验路径，按 score 线性插值
- 边界一致性：`update_continuous(1.0) ≡ update(True)`、`update_continuous(0.0) ≡ update(False)`
- 重构抽取 `_bayesian_update()` 私有方法消除重复

**改动文件**：`backend/algorithms/bkt.py`

### 1.4 UserAbilityHistory 写入

**问题**：表已存在但从未写入，前端能力曲线图使用模拟数据。

**实现**：`cognitive_diagnosis_service.py` 新增 `_record_ability_snapshot()`，每次 `update_knowledge_mastery()` 后自动写入 theta 快照。

### 1.5 OCR 手写识别 API

**新建** `backend/api/ocr.py`，`POST /api/ocr/parse`：
- 接收图片上传 → 调用硅基流动视觉模型 → 返回识别文本
- 识别完成自动清理临时文件

### 1.6 前端 API 补充

`frontend/services/apiService.js` 新增三个模块：
- `errorDiagnosisAPI` — `POST /error-classification/diagnose`
- `ocrAPI` — `POST /api/ocr/parse`
- `knowledgeTreeAPI` — 知识树节点/专题查询

---

## 二、数据埋点系统

### 2.1 前端埋点 SDK

**新建** `frontend/services/analytics.js`：

- `trackEvent(name, data)` 统一入口，17 类事件标准化上报
- 自动上下文注入：session_id、timestamp、device_type、page_url
- 批量发送：60 秒定时 flush + 20 条阈值触发，keepalive 防丢失
- 自动采集：session_start、session_heartbeat(60s)、session_end、page_view
- 语义化 API：`analytics.hintRequest()`、`analytics.answerSubmit()` 等

**初始化**：`frontend/main.js` 中 `initAnalytics(router)`

### 2.2 后端事件接收

**新建** `backend/api/analytics.py`，`POST /api/analytics/events`：
- 批量接收（上限 100 条/次），JWT 自动解析 user_id
- 原生 SQL INSERT，绕过 ORM 序列化开销
- 每条事件提取 `cognitive_signal`（行为 → 认知维度映射）

**数据库扩展**：
- `user_interaction_logs` 新增 `event_name`、`soft_label_dimension`、`cognitive_signal` 列
- 新建 `user_soft_labels` 表

**模型更新**：`backend/models/learning_analytics.py` 新增 `UserSoftLabel` 模型

### 2.3 六维软标签计算引擎

**新建** `backend/services/soft_label_service.py`：

| 维度 | 核心算法 | 窗口 |
|------|---------|------|
| 自主性 | 提示层级惩罚 + 答对未求助比例 | 最近 20 题 |
| 坚持性 | 重试加分 + 跳过惩罚 + 困难题完成率 | 最近 20 题 |
| 元认知 | 自评 vs 实际偏差 | 最近 80 条 |
| 求助效率 | 提示递进模式 + 消化深度 + 转化率 | 最近 20 次 |
| 反思深度 | 方案页滚动 + 停留时长 + 答对仍看解析 | 最近 7 天 |
| 知识迁移 | 跨知识点 vs 单知识点正确率差值 | 最近 30 题 |

### 2.4 Advisor 软标签联合判定

**修改** `backend/agent/advisor.py`：

模式判定从纯 mastery 升级为 mastery + 软标签联合判定：

| 模式 | 条件 |
|------|------|
| SCAFFOLD | avg_mastery < 0.4 OR 自主性 < 30 OR 坚持性 < 25 |
| CHALLENGE | avg_mastery > 0.8 AND 自主性 > 60 AND 迁移能力 > 50 |
| ENCOURAGE | 其余情况 |

---

## 三、数据流全景

```
前端 trackEvent()
  → 批量 buffer (60s / 20条)
  → POST /api/analytics/events
  → user_interaction_logs (+ cognitive_signal)
  → SoftLabelEngine (每日计算)
  → user_soft_labels
  → Advisor._determine_advisor_mode() 联合判定
  → 四种教学模式自动切换
```

---

## 四、文件清单

### 新建文件
| 文件 | 用途 |
|------|------|
| `backend/api/ocr.py` | OCR 手写识别端点 |
| `backend/api/analytics.py` | 埋点事件接收端点 |
| `backend/services/soft_label_service.py` | 六维软标签计算引擎 |
| `frontend/services/analytics.js` | 前端埋点 SDK |

### 修改文件
| 文件 | 改动 |
|------|------|
| `backend/algorithms/bkt.py` | `update_continuous()` + 四级掌握度 |
| `backend/algorithms/skill_tree.py` | NodeStatus 四级 + 阈值更新 |
| `backend/services/cognitive_diagnosis_service.py` | 四级统计 + UserAbilityHistory 写入 |
| `backend/services/learning_analytics_service.py` | 统一 BKT 参数 |
| `backend/agent/advisor.py` | 软标签联合判定 |
| `backend/api/__init__.py` | 注册 ocr + analytics 路由 |
| `backend/models/learning_analytics.py` | UserSoftLabel 模型 + 字段扩展 |
| `database/schema.sql` | 表结构扩展 |
| `frontend/main.js` | 初始化 analytics SDK |
| `frontend/services/apiService.js` | 新增 errorDiagnosis/ocr/knowledgeTree API |
