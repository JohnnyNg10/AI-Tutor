from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


from algorithms.bkt import BKTParams
from models.chat import KnowledgePoint, UserKnowledgeMastery
from models.learning_analytics import Favorite, MistakeBook, UserAbilityHistory
from models.profile import UserProfile
from models.question import Question
from services.profile_service import update_user_profile


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _compute_next_review_time(error_count: int, now: Optional[datetime] = None) -> datetime:
    """
    复习提醒时间（指数退避）
    T_n = T_{n-1} * 2, 从 1 天起步
    """
    now = now or datetime.now()
    days = 2 ** max(0, error_count - 1)
    return now + timedelta(days=days)


def estimate_theta(
    total_questions: int,
    correct_count: int,
    avg_mastery: float,
) -> Dict[str, float]:
    """
    基于 docs/list.md 的 K-IRT 联合估算思想：
    theta_final = α * theta_irt + (1-α) * theta_bkt
    """
    accuracy = (correct_count / total_questions) if total_questions > 0 else 0.5

    # 将能力值映射到 [1, 5] 区间，便于与题目难度对齐
    theta_irt = 1.0 + 4.0 * _clamp(accuracy, 0.0, 1.0)
    theta_bkt = 1.0 + 4.0 * _clamp(avg_mastery, 0.0, 1.0)

    alpha = 0.8 if total_questions > 10 else 0.3
    theta_final = alpha * theta_irt + (1.0 - alpha) * theta_bkt

    # 简化标准误（样本越多标准误越小）
    theta_se = max(0.05, 1.0 / ((total_questions + 1) ** 0.5))
    ci_margin = 1.96 * theta_se

    return {
        "theta": round(theta_final, 4),
        "theta_se": round(theta_se, 4),
        "theta_ci_lower": round(theta_final - ci_margin, 4),
        "theta_ci_upper": round(theta_final + ci_margin, 4),
    }


async def _upsert_bkt_mastery(
    db: AsyncSession,
    user_id: int,
    question: Question,
    is_correct: bool,
) -> Dict[str, float]:
    topics = question.knowledge_points or []
    if not topics:
        return {}

    if isinstance(topics, str):
        topics = [topics]

    topic_names = [str(t).strip() for t in topics if str(t).strip()]
    if not topic_names:
        return {}

    # 名称 -> 知识点 ID
    kp_stmt = select(KnowledgePoint).where(KnowledgePoint.name.in_(topic_names))
    kp_result = await db.execute(kp_stmt)
    kp_rows = kp_result.scalars().all()
    kp_by_name = {kp.name: kp for kp in kp_rows}

    mastery_updates: Dict[str, float] = {}

    for topic_name in topic_names:
        kp = kp_by_name.get(topic_name)
        if not kp:
            # 知识点表无此记录 → 自动创建，确保 BKT 写入不丢失
            kp = KnowledgePoint(
                name=topic_name,
                description="",
                parent_id=None,
                level=1,
            )
            db.add(kp)
            await db.flush()
            kp_by_name[topic_name] = kp

        ukm_stmt = select(UserKnowledgeMastery).where(
            and_(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.knowledge_point_id == kp.id,
            )
        )
        ukm_result = await db.execute(ukm_stmt)
        ukm = ukm_result.scalar_one_or_none()

        if not ukm:
            ukm = UserKnowledgeMastery(
                user_id=user_id,
                knowledge_point_id=kp.id,
                mastery_level=50,
                practice_count=0,
                correct_count=0,
                p_guess=0.2,
                p_slip=0.1,
                p_known=0.5,
                consecutive_correct=0,
                consecutive_wrong=0,
            )
            db.add(ukm)

        prior = _clamp(float(ukm.p_known or 0.5), 0.001, 0.999)
        p_guess = _clamp(float(ukm.p_guess or 0.2), 0.001, 0.49)
        p_slip = _clamp(float(ukm.p_slip or 0.1), 0.001, 0.49)

        if is_correct:
            numerator = prior * (1 - p_slip)
            denominator = numerator + (1 - prior) * p_guess
        else:
            numerator = prior * p_slip
            denominator = numerator + (1 - prior) * (1 - p_guess)

        posterior = numerator / denominator if denominator > 0 else prior
        p_transit = BKTParams().p_learn
        new_p_known = posterior + (1 - posterior) * p_transit
        new_p_known = _clamp(new_p_known, 0.0, 1.0)

        ukm.p_known = round(new_p_known, 4)
        ukm.mastery_level = int(round(new_p_known * 100))
        ukm.practice_count = int(ukm.practice_count or 0) + 1
        ukm.correct_count = int(ukm.correct_count or 0) + (1 if is_correct else 0)
        ukm.last_practiced_at = datetime.now()

        if is_correct:
            ukm.consecutive_correct = int(ukm.consecutive_correct or 0) + 1
            ukm.consecutive_wrong = 0
        else:
            ukm.consecutive_wrong = int(ukm.consecutive_wrong or 0) + 1
            ukm.consecutive_correct = 0

        mastery_updates[topic_name] = round(new_p_known, 4)

    return mastery_updates


