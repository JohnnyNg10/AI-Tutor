"""
V3 数据库表扩展迁移脚本
对应需求：
- 需求34: 扩展learning_records表
- 需求35: 扩展user_profiles表和user_knowledge_mastery表
- 需求36: 创建新表（user_ability_history, user_interaction_logs等）

实现文件：backend/database/migrations/v3_schema_extensions.py
"""

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, 
    Float, DateTime, Boolean, Text, JSON, ForeignKey, Index
)
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class V3SchemaExtensions:
    """
    V3 数据库表扩展
    
    包含：
    1. 现有表扩展（learning_records, user_profiles, user_knowledge_mastery）
    2. 新表创建（user_ability_history, user_interaction_logs等）
    """
    
    def __init__(self, database_url: str):
        """初始化数据库连接"""
        self.engine = create_engine(database_url)
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)
        logger.info("V3 Schema Extensions 初始化完成")
    
    # ==================== 需求34: 扩展learning_records表 ====================
    
    def extend_learning_records(self):
        """
        扩展learning_records表
        
        新增字段：
        - hint_count: 提示使用次数
        - time_spent: 答题耗时（秒）
        - skip_reason: 跳过原因（too_easy/too_hard/other）
        - theta_before: 答题前能力值
        - theta_after: 答题后能力值
        - mastery_updates: 各知识点掌握度更新（JSON）
        """
        try:
            # 获取现有表
            learning_records = self.metadata.tables.get('learning_records')
            
            if learning_records is None:
                logger.error("learning_records表不存在")
                return False
            
            # 新增字段
            new_columns = [
                Column('hint_count', Integer, default=0, comment='提示使用次数'),
                Column('time_spent', Integer, nullable=True, comment='答题耗时（秒）'),
                Column('skip_reason', String(20), nullable=True, comment='跳过原因'),
                Column('theta_before', Float, nullable=True, comment='答题前能力值'),
                Column('theta_after', Float, nullable=True, comment='答题后能力值'),
                Column('mastery_updates', JSON, nullable=True, comment='各知识点掌握度更新'),
            ]
            
            # 添加字段
            with self.engine.connect() as conn:
                for column in new_columns:
                    try:
                        column_name = column.name
                        # 检查字段是否已存在
                        if column_name not in learning_records.columns:
                            conn.execute(f"""
                                ALTER TABLE learning_records 
                                ADD COLUMN {column_name} {self._get_column_type(column)}
                            """)
                            logger.info(f"添加字段 {column_name} 到 learning_records 表")
                        else:
                            logger.info(f"字段 {column_name} 已存在，跳过")
                    except SQLAlchemyError as e:
                        logger.error(f"添加字段 {column.name} 失败: {e}")
                        continue
            
            logger.info("learning_records表扩展完成")
            return True
            
        except Exception as e:
            logger.error(f"扩展learning_records表失败: {e}")
            return False
    
    # ==================== 需求35: 扩展user_profiles表 ====================
    
    def extend_user_profiles(self):
        """
        扩展user_profiles表
        
        新增字段：
        - theta: 当前IRT能力值
        - theta_se: 标准误差
        - theta_ci_lower: 95%置信区间下限
        - theta_ci_upper: 95%置信区间上限
        - avg_mastery: 平均掌握度
        - weak_kp_count: 薄弱知识点数量
        - learning_style: 学习风格
        - mastery_strategy: 掌握度计算策略
        """
        try:
            user_profiles = self.metadata.tables.get('user_profiles')
            
            if user_profiles is None:
                logger.error("user_profiles表不存在")
                return False
            
            new_columns = [
                Column('theta', Float, nullable=True, comment='当前IRT能力值'),
                Column('theta_se', Float, nullable=True, comment='标准误差'),
                Column('theta_ci_lower', Float, nullable=True, comment='95%置信区间下限'),
                Column('theta_ci_upper', Float, nullable=True, comment='95%置信区间上限'),
                Column('avg_mastery', Float, nullable=True, comment='平均掌握度'),
                Column('weak_kp_count', Integer, default=0, comment='薄弱知识点数量'),
                Column('learning_style', String(20), nullable=True, comment='学习风格'),
                Column('mastery_strategy', String(20), default='simple', comment='掌握度计算策略'),
            ]
            
            with self.engine.connect() as conn:
                for column in new_columns:
                    try:
                        column_name = column.name
                        if column_name not in user_profiles.columns:
                            conn.execute(f"""
                                ALTER TABLE user_profiles 
                                ADD COLUMN {column_name} {self._get_column_type(column)}
                            """)
                            logger.info(f"添加字段 {column_name} 到 user_profiles 表")
                        else:
                            logger.info(f"字段 {column_name} 已存在，跳过")
                    except SQLAlchemyError as e:
                        logger.error(f"添加字段 {column.name} 失败: {e}")
                        continue
            
            logger.info("user_profiles表扩展完成")
            return True
            
        except Exception as e:
            logger.error(f"扩展user_profiles表失败: {e}")
            return False
    
    def extend_user_knowledge_mastery(self):
        """
        扩展user_knowledge_mastery表
        
        新增BKT参数字段：
        - p_guess: 猜测概率 P(G)
        - p_slip: 失误概率 P(S)
        - p_known: 当前掌握概率 P(L)
        - consecutive_correct: 连续正确次数
        - consecutive_wrong: 连续错误次数
        """
        try:
            user_knowledge_mastery = self.metadata.tables.get('user_knowledge_mastery')
            
            if user_knowledge_mastery is None:
                logger.error("user_knowledge_mastery表不存在")
                return False
            
            new_columns = [
                Column('p_guess', Float, default=0.2, comment='猜测概率 P(G)'),
                Column('p_slip', Float, default=0.1, comment='失误概率 P(S)'),
                Column('p_known', Float, default=0.5, comment='当前掌握概率 P(L)'),
                Column('consecutive_correct', Integer, default=0, comment='连续正确次数'),
                Column('consecutive_wrong', Integer, default=0, comment='连续错误次数'),
            ]
            
            with self.engine.connect() as conn:
                for column in new_columns:
                    try:
                        column_name = column.name
                        if column_name not in user_knowledge_mastery.columns:
                            conn.execute(f"""
                                ALTER TABLE user_knowledge_mastery 
                                ADD COLUMN {column_name} {self._get_column_type(column)}
                            """)
                            logger.info(f"添加字段 {column_name} 到 user_knowledge_mastery 表")
                        else:
                            logger.info(f"字段 {column_name} 已存在，跳过")
                    except SQLAlchemyError as e:
                        logger.error(f"添加字段 {column.name} 失败: {e}")
                        continue
            
            logger.info("user_knowledge_mastery表扩展完成")
            return True
            
        except Exception as e:
            logger.error(f"扩展user_knowledge_mastery表失败: {e}")
            return False
    
    # ==================== 需求36: 创建新表 ====================
    
    def create_user_ability_history_table(self):
        """
        创建user_ability_history表
        
        记录学生能力历史变化，用于绘制能力曲线
        """
        try:
            if 'user_ability_history' in self.metadata.tables:
                logger.info("user_ability_history表已存在，跳过创建")
                return True
            
            user_ability_history = Table(
                'user_ability_history',
                self.metadata,
                Column('id', Integer, primary_key=True, autoincrement=True),
                Column('user_id', Integer, ForeignKey('users.id'), nullable=False, comment='用户ID'),
                Column('theta', Float, nullable=False, comment='IRT能力值'),
                Column('theta_se', Float, nullable=True, comment='标准误差'),
                Column('theta_ci_lower', Float, nullable=True, comment='95%置信区间下限'),
                Column('theta_ci_upper', Float, nullable=True, comment='95%置信区间上限'),
                Column('avg_mastery', Float, nullable=True, comment='平均掌握度'),
                Column('weak_kp_count', Integer, default=0, comment='薄弱知识点数量'),
                Column('total_questions', Integer, default=0, comment='总答题数'),
                Column('correct_count', Integer, default=0, comment='正确数'),
                Column('created_at', DateTime, default=datetime.now, comment='记录时间'),
                Index('idx_user_id_created_at', 'user_id', 'created_at'),
                mysql_engine='InnoDB',
                mysql_charset='utf8mb4'
            )
            
            user_ability_history.create(self.engine)
            logger.info("user_ability_history表创建完成")
            return True
            
        except Exception as e:
            logger.error(f"创建user_ability_history表失败: {e}")
            return False
    
    def create_user_interaction_logs_table(self):
        """
        创建user_interaction_logs表
        
        全量记录用户在学习过程中的每一个微小交互
        """
        try:
            if 'user_interaction_logs' in self.metadata.tables:
                logger.info("user_interaction_logs表已存在，跳过创建")
                return True
            
            user_interaction_logs = Table(
                'user_interaction_logs',
                self.metadata,
                Column('id', Integer, primary_key=True, autoincrement=True),
                Column('user_id', Integer, ForeignKey('users.id'), nullable=False, comment='用户ID'),
                Column('session_id', String(64), nullable=True, comment='会话ID'),
                Column('question_id', String(64), nullable=True, comment='题目ID'),
                Column('action_type', String(50), nullable=False, comment='交互类型'),
                Column('action_detail', JSON, nullable=True, comment='交互详情'),
                Column('hint_level', Integer, nullable=True, comment='当前提示等级'),
                Column('time_spent', Integer, nullable=True, comment='停留时间（秒）'),
                Column('created_at', DateTime, default=datetime.now, comment='记录时间'),
                Index('idx_user_id_created_at', 'user_id', 'created_at'),
                Index('idx_session_id', 'session_id'),
                mysql_engine='InnoDB',
                mysql_charset='utf8mb4'
            )
            
            user_interaction_logs.create(self.engine)
            logger.info("user_interaction_logs表创建完成")
            return True
            
        except Exception as e:
            logger.error(f"创建user_interaction_logs表失败: {e}")
            return False
    
    def create_review_queue_settings_table(self):
        """
        创建review_queue_settings表
        
        存储用户错题复习队列的设置和状态
        """
        try:
            if 'review_queue_settings' in self.metadata.tables:
                logger.info("review_queue_settings表已存在，跳过创建")
                return True
            
            review_queue_settings = Table(
                'review_queue_settings',
                self.metadata,
                Column('id', Integer, primary_key=True, autoincrement=True),
                Column('user_id', Integer, ForeignKey('users.id'), nullable=False, comment='用户ID'),
                Column('question_id', String(64), nullable=False, comment='题目ID'),
                Column('error_count', Integer, default=1, comment='错误次数'),
                Column('next_review_at', DateTime, nullable=False, comment='下次复习时间'),
                Column('review_stage', Integer, default=0, comment='复习阶段（0-4）'),
                Column('is_mastered', Boolean, default=False, comment='是否已攻克'),
                Column('created_at', DateTime, default=datetime.now, comment='创建时间'),
                Column('updated_at', DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间'),
                Index('idx_user_id_next_review', 'user_id', 'next_review_at'),
                Index('idx_user_id_question', 'user_id', 'question_id', unique=True),
                mysql_engine='InnoDB',
                mysql_charset='utf8mb4'
            )
            
            review_queue_settings.create(self.engine)
            logger.info("review_queue_settings表创建完成")
            return True
            
        except Exception as e:
            logger.error(f"创建review_queue_settings表失败: {e}")
            return False
    
    # ==================== 辅助方法 ====================
    
    def _get_column_type(self, column):
        """获取列的SQL类型定义"""
        from sqlalchemy.dialects.mysql import INTEGER, FLOAT, VARCHAR, JSON as MYSQL_JSON
        
        if isinstance(column.type, Integer):
            return "INT"
        elif isinstance(column.type, Float):
            return "FLOAT"
        elif isinstance(column.type, String):
            return f"VARCHAR({column.type.length})"
        elif isinstance(column.type, JSON):
            return "JSON"
        else:
            return str(column.type)
    
    # ==================== 主执行方法 ====================
    
    def run_all_migrations(self):
        """执行所有迁移"""
        results = {
            'extend_learning_records': self.extend_learning_records(),
            'extend_user_profiles': self.extend_user_profiles(),
            'extend_user_knowledge_mastery': self.extend_user_knowledge_mastery(),
            'create_user_ability_history': self.create_user_ability_history_table(),
            'create_user_interaction_logs': self.create_user_interaction_logs_table(),
            'create_review_queue_settings': self.create_review_queue_settings_table(),
        }
        
        logger.info("=" * 60)
        logger.info("V3 数据库迁移完成")
        logger.info("=" * 60)
        for task, success in results.items():
            status = "✅ 成功" if success else "❌ 失败"
            logger.info(f"{task}: {status}")
        
        return all(results.values())


# ==================== 便捷函数 ====================

def run_v3_migrations(database_url: str = None):
    """
    便捷函数：运行V3数据库迁移
    
    使用示例:
        from v3_schema_extensions import run_v3_migrations
        run_v3_migrations("mysql://user:pass@localhost/ai_tutor")
    """
    if database_url is None:
        # 从配置文件读取
        import sys
        sys.path.append('D:\\Project\\AI Tutor\\backend')
        from utils.config import settings
        database_url = settings.database_url
    
    migrator = V3SchemaExtensions(database_url)
    return migrator.run_all_migrations()


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("V3 数据库表扩展迁移")
    print("=" * 60)
    
    # 这里使用测试数据库URL，实际使用时从配置文件读取
    test_url = "mysql+pymysql://root:password@localhost/ai_tutor_test"
    
    migrator = V3SchemaExtensions(test_url)
    success = migrator.run_all_migrations()
    
    if success:
        print("\n✅ 所有迁移执行成功")
    else:
        print("\n❌ 部分迁移执行失败，请检查日志")
