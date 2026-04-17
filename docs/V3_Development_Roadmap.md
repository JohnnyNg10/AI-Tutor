# AI Tutor V3 开发路线图 (Development Roadmap)

**文档版本**: v1.0  
**创建日期**: 2026-04-16  
**最后更新**: 2026-04-17  
**维护者**: AI Assistant

---

## 已完成需求汇总

| 需求编号 | 需求名称 | 状态 | 完成日期 | 代码位置 |
|---------|---------|------|---------|---------|
| 需求1 | 连击状态与难度自适应 | ✅ 已完成 | 2026-04-15 | `algorithms/streak_handler.py` |
| 需求5 | Actual Score计算 | ✅ 已完成 | 2026-04-15 | `algorithms/actual_score.py` |
| 需求6 | 自适应K因子 | ✅ 已完成 | 2026-04-15 | 集成在K-IRT中 |
| 需求7 | 艾宾浩斯遗忘曲线 | ✅ 已完成 | 2026-04-15 | `algorithms/memory_decay.py` |
| 需求10 | 游戏技能树 | ✅ 已完成 | 2026-04-15 | `algorithms/skill_tree.py` |
| 需求16 | 渐进式提示按钮 | ✅ 已完成 | 2026-04-16 | `algorithms/hint_button_state_machine.py` |
| 需求20 | 每日5题特训包 | ✅ 已完成 | 2026-04-16 | `algorithms/daily_training_pack.py` |
| 需求24 | RAG候选池构建 | ✅ 已完成 | 2026-04-17 | `algorithms/rag_candidate_pool.py` |
| 需求29 | 记忆衰减Cron任务 | ✅ 已完成 | 2026-04-16 | `algorithms/memory_decay_cron.py` |

---

## 核心依赖关系图

```
┌─────────────────────────────────────────────────────────────┐
│                    基础层 (Foundation)                       │
├─────────────────────────────────────────────────────────────┤
│  需求1(连击) ← 需求5(Actual Score) ← 需求16(提示按钮)        │
│  需求6(K因子) ← 需求7(遗忘曲线) ← 需求29(Cron)              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    数据层 (Data Layer)                       │
├─────────────────────────────────────────────────────────────┤
│  Redis核心数据结构 ← 需求20(每日5题) ← 需求??(Advisor推荐)   │
│  - Seen Pool (已做题目去重)                                  │
│  - Review Queue (错题复习队列)                               │
│  - Mastery Hash (实时掌握度)                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    推荐层 (Recommendation)                   │
├─────────────────────────────────────────────────────────────┤
│  需求??(RAG初筛) ← 需求??(元数据过滤) ← 需求??(相似度加权)    │
│  需求10(技能树) ← 需求??(薄弱点注入)                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    交互层 (Interaction)                      │
├─────────────────────────────────────────────────────────────┤
│  需求??(Instructor引导) ← 需求??(跳过处理)                   │
│  需求??(Advisor指令) ← 需求??(Redis缓存)                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 推荐开发顺序

### 🔥 第一阶段：Redis核心数据结构（基础层）

**优先级**: P0 (最高)  
**预估工期**: 2-3天  
**前置依赖**: 无  
**阻塞后续**: 需求20完善、Advisor推荐、RAG候选池

**为什么优先**:
1. **基础设施**: 需求20（每日5题）和后续所有推荐功能都依赖Redis
2. **解耦设计**: 先定义好数据Schema，前后端可以并行开发
3. **性能保障**: Redis是毫秒级响应的关键
4. **风险最低**: 纯技术实现，无业务逻辑争议

**待实现功能**:
| 功能 | Key模式 | 数据结构 | 说明 |
|-----|---------|---------|------|
| 已做题目去重池 | `ai:tutor:seen-q:{uid}` | Set | 防止重复推题 |
| 错题复习队列 | `ai:tutor:review-q:{uid}` | ZSet | 优先级复习调度 |
| 实时掌握度 | `ai:tutor:mastery:{uid}` | Hash | 快速读取认知状态 |
| Session状态 | `ai:tutor:session:{sid}` | Hash | 临时状态存储 |

**验收标准**:
```python
# 测试用例1：Seen Pool
redis.sadd("ai:tutor:seen-q:1", "q001")
assert redis.sismember("ai:tutor:seen-q:1", "q001") == True

