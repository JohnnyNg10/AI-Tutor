# 错因分析与掌握度量化：现状对比 & 实现方案

## 一、与猿辅导方案的逐项对比

### 1.1 错因分析对比

| 猿辅导五维 | 我们的现状 | 差距 |
|-----------|-----------|------|
| **知识漏洞** — 匹配知识图谱未掌握节点 | ✅ 已实现。BKT追踪每个知识点的P(L)，薄弱节点自动标红。84节点知识图谱已就绪 | 诊断说明已有但未接入错题诊断流程 |
| **思维路径** — 识别跳步、逻辑倒置 | ❌ 未实现。当前只做关键词匹配（正则），无法分析解题步骤的逻辑路径 | 需要LLM逐步比对 |
| **概念关联** — 判断是否混淆相似概念 | ❌ 未实现。知识图谱有依赖关系但无"易混淆概念对"数据 | 需要构建混淆矩阵 + LLM识别 |
| **解题习惯** — 步骤缺失、书写潦草 | ⚠️ 部分实现。`actual_score.py`追踪提示使用/跳过/耗时，`streak_handler.py`追踪连对连错，但未归类为"习惯"维度 | 需汇总为习惯画像 |
| **认知水平** — 记忆/理解/应用层级 | ⚠️ 部分实现。84节点已有`cognitive_level`字段（了解/理解/掌握/运用/综合运用），但未根据学生表现动态判定 | 需要将答题表现映射到认知层级 |

**我们已有的错因基础设施：**

```
backend/services/error_classification_service.py  → 8类错因定义 + 统计API
backend/algorithms/calculation_error_handler.py    → 4类关键词正则匹配
backend/services/pitfall_achievement_service.py    → 雷区聚类 + 成就检测
backend/api/error_classification.py                → 5个REST端点（含复健出题）
backend/services/llm_service.py                    → LLM调用能力就绪（generate_hint等）
```

**关键差距**：错因分类目前是**纯规则引擎**（正则匹配关键词），没有LLM参与的逐步推理。猿辅导的核心壁垒在于让LLM"像老师一样读懂解题过程"——这一步我们尚未启动。

### 1.2 掌握度量化对比

| 猿辅导方案 | 我们的现状 | 差距 |
|-----------|-----------|------|
| **DKT（深度知识追踪）** | ❌ 无。我们使用经典BKT（贝叶斯公式） | BKT足够轻量，但缺乏跨知识点迁移学习 |
| **IRT（项目反应理论）** | ⚠️ 极度简化。线性映射`theta = -3+6*(correct/total)`，无MLE估计 | 缺少真正的IRT参数估计（难度b、区分度a） |
| **多因子加权修正** | ⚠️ 部分实现。`actual_score.py`有4因子（正确0.6+提示0.25+时间0.1+跳过0.05），但**不参与掌握度计算** | actual_score未融入BKT的P(L)更新 |
| **四级掌握度** | ❌ 三级。薄弱(<0.5)/学习中(0.5-0.8)/已掌握(≥0.8) | 缺少"合格"和"良好"的中间档位 |
| **答题时长熵** | ⚠️ 追踪了time_spent但未建模 | 数据存在，缺分析 |
| **错因严重程度加权** | ❌ 无。所有错误同等对待 | 需要区分"概念混淆"vs"粗心"的权重 |
| **题目综合度权重** | ❌ 无。所有题目权重相同 | 需要利用题目的`difficulty`和`knowledge_points` |

**我们已有的算法栈：**

```
backend/algorithms/bkt.py              → BKT贝叶斯更新（p_learn=0.3, p_guess=0.2, p_slip=0.1）
backend/algorithms/irt_simple.py       → IRT简化版 + K-IRT联合估计
backend/algorithms/actual_score.py     → 4因子实际得分（正确/提示/时间/跳过）
backend/algorithms/adaptive_k.py       → 自适应学习率（基于theta变化方向）
backend/algorithms/memory_decay.py     → 记忆衰减（7天半衰期 + 每日cron）
backend/algorithms/streak_handler.py   → 连击状态追踪（仅内存）
backend/services/cognitive_diagnosis_service.py → 主诊断流程
```

---

## 二、我们的优势（千问方案未考虑到的）

1. **84节点知识图谱已就绪** — 完整的高中数列知识体系，含前置依赖、认知层级、诊断说明、标签映射
2. **BKT+IRT+记忆衰减+自适应K+实际得分** — 5个算法已实现并协同工作，只是缺少最后的融合层
3. **错误分类+雷区成就+复健出题** — 完整的错题→诊断→补救闭环已搭好骨架
4. **LLM服务已就绪** — `llm_service.py`有完整的逐步提示能力，可直接复用于错误诊断
5. **前后端数据流通畅** — API→Service→Algorithm→DB→Redis全链路已打通

