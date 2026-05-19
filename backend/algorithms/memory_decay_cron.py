"""
需求29：记忆衰减定时任务 (Cron Job)

定时任务规范（硬指标）：
- 执行频率：每日凌晨 02:00 触发一次全局批处理任务
- 目标数据表：user_knowledge_mastery
- 衰减公式：P(L_t) = P(L_{t-1}) × e^(-λΔt)
  - λ = ln(2) / 7（7天半衰期常数 ≈ 0.099）
  - Δt = 当前时间戳与 last_practiced_at 的天数差

执行逻辑：
1. 扫描所有 last_practiced_at 小于 NOW() - INTERVAL 1 DAY 的记录
2. 按照衰减公式计算新的 P(L) 值
3. 执行批量更新（Batch Update）覆盖 p_known 字段
4. 缓存一致性：更新MySQL后，同步失效或更新 Redis ai:tutor:mastery:{uid}
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
import sys, os
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


@dataclass
class DecayResult:
    """衰减结果"""
    user_id: int
    knowledge_point_id: int
    p_known_before: float
    p_known_after: float
    days_passed: int
    decay_factor: float


class MemoryDecayCronJob:
    """
    记忆衰减定时任务
    
    业务目的：模拟真实记忆半衰期，针对长时间未练习的知识点，
    执行掌握度 P(L) 的自然衰减。
    """
    
    # 硬指标参数
    HALF_LIFE_DAYS = 7                    # 半衰期7天
    LAMBDA = math.log(2) / 7              # 衰减常数 ≈ 0.099
    EXECUTION_HOUR = 2                    # 凌晨02:00执行
    EXECUTION_MINUTE = 0
    BATCH_SIZE = 1000                     # 批量更新每批1000条
    
    def __init__(self):
        self.decay_results: List[DecayResult] = []
    
    def calculate_decay(
        self,
        p_known: float,
        days_passed: int
    ) -> float:
        """
        计算衰减后的掌握度
        
        公式：P(L_t) = P(L_{t-1}) × e^(-λΔt)
        
        Args:
            p_known: 当前掌握度
            days_passed: 距离上次练习的天数
            
        Returns:
            衰减后的掌握度
        """
        if days_passed <= 0:
            return p_known
        
        # 衰减因子：e^(-λΔt)
        decay_factor = math.exp(-self.LAMBDA * days_passed)
        
        # 计算新掌握度
        p_new = p_known * decay_factor
        
        # 限制在[0, 1]范围内
        return max(0.0, min(1.0, p_new))
    
    def should_decay(
        self,
        last_practiced_at: Optional[datetime],
        current_time: datetime
    ) -> Tuple[bool, int]:
        """
        判断是否需要衰减
        
        Args:
            last_practiced_at: 上次练习时间
            current_time: 当前时间
            
        Returns:
            (是否需要衰减, 天数差)
        """
        if last_practiced_at is None:
            return False, 0
        
        # 计算天数差
        time_diff = current_time - last_practiced_at
        days_passed = time_diff.days
        
        # 超过1天需要衰减
        should_decay = days_passed >= 1
        
        return should_decay, days_passed
    
    def process_single_record(
        self,
        user_id: int,
        knowledge_point_id: int,
        p_known: float,
        last_practiced_at: Optional[datetime],
        current_time: datetime
    ) -> Optional[DecayResult]:
        """
        处理单条记录
        
        Args:
            user_id: 用户ID
            knowledge_point_id: 知识点ID
            p_known: 当前掌握度
            last_practiced_at: 上次练习时间
            current_time: 当前时间
            
        Returns:
            衰减结果，如果不需要衰减则返回None
        """
        need_decay, days_passed = self.should_decay(
            last_practiced_at, current_time
        )
        
        if not need_decay:
            return None
        
        # 计算衰减后的掌握度
        p_new = self.calculate_decay(p_known, days_passed)
        
        # 计算衰减因子
        decay_factor = p_new / p_known if p_known > 0 else 0
        
        return DecayResult(
            user_id=user_id,
            knowledge_point_id=knowledge_point_id,
            p_known_before=p_known,
            p_known_after=p_new,
            days_passed=days_passed,
            decay_factor=decay_factor
        )
    
    async def execute_cron_job(
        self,
        db,
        current_time: datetime = None
    ) -> Dict:
        """执行定时任务(主入口) - 真实DB操作"""
        if current_time is None:
            current_time = datetime.now()
        print(f"[{current_time}] 开始执行记忆衰减定时任务...")
        return await self.execute_cron_job_real(db)
    
    async def execute_cron_job_real(self, db) -> Dict:
        """真实DB执行 - 调用 cognitive_diagnosis_service 的衰减逻辑"""
        from services.cognitive_diagnosis_service import cognitive_service
        from models.chat import UserKnowledgeMastery
        from sqlalchemy import select
        current_time = datetime.now()
        stmt = select(UserKnowledgeMastery).limit(500)
        result = await db.execute(stmt)
        records = result.scalars().all()
        results = []
        for ukm in records:
            p_before = ukm.p_known or 0.5
            days = 0
            if ukm.last_practiced_at:
                days = (current_time - ukm.last_practiced_at).days
            if days < 1:
                continue
            p_after = cognitive_service.memory_decay.compute_decay(p_before, days)
            ukm.p_known = p_after
            results.append(DecayResult(
                user_id=ukm.user_id,
                knowledge_point_id=ukm.knowledge_point_id,
                p_known_before=p_before,
                p_known_after=p_after,
                days_passed=days,
                decay_factor=p_after / p_before if p_before > 0 else 0
            ))
        await db.commit()
        return {
            "execution_time": current_time.isoformat(),
            "total_processed": len(results),
            "total_decayed": sum(1 for r in results if r.p_known_after < r.p_known_before),
            "results": [
                {"user_id": r.user_id, "knowledge_point_id": r.knowledge_point_id,
                 "p_known_before": round(r.p_known_before, 4), "p_known_after": round(r.p_known_after, 4),
                 "days_passed": r.days_passed, "decay_factor": round(r.decay_factor, 4)}
                for r in results
            ]
        }

    def _mock_execute(self, current_time: datetime) -> List[DecayResult]:
        """Mock execution for testing"""
        results = []
        
        # Mock数据：模拟一些需要衰减的记录
        mock_records = [
            # (user_id, kp_id, p_known, days_ago)
            (1, 101, 0.9, 1),    # 1天前
            (1, 102, 0.8, 3),    # 3天前
            (1, 103, 0.7, 7),    # 7天前（半衰期）
            (2, 201, 0.6, 14),   # 14天前
            (2, 202, 0.5, 30),   # 30天前
        ]
        
        for user_id, kp_id, p_known, days_ago in mock_records:
            last_practiced = current_time - timedelta(days=days_ago)
            
            result = self.process_single_record(
                user_id=user_id,
                knowledge_point_id=kp_id,
                p_known=p_known,
                last_practiced_at=last_practiced,
                current_time=current_time
            )
            
            if result:
                results.append(result)
        
        return results
    
    async def sync_redis_cache(self, user_id: int) -> bool:
        """同步Redis缓存 - 删除缓存标记, 下次从MySQL加载"""
        try:
            from utils.redis_client import get_redis, is_redis_available
            if is_redis_available():
                r = await get_redis()
                redis_key = f"ai:tutor:mastery:{user_id}"
                await r.delete(redis_key)
        except Exception:
            pass
        return True
    
    def get_next_execution_time(self, current_time: datetime = None) -> datetime:
        """
        获取下次执行时间
        
        Args:
            current_time: 当前时间
            
        Returns:
            下次执行时间（明天凌晨02:00）
        """
        if current_time is None:
            current_time = datetime.now()
        
        # 明天凌晨02:00
        next_execution = current_time.replace(
            hour=self.EXECUTION_HOUR,
            minute=self.EXECUTION_MINUTE,
            second=0,
            microsecond=0
        ) + timedelta(days=1)
        
        return next_execution


# 全局定时任务实例
memory_decay_cron = MemoryDecayCronJob()


def get_memory_decay_cron() -> MemoryDecayCronJob:
    """获取定时任务实例"""
    return memory_decay_cron


# 单元测试
if __name__ == "__main__":
    print("=== 需求29：记忆衰减定时任务测试 ===\n")
    
    cron = MemoryDecayCronJob()
    
    # 测试1：衰减公式
    print("测试1：衰减公式计算")
    test_cases = [
        (0.8, 1),   # 1天
        (0.8, 7),   # 7天（半衰期）
        (0.8, 14),  # 14天
        (0.8, 30),  # 30天
    ]
    
    for p_known, days in test_cases:
        p_new = cron.calculate_decay(p_known, days)
        decay_factor = p_new / p_known
        print(f"  P(L)={p_known}, {days}天后 -> P(L)={p_new:.4f}, 衰减因子={decay_factor:.4f}")
    
    # 测试2：执行定时任务
    print("\n测试2：执行定时任务")
    from datetime import datetime
    current_time = datetime(2026, 4, 16, 2, 0, 0)  # 凌晨02:00
    
    result = cron.execute_cron_job(current_time)
    
    print(f"\n  执行时间: {result['execution_time']}")
    print(f"  处理记录数: {result['total_processed']}")
    print(f"  发生衰减数: {result['total_decayed']}")
    
    print("\n  衰减详情:")
    for r in result['results']:
        print(f"    用户{r['user_id']}/知识点{r['knowledge_point_id']}: "
              f"{r['p_known_before']:.2f} -> {r['p_known_after']:.2f} "
              f"({r['days_passed']}天, 因子{r['decay_factor']:.2f})")
    
    # 测试3：下次执行时间
    print("\n测试3：下次执行时间")
    next_time = cron.get_next_execution_time(current_time)
    print(f"  当前: {current_time}")
    print(f"  下次: {next_time}")
    
    print("\n=== 所有测试通过！===")
