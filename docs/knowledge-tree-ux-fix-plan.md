# 知识树学习进度模块 UX 修复与增强计划

## 一、回答你的四个问题

### Q1: 知识专题和节点的数据来源是什么？

**不是来自知识图谱。** 专区和节点来自 `backend/algorithms/skill_tree.py`，这是一个**完全硬编码**的 6 专题 × 5~6 节点 = 33 个节点的数据结构，与知识图谱完全独立。

```
skill_tree.py（当前在用）          knowledge_graph.py（未被 UI 使用）
├── 数列基础 (5 节点)              ├── 数列基础概念 (4 专题)
├── 等差数列 (6 节点)              ├── 等差数列 (5 专题)
├── 等比数列 (6 节点)              ├── 等比数列 (5 专题)
├── 数列求和 (6 节点)              ├── 递推数列 (7 专题)
├── 递推数列 (5 节点)              ├── 数列求和 (6 专题)
└── 数学归纳法 (5 节点)            └── 数列综合应用 (5 专题)
   = 33 个硬编码节点                 = 32 个专题 × N 个叶子节点
```

### Q2: 为什么这么少？

1. **skill_tree.py 只定义 33 个节点**，这 33 个是"技能树节点"（偏游戏化设计），不是完整的知识点清单
2. **用户掌握度匹配方式有问题** — `knowledge_tree_progress.py:89-92` 用节点 `name` 去匹配 `get_user_mastery_dict()` 返回的掌握度字典，如果用户掌握的关键词和节点名称不完全一致，就返回默认值 0.5
3. **知识图谱有 32 个专题 + 大量叶子节点**，但 `KnowledgeTree.vue` 没有使用知识图谱 API，用的是技能树 API

### Q3: 里程碑达成条件

当前里程碑是**纯进度百分比阈值**，在 `knowledge_tree_progress.py:116-122`：

| 里程碑 | 前端显示名 | 触发条件 | 用户能看到吗 |
|--------|----------|---------|------------|
| `first_blood` | 首次突破 | 进度 ≥ 10% | ❌ 不知道含义 |
| `half_way` | 半程里程碑 | 进度 ≥ 50% | ❌ 不知道含义 |
| `master` | 掌握大师 | 进度 ≥ 80% | ❌ 不知道含义 |
| `explorer` | 探索者 | 进度 ≥ 60% | ❌ 不知道含义 |
| `conqueror` | 征服者 | 进度 ≥ 95% | ❌ 不知道含义 |

没有任何 hover tooltip 说明"你需要把专题进度做到 80% 才能解锁掌握大师"。

### Q4: 知识点节点长什么样？

**当前完全看不见。** 前端 `KnowledgeTree.vue` 只展示了专题层级的汇总统计（总节点数、已掌握数），**没有渲染任何具体节点**。节点名称（如"等差数列定义"、"公差与公差范围判定"）存在于后端 `skill_tree.py`，但前端代码里没有任何地方显示它们。用户只知道"这个专题有 6 个节点，你掌握了 3 个"，但不知道这 6 个节点分别是什么。

---

## 二、当前数据流（完整）

```
ProfileView.vue
  └── <KnowledgeTree :userId="...">
        └── GET /api/knowledge-tree/progress
              └── knowledge_tree_progress.py
                    ├── SkillTreeBuilder (skill_tree.py) → 6 个专题的硬编码节点
                    ├── get_user_mastery_dict(db, user_id) → {kp_name: p_known}
                    │     └── cognitive_diagnosis_service.py
                    │           └── UserKnowledgeMastery 表 (BKT P(L) 值)
                    ├── 匹配：node.name in db_mastery → p_known，否则 → 0.5
                    ├── 计算每个专题进度 = mastered_nodes / total_nodes
                    └── 里程碑 = 纯进度百分比阈值
```

---

## 三、UX 问题清单与修复方案

### 问题 1：知识点节点不可见

**现状**：展开专题后只看到 4 个数字（已掌握/学习中/薄弱/未解锁），看不到具体是哪些知识点。

