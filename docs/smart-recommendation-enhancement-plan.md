# 智能推题模块增强开发计划

> 版本：v1.0
> 日期：2026-05-15
> 基于：现有代码审计 + AI批改模块方案 + 竞品分析

---

## 一、产品定位分析

### 1.1 三个模块的角色重新定义

当前项目有三个与"做题"相关的模块，但角色模糊：

| 模块 | 当前状态 | 应有定位 |
|------|---------|---------|
| **AI问答** (AiTutorView) | 自由提问+苏格拉底教学 | 辅助答疑入口（轻量、自由） |
| **智能推题** (RecommendView) | 答题→批改→下一题 | **产品主界面**（核心学习闭环） |
| **AI批改** (GradingView) | 上传试卷→批量批改→报告 | 考试/作业场景（重操作、批量） |

**核心判断**：智能推题应该是产品的主入口，因为它同时承载：
1. **个性化推荐** — 基于画像精准出题
2. **引导式教学** — 学生卡住时的苏格拉底式引导
3. **画像数据采集** — 答题行为是画像更新的最大数据源
4. **错因诊断** — 每道错题都是诊断机会
5. **能力成长** — 连续使用后能力曲线的核心数据来源

### 1.2 学生刷题场景的痛点挖掘

学生在刷题过程中的真实痛点：

```
痛点1: 卡住了没人帮
"做到第3步不会了，旁边没人问，只能看答案。看完答案又觉得没学到东西。"

痛点2: 做错了不知道为什么错
"答案说选C。我知道我错了，但我不知道我为什么错。
 是公式记错了？还是思路压根不对？"

痛点3: 手写习惯无法保留
"我都习惯在草稿纸上写过程，拍照上传还要重新打字，太麻烦了。"

痛点4: 不知道下一步该练什么
"做完这套题，分数出来了。但接下来我该重点练哪个知识点？
 继续刷整套？还是针对薄弱点专项练？"

痛点5: 重复做已经会了的题
"系统老是推我会做的等差数列，等比数列求和我一直不会，它就是不推。"

痛点6: 挫败感积累
"连着错了5道题，越做越烦躁，不想继续了。"
```

**AI Tutor应该提供的体验**：

```
痛点1 → 引导式教学：不直接给答案，分步引导，让学生自己推导
痛点2 → 错因诊断：每道错题精确分析错误类型 + 给出改进建议
痛点3 → OCR手写识别：拍照上传草稿，AI识别+用户校对
痛点4 → 智能推荐：基于画像精准定位下一个该练的知识点
痛点5 → 薄弱点优先：BKT追踪 + 复习队列调度，不会的反复练
痛点6 → 情感感知：检测挫败→鼓励→降难度→小成就→恢复信心
```

---

## 二、当前代码现状 vs 应有状态

### 2.1 智能推题 (RecommendView) 现状

```
当前流程：
  Advisor推荐5题 → 学生选择/输入答案 → 判对错 → AI诊断文字 → 下一题
                                    └→ 错题入复习队列 ─┘

缺失的关键环节：
  ✗ 没有OCR手写识别（只能打字或点选）
  ✗ 没有L0-L4渐进式提示按钮（卡住了要么跳过要么看答案）
  ✗ 没有多轮引导修正循环（做错了→看诊断→下一题，没有重试）
  ✗ 没有错因分类标签展示（AI诊断是自由文本，未结构化）
  ✗ 没有针对错因的即时补救练习
  ✗ 没有本轮学习目标展示（就是一串题目，不知道要学什么）
  ✗ 没有情感状态检测与自适应调整
```

### 2.2 已有但未接入的能力

这些代码已经写好，但**没有接入RecommendView**：