---

## 三、改进方案：分三阶段实施

### Phase 1：强化掌握度量化（1-2天，改动最小，收益最大）

#### 1.1 三级→四级掌握度

修改阈值，增加"良好"档位：

| 级别 | 阈值 | 颜色 | 含义 |
|------|------|------|------|
| 薄弱 | P(L) < 0.4 | 红色 #EF4444 | 需重新学习 |
| 合格 | 0.4 ≤ P(L) < 0.65 | 橙色 #F97316 | 需针对性刷题 |
| 良好 | 0.65 ≤ P(L) < 0.85 | 蓝色 #3B82F6 | 需拓展拔高 |
| 精通 | P(L) ≥ 0.85 | 绿色 #10B981 | 可进入下一专题 |

**改动文件**：
- `backend/algorithms/bkt.py` → `get_mastery_level()` 返回4级
- `backend/algorithms/skill_tree.py` → `NodeStatus` 增加 `QUALIFIED`、`PROFICIENT`
- `backend/services/mastery_visualization_service.py` → 颜色映射增加橙色
- `frontend/components/KnowledgeTree.vue` → 图例和节点颜色增加橙色

#### 1.2 多因子加权融合

将 `actual_score` 融入 BKT 的 P(L) 更新，替代当前的二元（对/错）输入：

```python
# 当前：只根据对错更新
p_known_new = bkt.update(p_known_old, is_correct)  # is_correct ∈ {0, 1}

# 改进：用 actual_score 替代二元输入
actual_score = calculate(correctness, hint_level, time_spent, expected_time, skip_reason)
# actual_score ∈ [0, 1]，是连续值
# 例如：做对了但用了L4提示 → actual_score = 0.6（而非1.0）
p_known_new = bkt.update_continuous(p_known_old, actual_score)
```

BKT需要增加一个 `update_continuous()` 方法，接收连续观测值而非二值。

**改动文件**：
- `backend/algorithms/bkt.py` → 增加 `update_continuous(p_known, score)`
- `backend/services/cognitive_diagnosis_service.py` → `update_knowledge_mastery()` 改用连续值

#### 1.3 统一两套BKT参数

当前 `cognitive_diagnosis_service.py`（p_learn=0.3）和 `learning_analytics_service.py`（p_transit=0.15）使用了不同的学习转移概率。

**改动**：统一使用 `BKTParams` 单例，`p_learn=0.3`。

---

### Phase 2：LLM驱动的错因诊断（2-3天，核心壁垒）

#### 2.1 错因诊断Prompt设计

复用在 `llm_service.py` 现有的 LLM 调用能力，增加专门的错因分析prompt：

```
系统指令：你是一位高中数学特级教师，专精于诊断学生的解题错误根因。

输入：
1. 题目内容 + 标准解答
2. 学生的作答步骤和最终答案
3. 学生在该知识点的历史掌握度 P(L) = {p_known}

请从以下五个维度分析学生的错误：

1. 知识漏洞：学生缺少哪个具体知识点？匹配知识图谱节点。
2. 思维路径：学生的解题思路在哪里偏离了标准路径？是跳步、倒置还是选择了错误方法？
3. 概念关联：学生是否混淆了相似概念？（如等差中项 vs 等比中项）
4. 解题习惯：是否存在审题遗漏、步骤跳跃、不验证等习惯问题？
5. 认知水平：学生的表现处于记忆/理解/应用/综合运用哪个层级？题目要求的层级是否超出学生当前水平？

返回JSON：
{
  "primary_error_dimension": "知识漏洞",
  "dimensions": {
    "知识漏洞": {"score": 0.8, "matched_node_id": "ap_003", "detail": "..."},
    "思维路径": {"score": 0.3, "detail": "..."},
    "概念关联": {"score": 0.1, "detail": "..."},
    "解题习惯": {"score": 0.2, "detail": "..."},
    "认知水平": {"score": 0.5, "detail": "..."}
  },
  "diagnosis_summary": "...",
  "remediation_suggestion": "...",
  "recommended_exercises_node_ids": ["ap_003", "ap_004"]
}
```

#### 2.2 错因权重融入掌握度更新

不同错因对P(L)的扣分权重不同：

