import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from jose import jwt

from database.db import get_db
from utils.config import settings
from utils.logger import logger

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

MAX_BATCH_SIZE = 100


def _extract_user_id(request: Request) -> Optional[int]:
    """尝试从 Authorization header 提取 user_id，失败返回 None（支持匿名事件）"""
    try:
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            return payload.get("user_id")
    except Exception:
        pass
    return None


@router.post("/events")
async def ingest_events(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """批量接收前端埋点事件

    接收前端 trackEvent() 上报的批量事件，写入 user_interaction_logs 表。
    支持匿名事件（无 token 时 user_id 为 NULL）。
    """
    body = await request.json()
    events: List[dict] = body.get("events", [])

    if not events:
        return {"received": 0}

    if len(events) > MAX_BATCH_SIZE:
        events = events[:MAX_BATCH_SIZE]

    user_id = _extract_user_id(request)

    rows_inserted = 0
    for ev in events:
        try:
            data = ev.get("data", {}) or {}
            event_name = ev.get("event_name", "")
            session_id = ev.get("session_id")
            timestamp_str = ev.get("timestamp")

            # 解析时间戳
            created_at = datetime.now()
            if timestamp_str:
                try:
                    created_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            # 提取知识点、题目ID等字段
            question_id = data.get("q_id") or data.get("question_id")
            knowledge_points = data.get("kp_list")
            difficulty = data.get("difficulty")

            # cognitive_signal：提取行为中反映认知特征的关键字段
            cognitive_signal = _extract_cognitive_signal(event_name, data)

            sql = text("""
                INSERT INTO user_interaction_logs
                    (user_id, session_id, interaction_type, question_id,
                     knowledge_points, difficulty, content,
                     metadata, event_name, cognitive_signal, created_at)
                VALUES
                    (:user_id, :session_id, :interaction_type, :question_id,
                     :knowledge_points, :difficulty, :content,
                     :metadata, :event_name, :cognitive_signal, :created_at)
            """)

            await db.execute(sql, {
                "user_id": user_id,
                "session_id": session_id,
                "interaction_type": event_name,
                "question_id": question_id,
                "knowledge_points": json.dumps(knowledge_points) if knowledge_points else None,
                "difficulty": difficulty,
                "content": data.get("answer_text") or data.get("skip_reason"),
                "metadata": json.dumps(data, ensure_ascii=False, default=str) if data else None,
                "event_name": event_name,
                "cognitive_signal": json.dumps(cognitive_signal, ensure_ascii=False) if cognitive_signal else None,
                "created_at": created_at,
            })
            rows_inserted += 1
        except Exception as e:
            logger.warning(f"Analytics event insert failed: {e}")

    await db.commit()

    return {"received": len(events), "inserted": rows_inserted}


def _extract_cognitive_signal(event_name: str, data: dict) -> Optional[dict]:
    """从事件数据中提取认知行为信号"""
    signal = {}

    # 求助行为 → 自主性信号
    if event_name == "hint_request":
        signal["dimension"] = "independence"
        signal["hint_level"] = data.get("hint_level")
        signal["attempts_before_hint"] = data.get("attempts_before_hint")
    elif event_name == "hint_dismiss":
        signal["dimension"] = "helpseeking"
        signal["view_duration_ms"] = data.get("view_duration_ms")
        signal["scroll_depth_pct"] = data.get("scroll_depth_pct")
    elif event_name == "hint_chain":
        signal["dimension"] = "helpseeking"
        signal["chain_length"] = len(data.get("chain", []))

    # 坚持性信号
    elif event_name == "answer_retry":
        signal["dimension"] = "persistence"
        signal["retry_index"] = data.get("retry_index")
        signal["time_since_previous_ms"] = data.get("time_since_previous_ms")
    elif event_name == "question_skip":
        signal["dimension"] = "persistence"
        signal["skip_reason"] = data.get("skip_reason")
        signal["attempts_before_skip"] = data.get("attempts_before_skip")

    # 反思深度信号
    elif event_name == "solution_view":
        signal["dimension"] = "reflection"
        signal["trigger"] = data.get("trigger")
    elif event_name == "solution_engage":
        signal["dimension"] = "reflection"
        signal["scroll_depth_pct"] = data.get("scroll_depth_pct")
        signal["total_duration_ms"] = data.get("total_duration_ms")

    # 元认知信号
    elif event_name == "knowledge_node_click":
        signal["dimension"] = "metacognition"
        signal["node_status"] = data.get("node_status")

    # 迁移能力信号
    elif event_name == "answer_submit":
        if data.get("kp_list") and len(data.get("kp_list", [])) >= 2:
            signal["dimension"] = "transfer"
            signal["kp_count"] = len(data.get("kp_list", []))

    # 情绪信号
    elif event_name == "emotion_signal":
        signal["dimension"] = "emotion"
        signal["trigger"] = data.get("trigger")
        signal["intensity"] = data.get("intensity")

    return signal if signal else None
