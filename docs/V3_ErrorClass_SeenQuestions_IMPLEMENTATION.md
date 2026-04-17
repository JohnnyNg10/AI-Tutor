# V3 错题本错误原因分类与Redis已做题目标记实现文档

**需求编号**: 行号13, 行号41  
**需求名称**: 
- 行号13: 错题本的分类不仅依靠章节，更依靠 AI 诊断出的"错误原因"进行聚类
- 行号41: 利用 Redis 高速读写特性，拦截已做题目，杜绝学生在短时间内刷到重复题目的糟糕体验

**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

### 行号13: 错题本错误原因分类
- 按错误原因聚类（计算失误、公式错误、概念错误等）
- 视图切换：时间/章节/错因
- 一键专项复健：连续推送3道同错因题目

### 行号41: Redis已做题目标记
- Redis Set存储已做题目ID
- 推题前检查是否已做过
- 滑动窗口（最近100题）+ 时间窗口（30天）

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/services/error_classification_service.py` | 错误原因分类服务 | ~400行 |
| `backend/services/seen_questions_service.py` | 已做题目标记服务 | ~350行 |
| `backend/api/error_classification.py` | 错误分类API | ~250行 |
| `backend/api/seen_questions.py` | 已做标记API | ~280行 |

---

## 3. 错题本错误原因分类（行号13）

### 3.1 8种错误类型

| 类型ID | 名称 | 图标 | 颜色 | 说明 |
|-------|------|------|------|------|
| calculation_error | 计算失误 | 🔢 | #FF6B6B | 数值计算、符号处理错误 |
| formula_error | 公式错误 | 📐 | #FAAD14 | 公式记忆、应用错误 |
| concept_error | 概念错误 | ❓ | #FF4D4F | 概念、定理理解有误 |
| logic_error | 逻辑错误 | 🧩 | #EB2F96 | 解题思路、推理错误 |
| careless_error | 粗心大意 | 👀 | #FA8C16 | 审题不清、漏看条件 |
| boundary_error | 边界条件 | 📏 | #F5222D | 未讨论边界情况 |
| transformation_error | 变形困难 | 🔄 | #722ED1 | 题目变形后无法适应 |
| unknown_error | 未分类 | ❔ | #999999 | 暂时无法归类 |

### 3.2 视图切换

```python
# 三种视图
view_type = 'time'          # 按时间排序
view_type = 'chapter'       # 按章节分组
view_type = 'error_category' # 按错误原因分类（行号13核心）
```

### 3.3 专项复健

**功能**: 在特定错因分类下，一键生成3道同错因练习题

**流程**:
1. 选择错误类型（如"计算失误"）
2. 点击"一键专项复健"
3. 系统推送3道同类型变式题
4. 提供针对性学习建议

---

## 4. Redis已做题目标记（行号41）

### 4.1 Redis数据结构

**Set结构（快速判断）:**
```
Key: ai:tutor:seen-q:{user_id}
Value: Set of question_ids
TTL: 30天
```

**ZSet结构（带时间戳）:**
```
Key: ai:tutor:seen-q-time:{user_id}
Score: timestamp
Member: question_id
```

### 4.2 双窗口策略

| 窗口类型 | 大小 | 用途 |
|---------|------|------|
| 滑动窗口 | 最近100题 | 防止短期重复 |
| 时间窗口 | 30天 | 长期记忆 |

### 4.3 核心API

| 端点 | 说明 |
|-----|------|
| `POST /seen-questions/mark` | 标记已做 |
| `GET /seen-questions/check/{id}` | 检查是否已做 |
| `POST /seen-questions/filter-unseen` | 过滤未做题目 |

---

## 5. 硬指标

### 5.1 错误分类

| 指标 | 值 |
|-----|-----|
| 错误类型数 | 8种 |
| 复健题数 | 3题 |
| 每类最大展示 | 20题 |

### 5.2 已做标记

| 指标 | 值 |
|-----|-----|
| 滑动窗口 | 100题 |
| 时间窗口 | 30天 |
| 数据结构 | Redis Set + ZSet |

---

## 6. Git提交记录

```bash
git add backend/services/error_classification_service.py
git add backend/services/seen_questions_service.py
git add backend/api/error_classification.py
git add backend/api/seen_questions.py
git add docs/V3_ErrorClass_SeenQuestions_IMPLEMENTATION.md

git commit -m "feat: Implement error classification and seen questions tracking (Row 13,41)

- Add 8 error type categories for wrong question classification
- Add view switching: time/chapter/error_category
- Add one-click rehabilitation pack (3 similar questions)
- Add Redis Set for seen questions tracking
- Add sliding window (100) + time window (30 days) strategy
- Add deduplication for question recommendation

对应飞书需求池:
- 行号13: 错题本按错误原因聚类
- 行号41: Redis已做题目标记"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
