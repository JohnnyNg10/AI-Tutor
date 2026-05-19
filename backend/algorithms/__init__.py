"""
AI Tutor V3 认知诊断算法模块
包含：BKT、IRT、K-IRT、自适应K因子、记忆衰减、Actual Score、连击处理等算法

严格遵循PRD文档参数：
- BKT: P(T)=0.3, P(G)=0.2, P(S)=0.1, P(L0)=0.5
- IRT: theta范围[-3, +3], 题目难度b范围[-3, +3], 区分度a默认1.0
- K-IRT: n>10时α=0.8, n<=10时α=0.3
- 自适应K因子: β=0.1, γ=0.5, K_initial=0.3
- 记忆衰减: 半衰期7天, λ=ln(2)/7
- Actual Score: L0-L4权重 1.0/0.8/0.6/0.4/0.1
- 需求1-连击处理: 连对3次+0.3难度, 连错2次-0.3难度
"""

from .bkt import BKTModel, BKTParams, batch_update_bkt
from .irt_simple import IRTModel, IRTParams, QuestionParams, KIRTModel
from .adaptive_k import AdaptiveKFactor, AdaptiveKParams
from .memory_decay import MemoryDecay, MemoryDecayParams
from .actual_score import (
    ActualScoreCalculator, 
    ActualScoreParams, 
    AnswerRecord, 
    HintLevel
)
from .streak_handler import (
    StreakHandler,
    StreakState,
    StreakType,
    StreakEffect,
    DifficultyAdjustment,
    UIEffect,
    get_streak_handler
)
from .skill_tree import (
    SkillTreeBuilder,
    SkillTree,
    KnowledgeNode,
    TopicProgress,
    NodeStatus,
    get_skill_tree_builder
)
from .hint_button_state_machine import (
    HintButtonStateMachine,
    HintButtonState,
    ButtonConfig,
    get_hint_button_sm
)
from .daily_training_pack import (
    DailyTrainingPackGenerator,
    DailyTrainingPack,
    DailyQuestion,
    QuestionType,
    get_daily_pack_generator
)
from .memory_decay_cron import (
    MemoryDecayCronJob,
    DecayResult,
    get_memory_decay_cron
)

__all__ = [
    # BKT
    'BKTModel',
    'BKTParams',
    'batch_update_bkt',
    
    # IRT
    'IRTModel',
    'IRTParams',
    'QuestionParams',
    'KIRTModel',
    
    # 自适应K因子
    'AdaptiveKFactor',
    'AdaptiveKParams',
    
    # 记忆衰减
    'MemoryDecay',
    'MemoryDecayParams',
    
    # Actual Score
    'ActualScoreCalculator',
    'ActualScoreParams',
    'AnswerRecord',
    'HintLevel',
    
    # 需求1：连击处理
    'StreakHandler',
    'StreakState',
    'StreakType',
    'StreakEffect',
    'DifficultyAdjustment',
    'UIEffect',
    'get_streak_handler',
    
    # 需求10：技能树
    'SkillTreeBuilder',
    'SkillTree',
    'KnowledgeNode',
    'TopicProgress',
    'NodeStatus',
    'get_skill_tree_builder',
    
    # 需求16：渐进式提示按钮
    'HintButtonStateMachine',
    'HintButtonState',
    'ButtonConfig',
    'get_hint_button_sm',
    
    # 需求20：每日5题特训包
    'DailyTrainingPackGenerator',
    'DailyTrainingPack',
    'DailyQuestion',
    'QuestionType',
    'get_daily_pack_generator',
    
    # 需求29：记忆衰减Cron任务
    'MemoryDecayCronJob',
    'DecayResult',
    'get_memory_decay_cron',
]

# 尝试导入Redis服务（如果已安装）
try:
    from services.redis_service import (
        RedisService,
        ReviewItem,
        get_redis_service,
        init_redis_service
    )
    __all__.extend([
        'RedisService',
        'ReviewItem',
        'get_redis_service',
        'init_redis_service'
    ])
except ImportError:
    pass  # Redis可选依赖

# Agent 模块已迁移至 agent/ 目录
try:
    from agent.advisor import get_advisor_recommendations
    __all__.extend(['get_advisor_recommendations'])
except ImportError:
    pass  # Advisor可选依赖

__version__ = '3.0.0'
