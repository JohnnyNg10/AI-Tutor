# V3 知识树进度与学习习惯徽章实现文档

**需求编号**: 行号22/27, 行号23/28  
**需求名称**: 
- 行号22/27: 摒弃传统题量进度条，基于"知识树节点解锁率"来定义学习进度
- 行号23/28: 弱化分数激励，强化对学生优良"学习习惯与抗压行为"的成就认可

**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

### 行号22/27: 知识树节点解锁率进度
- 进度定义：以专题为单位，计算 P(L) >= 0.8 的知识点占比
- 里程碑：50%、100%触发系统级庆祝播报
- 取代传统题量进度条

### 行号23/28: 学习习惯成就徽章
- 行为埋点检测（长耗时、不查看答案、复习正确率等）
- 10种学习习惯徽章
- 弱化分数，强化习惯认可

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/services/knowledge_tree_progress_service.py` | 知识树进度服务 | ~400行 |
| `backend/services/learning_habit_badge_service.py` | 学习习惯徽章服务 | ~400行 |
| `backend/api/knowledge_tree_progress.py` | 知识树进度API | ~250行 |
| `backend/api/learning_habit_badges.py` | 学习习惯徽章API | ~250行 |

---

## 3. 知识树进度（行号22/27）

### 3.1 进度计算

```python
# 专题进度 = 已掌握节点数 / 总节点数
progress = (mastered_nodes / total_nodes) * 100

# 掌握标准：P(L) >= 0.8
is_mastered = p_known >= 0.8

# 解锁标准：P(L) >= 0.5
is_unlocked = p_known >= 0.5
```

### 3.2 里程碑系统

| 里程碑 | 触发条件 | 反馈 |
|-------|---------|------|
| 50% | 进度 >= 50% | 恭喜！专题进度突破50%！ |
| 100% | 进度 >= 100% | 太棒了！专题已完全掌握！ |

### 3.3 API端点

- `GET /knowledge-tree/progress` - 知识树进度
- `GET /knowledge-tree/check-milestones` - 检查里程碑

---

## 4. 学习习惯徽章（行号23/28）

### 4.1 10种徽章

| 徽章ID | 名称 | 图标 | 类别 | 条件 |
|-------|------|------|------|------|
| persistent_solver | 🔥 坚韧不拔 | 🔥 | resilience | 单题耗时>10分钟未跳过 |
| independent_thinker | 🧠 独立思考者 | 🧠 | habit | 连续5题不查看L4 |
| review_master | 📚 温故知新 | 📚 | habit | 复习正确率100% |
| early_bird | 🌅 早起鸟 | 🌅 | habit | 连续7天早8点学习 |
| streak_keeper | 🔥 连胜达人 | 🔥 | habit | 连续答对10题 |
| hint_minimalist | 💡 提示极简主义 | 💡 | habit | 连续3题仅用L0-L1 |
| error_conqueror | ⚔️ 错题征服者 | ⚔️ | resilience | 连续3次错题重做正确 |
| deep_thinker | 🤔 深度思考者 | 🤔 | persistence | 思考时间>平均2倍且正确 |
| comeback_king | 👑 逆袭王者 | 👑 | resilience | 3错后3对 |
| daily_grind | 📅 每日坚持 | 📅 | habit | 连续30天每天5题 |

### 4.2 行为追踪

```python
# 追踪学习行为
behavior_data = {
    'consecutive_correct': 10,
    'consecutive_no_l4': 5,
    'time_spent': 600,
    'skipped': False
}
```

### 4.3 API端点

- `POST /learning-badges/track-behavior` - 追踪行为
- `POST /learning-badges/check-new` - 检查新徽章
- `GET /learning-badges/my-badges` - 我的徽章

---

## 5. 硬指标

### 5.1 知识树

| 指标 | 值 |
|-----|-----|
| 掌握阈值 | P(L) >= 0.8 |
| 解锁阈值 | P(L) >= 0.5 |
| 里程碑 | 50%, 100% |

### 5.2 学习习惯徽章

| 指标 | 值 |
|-----|-----|
| 徽章总数 | 10个 |
| 类别 | habit/resilience/persistence |
| 追踪窗口 | 最近100条行为 |

---

## 6. Git提交记录

```bash
git add backend/services/knowledge_tree_progress_service.py
git add backend/services/learning_habit_badge_service.py
git add backend/api/knowledge_tree_progress.py
git add backend/api/learning_habit_badges.py
git add docs/V3_KnowledgeTree_LearningBadges_IMPLEMENTATION.md

git commit -m "feat: Implement knowledge tree progress and learning habit badges (Row 22/27,23/28)

- Add knowledge tree progress calculation (P(L) >= 0.8)
- Add milestone detection (50%, 100%) with celebration
- Add 10 learning habit badges (persistence, resilience, habit)
- Add behavior tracking for badge detection
- Add progress tracking for badge unlock
- Add API endpoints for knowledge tree and badges

对应飞书需求池:
- 行号22/27: 知识树节点解锁率进度
- 行号23/28: 学习习惯成就徽章"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
