# 数据埋点与 Soft Label 软反馈评分体系设计

## 一、设计理念

传统在线教育产品仅记录"答对/答错"二元结果，丢失了答题过程中大量有价值的认知行为信号。本方案设计 **"行为埋点 → 信号提取 → 软标签评分 → 算法驱动"** 四层数据管道，将用户在前端的每一个微观交互转化为可量化的认知能力指标，最终驱动 Advisor Agent 的个性化推荐策略。

核心原则：
- **全量采集，按需聚合**：前端无感埋点全量上报，后端按维度聚合为行为特征
- **Soft Label 替代 Hard Label**：用连续值（0-100）替代二元对错，更细腻地刻画学习状态
- **行为 → 认知映射**：每个埋点不只记录"发生了什么"，更要回答"反映了什么认知特征"
- **闭环驱动**：软标签直接作为推荐算法的特征输入，实现数据驱动的策略调优

## 二、埋点事件体系（16 类）

### 2.1 答题生命周期事件

| # | 事件名 | 触发时机 | 核心字段 | 认知含义 |
|---|--------|---------|---------|---------|
| 1 | `question_impression` | 题目卡片进入视口 | q_id, kp_list, difficulty, source | 曝光基数 |
| 2 | `question_engage` | 用户开始审题（首次点击/输入） | q_id, time_since_impression_ms | 审题启动速度 |
| 3 | `answer_submit` | 提交答案 | q_id, answer_text, is_correct, attempt_index, total_time_ms, hesitation_count | 答题正确性与流畅度 |
| 4 | `answer_retry` | 答错后再次提交 | q_id, retry_index, time_since_previous_ms, answer_changed_pct | 纠错能力 |
| 5 | `question_complete` | 答题流程结束（正答/跳题/看答案） | q_id, exit_reason, total_attempts, total_time_ms, hints_used[] | 完成路径归因 |

### 2.2 求助行为事件

| # | 事件名 | 触发时机 | 核心字段 | 认知含义 |
|---|--------|---------|---------|---------|
| 6 | `hint_request` | 点击提示按钮 | q_id, hint_level(L0-L4), prev_hint_level, time_since_engage_ms, attempts_before_hint | 求助时机与层级选择 |
| 7 | `hint_dismiss` | 关闭提示浮层 | q_id, hint_level, view_duration_ms, scroll_depth_pct, action_after (retry/next_hint/giveup) | 提示消化程度 |
| 8 | `hint_chain` | 同一题内多次请求提示的完整链路 | q_id, chain: [{level, time_spent_ms, action_after}] | 提示递进策略 |

### 2.3 方案学习行为事件

| 9 | `solution_view` | 进入方案页 | q_id, trigger (after_wrong/after_correct/after_giveup), time_to_solution_ms | 学习动机区分 |
| 10 | `solution_engage` | 方案页交互（滚动/选中/复制） | q_id, scroll_depth_pct, highlight_count, total_duration_ms, revisit_count | 方案阅读深度 |

### 2.4 决策与导航事件

| 11 | `question_skip` | 跳过题目 | q_id, skip_reason (too_hard/too_easy/not_interested/tired), attempts_before_skip, time_spent_ms | 放弃归因 |
| 12 | `knowledge_node_click` | 点击知识树节点 | kp_name, node_status, time_spent_on_node_ms | 知识元认知 |
| 13 | `review_schedule_action` | 对复习提醒的操作 | q_id, action (accept/snooze/dismiss), review_interval_days, mastery_at_review_time | 复习行为模式 |

### 2.5 会话与上下文事件

| 14 | `session_start` | 进入应用 | device_type, last_session_gap_hours, entry_source | 使用频率与场景 |
| 15 | `session_heartbeat` | 每 60s 心跳 | current_page, questions_done_this_session, active_duration_ms | 持续参与度 |
| 16 | `session_end` | 离开应用/超时 | session_duration_ms, questions_completed, correct_rate, avg_hint_level, mastery_delta | 单次学习成效 |

### 2.6 情绪感知事件（基于交互模式推断）

