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

# AI Tutor 项目阶段目标规划

| 阶段 | 目标描述 | 可交付成果 | 技术栈 / 备注 |
|------|----------|------------|----------------|
| **阶段 1** | 实现 AI Tutor 问答系统（初版原型，无 RAG 和 KG） | - 可运行问答原型 <br> - 静态题库测试示例 | Python, FastAPI, LLM API调用，JSON题库 |
| **阶段 2** | 构建数学数列结构化题库，完成向量数据库，给 Agent 加入 RAG 模块 | - 小规模题库（100~200题） <br> - 向量化索引完成 <br> - Agent 能调用 RAG 生成答案 | Python, Chroma/FAISS, LangChain, LLM |
| **阶段 3** | 人工+LLM辅助构建 KG 知识图谱，实现分步骤解题 | - KG初版（知识点、方法、题目关联） <br> - Instructor Agent 可生成分步骤解题 | Python, NetworkX, LangChain, LLM，人工整理+模型辅助 |
| **阶段 4** | 实现个性化推送练习题 | - Advisor Agent 可根据学生错题或历史生成练习题列表 <br> - 简单学习画像生成 | Python, SQLAlchemy async, Redis, LangChain |
| **阶段 5** | 提供简单网页交互界面供学生使用 | - 前端页面可输入题目并显示解题步骤 <br> - 可显示推荐练习题和学习计划 | Vue3 / React, Axios, SSE，前后端接口对接 |

---

## 系统架构


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
├── backend/                        # 后端核心逻辑
│
│   ├── main.py                     # FastAPI启动入口
│
│   ├── api/                        # API接口层
│   │
│   │   ├── chat.py                 # Tutor对话接口
│   │   ├── profile.py              # 学生画像接口
│   │   ├── exercises.py            # 练习题推荐接口
│   │   │
│   │   ├── auth.py                 # 登录注册接口（新增）
│   │   └── upload.py               # 图片/文件上传接口（新增）
│
│
│   ├── agent/                      # 多Agent系统
│   │
│   │   ├── instructor.py           # 解题Agent
│   │   ├── advisor.py              # 学习规划Agent
│   │   └── planner.py              # Agent调度器（可选增强）
│
│
│   ├── multimodal/                 # 多模态输入处理模块
│   │
│   │   ├── image_parser.py         # 图片题目解析
│   │   ├── file_parser.py          # PDF/文档解析
│   │   └── question_formatter.py   # 统一转换为标准题目格式
│
│
│   ├── rag/                        # RAG模块
│   │
│   │   ├── vector_db.py            # 向量数据库
│   │   ├── retriever.py            # 检索逻辑
│   │   └── embedding.py            # 文本向量化
│
│
│   ├── kg/                         # 知识图谱模块
│   │
│   │   ├── kg_builder.py           # KG构建
│   │   └── kg_query.py             # KG查询接口
│
│
│   ├── models/                     # 数据库模型
│   │
│   │   ├── user.py                 # 用户表
│   │   ├── question.py             # 题目表
│   │   ├── record.py               # 学习记录
│   │   ├── profile.py              # 学生画像（新增）
│   │   └── exercise_history.py     # 练习历史（新增）
│
│
│   ├── services/                   # 业务逻辑层
│   │
│   │   ├── auth_service.py         # 登录注册逻辑
│   │   ├── tutor_service.py        # Tutor调用逻辑
│   │   ├── recommendation_service.py # 推荐系统
│   │   └── profile_service.py      # 学生画像更新
│
│
│   ├── database/                   # 数据库配置（新增）
│   │
│   │   ├── db.py                   # 数据库连接
│   │   └── init_db.py              # 初始化数据库
│
│
│   └── utils/                      # 工具函数
│
│        ├── data_loader.py         # 题库加载
│        ├── logger.py              # 日志
│        └── config.py              # 配置文件
│
│
├── frontend/                       # 前端
│
│   ├── pages/
│   │
│   │   ├── login.vue               # 登录页
│   │   ├── register.vue            # 注册页
│   │   ├── chat.vue                # Tutor页面
│   │   └── profile.vue             # 学习画像
│
│   ├── components/
│   │
│   │   ├── QuestionInput.vue       # 题目输入组件
│   │   ├── ImageUploader.vue       # 图片上传组件（新增）
│   │   └── AnswerDisplay.vue       # 解题步骤展示
│
│   └── services/
│
│        ├── api.js                 # API封装
│        └── auth.js                # 登录认证
│
│
├── dataset/                        # 原始数据
│
│   └── sequence_problems.json      # 数列题库
│
│
├── prompts/                        # Prompt模板
│
│   ├── instructor_prompt.txt
│   └── advisor_prompt.txt
│
│
├── storage/                        # 用户上传文件存储
│
│   ├── images/
│   └── documents/
│
│
├── docs/                           # 项目文档
│
│   ├── architecture.md
│   ├── ai_tutor_architecture.png
│   └── plan.md
│
│
└── requirements.txt