**修复**：展开专题时渲染节点列表，每个节点显示：
- 名称（如"等差数列定义"、"通项公式推导与应用"）
- 状态图标（绿色勾/蓝色学习中/红色薄弱/灰色锁）
- 掌握度进度条
- 前置依赖提示（"需要先掌握：数列的通项"）

**实现**：
1. 后端 `GET /api/knowledge-tree/progress` 返回每个专题的 `nodes` 数组
2. 前端 `KnowledgeTree.vue` 展开专题时渲染节点树
3. 使用 `skill_tree.py` 中已有的 `position {x, y, level}` 做垂直层级布局

### 问题 2：里程碑无达成条件提示

**现状**：里程碑只显示🏆解锁 / 🔒锁定，用户完全不知道如何达成。

**修复**：每个里程碑添加 tooltip（title 属性或 CSS hover 浮层），显示：
- 里程碑名称
- 达成条件（具体阈值）
- 当前进度与目标的差距（"还差 30% 即可解锁"）
- 对于已解锁的：解锁时间/条件达成时的庆祝信息

**实现**：
```html
<div class="milestone-item" :title="getMilestoneTooltip(name, achieved)">
  <!-- milestone content -->
</div>
```

```javascript
const milestoneConditions = {
  first_blood: { name: '首次突破', condition: '专题进度达到 10%', icon: '🌱' },
  half_way:   { name: '半程里程碑', condition: '专题进度达到 50%', icon: '🛤️' },
  explorer:   { name: '探索者', condition: '专题进度达到 60%', icon: '🧭' },
  master:     { name: '掌握大师', condition: '专题进度达到 80%', icon: '👑' },
  conqueror:  { name: '征服者', condition: '专题进度达到 95%', icon: '🏆' },
}
```

### 问题 3：数据源太单薄（33 个硬编码节点 vs 268 个知识点标签）

**现状**：`skill_tree.py` 只有 33 个人工定义的节点，且与 `knowledge_graph.py` 中 268 个知识点标签完全脱节。

**修复**：将知识树数据源从 `skill_tree.py` 切换到 `knowledge_graph.py`：
- 知识图谱有 6 个主干（Category）→ 32 个专题（Topic）→ 大量叶子节点
- 每个叶子节点已关联了原始标签（如"等差数列通项公式应用"）
- 用户掌握度可以通过标签匹配来映射

**但注意**：这需要将 knowledge_graph 的节点体系与 BKT 掌握度数据打通。这是一个较大的工程。**短期可以先不切换数据源，而是拓展 skill_tree.py 的节点数量**。

### 问题 4：能力曲线只有一个数据点

**现状**：`ProfileView.vue` 中的能力曲线图表期望多条数据，但只从 `/api/advisor/profile` 获取一个当前快照，图表显示只有 1 个点。

**修复**：从 `user_ability_history` 表获取历史 theta 数据（该表每次答题后都会记录），用 `/api/mastery/visualization` 中已有的能力曲线端点。

### 问题 5：加载骨架屏缺失

**现状**：数据加载时只显示文字"加载中..."和一个转圈，没有占位 UI。

**修复**：添加 Skeleton 占位符（灰色块模拟卡片布局），提升感知性能。

### 问题 6：错误回退数据误导用户

**现状**：`KnowledgeTree.vue` 和 `SixDimRadarChart.vue` 在 API 失败时使用硬编码假数据，用户不知道看到的是假数据。

**修复**：
1. 回退时在 UI 中明确标注"离线数据，非真实进度"
2. 提供"重新加载"按钮，方便网络恢复后刷新
3. 记录真实数据到 localStorage，回退时优先用上次的真实数据

### 问题 7：六维能力计算需要手动触发

**现状**：雷达图有"重新计算"按钮，但用户不知道什么时候该重新计算、计算逻辑是什么。

**修复**：
1. 显示上次计算时间
2. 自动在每次答题后触发重新计算
3. "重新计算"按钮改为"刷新"辅助按钮

### 问题 8：徽章和成就未在画像页展示

**现状**：后端有完整的 `learning_habit_badge_service.py`（10 种徽章）和 `pitfall_achievement_service.py`（双列卡片），但 ProfileView 完全没有渲染。

