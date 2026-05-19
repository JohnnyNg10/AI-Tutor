"""
认知诊断API接口
提供BKT、IRT、Actual Score等算法的REST API
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_db
from services.cognitive_diagnosis_service import (
    cognitive_service,
    update_mastery_after_answer,
    get_user_theta,
    compute_actual_score,
    get_user_mastery_dict,
)

router = APIRouter(prefix="/cognitive", tags=["cognitive-diagnosis"])


# ============ 请求/响应模型 ============

class MasteryUpdateRequest(BaseModel):
    """更新掌握度请求"""
    user_id: int = Field(..., description="用户ID")
    knowledge_point_id: int = Field(..., description="知识点ID")
    is_correct: bool = Field(..., description="是否答对")


class MasteryUpdateResponse(BaseModel):
    """更新掌握度响应"""
    user_id: int
    knowledge_point_id: int
    p_known: float = Field(..., description="更新后的掌握度")
    mastery_level: str = Field(..., description="掌握度等级: mastered/learning/weak")


class ThetaEstimateResponse(BaseModel):
    """能力值估计响应"""
    user_id: int
    theta: float = Field(..., description="最终能力值", ge=-3, le=3)
    theta_irt: float = Field(..., description="IRT估计值")
    theta_bkt: float = Field(..., description="BKT映射值")
    alpha: float = Field(..., description="K-IRT权重", ge=0, le=1)
    theta_se: float = Field(..., description="标准误")
    ci_lower: float = Field(..., description="置信区间下限")
    ci_upper: float = Field(..., description="置信区间上限")


class ActualScoreRequest(BaseModel):
    """计算Actual Score请求"""
    is_correct: bool = Field(..., description="是否正确")
    hint_level: int = Field(..., description="提示等级 0-4", ge=0, le=4)
    time_spent: float = Field(..., description="实际耗时(秒)", gt=0)
    expected_time: float = Field(..., description="期望耗时(秒)", gt=0)
    skip_reason: Optional[str] = Field(None, description="跳过原因")


class ActualScoreResponse(BaseModel):
    """计算Actual Score响应"""
    actual_score: float = Field(..., description="实际得分", ge=0, le=1)
    hint_level_name: str = Field(..., description="提示等级名称")
    components: dict = Field(..., description="分数组成部分")


class DifficultyRangeResponse(BaseModel):
    """推荐难度范围响应"""
    theta: float = Field(..., description="当前能力值")
    min_difficulty: float = Field(..., description="最小难度", ge=-3, le=3)
    max_difficulty: float = Field(..., description="最大难度", ge=-3, le=3)
    recommended_range: str = Field(..., description="推荐范围描述")


class ComprehensiveReportResponse(BaseModel):
    """综合诊断报告响应"""
    user_id: int
    ability: dict = Field(..., description="能力值信息")
    mastery_distribution: dict = Field(..., description="掌握度分布")
    recommended_difficulty: dict = Field(..., description="推荐难度范围")
    generated_at: str = Field(..., description="生成时间")


class MemoryDecayRequest(BaseModel):
    """应用记忆衰减请求"""
    user_id: int = Field(..., description="用户ID")


class MemoryDecayResponse(BaseModel):
    """应用记忆衰减响应"""
    user_id: int
    updated_count: int = Field(..., description="更新的知识点数量")
    updates: List[dict] = Field(..., description="更新详情")


# ============ 需求1：连击状态与难度自适应调整 ============

class StreakUpdateRequest(BaseModel):
    """更新连击状态请求（需求1）"""
    user_id: int = Field(..., description="用户ID")
    knowledge_point_id: int = Field(..., description="知识点ID")
    is_correct: bool = Field(..., description="是否答对")


class StreakUpdateResponse(BaseModel):
    """更新连击状态响应（需求1）"""
    user_id: int
    knowledge_point_id: int
    p_known: float = Field(..., description="更新后的掌握度")
    p_known_change: float = Field(..., description="掌握度变化")
    # 连击状态
    consecutive_correct: int = Field(..., description="连续正确次数")
    consecutive_wrong: int = Field(..., description="连续错误次数")
    # 难度调整
    difficulty_adjustment: dict = Field(..., description="难度调整详情")
    # UI效果
    ui_effect: Optional[dict] = Field(None, description="UI效果定义")
    should_trigger_effect: bool = Field(..., description="是否触发效果")


class StreakStateResponse(BaseModel):
    """获取连击状态响应（需求1）"""
    user_id: int
    consecutive_correct: int = Field(..., description="连续正确次数")
    consecutive_wrong: int = Field(..., description="连续错误次数")
    current_streak_type: str = Field(..., description="当前连击类型")
    current_streak_count: int = Field(..., description="当前连击计数")


# ============ 需求10：游戏技能树 ============

class SkillTreeRequest(BaseModel):
    """获取技能树请求（需求10）"""
    user_id: int = Field(..., description="用户ID")
    topic: str = Field(..., description="专题名称，如：等差数列")


class SkillTreeResponse(BaseModel):
    """技能树响应（需求10）"""
    topic: str
    nodes: dict = Field(..., description="节点详情")
    edges: List[tuple] = Field(..., description="边关系")
    total_nodes: int


class TopicProgressResponse(BaseModel):
    """专题进度响应（需求10）"""
    topic: str
    total_nodes: int
    mastered_nodes: int
    learning_nodes: int
    weak_nodes: int
    locked_nodes: int
    progress_percentage: float
    progress_text: str


class TrainingRecommendationResponse(BaseModel):
    """推荐训练响应（需求10）"""
    topic: str
    recommendations: List[dict] = Field(..., description="推荐节点列表")
    count: int


# ============ API端点 ============

@router.post("/mastery/update", response_model=MasteryUpdateResponse)
async def api_update_mastery(
    request: MasteryUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    更新知识点掌握度（BKT算法）
    
    根据答题结果使用贝叶斯知识追踪算法更新掌握度
    """
    try:
        p_known = await update_mastery_after_answer(
            db,
            request.user_id,
            request.knowledge_point_id,
            request.is_correct
        )
        
        mastery_level = cognitive_service.get_mastery_level(p_known)
        
        return MasteryUpdateResponse(
            user_id=request.user_id,
            knowledge_point_id=request.knowledge_point_id,
            p_known=round(p_known, 4),
            mastery_level=mastery_level
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新掌握度失败: {str(e)}")


@router.get("/theta/{user_id}", response_model=ThetaEstimateResponse)
async def api_get_theta(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取学生能力值估计（K-IRT联合估算）
    
    使用K-IRT算法联合估算学生能力值
    """
    try:
        theta_info = await get_user_theta(db, user_id)
        
        return ThetaEstimateResponse(
            user_id=user_id,
            **theta_info
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"估计能力值失败: {str(e)}")


@router.post("/actual-score/calculate", response_model=ActualScoreResponse)
async def api_calculate_actual_score(request: ActualScoreRequest):
    """
    计算Actual Score（实际得分）
    
    根据答题正确性、提示等级、耗时计算实际得分
    
    提示等级说明：
    - 0: 自主完成 (权重1.0)
    - 1: 方向提示 (权重0.8)
    - 2: 公式提示 (权重0.6)
    - 3: 步骤推导 (权重0.4)
    - 4: 完整答案 (权重0.1)
    """
    try:
        score = await compute_actual_score(
            is_correct=request.is_correct,
            hint_level=request.hint_level,
            time_spent=request.time_spent,
            expected_time=request.expected_time,
            skip_reason=request.skip_reason
        )
        
        # 获取提示等级名称
        hint_names = {
            0: "自主完成",
            1: "方向提示",
            2: "公式提示",
            3: "步骤推导",
            4: "完整答案"
        }
        
        # 计算各组成部分（用于展示）
        from algorithms.actual_score import ActualScoreCalculator, AnswerRecord, HintLevel
        calc = ActualScoreCalculator()
        record = AnswerRecord(
            is_correct=request.is_correct,
            hint_level=HintLevel(request.hint_level),
            time_spent=request.time_spent,
            expected_time=request.expected_time,
            skip_reason=request.skip_reason
        )
        
        components = {
            "correctness": request.is_correct,
            "hint_weight": calc.params.hint_weights[HintLevel(request.hint_level)],
            "time_ratio": round(request.time_spent / request.expected_time, 2),
            "skip_reason": request.skip_reason
        }
        
        return ActualScoreResponse(
            actual_score=round(score, 4),
            hint_level_name=hint_names.get(request.hint_level, "未知"),
            components=components
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"计算Actual Score失败: {str(e)}")


@router.get("/difficulty-range/{user_id}", response_model=DifficultyRangeResponse)
async def api_get_difficulty_range(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取推荐题目难度范围
    
    基于学生能力值推荐合适的题目难度范围 [theta-0.5, theta+0.5]
    """
    try:
        theta_info = await get_user_theta(db, user_id)
        theta = theta_info['theta']
        
        min_diff, max_diff = cognitive_service.get_recommended_difficulty_range(theta)
        
        return DifficultyRangeResponse(
            theta=theta,
            min_difficulty=min_diff,
            max_difficulty=max_diff,
            recommended_range=f"[{min_diff:+.1f}, {max_diff:+.1f}]"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取难度范围失败: {str(e)}")


@router.get("/report/{user_id}", response_model=ComprehensiveReportResponse)
async def api_get_comprehensive_report(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取综合诊断报告
    
    包含能力值、掌握度分布、推荐难度等完整信息
    """
    try:
        report = await cognitive_service.get_comprehensive_report(db, user_id)
        return ComprehensiveReportResponse(**report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")


@router.post("/memory-decay/apply", response_model=MemoryDecayResponse)
async def api_apply_memory_decay(
    request: MemoryDecayRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    应用记忆衰减（艾宾浩斯遗忘曲线）
    
    对所有知识点应用遗忘曲线计算，更新掌握度
    """
    try:
        updates = await cognitive_service.apply_memory_decay(db, request.user_id)
        
        return MemoryDecayResponse(
            user_id=request.user_id,
            updated_count=len(updates),
            updates=updates
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"应用记忆衰减失败: {str(e)}")


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "service": "cognitive-diagnosis",
        "algorithms": ["BKT", "IRT", "K-IRT", "Adaptive-K", "Memory-Decay", "Actual-Score", "Streak-Handler"]
    }


# ============ 需求1 API端点 ============

@router.post("/streak/update", response_model=StreakUpdateResponse)
async def api_update_streak(
    request: StreakUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    更新连击状态并触发难度自适应调整（需求1）
    
    核心逻辑：
    - 高光连击：连续正确3次，难度上限+0.3，触发火焰特效
    - 降级保护：连续错误2次，难度下限-0.3，触发保护伞/咖啡杯特效
    """
    try:
        # 调用服务层更新掌握度和连击状态
        result = await cognitive_service.update_knowledge_mastery(
            db,
            request.user_id,
            request.knowledge_point_id,
            request.is_correct
        )
        
        return StreakUpdateResponse(
            user_id=request.user_id,
            knowledge_point_id=request.knowledge_point_id,
            p_known=round(result['p_known'], 4),
            p_known_change=round(result['p_known_change'], 4),
            consecutive_correct=result['consecutive_correct'],
            consecutive_wrong=result['consecutive_wrong'],
            difficulty_adjustment=result['difficulty_adjustment'],
            ui_effect=result['ui_effect'],
            should_trigger_effect=result['should_trigger_effect']
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新连击状态失败: {str(e)}")


@router.get("/streak/state/{user_id}", response_model=StreakStateResponse)
async def api_get_streak_state(user_id: int):
    """
    获取用户当前连击状态（需求1）
    
    返回用户的连续正确/错误次数
    """
    try:
        from algorithms.streak_handler import get_streak_handler
        handler = get_streak_handler()
        state = handler.get_user_streak_state(user_id)
        
        return StreakStateResponse(
            user_id=user_id,
            consecutive_correct=state.consecutive_correct,
            consecutive_wrong=state.consecutive_wrong,
            current_streak_type=state.current_streak_type.value,
            current_streak_count=state.current_streak_count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取连击状态失败: {str(e)}")


@router.post("/streak/reset/{user_id}")
async def api_reset_streak(user_id: int):
    """
    重置用户连击状态（需求1）
    
    用于测试或特殊场景下重置连击计数
    """
    try:
        from algorithms.streak_handler import get_streak_handler
        handler = get_streak_handler()
        state = handler.reset_streak(user_id)
        
        return {
            "user_id": user_id,
            "message": "连击状态已重置",
            "state": state.to_dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置连击状态失败: {str(e)}")


# ============ 需求10 API端点 ============

async def _get_user_mastery_for_skill_tree(db: AsyncSession, user_id: int) -> dict:
    """
    从数据库获取用户掌握度，转换为技能树可用格式 {node_id: p_known}

    匹配策略（三级fallback）：
    1. 关联标签匹配（associated_tags）
    2. 节点名称匹配
    3. node_id匹配
    """
    from algorithms.skill_tree import get_skill_tree_builder
    builder = get_skill_tree_builder()

    db_mastery = await get_user_mastery_dict(db, user_id)

    # 使用 SkillTreeBuilder 的标签匹配方法
    return builder.match_user_mastery_by_tags(db_mastery)


@router.post("/skill-tree", response_model=SkillTreeResponse)
async def api_get_skill_tree(request: SkillTreeRequest, db: AsyncSession = Depends(get_db)):
    """
    获取用户的技能树（需求10）

    返回带状态的知识点技能树，包含：
    - 绿色：已掌握 (P(L) >= 0.8)
    - 黄色：学习中 (0.5 <= P(L) < 0.8)
    - 红色：薄弱点 (P(L) < 0.5)
    - 灰色：锁定（前置未达标）
    """
    try:
        from algorithms.skill_tree import get_skill_tree_builder
        builder = get_skill_tree_builder()

        mastery = await _get_user_mastery_for_skill_tree(db, request.user_id)
        user_tree = builder.build_user_skill_tree(request.topic, mastery)

        return SkillTreeResponse(
            topic=user_tree.topic,
            nodes={k: v.to_dict() for k, v in user_tree.nodes.items()},
            edges=user_tree.edges,
            total_nodes=user_tree.total_nodes
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取技能树失败: {str(e)}")


@router.post("/skill-tree/progress", response_model=TopicProgressResponse)
async def api_get_topic_progress(request: SkillTreeRequest, db: AsyncSession = Depends(get_db)):
    """
    获取专题进度（需求10）

    PRD公式：进度百分比 = (P(L) >= 0.8 的知识点数量) / (该专题总知识点数量)
    """
    try:
        from algorithms.skill_tree import get_skill_tree_builder
        builder = get_skill_tree_builder()

        mastery = await _get_user_mastery_for_skill_tree(db, request.user_id)
        progress = builder.calculate_topic_progress(request.topic, mastery)

        return TopicProgressResponse(**progress.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取专题进度失败: {str(e)}")


@router.post("/skill-tree/recommendations")
async def api_get_training_recommendations(request: SkillTreeRequest, db: AsyncSession = Depends(get_db), limit: int = 3):
    """
    获取推荐训练节点（一键特训）（需求10）

    推荐策略：
    1. 优先推荐薄弱点（红色）
    2. 其次推荐学习中（黄色）
    3. 排除已掌握（绿色）和锁定（灰色）
    """
    try:
        from algorithms.skill_tree import get_skill_tree_builder
        builder = get_skill_tree_builder()

        mastery = await _get_user_mastery_for_skill_tree(db, request.user_id)
        recommendations = builder.get_recommended_training(request.topic, mastery, limit=limit)

        return TrainingRecommendationResponse(
            topic=request.topic,
            recommendations=recommendations,
            count=len(recommendations)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取推荐训练失败: {str(e)}")


@router.get("/skill-tree/topics")
async def api_get_all_topics():
    """
    获取所有专题列表（需求10）
    """
    try:
        from algorithms.skill_tree import get_skill_tree_builder
        builder = get_skill_tree_builder()
        
        topics = builder.get_all_topics()
        
        return {
            "topics": topics,
            "count": len(topics)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取专题列表失败: {str(e)}")


# ============ 需求16：渐进式提示按钮 API端点 ============

class HintButtonClickRequest(BaseModel):
    """提示按钮点击请求（需求16）"""
    user_id: int = Field(..., description="用户ID")


class HintButtonClickResponse(BaseModel):
    """提示按钮点击响应（需求16）"""
    user_id: int
    previous_state: Optional[str] = Field(None, description="之前的状态")
    current_state: str = Field(..., description="当前状态")
    button_config: dict = Field(..., description="按钮配置")
    click_count: int = Field(..., description="点击次数")
    hint_level: Optional[int] = Field(None, description="提示等级")
    actual_weight: float = Field(..., description="Actual权重")


class HintButtonStateResponse(BaseModel):
    """获取提示按钮状态响应（需求16）"""
    user_id: int
    current_state: str = Field(..., description="当前状态")
    click_count: int = Field(..., description="点击次数")
    button_config: dict = Field(..., description="按钮配置")
    hint_level: Optional[int] = Field(None, description="提示等级")
    actual_weight: float = Field(..., description="Actual权重")
    is_visible: bool = Field(..., description="按钮是否可见")
    is_highlighted: bool = Field(..., description="按钮是否标红")


@router.post("/hint-button/click", response_model=HintButtonClickResponse)
async def api_hint_button_click(request: HintButtonClickRequest):
    """
    点击渐进式提示按钮（需求16）
    
    状态机流转：
    - 初始状态 -> L1 -> L2 -> L3 -> L4(隐藏)
    - 每次点击返回对应的hint_level和Actual权重
    """
    try:
        from algorithms.hint_button_state_machine import get_hint_button_sm
        sm = get_hint_button_sm()
        
        result = sm.click(request.user_id)
        
        return HintButtonClickResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"点击提示按钮失败: {str(e)}")


@router.post("/hint-button/reset")
async def api_hint_button_reset(request: HintButtonClickRequest):
    """
    重置提示按钮状态机（需求16）
    
    触发条件：学生提交正确答案时调用
    """
    try:
        from algorithms.hint_button_state_machine import get_hint_button_sm
        sm = get_hint_button_sm()
        
        result = sm.reset(request.user_id)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置提示按钮失败: {str(e)}")


@router.get("/hint-button/state/{user_id}", response_model=HintButtonStateResponse)
async def api_get_hint_button_state(user_id: int):
    """
    获取提示按钮当前状态（需求16）
    
    用于前端初始化按钮显示
    """
    try:
        from algorithms.hint_button_state_machine import get_hint_button_sm
        sm = get_hint_button_sm()
        
        result = sm.get_full_state(user_id)
        
        return HintButtonStateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取提示按钮状态失败: {str(e)}")


# ============ 需求20：每日5题特训包 API端点 ============

class DailyPackRequest(BaseModel):
    """获取每日特训包请求（需求20）"""
    user_id: int = Field(..., description="用户ID")
    date: Optional[str] = Field(None, description="日期，默认今天")


class DailyPackResponse(BaseModel):
    """每日特训包响应（需求20）"""
    user_id: int
    date: str
    total_questions: int
    questions: List[dict] = Field(..., description="题目列表")
    type_distribution: dict = Field(..., description="题型分布")


@router.post("/daily-pack", response_model=DailyPackResponse)
async def api_get_daily_pack(request: DailyPackRequest, db: AsyncSession = Depends(get_db)):
    """
    获取每日5题特训包（需求20）
    
    动态混排配比：
    - 温故题 (复习)：1-2题，从Redis Review Queue获取
    - 攻坚题 (薄弱)：2-3题，P(L)<0.5的知识点变式题
    - 探索题 (拓展)：1题，符合θ难度区间的全新题目
    
    UI标签：[温故]、[攻坚]、[探索]
    """
    try:
        from algorithms.daily_training_pack import get_daily_pack_generator
        generator = get_daily_pack_generator()
        
        # 从数据库获取用户实际数据
        theta_info = await get_user_theta(db, request.user_id)
        user_theta = theta_info.get('theta', 0.5)
        db_mastery = await get_user_mastery_dict(db, request.user_id)
        user_mastery = db_mastery if db_mastery else {"默认": 0.5}
        review_queue = []
        
        pack = generator.generate_pack(
            user_id=request.user_id,
            user_theta=user_theta,
            user_mastery=user_mastery,
            review_queue=review_queue,
            date=request.date
        )
        
        return DailyPackResponse(**pack.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取每日特训包失败: {str(e)}")


# ============ 需求29：记忆衰减Cron任务 API端点 ============

class CronJobResponse(BaseModel):
    """Cron任务执行响应（需求29）"""
    execution_time: str
    total_processed: int
    total_decayed: int
    results: List[dict]


@router.post("/cron/memory-decay", response_model=CronJobResponse)
async def api_execute_memory_decay_cron(db: AsyncSession = Depends(get_db)):
    """
    执行记忆衰减定时任务（需求29）

    执行频率：每日凌晨 02:00
    衰减公式：P(L_t) = P(L_{t-1}) × e^(-λΔt)
    缓存同步：更新MySQL后同步Redis
    """
    try:
        from algorithms.memory_decay_cron import MemoryDecayCronJob
        cron = MemoryDecayCronJob()
        result = await cron.execute_cron_job_real(db)
        return CronJobResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行记忆衰减任务失败: {str(e)}")


@router.get("/cron/memory-decay/next-execution")
async def api_get_next_cron_execution():
    """
    获取下次Cron执行时间（需求29）
    """
    try:
        from algorithms.memory_decay_cron import get_memory_decay_cron
        cron = get_memory_decay_cron()
        
        next_time = cron.get_next_execution_time()
        
        return {
            "next_execution": next_time.isoformat(),
            "hour": cron.EXECUTION_HOUR,
            "minute": cron.EXECUTION_MINUTE
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取下次执行时间失败: {str(e)}")