| 已有能力 | 代码位置 | 当前在哪用 |
|---------|---------|-----------|
| L0-L4渐进式提示 | `hint_generator.py` + `llm_service.py` | AiTutorView |
| OCR手写识别 | `multimodal/image_parser.py` | AiTutorView（仅文本提取） |
| 苏格拉底式引导教学 | `agent/instructor.py` + `agents/instructor_agent.py` | AiTutorView |
| 4种Advisor教学模式 | `agents/advisor_agent.py` | 已生成指令但未传递到前端 |
| 错因分类体系 | `error_classification_service.py` | 错误分类API（独立端点） |
| 情感感知 | `agents/instructor_agent.py` | AiTutorView |
| 复习队列调度 | `redis_service.py` + `advisor.py` | 后端自动（前端不感知） |
| 每日特训包 | `daily_training_pack.py` | 独立端点，未集成到RecommendView |

### 2.3 AI批改模块可复用的能力

AI批改方案中的以下设计可以直接复用到RecommendView：

| AI批改能力 | RecommendView复用方式 |
|-----------|---------------------|
| OCR+校对面板 | 单题答题时，学生拍照上传草稿→OCR→校对→提交 |
| 步骤级分析 | 大题答题时，AI逐步骤检查，给出步骤级对错 |
| 错因归类 | 答错后自动分类（概念/过程/计算/审题/格式） |
| 知识点掌握度推算 | 每题关联知识点后更新BKT |
| 批改报告中的错因分布 | 每轮5题完成后展示本轮错因分布 |

---

## 三、改造方案：六阶段实施

### Phase 1：单题答题体验升级（核心交互闭环）

**目标**：把RecommendView从"答题→下一题"变成"答题→引导→理解→再试→掌握"

#### 1.1 增加L0-L4渐进式提示按钮

在每道题下方增加提示按钮条：

```
┌─────────────────────────────────────────────┐
│  题目：已知等差数列{an}中，a₃=7, a₇=15...    │
│                                             │
│  [学生答题区 — 文本输入 or OCR上传]           │
│                                             │
│  ┌─ 提示按钮 ─────────────────────────────┐  │
│  │ [💡 L1 方向提示] [📐 L2 相关公式]       │  │
│  │ [📝 L3 关键步骤] [📖 L4 完整解析]       │  │
│  │ 已使用提示：L1 ✓  (Actual Score扣分: -5) │  │
│  └────────────────────────────────────────┘  │
│                                             │
│  [提交答案]  [跳过：太难了]  [跳过：太简单]   │
└─────────────────────────────────────────────┘
```

**改动**：
- `frontend/pages/RecommendView.vue` — 增加HintButton组件
- `backend/api/llm.py` 或新建端点 — 按需生成L0-L4提示
- 提示使用记录影响Actual Score（已实现，只需接入）

#### 1.2 OCR手写答题

增加图片上传按钮，学生可拍照上传草稿纸：

```
点击"上传草稿" → Qwen-VL OCR识别 → 显示识别文本 → 学生校对修改 → 确认提交
```

复用AI批改模块的OCR+校对面板设计。

#### 1.3 答错后的多轮引导修正

```
当前：答错 → 显示"正确答案是C" → 下一题

改为：
答错 → 错因诊断(LLM) → 展示具体错误位置和原因 →
   ┌─ 引导重试 ──────────────────────────────┐
   │ "你的第2步：将a₇=15代入时，应该是          │
   │  a₁+6d=15，你写成了a₁+7d=15。             │
   │  这是下标计算出错。请修改这一步后重新提交。" │
   │                                           │
   │  [修改后重新提交]  [看完整解析]  [下一题]  │
   └───────────────────────────────────────────┘
```

**核心逻辑**：不是所有错题都需要重试。判断标准：
- **概念错误** (concept_error) → 需要重试，因为"不会做"
- **计算错误** (calculation_error) → 提示定位即可，不需要重试
- **审题错误** (reading_error) → 提示即可，不需要重试

**改动**：
- `backend/services/error_diagnosis_service.py` — **新建**，LLM错因诊断
- `frontend/pages/RecommendView.vue` — 增加引导重试交互

---

### Phase 2：学习目标与进度可视化

