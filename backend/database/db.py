from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from utils.config import settings
from utils.logger import logger

Base = declarative_base()

async_engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            await session.close()


async def _column_exists(conn, table_name: str, column_name: str) -> bool:
    # Check if using SQLite
    if "sqlite" in settings.database_url.lower():
        # SQLite: use PRAGMA table_info
        query = text(f"PRAGMA table_info({table_name})")
        result = await conn.execute(query)
        rows = result.fetchall()
        # rows: [(cid, name, type, notnull, dflt_value, pk), ...]
        return any(row[1] == column_name for row in rows)
    else:
        # MySQL: use INFORMATION_SCHEMA
        query = text(
            """
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table_name
              AND COLUMN_NAME = :column_name
            LIMIT 1
            """
        )
        result = await conn.execute(query, {"table_name": table_name, "column_name": column_name})
        return result.first() is not None


async def _ensure_v3_schema(conn):
    table_columns = {
        "learning_records": [
            ("source_type", "ALTER TABLE learning_records ADD COLUMN source_type VARCHAR(50) NOT NULL DEFAULT 'recommended'"),
            ("custom_question_data", "ALTER TABLE learning_records ADD COLUMN custom_question_data JSON NULL"),
            ("ai_feedback", "ALTER TABLE learning_records ADD COLUMN ai_feedback TEXT NULL"),
            ("recommendation_session_id", "ALTER TABLE learning_records ADD COLUMN recommendation_session_id VARCHAR(100) NULL"),
            ("recommendation_algorithm_version", "ALTER TABLE learning_records ADD COLUMN recommendation_algorithm_version VARCHAR(50) NULL"),
            ("hint_count", "ALTER TABLE learning_records ADD COLUMN hint_count INT DEFAULT 0"),
            ("time_spent", "ALTER TABLE learning_records ADD COLUMN time_spent INT NULL"),
            ("skip_reason", "ALTER TABLE learning_records ADD COLUMN skip_reason VARCHAR(20) NULL"),
            ("theta_before", "ALTER TABLE learning_records ADD COLUMN theta_before FLOAT NULL"),
            ("theta_after", "ALTER TABLE learning_records ADD COLUMN theta_after FLOAT NULL"),
            ("mastery_updates", "ALTER TABLE learning_records ADD COLUMN mastery_updates JSON NULL"),
        ],
        "user_profiles": [
            ("theta_se", "ALTER TABLE user_profiles ADD COLUMN theta_se FLOAT NULL"),
            ("theta_ci_lower", "ALTER TABLE user_profiles ADD COLUMN theta_ci_lower FLOAT NULL"),
            ("theta_ci_upper", "ALTER TABLE user_profiles ADD COLUMN theta_ci_upper FLOAT NULL"),
            ("avg_mastery", "ALTER TABLE user_profiles ADD COLUMN avg_mastery FLOAT NULL"),
            ("weak_kp_count", "ALTER TABLE user_profiles ADD COLUMN weak_kp_count INT DEFAULT 0"),
            ("learning_style", "ALTER TABLE user_profiles ADD COLUMN learning_style VARCHAR(20) NULL"),
            ("mastery_strategy", "ALTER TABLE user_profiles ADD COLUMN mastery_strategy VARCHAR(20) DEFAULT 'simple'"),
        ],
        "user_knowledge_mastery": [
            ("p_guess", "ALTER TABLE user_knowledge_mastery ADD COLUMN p_guess FLOAT DEFAULT 0.2"),
            ("p_slip", "ALTER TABLE user_knowledge_mastery ADD COLUMN p_slip FLOAT DEFAULT 0.1"),
            ("p_known", "ALTER TABLE user_knowledge_mastery ADD COLUMN p_known FLOAT DEFAULT 0.5"),
            ("consecutive_correct", "ALTER TABLE user_knowledge_mastery ADD COLUMN consecutive_correct INT DEFAULT 0"),
            ("consecutive_wrong", "ALTER TABLE user_knowledge_mastery ADD COLUMN consecutive_wrong INT DEFAULT 0"),
        ],
    }

    for table_name, columns in table_columns.items():
        for column_name, ddl in columns:
            if not await _column_exists(conn, table_name, column_name):
                await conn.execute(text(ddl))
                logger.info(f"Added column {table_name}.{column_name}")


async def init_db():
    from models.user import User
    from models.question import Question
    from models.record import LearningRecord
    from models.profile import UserProfile
    from models.chat import (
        ChatSession, ChatMessage, SolutionStep,
        KnowledgePoint, QuestionKnowledgePoint, UserKnowledgeMastery
    )
    from models.learning_analytics import (
        UserAbilityHistory,
        MistakeBook,
        Favorite,
        UserInteractionLog,
    )

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_v3_schema(conn)
        logger.info("Database tables created/updated successfully")