| 17 | `emotion_signal` | 检测到异常行为模式 | trigger (rapid_click/short_answer/long_pause/rage_skip), intensity (1-5), context | 学习情绪监测 |

## 三、六维 Soft Label 评分模型

基于上述埋点数据，聚合为六个维度的软反馈指标。每个维度输出 0-100 的连续分值，每日更新。

### 3.1 自主性指数 (Independence Score)

**定义**：衡量学生在不依赖外部帮助的情况下独立解决问题的程度。

**计算因子**：
- 首次求助的提示层级：L0(+20) / L1(+10) / L2(-5) / L3(-15) / L4(-25)
- 求助延迟时长：>120s(+15) / 60-120s(+10) / 30-60s(0) / <30s(-10) / <10s(-20)
- 同一题内提示链长度：0次(+20) / 1次(+10) / 2次(0) / 3次(-10) / 4+次(-20)
- 直接查看答案（未尝试即看方案）：每次 -30
- 答对且未求助的题目占比

**更新公式**：滑动窗口（最近 20 题），加权平均后映射到 0-100。

### 3.2 坚持性指数 (Persistence Score)

**定义**：衡量学生面对困难时的坚持程度与抗挫折能力。

**计算因子**：
- 答错后继续尝试的比例：每道错题 +10（上限 3 次）
- 跳过前的尝试次数：0次(-20) / 1次(-10) / 2次(0) / 3次(+10) / 4+次(+20)
- 平均每题投入时长（相对题目难度归一化）
- 困难题（difficulty≥4）的完成率
- 同一知识点连续答错的坚持天数

**更新公式**：滑动窗口（最近 20 题），各因子加权求和后映射到 0-100。

### 3.3 元认知校准度 (Metacognitive Calibration)

**定义**：衡量学生对自己知识水平的判断准确度。高校准度意味着"知道自己会什么、不会什么"。

**计算因子**：
- 自我评估 vs 实际正确率的差值（通过知识树节点点击行为推断：点击"已掌握"节点但答错的次数）
- 跳题原因与题目实际难度的匹配度：跳因"太难"但实际难度<3 → 校准偏移-10
- 求助层级选择的合理性：低掌握度节点用高等级提示 → 合理(+10)；高掌握度节点频繁求助 → 不合理(-10)
- 复习接受率：系统推荐的复习题采纳率

**输出范围**：-1 到 1（0 表示完美校准，正值高估，负值低估），展示时映射到 0-100。

### 3.4 求助策略效率 (Help-seeking Efficiency)

**定义**：衡量学生使用提示系统的策略是否高效——知道何时求助、求助后能否有效利用。

**计算因子**：
- 提示递进模式评分：L0→L1→L2 渐进式(+15)、跳跃式 L0→L4(-10)、重复同层级求助(-5)
- 提示"转化率"：查看提示后答对的概率
- 提示消化度：hint_dismiss 时的 scroll_depth_pct（是否完整阅读）
- 无效求助次数：查看提示后 < 5s 即提交且答错

**更新公式**：最近 20 次求助行为加权评分。

### 3.5 反思深度 (Reflection Depth)

**定义**：衡量学生对解题过程和错误进行深度反思的程度。

**计算因子**：
- 方案页平均停留时长（相对题目难度归一化）
- 方案页滚动深度：<30%(-15) / 30-70%(0) / >70%(+15)
- 答对后仍查看方案的比例（"对答案也看解析" 是好习惯）
- 错题复习完成率
- 错题本标记/笔记添加次数
- 同一道错题的复习间隔规律性

**更新公式**：近 7 天行为聚合，指数衰减历史数据。

### 3.6 知识迁移能力 (Knowledge Transfer)

**定义**：衡量学生将已学知识应用到新情境、新题型的能力。

**计算因子**：
- 首次遇到新知识点的答对率
- 跨知识点题目表现：涉及 2+ 知识点的综合题正确率
- 难度递进适应速度：难度提升后的正确率衰减幅度
- 知识树相邻节点的掌握速度关联度
- 用户自传题目（OCR 上传）的表现