# 测试用例2：Review Queue
redis.zadd("ai:tutor:review-q:1", {"q001": time.time() + 86400})
due = redis.zrangebyscore("ai:tutor:review-q:1", 0, time.time())
assert len(due) == 0  # 1天后才到期

# 测试用例3：Mastery Hash
redis.hset("ai:tutor:mastery:1", "等差数列", 85)
mastery = redis.hget("ai:tutor:mastery:1", "等差数列")
assert mastery == "85"
```

**实现文件规划**:
- `backend/services/redis_service.py` - Redis服务封装
- `backend/algorithms/redis_data_structures.py` - 核心数据结构操作
- `backend/api/redis_api.py` - Redis管理API

---

### 🔥 第二阶段：Advisor Agent 指令集（核心功能）

**优先级**: P0  
**预估工期**: 3-4天  
**前置依赖**: Redis核心数据结构  
**阻塞后续**: Instructor交互、推荐引擎

**为什么优先**:
1. **核心功能**: Advisor是产品的"大脑"，控制教学策略
2. **依赖清晰**: 依赖Redis但不依赖RAG，可以Mock数据先跑通
3. **可演示**: 有明确的输入输出，方便产品验收

**待实现功能**:
| 指令编码 | 指令名称 | 触发条件 | 控制参数 |
|---------|---------|---------|---------|
| MODE_SCAFFOLD | 脚手架模式 | P(L) < 0.4 或 连续2题错误 | detailed, step_by_step, allow_skip |
| MODE_CHALLENGE | 挑战模式 | P(L) > 0.8 且 近期正确率高 | minimal, hint_level: direction |
| MODE_ENCOURAGE | 鼓励模式 | 连续3题错误或表达挫败感 | adaptive, encouragement |

**指令下发格式**:
```json
{
  "instruction": "MODE_SCAFFOLD",
  "reasoning": "学生在等比数列知识点掌握度仅为0.35,需要分步引导",
  "control_params": {
    "hint_level": "detailed",
    "max_hints": 5,
    "step_by_step": true,
    "estimated_steps": 4
  },
  "instructor_prompt": "请使用苏格拉底式提问,分4步引导学生理解..."
}
```

**验收标准**:
```python
# 测试用例1：脚手架模式
if p_known < 0.4:
    instruction = generate_advisor_instruction("MODE_SCAFFOLD")
    assert instruction["control_params"]["step_by_step"] == True
    assert instruction["control_params"]["hint_level"] == "detailed"

# 测试用例2：挑战模式
if p_known > 0.8 and recent_accuracy > 0.8:
    instruction = generate_advisor_instruction("MODE_CHALLENGE")
    assert instruction["control_params"]["hint_level"] == "minimal"
    assert instruction["control_params"]["step_by_step"] == False

# 测试用例3：鼓励模式
if consecutive_wrong >= 3:
    instruction = generate_advisor_instruction("MODE_ENCOURAGE")
    assert "encouragement" in instruction["control_params"]