| 错因维度 | 权重 | 理由 |
|---------|------|------|
| 概念关联（混淆） | 0.9 | 概念混淆说明基础不牢，需大幅降权 |
| 知识漏洞（缺失） | 0.8 | 根本不知道这个知识点 |
| 思维路径（方法错） | 0.6 | 知道但不会用 |
| 认知水平（超纲） | 0.3 | 不是学生的问题，题目太难 |
| 解题习惯（粗心） | 0.2 | 会做但粗心，轻微降权 |

```python
# 融入BKT更新
severity_weight = error_dimension_weights[primary_dimension]
adjusted_score = actual_score * (1 - severity_weight * error_confidence)
p_known_new = bkt.update_continuous(p_known_old, adjusted_score)
```

#### 2.3 新增API端点

```
POST /api/error-classification/diagnose
  请求：{ question_id, user_answer_steps[], final_answer, time_spent }
  响应：{ primary_dimension, dimensions{}, diagnosis_summary, matched_nodes[] }
```

**改动文件**：
- `backend/services/error_diagnosis_service.py` → **新建**，LLM错因诊断核心
- `backend/api/error_classification.py` → 增加 `/diagnose` 端点
- `backend/services/cognitive_diagnosis_service.py` → 融入错因权重

---

### Phase 3：跨知识点迁移 & 能力曲线（2-3天，长期壁垒）

#### 3.1 知识点相关性矩阵

基于知识图谱的依赖关系，构建知识点间的转移概率：

```
如果学生掌握了 ap_001（等差数列定义）
→ ap_002（等差数列通项）的学习速度应该加快20%
→ gp_001（等比数列定义）不受直接影响

实现：在BKT更新时，对关联节点施加衰减的增量
mastery_boost(child_node) += 0.05 * mastery_gain(parent_node)
```

#### 3.2 能力曲线数据填充

`UserAbilityHistory` 表已存在但从未写入。每次答题后记录 theta 快照：

```python
# 在 cognitive_diagnosis_service.py 的 update_knowledge_mastery() 末尾增加：
ability_record = UserAbilityHistory(
    user_id=user_id,
    theta=theta_info['theta'],
    theta_se=theta_info['theta_se'],
    recorded_at=datetime.now()
)
db.add(ability_record)
```

这样前端的能力曲线图就能从模拟数据切换为真实历史数据。

#### 3.3 学习习惯画像

汇总 `actual_score` 的4个因子，形成用户习惯画像：

```python
# 基于最近50次答题的聚合统计
habit_profile = {
    "independence_score": 1 - avg_hint_usage,      # 独立性（少用提示=高分）
    "persistence_score": avg_time_on_hard,          # 坚持度（难题上花时间）
    "caution_score": 1 - careless_error_rate,       # 细致度（粗心错误少=高分）
    "efficiency_score": min(1, expected_time/avg_time), # 效率
}
```

存入 `UserProfile.learning_style` 字段，前端在画像页展示。

---

## 四、实施优先级总结

| 阶段 | 内容 | 工作量 | 效果 |
|------|------|--------|------|
| Phase 1.1 | 三级→四级掌握度 | 0.5天 | 立即改善诊断精度 |
| Phase 1.2 | Actual Score融入BKT | 0.5天 | 掌握度更平滑、更真实 |
| Phase 1.3 | 统一BKT参数 | 0.5天 | 消除双轨不一致 |
| **Phase 1 合计** | | **1-2天** | **掌握度量化基本对标** |
| Phase 2.1 | LLM错因诊断Prompt | 1天 | 核心壁垒建立 |
| Phase 2.2 | 错因权重融入 | 0.5天 | 诊断→掌握度闭环 |
| Phase 2.3 | 诊断API端点 | 0.5天 | 前端可接入 |
| **Phase 2 合计** | | **2天** | **错因分析基本对标** |
| Phase 3.1 | 知识点相关性 | 1天 | 长期学习迁移建模 |
| Phase 3.2 | 能力曲线真实数据 | 0.5天 | 图表从假变真 |
| Phase 3.3 | 学习习惯画像 | 1天 | 新维度用户画像 |
| **Phase 3 合计** | | **2-3天** | **完整对标+超越** |

---

## 五、立即可开始的行动

**今天就能做、收益最高的3件事**：

1. **四级掌握度**（改3个文件，1小时内完成）— 直接提升诊断分辨率
2. **Actual Score融入BKT**（改2个文件，1小时内完成）— 让掌握度从"只看对错"变成"看过程质量"
3. **填充UserAbilityHistory**（加5行代码）— 让能力曲线图从假数据变成真数据