**目标**：每轮推荐不是"随机5道题"，而是"本节学习目标：掌握X、巩固Y"

#### 2.1 轮次学习目标展示

```
┌─────────────────────────────────────────────┐
│  📋 本节学习目标                              │
│  🎯 重点攻克：错位相减法（当前掌握度 35%）       │
│  🔄 巩固复习：等比数列求和公式（7天未练）        │
│  📊 预计题量：5-8题                           │
│                                             │
│  进度：■■■■□□□□□□ 2/5 题已完成               │
└─────────────────────────────────────────────┘
```

**数据来源**：
- 重点攻克：`get_weakest_nodes()` 返回的最薄弱节点
- 巩固复习：Redis复习队列中的到期题目
- 预计题量：基于薄弱知识点数量动态计算

#### 2.2 轮次完成总结

```
┌─────────────────────────────────────────────┐
│  🎉 本节完成！                               │
│                                             │
│  正确率：3/5 (60%)                           │
│  掌握度变化：                                 │
│    错位相减法：35% → 52% ↑ +17%              │
│    等比数列求和：70% → 72% ↑ +2%             │
│                                             │
│  错因分布：                                   │
│    计算错误：1次  概念错误：1次               │
│                                             │
│  🏆 成就解锁：首次突破（错位相减法>50%）        │
│                                             │
│  下一步建议：错位相减法还需巩固（52%），         │
│  建议休息5分钟后继续专项练习。                  │
│                                             │
│  [继续下一轮]  [针对性练习错位相减法]  [休息]   │
└─────────────────────────────────────────────┘
```

**改动**：
- `frontend/pages/RecommendView.vue` — 增加轮次头+总结面板
- `backend/agent/advisor.py` — 推荐接口增加学习目标字段

---

### Phase 3：错因诊断引擎接入

**目标**：每道错题都经过LLM诊断，输出结构化错因

#### 3.1 错因诊断服务

新建 `backend/services/error_diagnosis_service.py`：

```python
class ErrorDiagnosisService:
    """基于LLM的错因诊断服务"""

    async def diagnose(
        question: QuestionInfo,       # 题目内容+标准答案+知识点
        student_answer: str,          # 学生答案（经OCR+校对）
        user_mastery: Dict[str, float],  # 学生当前掌握度
        hint_levels_used: int         # 使用了多少提示
    ) -> ErrorDiagnosisResult:
        """
        返回结构化诊断结果：
        - primary_error_type: ErrorType枚举
        - error_location: 出错步骤
        - error_detail: 具体描述
        - matched_kp_node_id: 匹配的知识图谱节点
        - severity_weight: 严重程度权重
        - remediation_hint: 针对性引导提示
        - should_retry: 是否需要重试
        """
```

#### 3.2 错因→画像联动

答错后，根据错因类型应用不同权重更新BKT：

```
CONCEPT_ERROR  → P(L)衰减 ×1.5 → 大幅降掌握度
PROCESS_ERROR  → P(L)衰减 ×1.2 → 适度降掌握度
CALCULATION_ERROR → P(L)衰减 ×0.7 → 小幅降掌握度
READING_ERROR  → P(L)衰减 ×0.5 → 最低影响
```

#### 3.3 错题本自动收录

答错的题目自动进入错题本，带错因标签：
```python
mistake_record = {
    "question_id": ...,
    "error_type": "CALCULATION_ERROR",
    "error_tags": ["下标计算出错", "等差数列通项"],
    "wrong_answer": "a₁+7d=15",
    "correct_answer": "a₁+6d=15",
    "knowledge_point_id": "ap_002",
    "created_at": "2026-05-15T14:30:00Z"
}
```

---

### Phase 4：Advisor教学模式真正落地

**目标**：让4种教学模式真正控制前端的教学行为

#### 4.1 模式→行为映射

