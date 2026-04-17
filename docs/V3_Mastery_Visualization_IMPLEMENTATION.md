# V3 掌握度可视化实现文档

**需求编号**: 需求1  
**需求名称**: 将BKT算法生成的掌握度P(L)转化为直观的色彩和水位动效  
**实现日期**: 2026-04-17  
**状态**: ✅ 已完成

---

## 1. 需求概述

将BKT算法生成的掌握度P(L)转化为前端可视化组件所需的数据格式：
- 圆环/水滴组件展示整体掌握度
- 颜色联动（红/黄/绿）表示掌握度等级
- 水位动效展示掌握度百分比
- 专题进度计算（知识树节点解锁率）

---

## 2. 实现文件

| 文件路径 | 说明 | 代码行数 |
|---------|------|---------|
| `backend/services/mastery_visualization_service.py` | 掌握度可视化服务 | ~400行 |
| `backend/api/mastery_visualization.py` | 掌握度可视化API | ~250行 |

---

## 3. 核心功能实现

### 3.1 P(L)到掌握度等级的转换（硬指标）

```python
# 硬指标阈值
MASTERY_THRESHOLD_WEAK = 0.5      # < 0.5 为薄弱
MASTERY_THRESHOLD_LEARNING = 0.8  # < 0.8 为学习中
# >= 0.8 为已掌握

def p_known_to_level(self, p_known: float) -> str:
    if p_known < 0.5:
        return 'weak'      # 薄弱
    elif p_known < 0.8:
        return 'learning'  # 学习中
    else:
        return 'mastered'  # 已掌握
```

### 3.2 P(L)到颜色的转换（硬指标）

| P(L)范围 | 等级 | 颜色 | 含义 |
|---------|------|------|------|
| < 0.5 | weak | #FF4D4F (红) | 危险区 |
| 0.5 - 0.8 | learning | #FAAD14 (黄) | 过渡区 |
| >= 0.8 | mastered | #52C41A (绿) | 掌握区 |

### 3.3 水位高度计算

```python
def calculate_water_level(self, global_mastery: float) -> int:
    """将全局掌握度映射为0-100的水位高度"""
    return int(global_mastery * 100)
```

### 3.4 专题进度计算（硬指标）

```python
# 进度计算公式
progress_percentage = (P(L) >= 0.8的知识点数量) / (该专题总知识点数量) * 100
```

---

## 4. API接口

### 4.1 获取掌握度可视化数据

```http
GET /mastery/visualization?topics=等差数列&topics=等比数列
```

**响应：**
```json
{
  "success": true,
  "user_id": 1,
  "global_mastery": 0.65,
  "water_level": 65,
  "ring_color": "#FAAD14",
  "status_text": "正在学习",
  "statistics": {
    "total": 10,
    "weak": 2,
    "learning": 5,
    "mastered": 3
  },
  "mastery_levels": [
    {
      "kp_id": "arith_001",
      "kp_name": "等差数列基础",
      "p_known": 0.9,
      "level": "mastered",
      "color": "#52C41A",
      "percentage": 90
    }
  ],
  "topic_progress": [
    {
      "topic": "等差数列",
      "progress": 60.0,
      "progress_text": "60%",
      "status": "in_progress",
      "mastered": 3,
      "total": 5
    }
  ]
}
```

### 4.2 获取专题进度

```http
GET /mastery/topic-progress/等差数列
```

### 4.3 获取能力曲线

```http
GET /mastery/ability-curve?days=30
```

### 4.4 获取颜色映射配置

```http
GET /mastery/color-mapping
```

**响应：**
```json
{
  "success": true,
  "thresholds": {
    "weak": 0.5,
    "learning": 0.8
  },
  "colors": {
    "weak": "#FF4D4F",
    "learning": "#FAAD14",
    "mastered": "#52C41A"
  },
  "status_texts": {
    "weak": "需要加强",
    "learning": "正在学习",
    "mastered": "已掌握"
  }
}
```

---

## 5. 硬指标实现

### 5.1 掌握度阈值

| 阈值 | 值 | 实现位置 |
|-----|-----|---------|
| 薄弱阈值 | 0.5 | `MASTERY_THRESHOLD_WEAK` |
| 掌握阈值 | 0.8 | `MASTERY_THRESHOLD_LEARNING` |

### 5.2 颜色映射

| 等级 | 颜色值 | 实现位置 |
|-----|--------|---------|
| weak | #FF4D4F | `COLOR_MAP['weak']` |
| learning | #FAAD14 | `COLOR_MAP['learning']` |
| mastered | #52C41A | `COLOR_MAP['mastered']` |

### 5.3 专题进度公式

```
progress_percentage = (mastered_nodes / total_nodes) * 100

其中：
- mastered_nodes = P(L) >= 0.8的知识点数量
- total_nodes = 该专题总知识点数量
```

---

## 6. 前端组件对接

### 6.1 圆环组件

```javascript
// 使用API返回的数据
const ringData = {
  percentage: response.water_level,  // 0-100
  color: response.ring_color,        // #FF4D4F / #FAAD14 / #52C41A
  status: response.status_text       // 需要加强 / 正在学习 / 已掌握
};
```

### 6.2 水滴组件

```javascript
// 水位高度直接映射
const waterLevel = response.water_level;  // 0-100
```

### 6.3 专题进度条

```javascript
// 使用topic_progress数据
const topicProgress = response.topic_progress.map(topic => ({
  name: topic.topic,
  progress: topic.progress,
  status: topic.status  // not_started / in_progress / completed
}));
```

---

## 7. 验收标准

- [x] P(L) < 0.5 显示红色（危险区）
- [x] 0.5 <= P(L) < 0.8 显示黄色（过渡区）
- [x] P(L) >= 0.8 显示绿色（掌握区）
- [x] 水位高度正确映射（0-100）
- [x] 专题进度计算正确
- [x] 从Redis Mastery Hash读取数据
- [x] 能力曲线历史数据查询

---

## 8. Git提交记录

```bash
git add backend/services/mastery_visualization_service.py
git add backend/api/mastery_visualization.py
git add docs/V3_Mastery_Visualization_IMPLEMENTATION.md

git commit -m "feat: Implement mastery visualization API (Req #1)

- Add P(L) to color mapping (red/yellow/green)
- Add water level calculation (0-100)
- Add topic progress calculation
- Add ability curve data query
- Add mastery visualization API endpoints

Closes requirement #1"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-17  
**作者**: AI Assistant
