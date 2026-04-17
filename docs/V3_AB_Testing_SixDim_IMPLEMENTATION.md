# V3 A/B测试与六维能力画像实现文档

**需求编号**: 行号3, 行号4  
**需求名称**: 
- 行号3: 通过随机分队验证V3认知诊断算法相对V2传统推荐的有效性
- 行号4: 多维度展示学生数学思维深度与认知特质，而非单纯知识点

**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

### 行号3: A/B测试框架
实现V3认知诊断算法与V2传统推荐的对比实验：
- A组（对照组）: V2基础推荐
- B组（实验组）: V3 K-IRT + Soft Labeling
- 跟踪指标: 答题正确率提升率、用户会话时长

### 行号4: 六维能力画像
构建学生数学认知的六个维度：
1. 逻辑推演力 (Logical Reasoning)
2. 计算稳定性 (Calculation Stability)
3. 知识迁移力 (Knowledge Transfer)
4. 提示独立性 (Hint Independence)
5. 错题自愈力 (Error Recovery)
6. 学习抗挫力 (Learning Resilience)

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/services/ab_testing_service.py` | A/B测试服务 | ~450行 |
| `backend/services/six_dimensional_ability_service.py` | 六维能力服务 | ~600行 |
| `backend/api/ab_testing.py` | A/B测试API | ~300行 |
| `backend/api/six_dimensional_ability.py` | 六维能力API | ~400行 |

---

## 3. A/B测试框架（行号3）

### 3.1 用户分组

**分组逻辑:**
```python
# 使用一致性哈希确保用户始终分配到同一组
hash_value = int(hashlib.md5(f"{user_id}_{experiment_name}".encode()).hexdigest(), 16)
group = "A" if hash_value % 2 == 0 else "B"
```

**Redis存储:**
```
Key: ai:tutor:abtest:group:{user_id}
Value: A / B
TTL: 30天
```

### 3.2 策略差异

| 特性 | A组 (V2) | B组 (V3) |
|-----|---------|---------|
| K-IRT | ❌ | ✅ |
| Soft Labeling | ❌ | ✅ |
| 自适应难度 | ❌ | ✅ |
| BKT知识追踪 | ❌ | ✅ |

### 3.3 指标跟踪

**记录指标:**
- 答题总数
- 正确数/正确率
- 会话总时长
- 平均每题耗时
- 提示使用率
- 跳过率

**聚合统计:**
```
Key: ai:tutor:abtest:aggregate:A
Key: ai:tutor:abtest:aggregate:B
```

### 3.4 API接口

| 端点 | 说明 |
|-----|------|
| `GET /ab-test/group` | 获取用户实验组 |
| `GET /ab-test/strategy` | 获取推荐策略详情 |
| `POST /ab-test/record-event` | 记录答题事件 |
| `GET /ab-test/metrics` | 获取用户指标 |
| `GET /ab-test/results` | 获取实验结果对比 |
| `GET /ab-test/statistics` | 获取分组统计 |

---

## 4. 六维能力画像（行号4）

### 4.1 六维定义

| 维度 | 名称 | 说明 | 计算指标 |
|-----|------|------|---------|
| logical_reasoning | 逻辑推演力 | 分析数学问题、推导解题思路的能力 | 多步骤推理正确率、复杂题目完成率 |
| calculation_stability | 计算稳定性 | 准确执行数学计算、避免粗心错误的能力 | 计算错误率、数值运算准确率 |
| knowledge_transfer | 知识迁移力 | 将已学知识应用到新情境的能力 | 变式题正确率、跨知识点应用 |
| hint_independence | 提示独立性 | 独立解决问题、减少对外部提示依赖的能力 | 提示使用率、L0自主完成率 |
| error_recovery | 错题自愈力 | 从错误中学习、改正并掌握的能力 | 错题重做正确率、复习队列完成率 |
| learning_resilience | 学习抗挫力 | 面对困难坚持学习、不轻易放弃的能力 | 连续错误后继续率、难题停留时间 |

### 4.2 能力等级

| 等级 | 分数范围 | 说明 |
|-----|---------|------|
| excellent | 90-100 | 优异 |
| strong | 80-89 | 良好 |
| average | 60-79 | 一般 |
| weak | 0-59 | 需加强 |

### 4.3 计算逻辑

**逻辑推演力:**
```python
score = correct_rate * 100
if avg_steps > 3 and correct_rate > 0.7:
    score = min(100, score * 1.1)  # 复杂题目 bonus
```

**提示独立性:**
```python
l0_rate = l0_completions / total_questions
score = l0_rate * 100 - avg_hints * 5
```

**学习抗挫力:**
```python
base_score = 50
continuation_bonus = continued_after_errors * 10
persistence_bonus = min(max_consecutive * 5, 30)
score = base_score + continuation_bonus + persistence_bonus
```

### 4.4 API接口

| 端点 | 说明 |
|-----|------|
| `GET /six-dim-ability/profile` | 获取六维能力画像 |
| `POST /six-dim-ability/calculate` | 计算六维能力 |
| `GET /six-dim-ability/dimension/{name}` | 获取维度详情 |
| `GET /six-dim-ability/radar-chart` | 获取雷达图数据 |
| `GET /six-dim-ability/history` | 获取能力历史 |
| `GET /six-dim-ability/comparison` | 能力对比 |

---

## 5. 硬指标实现

### 5.1 A/B测试

| 指标 | 实现 |
|-----|------|
| 分组比例 | 50/50 |
| 一致性 | 基于用户ID哈希 |
| 数据保留 | 30天 |

### 5.2 六维能力

| 指标 | 实现 |
|-----|------|
| 分数范围 | 0-100 |
| 等级阈值 | 40/60/80/90 |
| 缓存TTL | 7天 |

---

## 6. Git提交记录

```bash
git add backend/services/ab_testing_service.py
git add backend/services/six_dimensional_ability_service.py
git add backend/api/ab_testing.py
git add backend/api/six_dimensional_ability.py
git add docs/V3_AB_Testing_SixDim_IMPLEMENTATION.md

git commit -m "feat: Implement A/B testing and six-dimensional ability profile (Row 3,4)

- Add A/B testing framework with A/B group assignment
- Add V2 vs V3 strategy differentiation
- Add experiment metrics tracking (accuracy, session time)
- Add six-dimensional ability calculation
- Add six dimensions: logical, calculation, transfer, independence, recovery, resilience
- Add radar chart data generation
- Add ability history tracking
- Add A/B testing and six-dim ability API endpoints

对应飞书需求池:
- 行号3: A/B测试框架
- 行号4: 六维能力画像"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
