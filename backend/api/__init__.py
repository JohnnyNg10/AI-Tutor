from fastapi import APIRouter
from api import (
    auth, chat, profile, upload, records, rag, questions,
    learning_tools, advisor, cognitive_diagnosis, knowledge_tree_progress,
    six_dimensional_ability,
    # V3 需求相关 API (需求 #1-10)
    ab_testing, mastery_visualization, ranking, six_dim_v2,
    review, pitfall_achievement, error_classification, favorite_insight,
    calculation_error, daily_completion, skip, seen_questions, session,
    knowledge_graph, learning_habit_badges,
)

api_router = APIRouter()

# 基础 API
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(profile.router, tags=["profile"])
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(records.router, tags=["records"])
api_router.include_router(rag.router, tags=["rag"])
api_router.include_router(questions.router, tags=["questions"])
api_router.include_router(learning_tools.router, tags=["learning_tools"])

# Agent API
api_router.include_router(advisor.router, tags=["advisor"])

# 认知诊断 API (需求#1 连击, #5 ActualScore, #10 技能树, #7 记忆衰减)
api_router.include_router(cognitive_diagnosis.router)

# V3 需求 API
api_router.include_router(ab_testing.router)                    # 需求#3 A/B测试
api_router.include_router(mastery_visualization.router)          # 需求#2 掌握度可视化
api_router.include_router(ranking.router)                        # 需求#9 IRT段位
api_router.include_router(six_dimensional_ability.router)        # 需求#4 六维能力画像
api_router.include_router(six_dim_v2.router)                     # 需求#8 六维能力V2
api_router.include_router(knowledge_tree_progress.router)        # 知识树进度
api_router.include_router(review.router)                         # 需求#12/13 复习队列
api_router.include_router(pitfall_achievement.router)            # 需求#11 雷区与成就
api_router.include_router(learning_habit_badges.router)          # 需求#23/28 学习习惯徽章
api_router.include_router(error_classification.router)           # 需求#14 错因分类
api_router.include_router(favorite_insight.router)              # 需求#15 收藏夹
api_router.include_router(skip.router)                          # 跳过处理
api_router.include_router(calculation_error.router)              # 计算失误
api_router.include_router(daily_completion.router)               # 每日完课
api_router.include_router(seen_questions.router)                 # 已做题目标记
api_router.include_router(session.router)                        # Session管理
api_router.include_router(knowledge_graph.router)               # 知识图谱
