"""
认知诊断服务 - 集成BKT、IRT、K-IRT等算法
基于 backend/algorithms/ 模块
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

# 导入算法模块
import sys
sys.path.append('..')
from algorithms.bkt import BKTModel, BKTParams
from algorithms import IRTModel, KIRTModel, QuestionParams
from algorithms.adaptive_k import AdaptiveKFactor, AdaptiveKParams
from algorithms.memory_decay import MemoryDecay, MemoryDecayParams
from algorithms.actual_score import ActualScoreCalculator, AnswerRecord, HintLevel
from algorithms.streak_handler import StreakHandler, StreakEffect

from models.chat import UserKnowledgeMastery, KnowledgePoint
from models.learning_analytics import UserAbilityHistory
from models.profile import UserProfile
from models.record import LearningRecord


class CognitiveDiagnosisService:
    """
    认知诊断服务
    
    集成所有算法：
    - BKT: 知识点掌握度追踪
    - IRT: 能力值估计
    - K-IRT: 联合估算
    - 自适应K因子: 动态调整学习步长
    - 记忆衰减: 遗忘曲线计算
    - Actual Score: 实际得分计算
    """
    
    def __init__(self):
        # 初始化算法模型
        self.bkt = BKTModel(BKTParams())
        self.irt = IRTModel()
        self.kirt = KIRTModel()
        self.adaptive_k = AdaptiveKFactor(AdaptiveKParams())
        self.memory_decay = MemoryDecay(MemoryDecayParams())
        self.actual_score_calc = ActualScoreCalculator()
        self.streak_handler = StreakHandler()  # 需求1：连击处理器
    
    async def update_knowledge_mastery(
        self,
        db: AsyncSession,
        user_id: int,
        knowledge_point_id: int,
        is_correct: bool
    ) -> Dict:
        """
        更新知识点掌握度（使用BKT算法）
        
        需求1：同时处理连对/连错状态，触发难度自适应调整
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            knowledge_point_id: 知识点ID
            is_correct: 是否答对
            
        Returns:
            包含掌握度、连击状态、UI效果的完整结果
        """
        # 查询当前的掌握度记录
        stmt = select(UserKnowledgeMastery).where(
            and_(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.knowledge_point_id == knowledge_point_id
            )
        )
        result = await db.execute(stmt)
        ukm = result.scalar_one_or_none()
        
        if ukm is None:
            # 创建新记录
            ukm = UserKnowledgeMastery(
                user_id=user_id,
                knowledge_point_id=knowledge_point_id,
                p_known=self.bkt.params.p_known_initial,
                p_guess=self.bkt.params.p_guess,
                p_slip=self.bkt.params.p_slip,
                consecutive_correct=0,
                consecutive_wrong=0
            )
            db.add(ukm)
        
        # 使用BKT算法更新掌握度
        p_known_old = ukm.p_known or self.bkt.params.p_known_initial
        p_known_new = self.bkt.update(p_known_old, is_correct)
        
        # 更新连续正确/错误次数
        if is_correct:
            ukm.consecutive_correct = (ukm.consecutive_correct or 0) + 1
            ukm.consecutive_wrong = 0
        else:
            ukm.consecutive_wrong = (ukm.consecutive_wrong or 0) + 1
            ukm.consecutive_correct = 0
        
        # 更新掌握度
        ukm.p_known = p_known_new
        ukm.mastery_level = int(p_known_new * 100)  # 转换为0-100
        ukm.last_practiced_at = datetime.now()
        
        # 需求1：获取当前能力值用于难度调整计算
        theta_info = await self.estimate_theta(db, user_id)
        theta = theta_info['theta']
        
        # 需求1：处理连击状态并获取UI效果
        streak_result = self.streak_handler.process_answer(user_id, is_correct, theta)
        
        # 记录能力历史快照
        await self._record_ability_snapshot(db, user_id, theta_info)

        await db.commit()

        return {
            'p_known': p_known_new,
            'p_known_change': p_known_new - p_known_old,
            'consecutive_correct': ukm.consecutive_correct,
            'consecutive_wrong': ukm.consecutive_wrong,
            'streak_state': streak_result['streak_state'],
            'difficulty_adjustment': streak_result['difficulty_adjustment'],
            'ui_effect': streak_result['ui_effect'],
            'should_trigger_effect': streak_result['should_trigger_effect']
        }
    
    async def _record_ability_snapshot(
        self,
        db: AsyncSession,
        user_id: int,
        theta_info: Dict[str, float]
    ) -> None:
        """记录能力历史快照，为前端能力曲线图提供真实数据"""
        stmt = select(UserKnowledgeMastery).where(
            UserKnowledgeMastery.user_id == user_id
        )
        result = await db.execute(stmt)
        mastery_list = result.scalars().all()

        avg_mastery = (sum(m.p_known or 0 for m in mastery_list) / len(mastery_list)
                       if mastery_list else 0.0)
        weak_kp_count = sum(1 for m in mastery_list if (m.p_known or 0) < 0.4)

        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = profile_result.scalar_one_or_none()

        snapshot = UserAbilityHistory(
            user_id=user_id,
            theta=theta_info['theta'],
            theta_se=theta_info.get('theta_se'),
            theta_ci_lower=theta_info.get('ci_lower'),
            theta_ci_upper=theta_info.get('ci_upper'),
            avg_mastery=round(avg_mastery, 4),
            weak_kp_count=weak_kp_count,
            total_questions=profile.total_questions if profile else 0,
            correct_count=profile.correct_count if profile else 0,
        )
        db.add(snapshot)

    async def estimate_theta(
        self,
        db: AsyncSession,
        user_id: int
    ) -> Dict[str, float]:
        """
        估计学生能力值（使用K-IRT联合估算）
        
        Returns:
            {
                'theta': 最终能力值,
                'theta_irt': IRT估计值,
                'theta_bkt': BKT映射值,
                'alpha': K-IRT权重,
                'theta_se': 标准误,
                'ci_lower': 置信区间下限,
                'ci_upper': 置信区间上限
            }
        """
        # 查询用户画像
        from services.profile_service import get_user_profile
        profile = await get_user_profile(db, user_id)
        
        if not profile:
            # 默认返回值
            return {
                'theta': 0.0,
                'theta_irt': 0.0,
                'theta_bkt': 0.0,
                'alpha': 0.3,
                'theta_se': 1.0,
                'ci_lower': -1.96,
                'ci_upper': 1.96
            }
        
        # IRT估计（基于正确率）
        total = profile.total_questions or 0
        correct = profile.correct_count or 0
        theta_irt = self.irt.estimate_theta_simple(correct, total)
        
        # BKT映射（基于平均掌握度）
        avg_mastery = profile.avg_mastery or 0.5
        theta_bkt = self.kirt.bkt_mastery_to_theta(avg_mastery)
        
        # K-IRT联合估算
        alpha = self.kirt.compute_alpha(total)
        theta_final = self.kirt.estimate_theta_final(theta_irt, theta_bkt, total)
        
        # 计算标准误和置信区间
        theta_se = max(0.05, 1.0 / ((total + 1) ** 0.5))
        ci_margin = 1.96 * theta_se
        
        return {
            'theta': round(theta_final, 4),
            'theta_irt': round(theta_irt, 4),
            'theta_bkt': round(theta_bkt, 4),
            'alpha': alpha,
            'theta_se': round(theta_se, 4),
            'ci_lower': round(theta_final - ci_margin, 4),
            'ci_upper': round(theta_final + ci_margin, 4)
        }
    
    async def calculate_actual_score(
        self,
        is_correct: bool,
        hint_level: int,
        time_spent: float,
        expected_time: float,
        skip_reason: Optional[str] = None
    ) -> float:
        """
        计算Actual Score
        
        Args:
            is_correct: 是否正确
            hint_level: 提示等级 0-4
            time_spent: 实际耗时（秒）
            expected_time: 期望耗时（秒）
            skip_reason: 跳过原因
            
        Returns:
            Actual Score (0-1)
        """
        record = AnswerRecord(
            is_correct=is_correct,
            hint_level=HintLevel(hint_level),
            time_spent=time_spent,
            expected_time=expected_time,
            skip_reason=skip_reason
        )
        return self.actual_score_calc.calculate(record)
    
    async def apply_memory_decay(
        self,
        db: AsyncSession,
        user_id: int
    ) -> List[Dict]:
        """
        应用记忆衰减到所有知识点
        
        Returns:
            衰减后的掌握度列表
        """
        now = datetime.now()
        
        # 查询所有知识点掌握度
        stmt = select(UserKnowledgeMastery).where(
            UserKnowledgeMastery.user_id == user_id
        )
        result = await db.execute(stmt)
        mastery_list = result.scalars().all()
        
        updates = []
        for ukm in mastery_list:
            if ukm.last_practiced_at:
                # 计算衰减
                p_decayed = self.memory_decay.compute_decay_with_timestamp(
                    ukm.p_known or 0.5,
                    ukm.last_practiced_at,
                    now
                )
                
                # 更新掌握度
                ukm.p_known = p_decayed
                ukm.mastery_level = int(p_decayed * 100)
                
                updates.append({
                    'knowledge_point_id': ukm.knowledge_point_id,
                    'p_known_original': ukm.p_known,
                    'p_known_decayed': p_decayed,
                    'days_passed': (now - ukm.last_practiced_at).days
                })
        
        await db.commit()
        return updates
    
    def get_recommended_difficulty_range(
        self,
        theta: float,
        delta: float = 0.5
    ) -> Tuple[float, float]:
        """
        获取推荐题目难度范围
        
        PRD标准：[theta - 0.5, theta + 0.5]
        """
        return self.irt.get_recommended_difficulty_range(theta, delta)
    
    def get_mastery_level(self, p_known: float) -> str:
        """
        获取四级掌握度等级
        - mastered:   P(L) >= 0.85
        - proficient: 0.65 <= P(L) < 0.85
        - qualified:  0.4 <= P(L) < 0.65
        - weak:       P(L) < 0.4
        """
        return self.bkt.get_mastery_level(p_known)
    
    async def get_comprehensive_report(
        self,
        db: AsyncSession,
        user_id: int
    ) -> Dict:
        """
        获取综合诊断报告
        """
        # 能力值估计
        theta_info = await self.estimate_theta(db, user_id)
        
        # 查询掌握度分布
        stmt = select(UserKnowledgeMastery).where(
            UserKnowledgeMastery.user_id == user_id
        )
        result = await db.execute(stmt)
        mastery_list = result.scalars().all()
        
        # 统计四级掌握度
        mastered_count = sum(1 for m in mastery_list if (m.p_known or 0) >= 0.85)
        proficient_count = sum(1 for m in mastery_list if 0.65 <= (m.p_known or 0) < 0.85)
        qualified_count = sum(1 for m in mastery_list if 0.4 <= (m.p_known or 0) < 0.65)
        weak_count = sum(1 for m in mastery_list if (m.p_known or 0) < 0.4)

        # 推荐难度范围
        diff_min, diff_max = self.get_recommended_difficulty_range(theta_info['theta'])

        return {
            'user_id': user_id,
            'ability': theta_info,
            'mastery_distribution': {
                'mastered': mastered_count,
                'proficient': proficient_count,
                'qualified': qualified_count,
                'weak': weak_count,
                'total': len(mastery_list)
            },
            'recommended_difficulty': {
                'min': diff_min,
                'max': diff_max
            },
            'generated_at': datetime.now().isoformat()
        }


# 全局服务实例
cognitive_service = CognitiveDiagnosisService()


# 便捷函数
async def update_mastery_after_answer(
    db: AsyncSession,
    user_id: int,
    knowledge_point_id: int,
    is_correct: bool
) -> float:
    """答题后更新掌握度"""
    return await cognitive_service.update_knowledge_mastery(
        db, user_id, knowledge_point_id, is_correct
    )

async def get_user_theta(
    db: AsyncSession,
    user_id: int
) -> Dict[str, float]:
    """获取用户能力值"""
    return await cognitive_service.estimate_theta(db, user_id)

async def compute_actual_score(
    is_correct: bool,
    hint_level: int,
    time_spent: float,
    expected_time: float,
    skip_reason: Optional[str] = None
) -> float:
    """计算Actual Score"""
    return await cognitive_service.calculate_actual_score(
        is_correct, hint_level, time_spent, expected_time, skip_reason
    )


async def get_user_mastery_dict(
    db: AsyncSession,
    user_id: int
) -> Dict[str, float]:
    """
    获取用户所有知识点的掌握度，返回 {kp_name: p_known}

    用于技能树、掌握度可视化等需要批量查询的场景
    """
    from sqlalchemy.orm import joinedload

    stmt = (
        select(UserKnowledgeMastery)
        .where(UserKnowledgeMastery.user_id == user_id)
        .options(joinedload(UserKnowledgeMastery.knowledge_point))
    )
    result = await db.execute(stmt)
    mastery_list = result.unique().scalars().all()

    mastery_dict = {}
    for m in mastery_list:
        if m.knowledge_point:
            name = m.knowledge_point.name
            mastery_dict[name] = m.p_known or 0.5

    return mastery_dict
