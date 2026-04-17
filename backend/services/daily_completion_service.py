"""
每日完课结算服务
实现V3.1激励机制体验雏形

对应行号23: 以极低的开发成本，实现V3.1规划中的"激励机制"体验雏形

功能：
1. 每日5题完成进度追踪
2. 完课结算数据生成
3. Actual Score到θ经验值转换
4. 掌握度提升可视化

实现文件: backend/services/daily_completion_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import math

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.redis_service import RedisService
from services.redis_cache_service import RedisCacheService
from utils.logger import logger


@dataclass
class DailyProgress:
    """每日进度"""
    user_id: int
    date: str
    total_questions: int = 5  # 固定5题
    completed_questions: int = 0
    correct_count: int = 0
    total_actual_score: float = 0.0
    current_theta: float = 0.0
    theta_before: float = 0.0
    theta_gain: float = 0.0
    is_completed: bool = False
    completed_at: Optional[str] = None
    questions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CompletionSummary:
    """完课结算数据"""
    user_id: int
    date: str
    is_completed: bool
    
    # 答题统计
    total_questions: int
    completed_questions: int
    correct_count: int
    accuracy_rate: float
    
    # Actual Score统计
    total_actual_score: float
    avg_actual_score: float
    max_actual_score: float
    
    # θ经验值提升
    theta_before: float
    theta_after: float
    theta_gain: float
    theta_gain_percentage: float
    
    # 掌握度提升
    mastery_improvements: List[Dict[str, Any]]
    total_mastery_gain: float
    
    # 结算文案
    celebration_title: str
    celebration_message: str
    
    # 微动效数据
    animation_data: Dict[str, Any]


@dataclass
class MasteryImprovement:
    """掌握度提升"""
    knowledge_point: str
    kp_name: str
    before: float
    after: float
    gain: float


class DailyCompletionService:
    """
    每日完课结算服务
    
    功能：
    1. 追踪每日5题完成进度
    2. 生成完课结算数据
    3. Actual Score到θ经验值转换
    4. 掌握度提升可视化
    """
    
    # Redis Key前缀
    DAILY_PROGRESS_KEY = "ai:tutor:daily-progress:{user_id}:{date}"
    COMPLETION_STATUS_KEY = "ai:tutor:completion:{user_id}:{date}"
    
    # 硬指标
    DAILY_QUESTION_COUNT = 5  # 每日5题
    THETA_GAIN_FACTOR = 0.1   # θ提升系数
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        self.cache_service = RedisCacheService()
        logger.info("每日完课结算服务初始化完成")
    
    # ==================== 进度追踪 ====================
    
    def get_daily_progress(self, user_id: int, date: Optional[str] = None) -> DailyProgress:
        """
        获取每日进度
        
        Args:
            user_id: 用户ID
            date: 日期（默认今天）
            
        Returns:
            每日进度
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            key = self.DAILY_PROGRESS_KEY.format(user_id=user_id, date=date)
            data = self.redis_service.redis_client.hgetall(key)
            
            if not data:
                # 初始化新的进度
                return DailyProgress(
                    user_id=user_id,
                    date=date,
                    total_questions=self.DAILY_QUESTION_COUNT,
                    completed_questions=0,
                    questions=[]
                )
            
            # 解析Redis数据
            return DailyProgress(
                user_id=user_id,
                date=date,
                total_questions=int(data.get(b'total_questions', self.DAILY_QUESTION_COUNT)),
                completed_questions=int(data.get(b'completed_questions', 0)),
                correct_count=int(data.get(b'correct_count', 0)),
                total_actual_score=float(data.get(b'total_actual_score', 0)),
                current_theta=float(data.get(b'current_theta', 0)),
                theta_before=float(data.get(b'theta_before', 0)),
                theta_gain=float(data.get(b'theta_gain', 0)),
                is_completed=data.get(b'is_completed', b'false') == b'true',
                completed_at=data.get(b'completed_at', b'').decode('utf-8') if data.get(b'completed_at') else None,
                questions=json.loads(data.get(b'questions', b'[]'))
            )
            
        except Exception as e:
            logger.error(f"获取每日进度失败: {e}")
            return DailyProgress(user_id=user_id, date=date, total_questions=self.DAILY_QUESTION_COUNT)
    
    def record_question_answer(
        self,
        user_id: int,
        question_id: str,
        is_correct: bool,
        actual_score: float,
        knowledge_point: str,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        记录答题结果
        
        Args:
            user_id: 用户ID
            question_id: 题目ID
            is_correct: 是否答对
            actual_score: Actual Score
            knowledge_point: 知识点
            date: 日期
            
        Returns:
            更新后的进度
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            # 获取当前进度
            progress = self.get_daily_progress(user_id, date)
            
            # 记录题目
            question_record = {
                'question_id': question_id,
                'is_correct': is_correct,
                'actual_score': actual_score,
                'knowledge_point': knowledge_point,
                'answered_at': datetime.now().isoformat()
            }
            progress.questions.append(question_record)
            
            # 更新统计
            progress.completed_questions += 1
            if is_correct:
                progress.correct_count += 1
            progress.total_actual_score += actual_score
            
            # 保存到Redis
            self._save_progress(progress)
            
            # 检查是否完成
            is_just_completed = False
            if progress.completed_questions >= self.DAILY_QUESTION_COUNT and not progress.is_completed:
                progress.is_completed = True
                progress.completed_at = datetime.now().isoformat()
                self._save_progress(progress)
                self._mark_completion(user_id, date)
                is_just_completed = True
            
            return {
                'success': True,
                'progress': {
                    'completed_questions': progress.completed_questions,
                    'total_questions': progress.total_questions,
                    'correct_count': progress.correct_count,
                    'accuracy_rate': round(progress.correct_count / progress.completed_questions * 100, 1) if progress.completed_questions > 0 else 0,
                    'total_actual_score': round(progress.total_actual_score, 2),
                    'is_completed': progress.is_completed,
                    'remaining': max(0, self.DAILY_QUESTION_COUNT - progress.completed_questions)
                },
                'is_just_completed': is_just_completed
            }
            
        except Exception as e:
            logger.error(f"记录答题结果失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _save_progress(self, progress: DailyProgress) -> None:
        """保存进度到Redis"""
        try:
            key = self.DAILY_PROGRESS_KEY.format(user_id=progress.user_id, date=progress.date)
            self.redis_service.redis_client.hset(key, mapping={
                'user_id': progress.user_id,
                'date': progress.date,
                'total_questions': progress.total_questions,
                'completed_questions': progress.completed_questions,
                'correct_count': progress.correct_count,
                'total_actual_score': progress.total_actual_score,
                'current_theta': progress.current_theta,
                'theta_before': progress.theta_before,
                'theta_gain': progress.theta_gain,
                'is_completed': 'true' if progress.is_completed else 'false',
                'completed_at': progress.completed_at or '',
                'questions': json.dumps(progress.questions)
            })
            # 设置过期时间（7天）
            self.redis_service.redis_client.expire(key, 7 * 24 * 3600)
        except Exception as e:
            logger.error(f"保存进度失败: {e}")
    
    def _mark_completion(self, user_id: int, date: str) -> None:
        """标记完成状态"""
        try:
            key = self.COMPLETION_STATUS_KEY.format(user_id=user_id, date=date)
            self.redis_service.redis_client.set(key, 'completed')
            self.redis_service.redis_client.expire(key, 7 * 24 * 3600)
        except Exception as e:
            logger.error(f"标记完成状态失败: {e}")
    
    # ==================== 完课结算 ====================
    
    def generate_completion_summary(
        self,
        user_id: int,
        date: Optional[str] = None
    ) -> Optional[CompletionSummary]:
        """
        生成完课结算数据
        
        Args:
            user_id: 用户ID
            date: 日期
            
        Returns:
            结算数据
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            # 获取进度
            progress = self.get_daily_progress(user_id, date)
            
            if not progress.is_completed:
                return None
            
            # 计算统计数据
            accuracy_rate = progress.correct_count / progress.completed_questions * 100 if progress.completed_questions > 0 else 0
            avg_actual_score = progress.total_actual_score / progress.completed_questions if progress.completed_questions > 0 else 0
            max_actual_score = max([q.get('actual_score', 0) for q in progress.questions]) if progress.questions else 0
            
            # 计算θ提升
            theta_before = progress.theta_before if progress.theta_before > 0 else self._get_user_theta(user_id, date)
            theta_gain = self._calculate_theta_gain(progress)
            theta_after = theta_before + theta_gain
            theta_gain_percentage = (theta_gain / theta_before * 100) if theta_before > 0 else 0
            
            # 计算掌握度提升
            mastery_improvements = self._calculate_mastery_improvements(progress)
            total_mastery_gain = sum([m['gain'] for m in mastery_improvements])
            
            # 生成结算文案
            celebration_title, celebration_message = self._generate_celebration_text(
                progress, accuracy_rate, theta_gain
            )
            
            # 生成微动效数据
            animation_data = self._generate_animation_data(
                progress, theta_gain, mastery_improvements
            )
            
            return CompletionSummary(
                user_id=user_id,
                date=date,
                is_completed=True,
                total_questions=progress.total_questions,
                completed_questions=progress.completed_questions,
                correct_count=progress.correct_count,
                accuracy_rate=round(accuracy_rate, 1),
                total_actual_score=round(progress.total_actual_score, 2),
                avg_actual_score=round(avg_actual_score, 2),
                max_actual_score=round(max_actual_score, 2),
                theta_before=round(theta_before, 2),
                theta_after=round(theta_after, 2),
                theta_gain=round(theta_gain, 2),
                theta_gain_percentage=round(theta_gain_percentage, 1),
                mastery_improvements=mastery_improvements,
                total_mastery_gain=round(total_mastery_gain, 2),
                celebration_title=celebration_title,
                celebration_message=celebration_message,
                animation_data=animation_data
            )
            
        except Exception as e:
            logger.error(f"生成完课结算数据失败: {e}")
            return None
    
    def _get_user_theta(self, user_id: int, date: str) -> float:
        """获取用户theta值"""
        try:
            # 从缓存或数据库获取
            theta = self.cache_service.get_user_theta(user_id)
            return theta if theta else 0.0
        except:
            return 0.0
    
    def _calculate_theta_gain(self, progress: DailyProgress) -> float:
        """
        计算θ经验值提升
        
        公式：θ_gain = total_actual_score * THETA_GAIN_FACTOR
        """
        return progress.total_actual_score * self.THETA_GAIN_FACTOR
    
    def _calculate_mastery_improvements(self, progress: DailyProgress) -> List[Dict[str, Any]]:
        """计算掌握度提升"""
        improvements = []
        
        # 按知识点分组统计
        kp_stats = {}
        for q in progress.questions:
            kp = q.get('knowledge_point', 'unknown')
            if kp not in kp_stats:
                kp_stats[kp] = {'correct': 0, 'total': 0, 'actual_score': 0}
            kp_stats[kp]['total'] += 1
            if q.get('is_correct'):
                kp_stats[kp]['correct'] += 1
            kp_stats[kp]['actual_score'] += q.get('actual_score', 0)
        
        # 计算每个知识点的提升
        for kp, stats in kp_stats.items():
            if stats['total'] > 0:
                # 模拟掌握度提升（实际应从数据库获取前后值）
                gain = stats['actual_score'] / stats['total'] * 0.1  # 简化计算
                improvements.append({
                    'knowledge_point': kp,
                    'kp_name': self._get_kp_name(kp),
                    'before': round(max(0, 0.5 - gain), 2),  # 模拟之前值
                    'after': round(0.5, 2),
                    'gain': round(gain, 2)
                })
        
        # 按提升幅度排序
        improvements.sort(key=lambda x: x['gain'], reverse=True)
        return improvements[:3]  # 只返回前3个
    
    def _get_kp_name(self, kp_id: str) -> str:
        """获取知识点名称"""
        # 简化实现，实际应从数据库查询
        kp_names = {
            'arith_seq': '等差数列',
            'geo_seq': '等比数列',
            'recurrence': '递推数列',
            'series_sum': '数列求和',
            'math_induction': '数学归纳法'
        }
        return kp_names.get(kp_id, kp_id)
    
    def _generate_celebration_text(
        self,
        progress: DailyProgress,
        accuracy_rate: float,
        theta_gain: float
    ) -> Tuple[str, str]:
        """生成结算文案"""
        # 根据表现选择文案
        if accuracy_rate >= 80:
            title = "太棒了！今日特训完美达成！"
            message = f"正确率{accuracy_rate:.0f}%，θ经验值+{theta_gain:.2f}，继续保持这个势头！"
        elif accuracy_rate >= 60:
            title = "不错的表现！今日特训已完成！"
            message = f"正确率{accuracy_rate:.0f}%，θ经验值+{theta_gain:.2f}，明天继续加油！"
        else:
            title = "坚持就是胜利！今日特训已完成！"
            message = f"完成比完美更重要，θ经验值+{theta_gain:.2f}，明天会更好的！"
        
        return title, message
    
    def _generate_animation_data(
        self,
        progress: DailyProgress,
        theta_gain: float,
        mastery_improvements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成微动效数据"""
        return {
            'type': 'completion_celebration',
            'duration_ms': 3000,
            'stages': [
                {
                    'stage': 1,
                    'name': '完成庆祝',
                    'effect': 'confetti',
                    'duration_ms': 1000,
                    'text': '今日5题已完成！'
                },
                {
                    'stage': 2,
                    'name': '经验值提升',
                    'effect': 'number_count_up',
                    'duration_ms': 1000,
                    'start_value': 0,
                    'end_value': theta_gain,
                    'text': f'θ经验值 +{theta_gain:.2f}'
                },
                {
                    'stage': 3,
                    'name': '掌握度展示',
                    'effect': 'progress_fill',
                    'duration_ms': 1000,
                    'improvements': mastery_improvements
                }
            ]
        }
    
    # ==================== 便捷函数 ====================
    
    def check_completion_status(self, user_id: int, date: Optional[str] = None) -> Dict[str, Any]:
        """检查完成状态"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        progress = self.get_daily_progress(user_id, date)
        
        return {
            'is_completed': progress.is_completed,
            'completed_questions': progress.completed_questions,
            'total_questions': progress.total_questions,
            'remaining': max(0, self.DAILY_QUESTION_COUNT - progress.completed_questions),
            'progress_percentage': round(progress.completed_questions / self.DAILY_QUESTION_COUNT * 100, 1)
        }


# ==================== 便捷函数 ====================

def get_daily_progress(user_id: int, date: Optional[str] = None) -> DailyProgress:
    """便捷函数：获取每日进度"""
    service = DailyCompletionService()
    return service.get_daily_progress(user_id, date)


def record_answer(
    user_id: int,
    question_id: str,
    is_correct: bool,
    actual_score: float,
    knowledge_point: str,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """便捷函数：记录答题"""
    service = DailyCompletionService()
    return service.record_question_answer(user_id, question_id, is_correct, actual_score, knowledge_point, date)


def get_completion_summary(user_id: int, date: Optional[str] = None) -> Optional[CompletionSummary]:
    """便捷函数：获取结算数据"""
    service = DailyCompletionService()
    return service.generate_completion_summary(user_id, date)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("每日完课结算服务测试")
    print("=" * 60)
    
    service = DailyCompletionService()
    user_id = 1
    date = datetime.now().strftime('%Y-%m-%d')
    
    # 测试记录答题
    print("\n记录答题测试：")
    for i in range(5):
        result = service.record_question_answer(
            user_id=user_id,
            question_id=f"q{i+1}",
            is_correct=i < 4,  # 4对1错
            actual_score=0.8 if i < 4 else 0.2,
            knowledge_point='arith_seq' if i < 3 else 'geo_seq',
            date=date
        )
        print(f"  第{i+1}题: {'完成' if result['success'] else '失败'}")
        if result.get('is_just_completed'):
            print(f"  >>> 今日5题已完成！")
    
    # 测试获取结算数据
    print("\n完课结算数据：")
    summary = service.generate_completion_summary(user_id, date)
    if summary:
        print(f"  正确率: {summary.accuracy_rate}%")
        print(f"  Total Actual Score: {summary.total_actual_score}")
        print(f"  θ提升: {summary.theta_before} -> {summary.theta_after} (+{summary.theta_gain})")
        print(f"  结算文案: {summary.celebration_title}")
        print(f"  消息: {summary.celebration_message}")
    
    print("\n测试完成")