**修复**：在 ProfileView 中新增两个板块：
1. **学习徽章墙**：调用 `GET /api/learning-badges/my-badges`，展示已获得和未获得的徽章
2. **雷区与攻克成就**：调用 `GET /api/pitfall-achievement/dual-column`，展示错误类型分析和已攻克的难关

---

## 四、实施步骤

### Phase A：必须修（紧急）

| # | 内容 | 文件 | 工作量 |
|---|------|------|--------|
| A1 | 展开专题时渲染知识点节点列表（名称+状态+进度条） | `KnowledgeTree.vue` + `knowledge_tree_progress.py` | 1.5h |
| A2 | 里程碑添加 hover tooltip 显示达成条件 | `KnowledgeTree.vue` | 0.5h |
| A3 | 里程碑区分不同程度（未达成→显示进度差距，已达成→显示达成时间） | `KnowledgeTree.vue` + `knowledge_tree_progress.py` | 0.5h |
| A4 | 错误回退时明确标注"离线数据" | `KnowledgeTree.vue` + `SixDimRadarChart.vue` | 0.5h |

### Phase B：应该修（高优先级）

| # | 内容 | 文件 | 工作量 |
|---|------|------|--------|
| B1 | 能力曲线从 `user_ability_history` 获取多条历史数据 | `ProfileView.vue` + `mastery_visualization.py` | 1h |
| B2 | 添加 Skeleton 加载骨架屏 | `ProfileView.vue` | 0.5h |
| B3 | 六维能力添加"上次计算时间"显示 + 自动刷新 | `SixDimRadarChart.vue` + 后端 | 0.5h |
| B4 | ProfileView 添加徽章墙板块 | `ProfileView.vue` + 新增组件 | 1.5h |
| B5 | ProfileView 添加雷区与攻克成就板块 | `ProfileView.vue` + 新增组件 | 1.5h |

### Phase C：锦上添花（中优先级）

| # | 内容 | 文件 | 工作量 |
|---|------|------|--------|
| C1 | 知识树切换数据源：skill_tree → knowledge_graph | 后端 + 前端 | 2-3h |
| C2 | 节点依赖关系可视化（用 SVG/Canvas 画树状图） | `KnowledgeTree.vue` | 2-3h |
| C3 | 专题间前置依赖（如"等差数列"需要在学完"数列基础"后才解锁） | `skill_tree.py` + 前端 | 1h |

---

## 五、新增/修改的 API 字段

### 修改 `GET /api/knowledge-tree/progress` 返回结构

```json
{
  "topics": [
    {
      "topic": "等差数列",
      "progress": 80,
      "progress_text": "80%",
      "status": "mastered",
      "statistics": { ... },
      "nodes": [                          // ← 新增
        {
          "node_id": "ap_001",
          "name": "等差数列定义",
          "p_known": 0.92,
          "status": "mastered",
          "position": {"x": 100, "y": 180, "level": 1},
          "prerequisites": ["base_002"],
          "prerequisite_names": ["数列的通项"]  // ← 新增
        }
      ],
      "milestones": [
        {
          "name": "first_blood",
          "display_name": "首次突破",
          "description": "专题进度达到 10%",
          "icon": "🌱",
          "threshold": 10,
          "achieved": true,
          "achieved_at": "2026-05-10T14:30:00Z"  // ← 新增
        }
      ]
    }
  ]
}
```

### 新增 API `GET /api/knowledge-tree/node/{node_id}`

获取单个知识节点的详情（包含学习建议、关联题目等）

---

## 六、验收标准

- [ ] 点击专题展开后能看到具体知识点节点名称和每个节点的掌握状态
- [ ] 鼠标悬停在里程碑上，能看到达成条件和当前进度差距
- [ ] 已解锁的里程碑显示达成时间
- [ ] API 失败时用户明确知道看到的不是真实数据
- [ ] 能力曲线显示多个历史数据点（非单点）
- [ ] 加载时有骨架屏占位，不是空白
- [ ] 画像页能看到学习徽章和雷区成就
