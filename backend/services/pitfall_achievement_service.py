"""
雷区与成就双列卡片服务
摒弃传统占比饼图，以双列卡片展示易错陷阱和已攻克的难关

对应行号14: 摒弃传统占比饼图，以"雷区"与"成就"双列卡片展示易错陷阱

模块A（高频雷区）：结合系统提取的易错点标签，列出学生最常踩坑的具体行为
模块B（已攻克的难关）：展示曾经在复习队列中频繁做错，但近期掌握度已跨越0.8的题目或知识点

实现文件: backend/services/pitfall_achievement_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy.ext.asyncio import AsyncSession

from services.redis_service import RedisService
from services.redis_cache_service import RedisCacheService
from utils.logger import logger


@dataclass
class PitfallCard:
    """雷区卡片"""
    id: str
    title: str
    description: str
    error_type: str
    frequency: int  # 犯错次数
    last_occurred: str
    related_questions: List[str]
    suggestion: str
    icon: str = "⚠️"
    color: str = "#FF4D4F"


@dataclass
class AchievementCard:
    """成就卡片"""
    id: str
    title: str
    description: str
    achievement_type: str
    conquered_at: str
    previous_errors: int  # 之前错误次数
    current_mastery: float  # 当前掌握度
    related_questions: List[str]
    icon: str = "🏆"
    color: str = "#52C41A"


@dataclass
class DualColumnData:
    """双列卡片数据"""
    user_id: int
    pitfalls: List[PitfallCard]
    achievements: List[AchievementCard]
    pitfall_count: int
    achievement_count: int
    updated_at: str


class PitfallAchievementService:
    """
    雷区与成就双列卡片服务
    
    功能：
    1. 高频雷区识别（基于错误类型聚类）
    2. 已攻克难关识别（复习队列完成+掌握度提升）
    3. 双列卡片数据生成
    4. 动态更新
    """
    
    # Redis Key前缀
    DUAL_COLUMN_KEY = "ai:tutor:dual-column:{user_id}"
    PITFALL_KEY = "ai:tutor:pitfall:{user_id}"
    ACHIEVEMENT_KEY = "ai:tutor:achievement:{user_id}"
    
    # 易错点标签
    ERROR_TYPE_LABELS = {
        'calculation': {'name': '计算失误', 'icon': '🔢', 'color': '#FF6B6B'},
        'formula': {'name': '公式混淆', 'icon': '📐', 'color': '#FAAD14'},
        'concept': {'name': '概念不清', 'icon': '❓', 'color': '#FF4D4F'},
        'logic': {'name': '逻辑错误', 'icon': '🧩', 'color': '#EB2F96'},
        'careless': {'name': '粗心大意', 'icon': '👀', 'color': '#FA8C16'},
        'boundary': {'name': '边界条件', 'icon': '📏', 'color': '#F5222D'},
        'transformation': {'name': '变形困难', 'icon': '🔄', 'color': '#722ED1'}
    }
    
    # 成就类型
    ACHIEVEMENT_TYPES = {
        'mastered': {'name': '已攻克', 'icon': '🏆', 'color': '#52C41A'},
        'improved': {'name': '大进步', 'icon': '📈', 'color': '#1890FF'},
        'persistent': {'name': '坚持不懈', 'icon': '💪', 'color': '#FAAD14'},
        'breakthrough': {'name': '突破自我', 'icon': '🚀', 'color': '#722ED1'}
    }
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        self.cache_service = RedisCacheService()
        logger.info("雷区与成就双列卡片服务初始化完成")
    
    # ==================== 雷区识别（模块A） ====================
    
    def identify_pitfalls(self, user_id: int) -> List[PitfallCard]:
        """
        识别高频雷区
        
        基于错误类型聚类，找出学生最常踩坑的具体行为
        """
        try:
            # 获取用户的错误记录
            error_records = self._get_user_error_records(user_id)
            
            if not error_records:
                return []
            
            # 按错误类型聚类
            error_clusters = {}
            for record in error_records:
                error_type = record.get('error_type', 'unknown')
                if error_type not in error_clusters:
                    error_clusters[error_type] = []
                error_clusters[error_type].append(record)
            
            # 生成雷区卡片
            pitfalls = []
            for error_type, records in error_clusters.items():
                if len(records) >= 2:  # 至少犯2次才算雷区
                    pitfall = self._create_pitfall_card(error_type, records)
                    if pitfall:
                        pitfalls.append(pitfall)
            
            # 按频率排序
            pitfalls.sort(key=lambda x: x.frequency, reverse=True)
            
            return pitfalls[:6]  # 最多6个雷区
            
        except Exception as e:
            logger.error(f"识别雷区失败: {e}")
            return []
    
    def _create_pitfall_card(
        self,
        error_type: str,
        records: List[Dict]
    ) -> Optional[PitfallCard]:
        """创建雷区卡片"""
        label = self.ERROR_TYPE_LABELS.get(error_type, {
            'name': '其他错误',
            'icon': '⚠️',
            'color': '#999999'
        })
        
        # 获取相关题目
        related_questions = list(set(r.get('question_id') for r in records if r.get('question_id')))
        
        # 生成建议
        suggestion = self._generate_pitfall_suggestion(error_type)
        
        return PitfallCard(
            id=f"pitfall_{error_type}",
            title=label['name'],
            description=f"你在{label['name']}方面犯了{len(records)}次错误",
            error_type=error_type,
            frequency=len(records),
            last_occurred=records[-1].get('timestamp', datetime.now().isoformat()),
            related_questions=related_questions[:5],
            suggestion=suggestion,
            icon=label['icon'],
            color=label['color']
        )
    
    def _generate_pitfall_suggestion(self, error_type: str) -> str:
        """生成雷区建议"""
        suggestions = {
            'calculation': '建议加强基础计算练习，养成检查习惯',
            'formula': '建议整理易混淆公式，对比记忆',
            'concept': '建议回归课本，重新理解基础概念',
            'logic': '建议多画思维导图，理清解题思路',
            'careless': '建议放慢速度，仔细审题',
            'boundary': '建议特别关注边界条件的讨论',
            'transformation': '建议多做变形题，培养灵活思维'
        }
        return suggestions.get(error_type, '建议针对性练习，避免重复犯错')
    
    # ==================== 成就识别（模块B） ====================
    
    def identify_achievements(self, user_id: int) -> List[AchievementCard]:
        """
        识别已攻克的难关
        
        展示曾经在复习队列中频繁做错，但近期掌握度已跨越0.8的题目或知识点
        """
        try:
            # 获取复习队列中已完成的题目
            completed_reviews = self._get_completed_reviews(user_id)
            
            # 获取掌握度提升的知识点
            improved_knowledge = self._get_improved_knowledge(user_id)
            
            achievements = []
            
            # 从复习队列完成生成成就
            for review in completed_reviews:
                achievement = self._create_achievement_from_review(review)
                if achievement:
                    achievements.append(achievement)
            
            # 从掌握度提升生成成就
            for knowledge in improved_knowledge:
                achievement = self._create_achievement_from_mastery(knowledge)
                if achievement:
                    achievements.append(achievement)
            
            # 按攻克时间排序
            achievements.sort(key=lambda x: x.conquered_at, reverse=True)
            
            return achievements[:6]  # 最多6个成就
            
        except Exception as e:
            logger.error(f"识别成就失败: {e}")
            return []
    
    def _create_achievement_from_review(self, review: Dict) -> Optional[AchievementCard]:
        """从复习记录创建成就"""
        question_id = review.get('question_id')
        error_count = review.get('previous_errors', 0)
        
        if error_count < 2:  # 至少之前错2次才算攻克
            return None
        
        return AchievementCard(
            id=f"achieve_review_{question_id}",
            title=f"攻克错题：{review.get('question_title', '未知题目')}",
            description=f"这道题你曾经错了{error_count}次，现在终于掌握了！",
            achievement_type='mastered',
            conquered_at=review.get('completed_at', datetime.now().isoformat()),
            previous_errors=error_count,
            current_mastery=review.get('current_mastery', 0.8),
            related_questions=[question_id],
            icon='🏆',
            color='#52C41A'
        )
    
    def _create_achievement_from_mastery(self, knowledge: Dict) -> Optional[AchievementCard]:
        """从掌握度提升创建成就"""
        kp_id = knowledge.get('knowledge_point_id')
        previous_mastery = knowledge.get('previous_mastery', 0)
        current_mastery = knowledge.get('current_mastery', 0)
        
        if previous_mastery >= 0.5 or current_mastery < 0.8:
            return None  # 之前已经不错，或现在还没掌握
        
        # 确定成就类型
        if current_mastery - previous_mastery > 0.4:
            achievement_type = 'breakthrough'
        elif previous_mastery < 0.3:
            achievement_type = 'improved'
        else:
            achievement_type = 'mastered'
        
        type_info = self.ACHIEVEMENT_TYPES.get(achievement_type, self.ACHIEVEMENT_TYPES['mastered'])
        
        return AchievementCard(
            id=f"achieve_kp_{kp_id}",
            title=f"掌握知识点：{knowledge.get('knowledge_point_name', '未知知识点')}",
            description=f"掌握度从{previous_mastery:.0%}提升到{current_mastery:.0%}！",
            achievement_type=achievement_type,
            conquered_at=knowledge.get('updated_at', datetime.now().isoformat()),
            previous_errors=knowledge.get('error_count', 0),
            current_mastery=current_mastery,
            related_questions=[],
            icon=type_info['icon'],
            color=type_info['color']
        )
    
    # ==================== 双列数据生成 ====================
    
    def generate_dual_column_data(self, user_id: int) -> DualColumnData:
        """
        生成双列卡片数据
        
        整合雷区和成就数据
        """
        try:
            # 识别雷区和成就
            pitfalls = self.identify_pitfalls(user_id)
            achievements = self.identify_achievements(user_id)
            
            data = DualColumnData(
                user_id=user_id,
                pitfalls=pitfalls,
                achievements=achievements,
                pitfall_count=len(pitfalls),
                achievement_count=len(achievements),
                updated_at=datetime.now().isoformat()
            )
            
            # 缓存数据
            self._cache_dual_column_data(user_id, data)
            
            return data
            
        except Exception as e:
            logger.error(f"生成双列数据失败: {e}")
            return DualColumnData(
                user_id=user_id,
                pitfalls=[],
                achievements=[],
                pitfall_count=0,
                achievement_count=0,
                updated_at=datetime.now().isoformat()
            )
    
    def _cache_dual_column_data(self, user_id: int, data: DualColumnData) -> None:
        """缓存双列数据"""
        try:
            key = self.DUAL_COLUMN_KEY.format(user_id=user_id)
            
            cache_data = {
                'user_id': data.user_id,
                'pitfall_count': data.pitfall_count,
                'achievement_count': data.achievement_count,
                'updated_at': data.updated_at
            }
            
            self.redis_service.redis_client.hset(key, mapping=cache_data)
            self.redis_service.redis_client.expire(key, 3600)  # 1小时TTL
            
        except Exception as e:
            logger.error(f"缓存双列数据失败: {e}")
    
    # ==================== 数据获取 ====================

    async def _get_user_error_records(self, db: AsyncSession, user_id: int) -> List[Dict]:
        """从 learning_records 查询用户最近错误记录"""
        from sqlalchemy import select, desc
        from models.record import LearningRecord
        stmt = (
            select(LearningRecord)
            .where(LearningRecord.user_id == user_id)
            .where(LearningRecord.is_correct == False)
            .order_by(desc(LearningRecord.created_at))
            .limit(50)
        )
        result = await db.execute(stmt)
        records = result.scalars().all()
        return [
            {
                'question_id': r.question_id,
                'timestamp': r.created_at.isoformat() if r.created_at else '',
                'skip_reason': r.skip_reason,
                'hint_count': r.hint_count,
            }
            for r in records
        ]

    async def _get_completed_reviews(self, db: AsyncSession, user_id: int) -> List[Dict]:
        """从 mistake_book 查询已攻克的错题"""
        from sqlalchemy import select
        from models.learning_analytics import MistakeBook
        stmt = (
            select(MistakeBook)
            .where(MistakeBook.user_id == user_id)
            .where(MistakeBook.mastered == True)
            .limit(30)
        )
        result = await db.execute(stmt)
        records = result.scalars().all()
        return [
            {
                'question_id': r.question_id,
                'error_count': r.error_count,
                'mastered_at': r.mastered_at.isoformat() if r.mastered_at else '',
            }
            for r in records
        ]

    async def _get_improved_knowledge(self, db: AsyncSession, user_id: int) -> List[Dict]:
        """从 user_knowledge_mastery 查询掌握度已达标 (>=0.8) 的知识点"""
        from sqlalchemy import select
        from models.chat import UserKnowledgeMastery
        stmt = (
            select(UserKnowledgeMastery)
            .where(UserKnowledgeMastery.user_id == user_id)
            .where(UserKnowledgeMastery.p_known >= 0.8)
        )
        result = await db.execute(stmt)
        records = result.unique().scalars().all()
        return [
            {
                'kp_id': r.knowledge_point_id,
                'kp_name': r.knowledge_point.name if r.knowledge_point else str(r.knowledge_point_id),
                'p_known': r.p_known,
            }
            for r in records
        ]

    async def get_dual_column_async(self, db: AsyncSession, user_id: int) -> Dict[str, Any]:
        """异步版双列数据获取（使用真实 DB 查询）"""
        errors = await self._get_user_error_records(db, user_id)
        improved = await self._get_improved_knowledge(db, user_id)
        reviews = await self._get_completed_reviews(db, user_id)

        # 构建雷区卡片
        pitfalls = []
        error_counts: Dict[str, int] = {}
        for e in errors:
            kind = e.get('skip_reason') or '未分类'
            error_counts[kind] = error_counts.get(kind, 0) + 1

        for kind, count in sorted(error_counts.items(), key=lambda x: -x[1]):
            pitfalls.append({
                'id': f'pitfall_{kind}',
                'title': kind,
                'frequency': count,
                'suggestion': '建议针对性练习',
            })

        # 构建成就卡片
        achievements = [
            {
                'id': f'ach_{kp["kp_id"]}',
                'title': f'已掌握: {kp["kp_name"]}',
                'p_known': kp['p_known'],
            }
            for kp in improved[:5]
        ]

        return {
            'user_id': user_id,
            'pitfalls': pitfalls,
            'achievements': achievements,
            'reviewed_count': len(reviews),
            'pitfall_count': len(pitfalls),
            'achievement_count': len(achievements),
        }
    
    # ==================== API数据格式 ====================
    
    def get_dual_column_for_display(self, user_id: int) -> Dict[str, Any]:
        """获取用于前端展示的双列数据"""
        data = self.generate_dual_column_data(user_id)
        
        return {
            'user_id': data.user_id,
            'updated_at': data.updated_at,
            'left_column': {
                'title': '⚠️ 高频雷区',
                'subtitle': f'共{data.pitfall_count}个易错点需要关注',
                'cards': [
                    {
                        'id': p.id,
                        'title': p.title,
                        'description': p.description,
                        'icon': p.icon,
                        'color': p.color,
                        'frequency': p.frequency,
                        'suggestion': p.suggestion,
                        'related_questions': p.related_questions
                    }
                    for p in data.pitfalls
                ]
            },
            'right_column': {
                'title': '🏆 已攻克的难关',
                'subtitle': f'共{data.achievement_count}个成就',
                'cards': [
                    {
                        'id': a.id,
                        'title': a.title,
                        'description': a.description,
                        'icon': a.icon,
                        'color': a.color,
                        'achievement_type': a.achievement_type,
                        'conquered_at': a.conquered_at,
                        'previous_errors': a.previous_errors,
                        'current_mastery': a.current_mastery
                    }
                    for a in data.achievements
                ]
            }
        }


# ==================== 便捷函数 ====================

def get_user_dual_column_cards(user_id: int) -> Dict[str, Any]:
    """便捷函数：获取用户双列卡片"""
    service = PitfallAchievementService()
    return service.get_dual_column_for_display(user_id)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("雷区与成就双列卡片服务测试")
    print("=" * 60)
    
    service = PitfallAchievementService()
    
    # 测试雷区识别
    print("\n雷区识别测试：")
    pitfalls = service.identify_pitfalls(1)
    for p in pitfalls[:3]:
        print(f"  {p.icon} {p.title}: {p.frequency}次")
    
    # 测试双列数据生成
    print("\n双列数据测试：")
    data = service.get_dual_column_for_display(1)
    print(f"  左列: {data['left_column']['title']} ({len(data['left_column']['cards'])}个)")
    print(f"  右列: {data['right_column']['title']} ({len(data['right_column']['cards'])}个)")
    
    print("\n测试完成")
