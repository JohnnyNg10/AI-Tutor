# Product Engineer Sprint — 2026-05-11

## 角色定位

**Product Engineer** = 全栈开发能力 + 产品思维 + 用户视角

今天扮演的角色：在 AI Tutor 项目中，作为 Product Engineer 完成了从用户痛点发现 → 方案设计 → 前后端实现 → 效果验证的完整闭环。

---

## 今日交付成果

### 一、核心 UX 修复

| # | 内容 | 影响范围 |
|---|------|---------|
| 1 | 知识树从 mock 数据切换为真实 DB 查询 | 后端 + 前端 |
| 2 | 知识树专题从 2 个扩展到 6 个（数列基础/等差/等比/求和/递推/归纳法） | 后端 skill_tree |
| 3 | 知识点节点可视化和每个节点的掌握度进度条 | 前端 KnowledgeTree |
| 4 | 里程碑 hover tooltip 显示达成条件和进度差距 | 前端 KnowledgeTree |
| 5 | 错误回退时明确标注"离线数据"而非假数据 | 前端 KnowledgeTree |
| 6 | 学习徽章墙组件（调用 /learning-badges API） | 新组件 |
| 7 | 雷区与攻克成就双列卡片（调用 /pitfall-achievement API） | 新组件 |
| 8 | ProfileView 骨架屏加载 | 前端 |
| 9 | 能力曲线支持历史数据 | 前端 |

### 二、基础设施修复

| # | 内容 | 影响范围 |
|---|------|---------|
| 1 | Redis 安装和配置（C:\Redis） | 基础设施 |
| 2 | RedisService 降级兼容（无 Redis 时服务不崩溃） | 后端 |
| 3 | OCR 重新上线（更新 API key + 模型迁移至 Qwen3-VL） | 后端 |
| 4 | current_user 类型 bug 修复（20+ 文件） | 后端 |
| 5 | learning_habit_badges 路由注册（之前从未被 include） | 后端 |
| 6 | pitfall_achievement_service 导入路径修复 | 后端 |

### 三、状态持久化

| # | 内容 | 影响范围 |
|---|------|---------|
| 1 | useRecommendSession composable（推荐做题进度断点续传） | 新 composable |
| 2 | useReviewSession composable（复习模式断点续传） | 新 composable |
| 3 | RecommendView 离开时自动保存 + 回来时恢复 + 横幅提示 | 前端 |
| 4 | MistakeBookView 复习模式持久化 | 前端 |

### 四、产品文档

| # | 内容 |
|---|------|
| 1 | RAG 候选池产品报告（三层漏斗、加权公式设计、三级降级链路）|
| 2 | 简历条目更新（新增 RAG 架构设计 + AI 安全治理 bullet points）|

---

## 当前运行状态

- Redis: 6379 ✅
- 后端: 8000 ✅
- 前端: 5177 ✅

---

## 关键设计决策

1. **知识树数据源**：短期保持 skill_tree.py 硬编码节点 + DB 掌握度，中期切换到 knowledge_graph
2. **状态持久化**：localStorage 优先（即时恢复）+ 后端 Redis Session 可选（跨设备）
3. **RAG 架构**：L1 完整路径 → L2 快速路径 → L3 随机兜底，三级降级保障可用性
4. **错误处理**：去除所有假数据回退，改为明确的"离线模式"标注 + 重试按钮
