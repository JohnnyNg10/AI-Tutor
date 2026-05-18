"""AI批改模块数据模型"""
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database.db import Base


class GradingSession(Base):
    """批改会话"""
    __tablename__ = "grading_sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), default="未命名批改")
    question_count = Column(Integer, default=0)
    avg_score = Column(Float, default=0.0)
    total_time_spent = Column(Integer, default=0)
    status = Column(String(20), default="uploading")  # uploading/reviewing/grading/done/cancelled
    error_distribution = Column(JSON, nullable=True)
    weakest_kps = Column(JSON, nullable=True)
    strongest_kps = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    questions = relationship("GradingQuestion", back_populates="session", order_by="GradingQuestion.question_index")


class GradingQuestion(Base):
    """批改题目明细"""
    __tablename__ = "grading_questions"

    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("grading_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_index = Column(Integer, default=0)
    question_text = Column(Text, nullable=True)
    student_answer = Column(Text, nullable=True)
    ocr_raw_text = Column(Text, nullable=True)
    ocr_corrections = Column(JSON, nullable=True)
    grading_result = Column(JSON, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    score = Column(Float, default=0.0)
    error_type = Column(String(50), nullable=True)
    error_tags = Column(JSON, nullable=True)
    knowledge_points = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("GradingSession", back_populates="questions")
