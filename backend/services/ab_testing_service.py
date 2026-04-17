"""
A/B测试服务
实现V3认知诊断算法相对V2传统推荐的有效性验证

对应行号3: 通过随机分队验证V3认知诊断算法相对V2传统推荐的有效性

实现文件: backend/services/ab_testing_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import random
import hashlib

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.redis_service import RedisService
from utils.logger import logger


class ExperimentGroup(str, Enum):
    """实验分组"""
    CONTROL = "A"      # 对照组：V2基础推荐
    TREATMENT = "B"    # 实验组：V3 K-IRT + Soft Labeling


@dataclass
class ABTestMetrics:
    """A/B测试指标"""
    user_id: int
    group: str
    total_questions: int = 0
    correct_count: int = 0
    accuracy_rate: float = 0.0
    accuracy_improvement: float = 0.0  # 正确率提升率
    total_session_time: int = 0  # 会话时长(秒)
    avg_time_per_question: float = 0.0
    hint_usage_rate: float = 0.0  # 提示使用率
    skip_rate: float = 0.0  # 跳过率
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ABTestConfig:
    """A/B测试配置"""
    experiment_name: str
    start_date: str
    end_date: Optional[str]
    traffic_split: float = 0.5  # 流量分配比例
    enabled: bool = True


class ABTestingService:
    """
    A/B测试服务
    
    功能:
    1. 用户分组（A/B组）
    2. 策略差异控制
    3. 数据指标跟踪
    4. 实验结果分析
    """
    
    # Redis Key前缀
    ABTEST_GROUP_KEY = "ai:tutor:abtest:group:{user_id}"
    ABTEST_METRICS_KEY = "ai:tutor:abtest:metrics:{user_id}"
    ABTEST_CONFIG_KEY = "ai:tutor:abtest:config"
    ABTEST_AGGREGATE_KEY = "ai:tutor:abtest:aggregate"
    
    # 实验配置
    EXPERIMENT_NAME = "V3_Cognitive_Diagnosis"
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        logger.info("A/B测试服务初始化完成")
    
    # ==================== 用户分组 ====================
    
    def assign_user_to_group(self, user_id: int) -> ExperimentGroup:
        """
        将用户分配到实验组
        
        使用一致性哈希确保用户始终分配到同一组
        """
        try:
            # 检查是否已分配
            existing_group = self.get_user_group(user_id)
            if existing_group:
                return existing_group
            
            # 使用用户ID哈希进行分组（确保一致性）
            hash_value = int(hashlib.md5(f"{user_id}_{self.EXPERIMENT_NAME}".encode()).hexdigest(), 16)
            
            # 50/50分配
            if hash_value % 2 == 0:
                group = ExperimentGroup.CONTROL  # A组
            else:
                group = ExperimentGroup.TREATMENT  # B组
            
            # 存储分组结果
            group_key = self.ABTEST_GROUP_KEY.format(user_id=user_id)
            self.redis_service.redis_client.setex(
                group_key,
                30 * 24 * 60 * 60,  # 30天TTL
                group.value
            )
            
            logger.info(f"用户 {user_id} 分配到 {group.value} 组")
            return group
            
        except Exception as e:
            logger.error(f"分配用户到实验组失败: {e}")
            # 默认分配到对照组
            return ExperimentGroup.CONTROL
    
    def get_user_group(self, user_id: int) -> Optional[ExperimentGroup]:
        """获取用户所属实验组"""
        try:
            group_key = self.ABTEST_GROUP_KEY.format(user_id=user_id)
            group_value = self.redis_service.redis_client.get(group_key)
            
            if group_value:
                return ExperimentGroup(group_value)
            
            return None
            
        except Exception as e:
            logger.error(f"获取用户实验组失败: {e}")
            return None
    
    def get_or_assign_group(self, user_id: int) -> ExperimentGroup:
        """获取或分配用户到实验组"""
        group = self.get_user_group(user_id)
        if group:
            return group
        return self.assign_user_to_group(user_id)
    
    # ==================== 策略差异控制 ====================
    
    def get_recommendation_strategy(self, user_id: int) -> Dict[str, Any]:
        """
        获取推荐策略
        
        A组: V2基础推荐
        B组: V3 K-IRT + Soft Labeling
        """
        group = self.get_or_assign_group(user_id)
        
        if group == ExperimentGroup.CONTROL:
            # A组: V2基础推荐
            return {
                "group": "A",
                "strategy": "V2_BASIC",
                "features": {
                    "use_k_irt": False,
                    "use_soft_labeling": False,
                    "use_adaptive_difficulty": False,
                    "use_bkt": False
                },
                "description": "V2基础推荐策略"
            }
        else:
            # B组: V3 K-IRT + Soft Labeling
            return {
                "group": "B",
                "strategy": "V3_ADVANCED",
                "features": {
                    "use_k_irt": True,
                    "use_soft_labeling": True,
                    "use_adaptive_difficulty": True,
                    "use_bkt": True
                },
                "description": "V3 K-IRT + Soft Labeling 策略"
            }
    
    def should_use_v3_features(self, user_id: int) -> bool:
        """判断是否使用V3特性"""
        group = self.get_or_assign_group(user_id)
        return group == ExperimentGroup.TREATMENT
    
    # ==================== 数据指标跟踪 ====================
    
    def record_answer_event(
        self,
        user_id: int,
        is_correct: bool,
        time_spent: int,
        hint_count: int = 0
    ) -> bool:
        """
        记录答题事件
        
        用于跟踪正确率、答题时长等指标
        """
        try:
            group = self.get_or_assign_group(user_id)
            metrics_key = self.ABTEST_METRICS_KEY.format(user_id=user_id)
            
            # 获取现有指标
            existing_data = self.redis_service.redis_client.hgetall(metrics_key)
            
            # 更新指标
            total = int(existing_data.get('total_questions', 0)) + 1
            correct = int(existing_data.get('correct_count', 0)) + (1 if is_correct else 0)
            total_time = int(existing_data.get('total_session_time', 0)) + time_spent
            total_hints = int(existing_data.get('total_hints', 0)) + hint_count
            
            accuracy_rate = correct / total if total > 0 else 0.0
            avg_time = total_time / total if total > 0 else 0.0
            hint_rate = total_hints / total if total > 0 else 0.0
            
            # 保存更新后的指标
            self.redis_service.redis_client.hset(metrics_key, mapping={
                'user_id': user_id,
                'group': group.value,
                'total_questions': total,
                'correct_count': correct,
                'accuracy_rate': accuracy_rate,
                'total_session_time': total_time,
                'avg_time_per_question': avg_time,
                'hint_usage_rate': hint_rate,
                'last_updated': datetime.now().isoformat()
            })
            
            # 更新聚合统计
            self._update_aggregate_metrics(group, is_correct, time_spent)
            
            return True
            
        except Exception as e:
            logger.error(f"记录答题事件失败: {e}")
            return False
    
    def _update_aggregate_metrics(
        self,
        group: ExperimentGroup,
        is_correct: bool,
        time_spent: int
    ) -> None:
        """更新聚合统计"""
        try:
            aggregate_key = f"{self.ABTEST_AGGREGATE_KEY}:{group.value}"
            
            pipe = self.redis_service.redis_client.pipeline()
            
            # 增加计数
            pipe.hincrby(aggregate_key, 'total_questions', 1)
            pipe.hincrby(aggregate_key, 'correct_count', 1 if is_correct else 0)
            pipe.hincrby(aggregate_key, 'total_time', time_spent)
            
            pipe.execute()
            
        except Exception as e:
            logger.error(f"更新聚合统计失败: {e}")
    
    def get_user_metrics(self, user_id: int) -> Optional[ABTestMetrics]:
        """获取用户指标"""
        try:
            group = self.get_or_assign_group(user_id)
            metrics_key = self.ABTEST_METRICS_KEY.format(user_id=user_id)
            
            data = self.redis_service.redis_client.hgetall(metrics_key)
            
            if not data:
                return None
            
            return ABTestMetrics(
                user_id=user_id,
                group=data.get('group', group.value),
                total_questions=int(data.get('total_questions', 0)),
                correct_count=int(data.get('correct_count', 0)),
                accuracy_rate=float(data.get('accuracy_rate', 0)),
                total_session_time=int(data.get('total_session_time', 0)),
                avg_time_per_question=float(data.get('avg_time_per_question', 0)),
                hint_usage_rate=float(data.get('hint_usage_rate', 0)),
                last_updated=data.get('last_updated', datetime.now().isoformat())
            )
            
        except Exception as e:
            logger.error(f"获取用户指标失败: {e}")
            return None
    
    # ==================== 实验结果分析 ====================
    
    def get_experiment_results(self) -> Dict[str, Any]:
        """
        获取实验结果
        
        对比A组和B组的关键指标
        """
        try:
            results = {
                "experiment_name": self.EXPERIMENT_NAME,
                "timestamp": datetime.now().isoformat(),
                "groups": {}
            }
            
            for group in [ExperimentGroup.CONTROL, ExperimentGroup.TREATMENT]:
                aggregate_key = f"{self.ABTEST_AGGREGATE_KEY}:{group.value}"
                data = self.redis_service.redis_client.hgetall(aggregate_key)
                
                if data:
                    total = int(data.get('total_questions', 0))
                    correct = int(data.get('correct_count', 0))
                    total_time = int(data.get('total_time', 0))
                    
                    results["groups"][group.value] = {
                        "total_questions": total,
                        "correct_count": correct,
                        "accuracy_rate": correct / total if total > 0 else 0.0,
                        "total_time": total_time,
                        "avg_time_per_question": total_time / total if total > 0 else 0.0
                    }
            
            # 计算提升率
            if "A" in results["groups"] and "B" in results["groups"]:
                a_accuracy = results["groups"]["A"]["accuracy_rate"]
                b_accuracy = results["groups"]["B"]["accuracy_rate"]
                
                if a_accuracy > 0:
                    improvement = (b_accuracy - a_accuracy) / a_accuracy * 100
                    results["improvement"] = {
                        "accuracy_rate": round(improvement, 2),
                        "conclusion": "V3优于V2" if improvement > 0 else "V2优于V3"
                    }
            
            return results
            
        except Exception as e:
            logger.error(f"获取实验结果失败: {e}")
            return {"error": str(e)}
    
    def get_group_statistics(self) -> Dict[str, Any]:
        """获取分组统计"""
        try:
            # 扫描所有用户分组
            pattern = self.ABTEST_GROUP_KEY.format(user_id="*")
            keys = self.redis_service.redis_client.keys(pattern)
            
            a_count = 0
            b_count = 0
            
            for key in keys:
                group = self.redis_service.redis_client.get(key)
                if group == "A":
                    a_count += 1
                elif group == "B":
                    b_count += 1
            
            total = a_count + b_count
            
            return {
                "total_users": total,
                "group_a": {
                    "count": a_count,
                    "percentage": round(a_count / total * 100, 1) if total > 0 else 0
                },
                "group_b": {
                    "count": b_count,
                    "percentage": round(b_count / total * 100, 1) if total > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"获取分组统计失败: {e}")
            return {"error": str(e)}
    
    # ==================== 实验管理 ====================
    
    def reset_experiment(self) -> bool:
        """重置实验（清除所有数据）"""
        try:
            # 删除所有A/B测试相关的key
            patterns = [
                self.ABTEST_GROUP_KEY.format(user_id="*"),
                self.ABTEST_METRICS_KEY.format(user_id="*"),
                f"{self.ABTEST_AGGREGATE_KEY}:*"
            ]
            
            for pattern in patterns:
                keys = self.redis_service.redis_client.keys(pattern)
                if keys:
                    self.redis_service.redis_client.delete(*keys)
            
            logger.info("A/B测试实验已重置")
            return True
            
        except Exception as e:
            logger.error(f"重置实验失败: {e}")
            return False


# ==================== 便捷函数 ====================

def get_user_experiment_group(user_id: int) -> str:
    """便捷函数：获取用户实验组"""
    service = ABTestingService()
    group = service.get_or_assign_group(user_id)
    return group.value


def is_v3_user(user_id: int) -> bool:
    """便捷函数：判断用户是否使用V3特性"""
    service = ABTestingService()
    return service.should_use_v3_features(user_id)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("A/B测试服务测试")
    print("=" * 60)
    
    service = ABTestingService()
    
    # 测试用户分组
    print("\n用户分组测试：")
    for user_id in [1, 2, 3, 4, 5]:
        group = service.assign_user_to_group(user_id)
        print(f"  用户 {user_id} -> {group.value} 组")
    
    # 测试策略获取
    print("\n推荐策略测试：")
    for user_id in [1, 2]:
        strategy = service.get_recommendation_strategy(user_id)
        print(f"  用户 {user_id} ({strategy['group']}组): {strategy['strategy']}")
    
    # 测试指标记录
    print("\n指标记录测试：")
    service.record_answer_event(1, True, 60, 1)
    service.record_answer_event(1, False, 120, 2)
    service.record_answer_event(2, True, 45, 0)
    print("  已记录答题事件")
    
    # 测试指标查询
    print("\n指标查询测试：")
    metrics = service.get_user_metrics(1)
    if metrics:
        print(f"  用户1: 正确率={metrics.accuracy_rate:.1%}, 答题数={metrics.total_questions}")
    
    # 测试实验结果
    print("\n实验结果测试：")
    results = service.get_experiment_results()
    print(f"  实验名称: {results.get('experiment_name')}")
    if 'groups' in results:
        for group, data in results['groups'].items():
            print(f"  {group}组: 正确率={data.get('accuracy_rate', 0):.1%}")
    
    # 清理
    service.reset_experiment()
    print("\n测试数据已清理")
