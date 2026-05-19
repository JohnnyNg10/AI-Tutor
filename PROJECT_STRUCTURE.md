# AI Tutor 项目结构图

> 高中数学数列智能辅导系统
> 更新: 2026-05-11

---

## 顶层

```
AI Tutor/
├── backend/           # FastAPI后端 (所有核心逻辑)
├── frontend/          # Vue3前端
├── knowledge_base/    # 原始标注题库 (.md, 由小组成员人工编写, 导入ChromaDB)
├── database/          # SQL Schema定义
├── docs/              # 项目文档
├── PM/                # 产品经理求职材料
├── scripts/           # 运维/部署脚本
└── [配置] .gitignore, README.md, SETUP.md
```

---

## backend/ 结构

```
backend/
├── main.py                 ← 启动入口

├── agent/                  ← AI Agent (推荐+辅导)
│   ├── advisor.py             推荐引擎: 画像→推荐→反馈
│   └── instructor.py          辅导引擎: 对话→逐步提示(L0-L4)

├── api/                    ← HTTP路由 (注册在 __init__.py)
│   ├── auth.py                /auth/*           登录注册
│   ├── chat.py                /chat/*           核心聊天(SSE流式)
│   ├── advisor.py             /advisor/*        推荐+反馈
│   ├── upload.py              /upload/*         用户上传题目
│   ├── profile.py             /profile/*        用户画像
│   ├── records.py             /records/*        学习记录
│   ├── recommendation_v3.py   /recommendation/v3/*  V3推荐(ChromaDB)
│   ├── cognitive_diagnosis.py 认知诊断(skill-tree/daily-pack/streak)
│   ├── mastery_visualization.py  掌握度可视化
│   ├── six_dimensional_ability.py 六维能力V1
│   ├── six_dim_v2.py         六维能力V2(实时)
│   ├── ranking.py            IRT段位排名
│   ├── review.py             复习队列
│   ├── error_classification.py 错因分类
│   ├── pitfall_achievement.py  雷区成就
│   ├── knowledge_tree_progress.py 知识树进度
│   ├── ab_testing.py         A/B测试
│   ├── data_migration.py     数据迁移
│   └── ...                   其他已注册路由

├── services/               ← 业务逻辑层 (编排算法+DB+Redis)
│   ├── cognitive_diagnosis_service.py  认知诊断(BKT/IRT/衰减/连击)
│   ├── smart_recommendation_service.py  双源推荐
│   ├── redis_service.py               Redis数据结构
│   ├── redis_cache_service.py         Redis缓存封装
│   ├── chroma_service.py              ChromaDB封装
│   ├── llm_service.py                 LLM调用
│   ├── question_validation_service.py  LLM审核用户上传题
│   ├── question_structuring_service.py LLM结构化用户输入
│   ├── irt_ranking_service.py         IRT段位
│   ├── six_dim_v2_service.py          六维V2
│   ├── error_classification_service.py 错因分类
│   ├── knowledge_tree_progress_service.py 知识树进度
│   ├── interaction_logger_service.py  交互日志
│   ├── session_service.py             Redis Session
│   └── ...                           其他服务

├── algorithms/             ← 纯算法 (无DB/Redis依赖)
│   ├── bkt.py                  贝叶斯知识追踪
│   ├── irt_simple.py           项目反应理论
│   ├── memory_decay.py         艾宾浩斯遗忘曲线
│   ├── memory_decay_cron.py    记忆衰减定时任务
│   ├── skill_tree.py           知识依赖技能树
│   ├── rag_candidate_pool.py   RAG候选池
│   ├── question_recommendation.py  推荐引擎
│   ├── streak_handler.py       连击处理
│   ├── hint_generator.py       提示生成
│   └── ...

├── models/                 ← SQLAlchemy ORM
│   ├── user.py                 User
│   ├── question.py             Question
│   ├── record.py               LearningRecord
│   ├── profile.py              UserProfile
│   ├── chat.py                 ChatSession/Message/KnowledgePoint/UserKnowledgeMastery
│   └── learning_analytics.py   AbilityHistory/InteractionLog/MistakeBook/Favorite

├── rag/                    ← RAG检索
│   ├── retriever.py            知识检索器(ChromaDB查询/插入)
│   ├── init_chroma_db_v2.py    ChromaDB初始化
│   └── pipeline.py             RAG Pipeline

├── database/
│   └── db.py                  异步引擎+Session工厂+Schema迁移

├── utils/
│   ├── config.py               配置中心(.env)
│   ├── redis_client.py         Redis异步客户端
│   ├── auth.py                 JWT鉴权
│   └── logger.py               日志

├── init_data.py             → MySQL测试数据(5条)
├── init_questions.py        → ChromaDB导入(member_E JSON)
├── import_all_questions.py  → ChromaDB导入(knowledge_base所有.md)
└── init_knowledge.py        → ChromaDB知识点导入
```

---

## frontend/ 结构

```
frontend/
├── main.js              Vue入口
├── App.vue              根组件
├── vite.config.js       代理 /api → localhost:8000
├── router/index.js      路由: / /login /recommend /exercises /profile /mistakes
├── services/
│   ├── apiService.js    API封装(advisor/exercises等)
│   └── tutor-api.js     旧版SSE聊天适配
├── pages/
│   ├── AiTutorView.vue      主对话页(AI辅导)
│   ├── RecommendView.vue    推荐刷题页(核心)
│   ├── ExercisesView.vue    练习题页(依赖已删除的V2, 需更新)
│   ├── ProfileView.vue      用户画像
│   ├── MistakeBookView.vue  错题本
│   └── LoginView/RegisterView
└── components/
    ├── QuestionInput.vue     题目输入框
    ├── AnswerDisplay.vue     答案展示
    ├── SixDimRadarChart.vue  六维雷达图
    └── KnowledgeTree.vue     知识树
```

---

## 数据流: 用户如何看到推荐题目

```
RecommendView.vue
  → GET /advisor/recommend
    → api/advisor.py
      → agent/advisor.py: get_advisor_recommendations()
        ├── Redis: 画像缓存(profile), 复习队列(due reviews)
        ├── MySQL: 已做题去重, _fast_recommend() 标签匹配+难度匹配
        └── ChromaDB: (当前快速路径中绕过, 但有完整向量检索能力)
      → 返回 { recommendations, advisor_mode, profile_snapshot }
  → 用户作答
    → POST /advisor/feedback
      → 更新BKT/IRT (MySQL)
      → 更新复习队列 (Redis ZSet)
      → 更新连击状态 (Redis Hash)
```

## 题库数据链路

```
knowledge_base/question/member_*/*.md   (人工标注, ~130题)
  → import_all_questions.py 解析
    → ChromaDB example_questions collection  (向量库, 实际检索源)
    
dataset/member_E_questions_with_embedding.json  (33题, 带预计算embedding)
  → init_questions.py
    → ChromaDB example_questions

init_data.py
  → MySQL questions 表  (仅5条测试数据, 实际不使用)
```

## 已清理 (2026-05-11)

删除了 25+ 过时文件:
- V2推荐系统 (`recommendation_service.py`, `exercises.py`) — 查空的MySQL表
- 重复Agent (`agents/`, `advisor_api.py`) — 未注册路由
- Mock服务器, 空文件, 调试产物, 散落的测试文件
- 旧版ChromaDB初始化, 重复的IRT实现
