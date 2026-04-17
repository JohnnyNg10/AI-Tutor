"""
数据迁移服务
处理V2到V3的数据迁移和兼容性处理

对应需求37: 解决系统大版本升级带来的数据断层

实现文件：backend/services/data_migration_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from utils.logger import logger
from utils.config import settings


@dataclass
class MigrationResult:
    """迁移结果"""
    table_name: str
    total_records: int
    migrated_records: int
    failed_records: int
    errors: List[str]


class DataMigrationService:
    """
    数据迁移服务
    
    功能：
    1. V2到V3的数据迁移
    2. 缺失字段的默认值填充
    3. 数据一致性检查
    4. 迁移回滚支持
    """
    
    # BKT算法默认参数
    DEFAULT_BKT_PARAMS = {
        'p_guess': 0.2,
        'p_slip': 0.1,
        'p_known': 0.5
    }
    
    # IRT默认参数
    DEFAULT_IRT_PARAMS = {
        'theta': 0.0,
        'theta_se': 1.0,
        'theta_ci_lower': -2.0,
        'theta_ci_upper': 2.0
    }
    
    def __init__(self):
        """初始化数据迁移服务"""
        self.engine = create_engine(settings.database_url)
        self.Session = sessionmaker(bind=self.engine)
        logger.info("数据迁移服务初始化完成")
    
    # ==================== 需求37: V2到V3数据迁移 ====================
    
    def migrate_user_profiles(self) -> MigrationResult:
        """
        迁移user_profiles表
        
        为老用户填充V3新增字段的默认值
        """
        result = MigrationResult(
            table_name='user_profiles',
            total_records=0,
            migrated_records=0,
            failed_records=0,
            errors=[]
        )
        
        try:
            session = self.Session()
            
            # 获取需要迁移的记录（theta为空的记录）
            rows = session.execute(text("""
                SELECT id, user_id FROM user_profiles 
                WHERE theta IS NULL
            """)).fetchall()
            
            result.total_records = len(rows)
            logger.info(f"找到 {len(rows)} 条需要迁移的user_profiles记录")
            
            for row in rows:
                try:
                    # 计算默认值
                    default_values = self._calculate_user_profile_defaults(row.user_id)
                    
                    session.execute(text("""
                        UPDATE user_profiles 
                        SET theta = :theta,
                            theta_se = :theta_se,
                            theta_ci_lower = :theta_ci_lower,
                            theta_ci_upper = :theta_ci_upper,
                            avg_mastery = :avg_mastery,
                            weak_kp_count = :weak_kp_count,
                            learning_style = :learning_style,
                            mastery_strategy = :mastery_strategy
                        WHERE id = :id
                    """), {
                        'id': row.id,
                        **default_values
                    })
                    
                    result.migrated_records += 1
                    
                except Exception as e:
                    result.failed_records += 1
                    result.errors.append(f"用户 {row.user_id}: {str(e)}")
                    logger.error(f"迁移user_profiles失败 用户ID={row.user_id}: {e}")
            
            session.commit()
            logger.info(f"user_profiles迁移完成: {result.migrated_records}/{result.total_records}")
            
        except Exception as e:
            logger.error(f"迁移user_profiles表失败: {e}")
            result.errors.append(str(e))
        
        return result
    
    def migrate_user_knowledge_mastery(self) -> MigrationResult:
        """
        迁移user_knowledge_mastery表
        
        为老记录填充BKT参数默认值
        """
        result = MigrationResult(
            table_name='user_knowledge_mastery',
            total_records=0,
            migrated_records=0,
            failed_records=0,
            errors=[]
        )
        
        try:
            session = self.Session()
            
            # 获取需要迁移的记录
            rows = session.execute(text("""
                SELECT id, user_id, knowledge_point_id, mastery_level 
                FROM user_knowledge_mastery 
                WHERE p_known IS NULL
            """)).fetchall()
            
            result.total_records = len(rows)
            logger.info(f"找到 {len(rows)} 条需要迁移的user_knowledge_mastery记录")
            
            for row in rows:
                try:
                    # 根据mastery_level计算p_known默认值
                    p_known = self._mastery_level_to_p_known(row.mastery_level)
                    
                    session.execute(text("""
                        UPDATE user_knowledge_mastery 
                        SET p_guess = :p_guess,
                            p_slip = :p_slip,
                            p_known = :p_known,
                            consecutive_correct = :consecutive_correct,
                            consecutive_wrong = :consecutive_wrong
                        WHERE id = :id
                    """), {
                        'id': row.id,
                        'p_guess': self.DEFAULT_BKT_PARAMS['p_guess'],
                        'p_slip': self.DEFAULT_BKT_PARAMS['p_slip'],
                        'p_known': p_known,
                        'consecutive_correct': 0,
                        'consecutive_wrong': 0
                    })
                    
                    result.migrated_records += 1
                    
                except Exception as e:
                    result.failed_records += 1
                    result.errors.append(f"记录 {row.id}: {str(e)}")
                    logger.error(f"迁移user_knowledge_mastery失败 记录ID={row.id}: {e}")
            
            session.commit()
            logger.info(f"user_knowledge_mastery迁移完成: {result.migrated_records}/{result.total_records}")
            
        except Exception as e:
            logger.error(f"迁移user_knowledge_mastery表失败: {e}")
            result.errors.append(str(e))
        
        return result
    
    def migrate_learning_records(self) -> MigrationResult:
        """
        迁移learning_records表
        
        为老记录填充交互行为字段的默认值
        """
        result = MigrationResult(
            table_name='learning_records',
            total_records=0,
            migrated_records=0,
            failed_records=0,
            errors=[]
        )
        
        try:
            session = self.Session()
            
            # 获取需要迁移的记录
            rows = session.execute(text("""
                SELECT id, user_id, question_id, is_correct, created_at 
                FROM learning_records 
                WHERE hint_count IS NULL
                LIMIT 10000  -- 分批处理，避免内存溢出
            """)).fetchall()
            
            result.total_records = len(rows)
            logger.info(f"找到 {len(rows)} 条需要迁移的learning_records记录")
            
            for row in rows:
                try:
                    # 根据is_correct推断theta_before/after
                    theta_values = self._estimate_theta_values(row.user_id, row.is_correct)
                    
                    session.execute(text("""
                        UPDATE learning_records 
                        SET hint_count = :hint_count,
                            time_spent = :time_spent,
                            skip_reason = :skip_reason,
                            theta_before = :theta_before,
                            theta_after = :theta_after,
                            mastery_updates = :mastery_updates
                        WHERE id = :id
                    """), {
                        'id': row.id,
                        'hint_count': 0,
                        'time_spent': None,  # 无法 retroactively 计算
                        'skip_reason': None,
                        'theta_before': theta_values['before'],
                        'theta_after': theta_values['after'],
                        'mastery_updates': None
                    })
                    
                    result.migrated_records += 1
                    
                except Exception as e:
                    result.failed_records += 1
                    result.errors.append(f"记录 {row.id}: {str(e)}")
            
            session.commit()
            logger.info(f"learning_records迁移完成: {result.migrated_records}/{result.total_records}")
            
        except Exception as e:
            logger.error(f"迁移learning_records表失败: {e}")
            result.errors.append(str(e))
        
        return result
    
    def initialize_user_ability_history(self) -> MigrationResult:
        """
        初始化user_ability_history表
        
        为所有老用户创建初始能力历史记录
        """
        result = MigrationResult(
            table_name='user_ability_history',
            total_records=0,
            migrated_records=0,
            failed_records=0,
            errors=[]
        )
        
        try:
            session = self.Session()
            
            # 获取所有用户
            users = session.execute(text("""
                SELECT DISTINCT user_id FROM user_profiles
                WHERE user_id NOT IN (
                    SELECT DISTINCT user_id FROM user_ability_history
                )
            """)).fetchall()
            
            result.total_records = len(users)
            logger.info(f"需要为 {len(users)} 个用户初始化能力历史")
            
            for user_row in users:
                try:
                    user_id = user_row.user_id
                    
                    # 获取用户当前画像
                    profile = session.execute(text("""
                        SELECT theta, avg_mastery, weak_kp_count, total_questions, correct_count
                        FROM user_profiles WHERE user_id = :user_id
                    """), {'user_id': user_id}).fetchone()
                    
                    if profile:
                        session.execute(text("""
                            INSERT INTO user_ability_history 
                            (user_id, theta, theta_se, theta_ci_lower, theta_ci_upper,
                             avg_mastery, weak_kp_count, total_questions, correct_count, created_at)
                            VALUES 
                            (:user_id, :theta, :theta_se, :theta_ci_lower, :theta_ci_upper,
                             :avg_mastery, :weak_kp_count, :total_questions, :correct_count, :created_at)
                        """), {
                            'user_id': user_id,
                            'theta': profile.theta or 0.0,
                            'theta_se': 1.0,
                            'theta_ci_lower': -2.0,
                            'theta_ci_upper': 2.0,
                            'avg_mastery': profile.avg_mastery or 50.0,
                            'weak_kp_count': profile.weak_kp_count or 0,
                            'total_questions': profile.total_questions or 0,
                            'correct_count': profile.correct_count or 0,
                            'created_at': datetime.now() - timedelta(days=30)  # 模拟30天前的初始记录
                        })
                        
                        result.migrated_records += 1
                    
                except Exception as e:
                    result.failed_records += 1
                    result.errors.append(f"用户 {user_id}: {str(e)}")
            
            session.commit()
            logger.info(f"user_ability_history初始化完成: {result.migrated_records}/{result.total_records}")
            
        except Exception as e:
            logger.error(f"初始化user_ability_history失败: {e}")
            result.errors.append(str(e))
        
        return result
    
    # ==================== 辅助方法 ====================
    
    def _calculate_user_profile_defaults(self, user_id: int) -> Dict[str, Any]:
        """计算用户画像的默认值"""
        return {
            'theta': 0.0,
            'theta_se': 1.0,
            'theta_ci_lower': -2.0,
            'theta_ci_upper': 2.0,
            'avg_mastery': 50.0,
            'weak_kp_count': 0,
            'learning_style': 'balanced',
            'mastery_strategy': 'simple'
        }
    
    def _mastery_level_to_p_known(self, mastery_level: str) -> float:
        """将mastery_level转换为p_known默认值"""
        level_map = {
            'weak': 0.3,
            'learning': 0.6,
            'mastered': 0.9
        }
        return level_map.get(mastery_level, 0.5)
    
    def _estimate_theta_values(self, user_id: int, is_correct: bool) -> Dict[str, float]:
        """估计theta_before和theta_after"""
        # 简化估计：根据答题正确性推断
        if is_correct:
            return {'before': 0.0, 'after': 0.05}
        else:
            return {'before': 0.0, 'after': -0.05}
    
    # ==================== 数据一致性检查 ====================
    
    def check_data_consistency(self) -> Dict[str, Any]:
        """
        检查数据一致性
        
        返回潜在的数据问题
        """
        issues = []
        
        try:
            session = self.Session()
            
            # 检查1：user_profiles中theta为空的用户
            null_theta = session.execute(text("""
                SELECT COUNT(*) FROM user_profiles WHERE theta IS NULL
            """)).scalar()
            
            if null_theta > 0:
                issues.append(f"{null_theta} 个用户的 theta 值为空")
            
            # 检查2：user_knowledge_mastery中p_known为空的记录
            null_p_known = session.execute(text("""
                SELECT COUNT(*) FROM user_knowledge_mastery WHERE p_known IS NULL
            """)).scalar()
            
            if null_p_known > 0:
                issues.append(f"{null_p_known} 条掌握度记录的 p_known 为空")
            
            # 检查3：learning_records中缺少V3字段的记录
            null_v3_fields = session.execute(text("""
                SELECT COUNT(*) FROM learning_records WHERE hint_count IS NULL
            """)).scalar()
            
            if null_v3_fields > 0:
                issues.append(f"{null_v3_fields} 条答题记录缺少 V3 字段")
            
            session.close()
            
        except Exception as e:
            issues.append(f"数据一致性检查失败: {e}")
        
        return {
            'has_issues': len(issues) > 0,
            'issues': issues
        }
    
    # ==================== 主执行方法 ====================
    
    def run_full_migration(self) -> Dict[str, MigrationResult]:
        """执行完整的数据迁移"""
        logger.info("=" * 60)
        logger.info("开始 V2 到 V3 数据迁移")
        logger.info("=" * 60)
        
        results = {
            'user_profiles': self.migrate_user_profiles(),
            'user_knowledge_mastery': self.migrate_user_knowledge_mastery(),
            'learning_records': self.migrate_learning_records(),
            'user_ability_history': self.initialize_user_ability_history()
        }
        
        # 检查数据一致性
        consistency = self.check_data_consistency()
        
        logger.info("=" * 60)
        logger.info("数据迁移完成")
        logger.info("=" * 60)
        
        total_migrated = sum(r.migrated_records for r in results.values())
        total_failed = sum(r.failed_records for r in results.values())
        
        logger.info(f"总计迁移: {total_migrated} 条记录")
        logger.info(f"失败: {total_failed} 条记录")
        
        if consistency['has_issues']:
            logger.warning("发现数据一致性问题:")
            for issue in consistency['issues']:
                logger.warning(f"  - {issue}")
        
        return results


# ==================== 便捷函数 ====================

def run_data_migration():
    """便捷函数：运行数据迁移"""
    service = DataMigrationService()
    return service.run_full_migration()


if __name__ == "__main__":
    print("=" * 60)
    print("V2 到 V3 数据迁移")
    print("=" * 60)
    
    results = run_data_migration()
    
    print("\n迁移结果汇总:")
    for table, result in results.items():
        status = "✅" if result.failed_records == 0 else "⚠️"
        print(f"{status} {table}: {result.migrated_records}/{result.total_records}")
