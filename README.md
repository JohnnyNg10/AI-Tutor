# AI Tutor - 高中数学数列智能辅导系统

## 项目简介
本项目旨在开发一个基于大语言模型的 AI Tutor 系统，用于辅助高中生学习数学数列知识。  
系统采用 **多 Agent 协作架构**：
- **Instructor Agent**：分析题目、提供分步骤解题讲解
- **Advisor Agent**：生成学生画像、推送个性化练习题、生成短期学习计划  

核心技术：
- **RAG (Retrieval-Augmented Generation)** + **知识图谱 (KG)**
- 双 Agent 架构实现智能教学
- 前后端分离：FastAPI + Vue3

---

## 项目目标（阶段性）

1. 实现 AI Tutor 问答系统（初版原型）
2. 构建数学数列结构化题库，并构建知识图谱
3. 实现个性化推送练习题
4. 实现分步骤解题讲解
5. 提供简单网页交互界面供学生使用

---

## 系统架构

![AI Tutor 系统架构](docs/ai_tutor_architecture.png)  

**说明：**
- Instructor Agent：题目分析、分步骤讲解
- Advisor Agent：学习画像、错题分析、练习题推荐
- RAG + KG：向量检索 + 知识图谱查询
- 后端 FastAPI：API 调度
- 前端 Vue3：题目输入与结果显示

---

## 技术栈

| 模块 | 技术栈 |
|------|--------|
| 后端 | Python, FastAPI, SQLAlchemy async, Celery + Redis |
| Agent | Python, LangChain, LlamaIndex, RAG |
| 数据库 | MySQL, Elasticsearch |
| 前端 | Vue3, Axios, SSE |
| 数据处理 | Python, Pandas, NumPy |
| 知识图谱 | NetworkX, JSON |

---

## 项目目录结构

```text
ai_tutor_project/
│
├── backend/                     # 后端核心逻辑
│   ├── main.py                  # FastAPI启动入口
│   ├── api/                     # API接口
│   │    ├── chat.py             # Instructor/Advisor对话接口
│   │    ├── profile.py          # 学生画像接口
│   │    └── exercises.py        # 推送练习题接口
│   ├── agent/                   # 双Agent逻辑
│   │    ├── instructor.py
│   │    └── advisor.py
│   ├── rag/                     # RAG知识库检索
│   │    ├── vector_db.py
│   │    └── retriever.py
│   ├── kg/                      # 数学知识图谱构建
│   │    └── kg_builder.py
│   ├── models/                  # 数据库模型
│   │    ├── user.py
│   │    ├── question.py
│   │    └── record.py
│   └── utils/                   # 工具函数
│        └── data_loader.py
│
├── frontend/                     # Web界面
│   ├── pages/
│   ├── components/
│   └── services/
│
├── dataset/                      # 数列题库JSON
│   └── sequence_problems.json
│
├── prompts/                      # Prompt模板
│   ├── instructor_prompt.txt
│   └── advisor_prompt.txt
│
└── docs/
     ├── ai_tutor_architecture.png   # 系统架构图
     └── plan.md                     # 项目计划文档