```

**实现文件规划**:
- `backend/agents/advisor_agent.py` - Advisor Agent核心
- `backend/algorithms/advisor_instructions.py` - 指令生成逻辑
- `backend/api/advisor_api.py` - Advisor API接口

---

### 🔥 第三阶段：RAG候选池构建（推荐质量）✅ 已完成

**优先级**: P1  
**预估工期**: 4-5天  
**实际工期**: 1天  
**完成日期**: 2026-04-17  
**前置依赖**: Advisor Agent、Redis数据结构  
**阻塞后续**: 每日5题完善、技能树推荐

**实现状态**: ✅ 已完成，详见 `docs/V3_RAG_Candidate_Pool_IMPLEMENTATION.md`

**已实现功能**:
| 步骤 | 功能 | 状态 | 文件 |
|-----|------|------|------|
| 1 | RAG初筛 | ✅ | `rag_candidate_pool.py` |
| 2 | 元数据过滤 | ✅ | `rag_candidate_pool.py` |
| 3 | 相似度加权 | ✅ | `rag_candidate_pool.py` |
| 4 | 复习队列调度 | ✅ | `question_recommendation.py` |
| 5 | 新题/复习策略 | ✅ | `question_recommendation.py` |
| 6 | 推荐理由生成 | ✅ | `question_recommendation.py` |

**算法流程**:
```python
# Step 1: RAG初筛
weak_kps = ["等比数列", "递推公式"]
candidate_pool = vector_search(weak_kps, top_k=50)

# Step 2: 元数据过滤
filtered = [
    c for c in candidate_pool
    if abs(c["difficulty"] - theta) <= 1.0  # 难度匹配
    and c["id"] not in seen_set  # 去重
    and c["kp"] in weak_kps  # 知识点相关
]

# Step 3: 相似度加权
context_similarity = cosine_similarity(recent_context, question_content)
final_score = 0.6 * kp_relevance + 0.3 * difficulty_match + 0.1 * context_similarity
```

**实现文件**:
- ✅ `backend/services/chroma_service.py` - Chroma向量数据库服务
- ✅ `backend/algorithms/rag_candidate_pool.py` - RAG候选池构建
- ✅ `backend/algorithms/question_recommendation.py` - 题目推荐算法
- ✅ `backend/api/recommendation_v3.py` - V3推荐API

---

### 🔥 第四阶段：Instructor教学交互（用户体验）

**优先级**: P1  
**预估工期**: 3-4天  
**前置依赖**: Advisor指令集、提示按钮  
**阻塞后续**: 完整教学流程

**为什么优先**:
1. **用户体验**: 需求16的提示按钮需要Instructor配合才能发挥作用
2. **产品闭环**: 学生与系统的核心交互界面
3. **依赖清晰**: 依赖Advisor指令，可以并行开发

**待实现功能**:
| 用户表达 | 检测关键词 | 系统画像更新 | Instructor响应策略 |
|---------|-----------|-------------|-------------------|
| 困难感知 | "好难"、"太难了" | 难度感知+1 | 分解步骤，增加中间推导 |
| 信心充足 | "能克服"、"简单" | 学习风格="进取型" | 减少提示，鼓励自主探索 |
| 步骤困惑 | "看不懂"、"跳太快" | 需要详细解释 | 展开被省略的中间步骤 |

**提示等级下发**:
| 等级 | 触发条件 | Instructor行为 | Actual权重 |
|-----|---------|---------------|-----------|
| L0-自主 | 直接提交答案 | 仅批改，不干预 | 1.0 |
| L1-方向 | 点击"有点思路但卡住了" | 给出解题方向提示 | 0.8 |
| L2-公式 | 点击"需要公式提醒" | 给出相关公式定理 | 0.6 |
| L3-步骤 | 点击"教教我" | 给出关键推导步骤 | 0.4 |
| L4-答案 | 点击"看答案" | 给出完整解答 | 0.1 |

**验收标准**:
```python
# 测试用例1：L1方向提示
if hint_level == 1:
    response = instructor.generate_hint(question, level=1)
    assert "方向" in response or "思路" in response
    assert "公式" not in response  # L1不包含公式

# 测试用例2：L2公式提示
if hint_level == 2:
    response = instructor.generate_hint(question, level=2)
    assert "公式" in response or "定理" in response

# 测试用例3：L4完整答案
if hint_level == 4:
    response = instructor.generate_hint(question, level=4)
    assert "答案" in response or "解" in response
    assert "=" in response  # 包含等式