**更新公式**：跨知识点题目窗口（最近 30 题），与同难度单知识点题目对比。

## 四、行为信号 → 算法策略映射

软标签不只要"好看"，更要**直接驱动推荐策略**：

| 软标签维度 | 阈值条件 | 策略干预 |
|-----------|---------|---------|
| 自主性 < 30 | 过度依赖提示 | 限制 L3/L4 提示可用性，引导先尝试 |
| 自主性 > 80 | 高度独立 | 开放全部提示等级，减少干预 |
| 坚持性 < 25 | 轻易放弃 | 降低推荐难度 0.5，增加鼓励文案 |
| 坚持性 > 75 | 韧性极强 | 适当提升挑战难度 |
| 校准度 < -0.5 | 严重低估自己 | 提高题目难度 0.3，展示能力趋势图 |
| 校准度 > 0.5 | 严重高估自己 | 推送一道"认知冲突"题（看似简单实则需要 deep knowledge） |
| 求助效率 < 30 | 不会求助 | 推送提示使用引导教学 |
| 求助效率 > 80 | 策略良好 | 解锁"快速提示"快捷操作 |
| 反思深度 < 20 | 不做反思 | 答题后强制展示关键步骤（至少 10s） |
| 迁移能力增长 | 连续 2 周上升 | Advisor 模式从 SCAFFOLD → ENCOURAGE → CHALLENGE |

**Advisor Agent 三模式切换**在原有 mastery 判定基础上增加软标签联合判定：
- `MODE_SCAFFOLD`：avg_mastery < 0.4 **OR** 自主性 < 30 **OR** 坚持性 < 25
- `MODE_CHALLENGE`：avg_mastery > 0.8 **AND** 自主性 > 60 **AND** 迁移能力 > 50
- `MODE_ENCOURAGE`：其余情况

## 五、数据库扩展设计

### 5.1 新增表：user_soft_labels

```sql
CREATE TABLE user_soft_labels (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    user_id INTEGER NOT NULL,
    independence_score DECIMAL(5,2) DEFAULT 50.00,   -- 自主性 0-100
    persistence_score DECIMAL(5,2) DEFAULT 50.00,    -- 坚持性 0-100
    metacognition_score DECIMAL(5,2) DEFAULT 50.00,  -- 元认知校准 0-100
    helpseeking_score DECIMAL(5,2) DEFAULT 50.00,     -- 求助效率 0-100
    reflection_score DECIMAL(5,2) DEFAULT 50.00,      -- 反思深度 0-100
    transfer_score DECIMAL(5,2) DEFAULT 50.00,        -- 知识迁移 0-100
    composite_score DECIMAL(5,2) DEFAULT 50.00,       -- 综合软标签
    sample_size INTEGER DEFAULT 0,                     -- 有效样本数
    calculated_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE KEY uk_user (user_id),
    INDEX idx_composite (composite_score)
);
```

### 5.2 扩展 user_interaction_logs 表

在现有表基础上增加字段：
```sql
ALTER TABLE user_interaction_logs ADD COLUMN event_name VARCHAR(80);
ALTER TABLE user_interaction_logs ADD COLUMN soft_label_dimension VARCHAR(30);
ALTER TABLE user_interaction_logs ADD COLUMN cognitive_signal JSON;
```

## 六、实现路线图

| 阶段 | 内容 | 预期产出 |
|------|------|---------|
| Phase 1 | 前端埋点 SDK 封装（`trackEvent()` 统一入口） | 16 类事件全量上报 |
| Phase 2 | 后端事件接收 + 批量写入 MySQL | 数据管道跑通 |
| Phase 3 | 六维软标签计算脚本（每日定时任务） | `user_soft_labels` 表产出 |
| Phase 4 | Advisor Agent 接入软标签联合判定 | 推荐策略升级 |
| Phase 5 | 前端学习画像新增"学习行为分析"板块 | 用户可见的行为洞察 |
| Phase 6 | A/B 测试验证软标签驱动的推荐 vs 纯 mastery 推荐 | 效果归因 |