| 模式 | 触发条件 | 前端行为 |
|------|---------|---------|
| **SCAFFOLD** (脚手架) | 薄弱知识点 P(L)<0.4 | L1提示默认展开、每题后追问"这一步理解了吗？"、答错必须重试 |
| **NORMAL** (正常) | 0.4≤P(L)<0.7 | 标准5题、提示按钮可用、答错可选择重试或跳过 |
| **CHALLENGE** (挑战) | 知识点已掌握 P(L)≥0.8 | 提高难度(θ+0.3)、隐藏L1-L2提示只保留L3-L4、鼓励独立思考 |
| **ENCOURAGE** (鼓励) | 连续错误≥3题 | 降低难度(θ-0.3)、优先出已做对的题型重建信心、"你已经很努力了"等情感支持文案 |

#### 4.2 Advisor指令流

```
后端 Advisor Agent
  │
  ├→ 生成 advisor_mode (SCAFFOLD/CHALLENGE/ENCOURAGE/NORMAL)
  ├→ 生成 advisor_instruction (给Instructor的教学指令)
  ├→ 控制题目难度区间
  ├→ 控制每轮题目数量
  └→ 控制是否强制重试
        │
        ▼
  前端 RecommendView
  ├→ 展示Advisor模式卡片
  ├→ 调整提示按钮行为
  ├→ 调整重试/跳过逻辑
  └→ 展示教学模式说明
```

---

### Phase 5：画像数据采集闭环

**目标**：RecommendView成为画像数据的最大来源

#### 5.1 每次答题记录的数据

```python
answer_record = {
    # 答题结果
    "question_id": ...,
    "knowledge_point_ids": [...],
    "is_correct": True/False,
    "user_answer": "...",
    "time_spent": 120,  # 秒

    # 提示使用
    "hint_levels_used": 2,  # 使用了L1+L2
    "hint_L1_used": True,
    "hint_L2_used": True,

    # 错因诊断（答错时）
    "error_type": "CALCULATION_ERROR",
    "error_tags": ["下标计算出错"],
    "error_severity": 0.7,

    # 教学模式
    "advisor_mode": "SCAFFOLD",
    "did_retry": True,  # 是否重试过
    "retry_correct": True,  # 重试后是否正确

    # OCR相关（如有）
    "ocr_used": True,
    "ocr_corrections": 3,  # 用户修正了几处
}
```

#### 5.2 画像更新触发

| 触发条件 | 更新内容 |
|---------|---------|
| 每题答完 | BKT更新对应知识点 + Redis缓存 |
| 每轮5题完成 | IRT能力重估 + 薄弱点重新排序 + 复习队列更新 |
| 连续3轮完成 | 能力曲线记录 + 学习路径重规划 + Advisor模式调整 |
| 检测到成就 | 徽章解锁 + 庆祝动画 + 通知 |

#### 5.3 能力曲线真实数据填充

`UserAbilityHistory` 表已存在但从未写入。每轮完成后记录theta快照：

```python
# 在 advisor.py 的 feedback 完成后增加：
ability_record = UserAbilityHistory(
    user_id=user_id,
    theta=theta_info['theta'],
    theta_se=theta_info['theta_se'],
    recorded_at=datetime.now()
)
db.add(ability_record)
```

这样前端能力曲线图（`MasteryVisualization.vue`）就能从模拟数据切换到真实历史。

---

### Phase 6：与AI批改模块的融合

**目标**：AI批改的试卷分析结果可以触发RecommendView的针对性练习

#### 6.1 批改→推荐的桥接

```
AI批改报告
  │
  ├→ 识别薄弱知识点列表
  ├→ 错因分布数据
  └→ 生成专项练习包
        │
        ▼
  RecommendView 打开
  ├→ 预设学习目标："攻克批改中暴露的3个薄弱点"
  ├→ 题目来源：薄弱知识点+错因针对性选题
  └→ 教学模式：SCAFFOLD（因为这些知识点都薄弱）
```

#### 6.2 统一的数据格式

确保AI批改和智能推题使用相同的：
- 错误类型枚举（ErrorType）
- 知识点ID体系（skill_tree node_id）
- BKT更新逻辑（统一参数）
- 画像数据结构