# 测试用例4：困难感知检测
if "好难" in user_message:
    sentiment = analyze_sentiment(user_message)
    assert sentiment == "difficult_perceived"
    assert user_profile["difficulty_perception"] >= 1
```

**实现文件规划**:
- `backend/agents/instructor_agent.py` - Instructor Agent核心
- `backend/algorithms/hint_generator.py` - 提示生成器
- `backend/algorithms/sentiment_analyzer.py` - 情感分析器
- `backend/api/instructor_api.py` - Instructor API接口

---

### 🔥 第五阶段：跳过处理机制（细节完善）

**优先级**: P2  
**预估工期**: 2天  
**前置依赖**: Actual Score、Advisor指令集  
**阻塞后续**: 无

**为什么优先**:
1. **完善体验**: 处理异常流程，提升用户体验
2. **简单独立**: 逻辑清晰，不依赖复杂算法
3. **快速交付**: 可以并行开发

**待实现功能**:
| 跳过类型 | 用户心理 | 算法处理 | Advisor介入话术 |
|---------|---------|---------|----------------|
| 太简单 | 系统看低我了 | Actual=1.0, θ+=0.1 | "看来这些基础难不倒你!我们直接跳过..." |
| 太难了 | 系统高估我了 | Actual=0.0, θ-=0.05 | "这道题涉及的放缩法确实超前,别灰心..." |

**验收标准**:
```python
# 测试用例1：太简单处理
if skip_reason == "too_easy":
    result = handle_skip(user_id, question_id, "too_easy")
    assert result["actual_score"] == 1.0
    assert result["theta_delta"] == 0.1
    assert "难不倒你" in result["advisor_message"]

# 测试用例2：太难处理
if skip_reason == "too_hard":
    result = handle_skip(user_id, question_id, "too_hard")
    assert result["actual_score"] == 0.0
    assert result["theta_delta"] == -0.05
    assert "别灰心" in result["advisor_message"]

# 测试用例3：跳过记录
skip_record = get_skip_record(user_id, question_id)
assert skip_record["reason"] in ["too_easy", "too_hard", "other"]
assert skip_record["timestamp"] is not None
```

**实现文件规划**:
- `backend/algorithms/skip_handler.py` - 跳过处理逻辑
- `backend/api/skip_api.py` - 跳过处理API

---

## 开发里程碑

| 里程碑 | 预计完成 | 交付物 | 验收标准 |
|-------|---------|--------|---------|
| M1 | +1周 | Redis数据结构 | 所有Redis操作API通过单元测试 |
| M2 | +2周 | Advisor指令集 | 三种模式指令生成正确 |
| M3 | +3周 | RAG候选池 | 向量检索+过滤+排序完整流程 |
| M4 | +4周 | Instructor交互 | L0-L4提示生成正确 |
| M5 | +5周 | 跳过处理 | 太简单/太难处理逻辑正确 |

---

## 风险与应对

| 风险 | 概率 | 影响 | 应对措施 |
|-----|------|------|---------|
| Chroma向量库性能瓶颈 | 中 | 高 | 提前进行压力测试，准备备选方案(Milvus) |
| Redis数据一致性 | 中 | 高 | 设计完善的同步机制，MySQL为主，Redis为缓存 |
| LLM响应延迟 | 高 | 中 | Instructor响应采用流式输出，首字节<1s |
| 需求变更 | 中 | 中 | 每个阶段预留20%缓冲时间 |

---

## 附录

### A. 技术栈确认
- **向量数据库**: Chroma (备选: Milvus)
- **缓存**: Redis 7.x
- **LLM**: OpenAI GPT-4 / Claude (待定)
- **框架**: FastAPI + SQLAlchemy

### B. 参考文档
- PRD: `docs/list.md`
- 已实现需求: `docs/V3_Requirement*_IMPLEMENTATION.md`

### C. 变更日志
| 版本 | 日期 | 变更内容 | 作者 |
|-----|------|---------|------|
| v1.0 | 2026-04-16 | 初始版本，定义5个阶段开发顺序 | AI Assistant |
