"""AI批改业务流程编排"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from models.grading import GradingSession, GradingQuestion
from multimodal.image_parser import image_parser
from utils.logger import logger

ERROR_TYPE_WEIGHTS = {
    "CONCEPT_ERROR": 1.5,
    "PROCESS_ERROR": 1.2,
    "CALCULATION_ERROR": 0.7,
    "READING_ERROR": 0.5,
    "FORMAT_ERROR": 0.3,
}


class GradingService:

    async def create_session(self, db: AsyncSession, user_id: int,
                             title: str = "未命名批改") -> GradingSession:
        session = GradingSession(
            id=uuid.uuid4().hex[:12],
            user_id=user_id,
            title=title,
            status="uploading",
        )
        db.add(session)
        await db.commit()
        return session

    async def upload_and_ocr(self, db: AsyncSession, session_id: str,
                             files: List[bytes], filenames: List[str]) -> List[dict]:
        """上传图片并执行OCR识别"""
        session = await db.get(GradingSession, session_id)
        if not session:
            raise ValueError(f"批改会话不存在: {session_id}")

        import os
        from utils.config import settings

        results = []
        for i, (content, fname) in enumerate(zip(files, filenames)):
            ext = fname.rsplit(".", 1)[-1] if "." in fname else "jpg"
            tmp_path = os.path.join(settings.upload_dir, f"grading_{uuid.uuid4().hex[:8]}.{ext}")
            os.makedirs(settings.upload_dir, exist_ok=True)
            with open(tmp_path, "wb") as f:
                f.write(content)

            try:
                ocr_result = await image_parser.parse_image(tmp_path)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

            if ocr_result:
                q_text = ocr_result.get("question_text", "")
                a_text = ocr_result.get("answer_text", "")
                results.append({
                    "index": i,
                    "filename": fname,
                    "ocr_text": q_text,
                    "answer_text": a_text,
                    "has_question": ocr_result.get("has_question", bool(q_text.strip())),
                    "has_answer": ocr_result.get("has_answer", bool(a_text.strip())),
                    "success": ocr_result.get("success", False),
                })
            else:
                results.append({
                    "index": i,
                    "filename": fname,
                    "ocr_text": "",
                    "answer_text": "",
                    "has_question": False,
                    "has_answer": False,
                    "success": False,
                })

        # LLM 根据内容语义分组（题目+解题过程配对）
        if len(results) >= 2:
            try:
                results = await self._group_ocr_results_by_llm(results)
            except Exception as e:
                logger.warning(f"LLM分组失败，保留原始结果: {e}")

        session.status = "reviewing"
        session.question_count = len(results)
        await db.commit()

        return results

    async def _group_ocr_results_by_llm(self, results: List[dict]) -> List[dict]:
        """使用 LLM 根据数学内容语义将 OCR 结果分组（题目+解题过程配对）"""
        import json
        import re
        from openai import AsyncOpenAI
        from utils.config import settings

        # 构造 prompt：列出每条结果
        items_desc = []
        for r in results:
            q_preview = (r.get("ocr_text") or "")[:200]
            a_preview = (r.get("answer_text") or "")[:200]
            has_q = r["has_question"]
            has_a = r["has_answer"]

            if has_q and has_a:
                type_label = "题目+解题过程（混合）"
                content = f"题目：{q_preview}\n解题过程：{a_preview}"
            elif has_q:
                type_label = "题目（无解题过程）"
                content = q_preview
            elif has_a:
                type_label = "解题过程（无题目）"
                content = a_preview
            else:
                type_label = "未识别到数学内容"
                content = (q_preview or a_preview or "(空)")

            items_desc.append(f"[索引{r['index']}] 类型: {type_label}\n内容: {content}")

        prompt = f"""你是一个数学题目识别系统。以下是从 {len(results)} 张图片中 OCR 识别出的内容。

每条记录包含一个索引和识别出的数学文本。请根据**数学内容语义**判断哪些解题过程属于哪道题目，将它们分组。

识别结果：
{chr(10).join(items_desc)}

请分析以上内容并返回 JSON 分组结果。分组规则：
1. 同一道题的"题目内容"和"解题过程"放在同一组
2. 通过数学主题、公式、知识点判断是否属于同一题（如：都涉及数列递推 → 可能同组；一个数列一个几何 → 不同组）
3. 如果某条内容同时包含题目和解题过程（混合类型），它自己就是一个完整组
4. 如果某条只有题目没有解题过程，单独成组（answer_indices 为空）
5. 如果某条只有解题过程没有题目，尝试匹配最相关的题目；匹配不上则单独成组
6. 每个索引必须且只能出现在一个组中
7. 给每组一个简短的主题描述（topic）

请严格按以下 JSON 格式返回（不要添加任何其他文字）：
```json
{{
  "groups": [
    {{
      "question_indices": [0, 2],
      "answer_indices": [1],
      "topic": "数列递推求通项公式"
    }},
    {{
      "question_indices": [3],
      "answer_indices": [],
      "topic": "解三角形"
    }}
  ]
}}
```

