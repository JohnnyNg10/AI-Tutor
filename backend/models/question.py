from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database.db import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 1. 题目内容
    content = Column(Text, nullable=False, comment="题目题干内容")

    # 2. 答案 (改名为 standard_answer 以区分用户答案)
    standard_answer = Column(Text, nullable=True, comment="标准答案")

    # 3. 难度 (建议统一范围，比如 1-5 或 1.0-5.0)
    difficulty = Column(Integer, default=1, comment="难度等级: 1-简单, 2-中等, 3-困难")

    # 4. 知识点 (保持复数，因为一道题通常有多个知识点)
    # 建议统一存储格式：始终是 List[str] 或 List[int]
    # 例如：["一元二次方程", "配方法"] 或 [101, 102]
    knowledge_points = Column(JSON, nullable=True, default=list, comment="知识点列表")

    # 5. 题型 (改为 question_type，统一用 question 前缀)
    # 例如："single_choice", "multiple_choice", "fill_blank"
    question_type = Column(String(50), nullable=True, comment="题型")

    # 6. 题目来源 (新增)
    # system: 系统题库（开发时导入的正式题目）
    # user_uploaded: 用户上传的题目
    source = Column(String(20), default="user_uploaded", comment="题目来源: system(系统题库), user_uploaded(用户上传)")

    # 7. 是否有效 (新增，用于软删除和审核)
    # 审核不通过的题目标记为 False，不推荐给用户
    is_active = Column(Boolean, default=True, comment="是否有效: 用于审核不通过的题目")

    # 8. 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user = relationship("User", lazy="joined")
    learning_records = relationship("LearningRecord", back_populates="question", lazy="selectin")