---

## 四、改动文件清单

### 后端（新建）

| 文件 | 说明 |
|------|------|
| `backend/services/error_diagnosis_service.py` | LLM错因诊断服务（核心新增） |
| `backend/api/grading.py` | AI批改API（按AI批改方案实施） |

### 后端（修改）

| 文件 | 改动内容 |
|------|---------|
| `backend/agent/advisor.py` | 推荐接口增加：学习目标字段、Advisor模式参数、L0-L4提示预生成 |
| `backend/agents/advisor_agent.py` | 4种模式的行为参数细化（难度调整量、题量、是否强制重试） |
| `backend/services/cognitive_diagnosis_service.py` | Actual Score融入BKT更新、错因权重衰减 |
| `backend/algorithms/bkt.py` | `update_continuous()` 支持连续观测值、4级掌握度阈值 |
| `backend/algorithms/skill_tree.py` | NodeStatus 增加 QUALIFIED/PROFICIENT 四级状态 |
| `backend/api/error_classification.py` | 增加 `/diagnose` 端点，对接错因诊断服务 |
| `backend/services/learning_analytics_service.py` | 统一BKT参数（p_learn=0.3）、能力曲线数据写入 |

### 前端（新建）

| 文件 | 说明 |
|------|------|
| `frontend/components/recommend/LearningGoalHeader.vue` | 学习目标+进度头部 |
| `frontend/components/recommend/HintButtonBar.vue` | L0-L4渐进式提示按钮 |
| `frontend/components/recommend/RetryPanel.vue` | 答错后的重试引导面板 |
| `frontend/components/recommend/RoundSummary.vue` | 轮次完成总结面板 |
| `frontend/components/recommend/OCRUploader.vue` | 手写答案OCR上传组件 |
| `frontend/components/recommend/OCRReviewPanel.vue` | OCR校对面板（复用AI批改设计） |

### 前端（修改）

| 文件 | 改动内容 |
|------|---------|
| `frontend/pages/RecommendView.vue` | **大幅改造**：集成上述所有新组件，重构答题流程 |
| `frontend/composables/useRecommendSession.js` | 增加提示使用记录、重试状态、目标追踪 |
| `frontend/services/apiService.js` | 增加diagnose、hint、OCR相关API调用 |

---

## 五、实施优先级

| 阶段 | 内容 | 工作量 | 用户感知提升 |
|------|------|--------|------------|
| Phase 1 | 答题体验升级（提示+OCR+引导重试） | 3天 | ★★★★★ 核心体验质变 |
| Phase 2 | 学习目标+进度可视化 | 1天 | ★★★★ 目标感、成就感 |
| Phase 3 | 错因诊断引擎 | 2天 | ★★★★★ 建立核心壁垒 |
| Phase 4 | Advisor教学模式落地 | 1.5天 | ★★★ 个性化教学感知 |
| Phase 5 | 画像数据采集闭环 | 1天 | ★★★ 推荐越来越准 |
| Phase 6 | AI批改融合 | 2天 | ★★★★ 批改→练习闭环 |

**总计**：约10.5天

**MVP建议**：Phase 1+2 = 4天，先让智能推题从"刷题机器"变成"引导式教学"。

---

## 六、验收标准

- [ ] 每道题下方有L0-L4提示按钮，点击显示对应级别提示
- [ ] 使用提示后Actual Score正确扣分
- [ ] 支持拍照上传手写答案→OCR识别→校对修改→提交
- [ ] 答错后显示结构化错因（类型+位置+建议），而非仅"正确答案是X"
- [ ] 概念错误/过程错误的题，引导学生重试
- [ ] 每轮开始展示学习目标（要攻克什么）
- [ ] 每轮结束展示总结（掌握度变化+错因分布+下一步建议）
- [ ] Advisor教学模式真正影响前端交互行为
- [ ] 能力曲线图显示真实历史数据