question_indices 包含该组所有包含题目内容的索引，answer_indices 包含该组所有包含解题过程的索引。"""

        # 调用 LLM
        client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
        )
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2000,
        )
        content = response.choices[0].message.content.strip()
        logger.info(f"LLM grouping response length: {len(content)}")

        # 解析 JSON
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            parsed = json.loads(json_match.group(1))
        else:
            parsed = json.loads(content)

        groups = parsed.get("groups", [])
        if not groups:
            logger.info("LLM returned no groups, keeping original results")
            return results

        # 验证：每个索引是否恰好出现一次
        all_indices = set()
        for g in groups:
            for idx in (g.get("question_indices", []) + g.get("answer_indices", [])):
                if idx in all_indices:
                    logger.warning(f"LLM分组索引 {idx} 重复，回退到原始结果")
                    return results
                all_indices.add(idx)
        if all_indices != set(range(len(results))):
            logger.warning(f"LLM分组索引不完整 {all_indices} vs {set(range(len(results)))}, 回退到原始结果")
            return results

        # 按分组合并
        merged = []
        for g in groups:
            q_indices = g.get("question_indices", [])
            a_indices = g.get("answer_indices", [])
            topic = g.get("topic", "")

            # 合并题目文本
            q_texts = []
            for idx in q_indices:
                t = results[idx].get("ocr_text", "") or results[idx].get("question_text", "")
                if t.strip():
                    q_texts.append(t.strip())
            merged_question = "\n\n".join(q_texts)

            # 合并答案文本
            a_texts = []
            for idx in a_indices:
                t = results[idx].get("answer_text", "") or results[idx].get("student_answer", "")
                if t.strip():
                    a_texts.append(t.strip())
            merged_answer = "\n\n".join(a_texts)

            # 如果题目索引里的条目本身也包含答案，追加
            for idx in q_indices:
                extra_a = results[idx].get("answer_text", "")
                if extra_a and extra_a.strip():
                    merged_answer = (merged_answer + "\n\n" + extra_a.strip()).strip()

            all_source_indices = q_indices + a_indices
            merged.append({
                "index": len(merged),
                "question_text": merged_question,
                "student_answer": merged_answer,
                "ocr_text": merged_question,
                "answer_text": merged_answer,
                "has_question": bool(merged_question.strip()),
                "has_answer": bool(merged_answer.strip()),
                "merged_from": all_source_indices,
                "source_image_indices": all_source_indices,
                "source_filenames": [results[i]["filename"] for i in all_source_indices if i < len(results)],
                "topic": topic,
                "success": True,
            })

        logger.info(f"LLM grouped {len(results)} raw results into {len(merged)} questions")
        for m in merged:
            logger.info(f"  Q{m['index']}: topic={m['topic']}, sources={m['merged_from']}")

        return merged

    async def submit_corrections(self, db: AsyncSession, session_id: str,
                                  corrections: List[dict]) -> List[GradingQuestion]:
        """用户校对后提交，创建题目记录"""
        session = await db.get(GradingSession, session_id)
        if not session:
            raise ValueError(f"批改会话不存在: {session_id}")

        session.status = "grading"
        questions = []
        for corr in corrections:
            q = GradingQuestion(
                id=uuid.uuid4().hex[:12],
                session_id=session_id,
                question_index=corr.get("index", 0),
                question_text=corr.get("question_text") or corr.get("corrected_text", ""),
                student_answer=corr.get("student_answer") or corr.get("corrected_answer", ""),
                ocr_raw_text=corr.get("ocr_text", ""),
                ocr_corrections=corr.get("corrections", []),
            )
            db.add(q)
            questions.append(q)

        await db.commit()
        return questions

    async def grade_question(self, db: AsyncSession, question_id: str,
                              grading_result: dict) -> GradingQuestion:
        """记录单题批改结果"""
        q = await db.get(GradingQuestion, question_id)
        if not q:
            raise ValueError(f"题目不存在: {question_id}")

        q.grading_result = grading_result
        q.is_correct = grading_result.get("is_correct")
        q.score = grading_result.get("final_score", 0)
        q.error_type = grading_result.get("error", {}).get("primary_type") if grading_result.get("error") else None
        q.error_tags = grading_result.get("error_tags", [])
        q.knowledge_points = grading_result.get("knowledge_points", [])
        await db.commit()
        return q

    async def complete_session(self, db: AsyncSession, session_id: str) -> dict:
        """批改完成，计算聚合统计"""
        session = await db.get(GradingSession, session_id)
        if not session:
            raise ValueError(f"批改会话不存在: {session_id}")

        stmt = select(GradingQuestion).where(GradingQuestion.session_id == session_id)
        result = await db.execute(stmt)
        questions = result.scalars().all()

        if not questions:
            return {"session_id": session_id, "question_count": 0}

        scores = [q.score or 0 for q in questions]
        avg_score = sum(scores) / len(scores) if scores else 0
        correct_count = sum(1 for q in questions if q.is_correct)

        # 错因分布
        error_dist = {}
        for q in questions:
            et = q.error_type
            if et:
                error_dist[et] = error_dist.get(et, 0) + 1

        # 知识点统计
        kp_correct: Dict[str, list] = {}
        for q in questions:
            kps = q.knowledge_points or []
            for kp in kps:
                if kp not in kp_correct:
                    kp_correct[kp] = []
                kp_correct[kp].append(q.is_correct)

        kp_stats = {}
        for kp, results_list in kp_correct.items():
            kp_stats[kp] = {
                "total": len(results_list),
                "correct": sum(1 for r in results_list if r),
                "rate": round(sum(1 for r in results_list if r) / len(results_list), 2),
            }

        sorted_kps = sorted(kp_stats.items(), key=lambda x: x[1]["rate"])
        weakest_kps = [{"name": k, **v} for k, v in sorted_kps[:3]]
        strongest_kps = [{"name": k, **v} for k, v in sorted_kps[-3:][::-1]]

        session.status = "done"
        session.avg_score = round(avg_score, 1)
        session.error_distribution = error_dist
        session.weakest_kps = weakest_kps
        session.strongest_kps = strongest_kps
        await db.commit()

        return {
            "session_id": session_id,
            "question_count": len(questions),
            "correct_count": correct_count,
            "avg_score": round(avg_score, 1),
            "error_distribution": error_dist,
            "kp_stats": kp_stats,
            "weakest_kps": weakest_kps,
            "strongest_kps": strongest_kps,
        }

    async def get_result(self, db: AsyncSession, session_id: str) -> dict:
        """获取批改结果详情"""
        session = await db.get(GradingSession, session_id)
        if not session:
            raise ValueError(f"批改会话不存在: {session_id}")

        stmt = select(GradingQuestion).where(
            GradingQuestion.session_id == session_id
        ).order_by(GradingQuestion.question_index)
        result = await db.execute(stmt)
        questions = result.scalars().all()

        return {
            "session_id": session.id,
            "title": session.title,
            "status": session.status,
            "question_count": session.question_count,
            "avg_score": session.avg_score,
            "error_distribution": session.error_distribution,
            "weakest_kps": session.weakest_kps,
            "strongest_kps": session.strongest_kps,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "questions": [
                {
                    "id": q.id,
                    "question_index": q.question_index,
                    "question_text": q.question_text,
                    "student_answer": q.student_answer,
                    "is_correct": q.is_correct,
                    "score": q.score,
                    "error_type": q.error_type,
                    "error_tags": q.error_tags,
                    "knowledge_points": q.knowledge_points,
                    "grading_result": q.grading_result,
                }
                for q in questions
            ],
        }

    async def get_report(self, db: AsyncSession, session_id: str) -> dict:
        return await self.get_result(db, session_id)

    async def get_history(self, db: AsyncSession, user_id: int,
                          page: int = 1, size: int = 10) -> dict:
        """获取批改历史"""
        stmt = (
            select(GradingSession)
            .where(GradingSession.user_id == user_id)
            .order_by(GradingSession.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await db.execute(stmt)
        sessions = result.scalars().all()

        count_stmt = (
            select(func.count(GradingSession.id))
            .where(GradingSession.user_id == user_id)
        )
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        return {
            "items": [
                {
                    "session_id": s.id,
                    "title": s.title,
                    "status": s.status,
                    "question_count": s.question_count,
                    "avg_score": s.avg_score,
                    "error_distribution": s.error_distribution,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sessions
            ],
            "total": total,
            "page": page,
            "size": size,
        }

    async def delete_session(self, db: AsyncSession, session_id: str) -> bool:
        session = await db.get(GradingSession, session_id)
        if not session:
            return False
        await db.delete(session)
        await db.commit()
        return True

    async def cancel_grading(self, db: AsyncSession, session_id: str) -> bool:
        session = await db.get(GradingSession, session_id)
        if not session:
            return False
        session.status = "cancelled"
        await db.commit()
        return True

    async def get_trend(self, db: AsyncSession, user_id: int,
                        limit: int = 10) -> dict:
        """获取趋势分析数据"""
        stmt = (
            select(GradingSession)
            .where(GradingSession.user_id == user_id, GradingSession.status == "done")
            .order_by(GradingSession.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        sessions = result.scalars().all()

        return {
            "sessions": [
                {
                    "session_id": s.id,
                    "title": s.title,
                    "avg_score": s.avg_score,
                    "question_count": s.question_count,
                    "error_distribution": s.error_distribution,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in reversed(sessions)
            ],
        }


grading_service = GradingService()
