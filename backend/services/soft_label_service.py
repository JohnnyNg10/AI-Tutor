"""
六维 Soft Label 软标签评分引擎

基于用户交互埋点数据，每日计算六维软标签：
- 自主性 (Independence)：独立解题能力
- 坚持性 (Persistence)：面对困难的坚持程度
- 元认知 (Metacognition)：对自己知识水平的判断准确度
- 求助效率 (Help-seeking)：提示系统使用策略
- 反思深度 (Reflection)：对解题过程的反思程度
- 知识迁移 (Transfer)：将知识应用到新情境的能力

每个维度输出 0-100 连续分值。
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from utils.logger import logger

# 滑动窗口大小
WINDOW_RECENT_QUESTIONS = 20
WINDOW_RECENT_HINTS = 20
WINDOW_TRANSFER_QUESTIONS = 30
WINDOW_REFLECTION_DAYS = 7


class SoftLabelEngine:
    """六维软标签计算引擎"""

    async def compute_all(self, db: AsyncSession, user_id: int) -> Dict[str, float]:
        """计算用户全部六维软标签，返回 {dimension: score}"""
        scores = {
            "independence": await self._compute_independence(db, user_id),
            "persistence": await self._compute_persistence(db, user_id),
            "metacognition": await self._compute_metacognition(db, user_id),
            "helpseeking": await self._compute_helpseeking(db, user_id),
            "reflection": await self._compute_reflection(db, user_id),
            "transfer": await self._compute_transfer(db, user_id),
        }
        scores["composite"] = round(sum(scores.values()) / 6, 2)
        return scores

    # ── 自主性指数 ────────────────────────────────────────
    async def _compute_independence(self, db: AsyncSession, user_id: int) -> float:
        """基于最近 N 题的求助行为计算自主性"""
        rows = await self._query_events(db, user_id,
            ["hint_request", "answer_submit", "solution_view", "question_complete"],
            WINDOW_RECENT_QUESTIONS * 3)

        if not rows:
            return 50.0

        score = 50.0
        hint_requests = [r for r in rows if r.event_name == "hint_request"]
        answer_submits = [r for r in rows if r.event_name == "answer_submit"]

        # 提示层级惩罚
        for h in hint_requests:
            data = h.interaction_metadata or {}
            level = data.get("hint_level", 0)
            weights = {0: 20, 1: 10, 2: -5, 3: -15, 4: -25}
            score += weights.get(level, 0)

        # 直接看答案（未尝试即看方案）
        for r in rows:
            if r.event_name == "solution_view":
                data = r.interaction_metadata or {}
                if data.get("trigger") == "after_giveup":
                    score -= 30

        # 答对且未求助的题目占比加分
        if answer_submits:
            correct_no_hint = sum(
                1 for a in answer_submits
                if a.interaction_metadata
                and a.interaction_metadata.get("is_correct")
                and not any(
                    h.interaction_metadata
                    and h.interaction_metadata.get("q_id") == a.interaction_metadata.get("q_id")
                    for h in hint_requests
                )
            )
            ratio = correct_no_hint / len(answer_submits)
            score += int(ratio * 25)

        return max(0.0, min(100.0, score))

    # ── 坚持性指数 ────────────────────────────────────────
    async def _compute_persistence(self, db: AsyncSession, user_id: int) -> float:
        """基于答错后行为和跳过模式计算坚持性"""
        rows = await self._query_events(db, user_id,
            ["answer_retry", "question_skip", "answer_submit", "question_complete"],
            WINDOW_RECENT_QUESTIONS * 3)

        if not rows:
            return 50.0

        score = 50.0
        retries = [r for r in rows if r.event_name == "answer_retry"]
        skips = [r for r in rows if r.event_name == "question_skip"]

        # 答错后重试加分（每次 +10，上限 3 次）
        for r in retries:
            data = r.interaction_metadata or {}
            retry_idx = data.get("retry_index", 0)
            if retry_idx <= 3:
                score += 10

        # 跳过惩罚
        for s in skips:
            data = s.interaction_metadata or {}
            attempts = data.get("attempts_before_skip", 0)
            if attempts == 0:
                score -= 20
            elif attempts == 1:
                score -= 10
            elif attempts >= 3:
                score += 10

        # 困难题完成率（difficulty >= 4 的题目是否完成）
        completes = [r for r in rows if r.event_name == "question_complete"]
        hard_completes = [
            c for c in completes
            if c.interaction_metadata
            and c.interaction_metadata.get("difficulty", 0) >= 4
            and c.interaction_metadata.get("exit_reason") != "gave_up"
        ]
        if hard_completes:
            score += len(hard_completes) * 5

        return max(0.0, min(100.0, score))

    # ── 元认知校准度 ──────────────────────────────────────
    async def _compute_metacognition(self, db: AsyncSession, user_id: int) -> float:
        """基于自评 vs 实际的偏差计算元认知校准度"""
        rows = await self._query_events(db, user_id,
            ["knowledge_node_click", "answer_submit", "review_schedule_action"],
            WINDOW_RECENT_QUESTIONS * 4)

        if not rows:
            return 50.0

        score = 50.0

        # 知识树节点点击 vs 实际答题表现
        node_clicks = [r for r in rows if r.event_name == "knowledge_node_click"]
        submits = [r for r in rows if r.event_name == "answer_submit"]

        for nc in node_clicks:
            ndata = nc.interaction_metadata or {}
            clicked_status = ndata.get("node_status", "")
            kp_name = ndata.get("kp_name", "")

            if clicked_status == "mastered":
                # 检查该知识点是否真的有答题且答错
                for s in submits:
                    sdata = s.interaction_metadata or {}
                    if kp_name and kp_name in str(sdata.get("kp_list", [])):
                        if not sdata.get("is_correct"):
                            score -= 15

        # 跳题原因与实际难度的匹配度
        skips = [r for r in rows if r.event_name == "question_skip"]
        for s in skips:
            data = s.interaction_metadata or {}
            if data.get("skip_reason") == "too_hard" and data.get("difficulty", 3) < 3:
                score -= 10

        return max(0.0, min(100.0, score))

    # ── 求助策略效率 ──────────────────────────────────────
    async def _compute_helpseeking(self, db: AsyncSession, user_id: int) -> float:
        """基于提示递进模式和提示转化率计算求助效率"""
        rows = await self._query_events(db, user_id,
            ["hint_request", "hint_dismiss", "hint_chain", "answer_submit"],
            WINDOW_RECENT_HINTS * 3)

        if not rows:
            return 50.0

        score = 50.0
        hint_requests = [r for r in rows if r.event_name == "hint_request"]
        hint_dismisses = [r for r in rows if r.event_name == "hint_dismiss"]

        # 提示递进模式评分
        chains = [r for r in rows if r.event_name == "hint_chain"]
        for c in chains:
            data = c.interaction_metadata or {}
            chain = data.get("chain", [])
            if len(chain) >= 2:
                levels = [step.get("level") for step in chain if "level" in step]
                # 渐进式 (L0→L1→L2) 加分
                if levels == sorted(levels) and max(levels) - min(levels) <= 2:
                    score += 15
                # 跳跃式 (L0→L4) 减分
                elif len(levels) >= 2 and max(levels) - min(levels) >= 3:
                    score -= 10

        # 提示消化度：查看提示后是否完整阅读
        for d in hint_dismisses:
            data = d.interaction_metadata or {}
            scroll_pct = data.get("scroll_depth_pct", 0)
            if scroll_pct >= 70:
                score += 5
            elif scroll_pct < 30:
                score -= 5

        # 提示转化率：查看提示后答对的概率
        if hint_requests:
            submits = [r for r in rows if r.event_name == "answer_submit"]
            hint_q_ids = {
                h.interaction_metadata.get("q_id")
                for h in hint_requests
                if h.interaction_metadata
            }
            correct_after_hint = sum(
                1 for s in submits
                if s.interaction_metadata
                and s.interaction_metadata.get("q_id") in hint_q_ids
                and s.interaction_metadata.get("is_correct")
            )
            if hint_q_ids:
                conversion_rate = correct_after_hint / len(hint_q_ids)
                score += int((conversion_rate - 0.5) * 30)

        return max(0.0, min(100.0, score))

    # ── 反思深度 ──────────────────────────────────────────
    async def _compute_reflection(self, db: AsyncSession, user_id: int) -> float:
        """基于方案页行为和错题复习计算反思深度"""
        cutoff = datetime.now() - timedelta(days=WINDOW_REFLECTION_DAYS)
        rows = await self._query_events_since(db, user_id,
            ["solution_view", "solution_engage", "answer_submit"],
            cutoff)

        if not rows:
            return 50.0

        score = 50.0

        # 方案页滚动深度
        engages = [r for r in rows if r.event_name == "solution_engage"]
        for e in engages:
            data = e.interaction_metadata or {}
            scroll_pct = data.get("scroll_depth_pct", 0)
            if scroll_pct > 70:
                score += 10
            elif scroll_pct < 30:
                score -= 10

        # 方案页停留时长
        for e in engages:
            data = e.interaction_metadata or {}
            duration_ms = data.get("total_duration_ms", 0)
            if duration_ms > 60000:
                score += 5

        # 答对后仍查看方案
        solution_views = {s.interaction_metadata.get("q_id") for s in rows
                          if s.event_name == "solution_view" and s.interaction_metadata}
        submits = [r for r in rows if r.event_name == "answer_submit"]
        correct_with_review = sum(
            1 for s in submits
            if s.interaction_metadata
            and s.interaction_metadata.get("is_correct")
            and s.interaction_metadata.get("q_id") in solution_views
        )
        if correct_with_review:
            score += correct_with_review * 5

        return max(0.0, min(100.0, score))

    # ── 知识迁移能力 ──────────────────────────────────────
    async def _compute_transfer(self, db: AsyncSession, user_id: int) -> float:
        """基于跨知识点题目表现计算知识迁移能力"""
        rows = await self._query_events(db, user_id,
            ["answer_submit"],
            WINDOW_TRANSFER_QUESTIONS)

        if not rows:
            return 50.0

        score = 50.0
        cross_kp_submits = []
        single_kp_submits = []

        for r in rows:
            data = r.interaction_metadata or {}
            kp_list = data.get("kp_list", [])
            if isinstance(kp_list, list) and len(kp_list) >= 2:
                cross_kp_submits.append(r)
            else:
                single_kp_submits.append(r)

        # 跨知识点正确率 vs 单知识点正确率
        if cross_kp_submits:
            cross_correct = sum(
                1 for s in cross_kp_submits
                if s.interaction_metadata and s.interaction_metadata.get("is_correct")
            )
            cross_rate = cross_correct / len(cross_kp_submits)

            if single_kp_submits:
                single_correct = sum(
                    1 for s in single_kp_submits
                    if s.interaction_metadata and s.interaction_metadata.get("is_correct")
                )
                single_rate = single_correct / len(single_kp_submits)

                # 跨知识点 vs 单知识点的差距
                delta = single_rate - cross_rate
                score -= int(delta * 50)

            # 跨知识点题目数量加分（敢于挑战综合题）
            score += min(len(cross_kp_submits) * 2, 20)

        return max(0.0, min(100.0, score))

    # ── 数据查询辅助 ──────────────────────────────────────
    async def _query_events(self, db: AsyncSession, user_id: int,
                            event_names: list, limit: int) -> list:
        """查询指定事件类型的最近 N 条记录"""
        sql = text("""
            SELECT * FROM user_interaction_logs
            WHERE user_id = :uid
              AND event_name IN :names
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        result = await db.execute(sql, {
            "uid": user_id,
            "names": tuple(event_names),
            "limit": limit,
        })
        return result.fetchall()

    async def _query_events_since(self, db: AsyncSession, user_id: int,
                                  event_names: list, since: datetime) -> list:
        """查询指定时间范围内的记录"""
        sql = text("""
            SELECT * FROM user_interaction_logs
            WHERE user_id = :uid
              AND event_name IN :names
              AND created_at >= :since
            ORDER BY created_at DESC
        """)
        result = await db.execute(sql, {
            "uid": user_id,
            "names": tuple(event_names),
            "since": since,
        })
        return result.fetchall()

    async def save_labels(self, db: AsyncSession, user_id: int,
                          scores: Dict[str, float], sample_size: int) -> None:
        """写入或更新 user_soft_labels"""
        sql = text("""
            INSERT INTO user_soft_labels
                (user_id, independence_score, persistence_score,
                 metacognition_score, helpseeking_score,
                 reflection_score, transfer_score, composite_score,
                 sample_size, calculated_at)
            VALUES
                (:uid, :ind, :per, :met, :hlp, :ref, :trn, :cmp, :n, NOW())
            ON DUPLICATE KEY UPDATE
                independence_score = VALUES(independence_score),
                persistence_score = VALUES(persistence_score),
                metacognition_score = VALUES(metacognition_score),
                helpseeking_score = VALUES(helpseeking_score),
                reflection_score = VALUES(reflection_score),
                transfer_score = VALUES(transfer_score),
                composite_score = VALUES(composite_score),
                sample_size = VALUES(sample_size),
                calculated_at = NOW(),
                updated_at = NOW()
        """)
        await db.execute(sql, {
            "uid": user_id,
            "ind": scores["independence"],
            "per": scores["persistence"],
            "met": scores["metacognition"],
            "hlp": scores["helpseeking"],
            "ref": scores["reflection"],
            "trn": scores["transfer"],
            "cmp": scores["composite"],
            "n": sample_size,
        })
        await db.commit()


# 全局实例
soft_label_engine = SoftLabelEngine()


async def compute_soft_labels_for_user(db: AsyncSession, user_id: int) -> Dict[str, float]:
    """便捷函数：计算并保存用户软标签"""
    scores = await soft_label_engine.compute_all(db, user_id)
    await soft_label_engine.save_labels(db, user_id, scores, sample_size=1)
    logger.info(f"Soft labels computed for user {user_id}: composite={scores['composite']}")
    return scores