async def upsert_mistake_book(
    db: AsyncSession,
    user_id: int,
    question_id: int,
    is_correct: bool,
) -> Optional[MistakeBook]:
    stmt = select(MistakeBook).where(
        and_(MistakeBook.user_id == user_id, MistakeBook.question_id == question_id)
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()

    now = datetime.now()

    if not is_correct:
        if not item:
            item = MistakeBook(
                user_id=user_id,
                question_id=question_id,
                error_count=1,
                first_error_at=now,
                last_error_at=now,
                next_review_at=_compute_next_review_time(1, now),
            )
            db.add(item)
        else:
            item.error_count = int(item.error_count or 0) + 1
            item.last_error_at = now
            item.mastered = False
            item.mastered_at = None
            item.next_review_at = _compute_next_review_time(item.error_count, now)

        return item

    # 做对时，若存在错题记录则标记为已掌握并记录复习行为
    if item:
        item.review_count = int(item.review_count or 0) + 1
        item.last_review_at = now
        if item.error_count > 0:
            item.mastered = True
            item.mastered_at = now
    return item


async def update_profile_and_ability(
    db: AsyncSession,
    user_id: int,
    question: Question,
    is_correct: bool,
) -> Dict[str, float]:
    profile = await update_user_profile(db=db, user_id=user_id, question=question, is_correct=is_correct)

    mastery_map = profile.knowledge_mastery or {}
    avg_mastery = 0.5
    if isinstance(mastery_map, dict) and mastery_map:
        avg_mastery = sum(float(v) for v in mastery_map.values()) / len(mastery_map)

    weak_kp_count = 0
    if isinstance(mastery_map, dict):
        weak_kp_count = sum(1 for v in mastery_map.values() if float(v) < 0.4)

    theta_data = estimate_theta(
        total_questions=int(profile.total_questions or 0),
        correct_count=int(profile.correct_count or 0),
        avg_mastery=float(avg_mastery),
    )

    profile.avg_mastery = round(avg_mastery, 4)
    profile.weak_kp_count = weak_kp_count
    profile.theta_se = theta_data["theta_se"]
    profile.theta_ci_lower = theta_data["theta_ci_lower"]
    profile.theta_ci_upper = theta_data["theta_ci_upper"]

    history = UserAbilityHistory(
        user_id=user_id,
        theta=theta_data["theta"],
        theta_se=theta_data["theta_se"],
        theta_ci_lower=theta_data["theta_ci_lower"],
        theta_ci_upper=theta_data["theta_ci_upper"],
        avg_mastery=round(avg_mastery, 4),
        weak_kp_count=weak_kp_count,
        total_questions=int(profile.total_questions or 0),
        correct_count=int(profile.correct_count or 0),
    )
    db.add(history)

    await db.flush()

    return {
        **theta_data,
        "avg_mastery": round(avg_mastery, 4),
        "weak_kp_count": weak_kp_count,
    }


async def process_answer_analytics(
    db: AsyncSession,
    user_id: int,
    question: Question,
    is_correct: bool,
) -> Dict[str, object]:
    """
    统一处理答题后的 V3 分析动作：
    - 画像更新 + 能力曲线写入
    - 错题本自动收录/复习更新
    - BKT 掌握度更新
    """
    theta_data = await update_profile_and_ability(
        db=db,
        user_id=user_id,
        question=question,
        is_correct=is_correct,
    )

    mistake_item = await upsert_mistake_book(
        db=db,
        user_id=user_id,
        question_id=question.id,
        is_correct=is_correct,
    )

    mastery_updates = await _upsert_bkt_mastery(
        db=db,
        user_id=user_id,
        question=question,
        is_correct=is_correct,
    )

    await db.commit()

    return {
        "theta_data": theta_data,
        "mastery_updates": mastery_updates,
        "mistake_book_id": mistake_item.id if mistake_item else None,
    }


async def create_or_update_favorite(
    db: AsyncSession,
    user_id: int,
    question_id: int,
    folder_name: str = "默认收藏夹",
    note: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Favorite:
    stmt = select(Favorite).where(
        and_(Favorite.user_id == user_id, Favorite.question_id == question_id)
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()

    if not item:
        item = Favorite(
            user_id=user_id,
            question_id=question_id,
            folder_name=folder_name or "默认收藏夹",
            note=note,
            tags=tags or [],
        )
        db.add(item)
    else:
        item.folder_name = folder_name or item.folder_name
        item.note = note
        item.tags = tags or []

    await db.commit()
    await db.refresh(item)
    return item


async def list_favorites(
    db: AsyncSession,
    user_id: int,
    folder_name: Optional[str] = None,
    limit: int = 50,
) -> Sequence[Favorite]:
    stmt = select(Favorite).options(joinedload(Favorite.question)).where(Favorite.user_id == user_id)

    if folder_name:
        stmt = stmt.where(Favorite.folder_name == folder_name)

    stmt = stmt.order_by(Favorite.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def remove_favorite(db: AsyncSession, user_id: int, favorite_id: int) -> bool:
    stmt = select(Favorite).where(and_(Favorite.id == favorite_id, Favorite.user_id == user_id))
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        return False

    await db.delete(item)
    await db.commit()
    return True


async def list_mistake_book(
    db: AsyncSession,
    user_id: int,
    mastered: Optional[bool] = None,
    only_due: bool = False,
    knowledge_point: Optional[str] = None,
    days: Optional[int] = None,
    limit: int = 100,
) -> Sequence[MistakeBook]:
    stmt = select(MistakeBook).where(MistakeBook.user_id == user_id)

    if mastered is not None:
        stmt = stmt.where(MistakeBook.mastered == mastered)

    now = datetime.now()
    if only_due:
        stmt = stmt.where(and_(MistakeBook.next_review_at.is_not(None), MistakeBook.next_review_at <= now))

    if days and days > 0:
        stmt = stmt.where(MistakeBook.created_at >= now - timedelta(days=days))

    stmt = stmt.order_by(MistakeBook.updated_at.desc()).limit(limit)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    if not knowledge_point:
        return rows

    # 按知识点筛选（通过 question.knowledge_points）
    filtered: List[MistakeBook] = []
    for item in rows:
        if not item.question:
            continue
        kps = item.question.knowledge_points or []
        if isinstance(kps, list) and knowledge_point in kps:
            filtered.append(item)
    return filtered


async def list_review_reminders(
    db: AsyncSession,
    user_id: int,
    window_days: int = 3,
) -> Dict[str, List[MistakeBook]]:
    now = datetime.now()
    until = now + timedelta(days=window_days)

    due_stmt = select(MistakeBook).options(joinedload(MistakeBook.question)).where(

        and_(
            MistakeBook.user_id == user_id,
            MistakeBook.mastered == False,
            MistakeBook.next_review_at.is_not(None),
            MistakeBook.next_review_at <= now,
        )
    ).order_by(MistakeBook.next_review_at.asc())

    upcoming_stmt = select(MistakeBook).options(joinedload(MistakeBook.question)).where(

        and_(
            MistakeBook.user_id == user_id,
            MistakeBook.mastered == False,
            MistakeBook.next_review_at.is_not(None),
            MistakeBook.next_review_at > now,
            MistakeBook.next_review_at <= until,
        )
    ).order_by(MistakeBook.next_review_at.asc())

    due_result = await db.execute(due_stmt)
    upcoming_result = await db.execute(upcoming_stmt)

    return {
        "due": list(due_result.scalars().all()),
        "upcoming": list(upcoming_result.scalars().all()),
    }


async def get_mastery_dashboard(db: AsyncSession, user_id: int, trend_limit: int = 30) -> Dict[str, object]:
    profile_stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    mastery_map = (profile.knowledge_mastery or {}) if profile else {}
    if not isinstance(mastery_map, dict):
        mastery_map = {}

    # 维度颜色：来自 docs/list.md 建议阈值
    # 绿色 >= 0.8, 黄色 [0.4, 0.8), 红色 < 0.4
    def color_for(score: float) -> str:
        if score >= 0.8:
            return "green"
        if score >= 0.4:
            return "yellow"
        return "red"

    radar_dimensions = [
        {
            "knowledge_point": kp,
            "mastery": round(float(score), 4),
            "color": color_for(float(score)),
        }
        for kp, score in sorted(mastery_map.items(), key=lambda x: x[1], reverse=True)[:6]
    ]

    history_stmt = (
        select(UserAbilityHistory)
        .where(UserAbilityHistory.user_id == user_id)
        .order_by(UserAbilityHistory.recorded_at.desc())
        .limit(trend_limit)
    )
    history_result = await db.execute(history_stmt)
    history_rows = list(history_result.scalars().all())
    history_rows.reverse()

    ability_curve = [
        {
            "time": h.recorded_at.isoformat() if h.recorded_at else None,
            "theta": h.theta,
            "theta_ci_lower": h.theta_ci_lower,
            "theta_ci_upper": h.theta_ci_upper,
            "avg_mastery": h.avg_mastery,
        }
        for h in history_rows
    ]

    mistake_distribution_stmt = (
        select(MistakeBook)
        .options(joinedload(MistakeBook.question))
        .where(MistakeBook.user_id == user_id)
    )

    mistake_distribution_result = await db.execute(mistake_distribution_stmt)
    mistakes = mistake_distribution_result.scalars().all()

    distribution: Dict[str, int] = {}
    for m in mistakes:
        if not m.question:
            continue
        topics = m.question.knowledge_points or []
        if not isinstance(topics, list):
            continue
        for t in topics:
            key = str(t)
            distribution[key] = distribution.get(key, 0) + int(m.error_count or 0)

    return {
        "user_id": user_id,
        "radar_dimensions": radar_dimensions,
        "knowledge_tree_nodes": [
            {
                "knowledge_point": kp,
                "mastery": round(float(score), 4),
                "color": color_for(float(score)),
            }
            for kp, score in mastery_map.items()
        ],
        "ability_curve": ability_curve,
        "mistake_distribution": distribution,
    }
