from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage
import os
import uuid

from database.db import get_db
from models.chat import ChatSession, ChatMessage, MessageType, RoleType
from models.question import Question
from models.user import User
from services.auth_service import get_current_user
from services.tutor_service import tutor_service
from services.question_structuring_service import question_structuring_service
from services.question_validation_service import question_validation_service
from utils.config import settings
from utils.logger import logger

router = APIRouter(prefix="/chat")


async def save_uploaded_file(upload_file: UploadFile) -> str:
    """save uploaded file to local storage and return the file path"""
    os.makedirs(settings.upload_dir, exist_ok=True)

    file_extension = os.path.splitext(upload_file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(settings.upload_dir, unique_filename)

    with open(file_path, "wb") as buffer:
        content = await upload_file.read()
        buffer.write(content)

    logger.info(f"file saved: {file_path}")
    return file_path


@router.post("/ask-stream")
async def ask_stream(
    question: str = Form(...),
    image: Optional[UploadFile] = File(None),
    hint_level: str = Form("L0"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        image_path = None

        if image:
            image_path = await save_uploaded_file(image)

        session_stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == current_user.id, ChatSession.status == "active")
            .order_by(ChatSession.start_time.desc())
        )
        session_result = await db.execute(session_stmt)
        chat_session = session_result.scalars().first()

        if chat_session is None:
            chat_session = ChatSession(
                user_id=current_user.id,
                session_name=(question[:50] if question else "新会话"),
                status="active",
                total_messages=0,
            )
            db.add(chat_session)
            await db.flush()

        chat_message = ChatMessage(
            session_id=chat_session.id,
            user_id=current_user.id,
            role=RoleType.USER,
            content=question,
            message_type=MessageType.IMAGE if image_path else MessageType.TEXT,
            image_path=image_path,
        )
        db.add(chat_message)
        chat_session.total_messages = (chat_session.total_messages or 0) + 1

        # 结构化题目（从图片或文字中提取纯净题目）
        logger.info(f"开始题目结构化，输入: {question[:50]}...")
        structured_question = None
        image_ocr_failed = False
        if image_path:
            logger.info(f"用户上传图片: {image_path}")
            structured_question = await question_structuring_service.structure_from_image(image_path)
            if structured_question is None:
                image_ocr_failed = True
                logger.warning(f"图片OCR失败: {image_path}")
                user_text = question.strip() if question and question.strip() else ""
                if user_text:
                    question = f"[用户上传了图片但系统暂不支持图片识别。用户附带的文字是：{user_text}] 请友好地请用户把题目完整打字发过来。"
                else:
                    question = "[用户上传了图片但系统暂不支持图片识别，且没有附带文字描述] 请友好地请用户把题目打字发过来。"
            else:
                content = structured_question.get("content", "")
                knowledge = structured_question.get("knowledge_points", [])
                logger.info(f"图片OCR成功，提取到题目: {content[:80]}... 知识点: {knowledge}")
                if content:
                    qtype = structured_question.get("question_type", "解答题")
                    kp_str = "、".join(knowledge) if knowledge else "待判断"
                    question = f"[从图片识别到的题目]\n{content}\n\n题目类型：{qtype}\n涉及知识点：{kp_str}"
        else:
            logger.info(f"从文字提取题目")
            structured_question = await question_structuring_service.structure_from_text(question)
        
        # 审核题目内容（确保是真正的数学题目，而非提问词）
        question_record = None
        if structured_question and structured_question.get("content"):
            content_to_validate = structured_question["content"]
            logger.info(f"开始审核题目内容: {content_to_validate[:50]}...")
            
            validation_result = await question_validation_service.validate(
                content=content_to_validate,
                source="image" if image_path else "text",
                original_input=question
            )
            
            if validation_result.is_valid:
                # 审核通过，保存题目
                question_record = Question(
                    user_id=current_user.id,
                    content=validation_result.content or content_to_validate,
                    question_type=validation_result.question_type or structured_question.get("question_type", "解答题"),
                    difficulty=validation_result.difficulty or structured_question.get("difficulty", 0.5),
                    knowledge_points=validation_result.knowledge_points or structured_question.get("knowledge_points", []),
                    source="user_uploaded",  # 用户上传的题目
                    is_active=True,  # 审核通过，标记为有效
                )
                db.add(question_record)
                logger.info(f"题目审核通过并已保存: {question_record.content[:100]}...")
            else:
                # 审核不通过，不保存到题库
                logger.warning(f"题目审核未通过，不保存到题库。原因: {validation_result.reason} | 内容: {content_to_validate[:100]}...")
                question_record = None
        else:
            # 结构化失败，尝试直接审核原始输入
            logger.info(f"题目结构化失败，尝试审核原始输入: {question[:50]}...")
            validation_result = await question_validation_service.validate(
                content=question,
                source="text",
                original_input=question
            )
            
            if validation_result.is_valid:
                question_record = Question(
                    user_id=current_user.id,
                    content=validation_result.content or question,
                    question_type=validation_result.question_type or "text",
                    difficulty=validation_result.difficulty or 0.5,
                    knowledge_points=validation_result.knowledge_points or [],
                    source="user_uploaded",  # 用户上传的题目
                    is_active=True,  # 审核通过，标记为有效
                )
                db.add(question_record)
                logger.info(f"原始输入审核通过并已保存: {question_record.content[:100]}...")
            else:
                logger.warning(f"原始输入审核未通过，不保存到题库。原因: {validation_result.reason}")

        await db.commit()

        if question_record:
            logger.info(
                f"question saved, user_id={current_user.id}, message_id={chat_message.id}, question_id={question_record.id}"
            )
        else:
            logger.info(
                f"question not saved (validation failed), user_id={current_user.id}, message_id={chat_message.id}"
            )

        # 获取历史消息作为上下文
        history_stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(10)  # 获取最近10条消息
        )
        history_result = await db.execute(history_stmt)
        history_messages = history_result.scalars().all()
        
        # 转换为 LangChain 消息格式（排除当前这条用户消息）
        chat_history: List = []
        for msg in reversed(history_messages):  # 反转回正序
            if msg.id == chat_message.id:  # 跳过刚添加的当前消息
                continue
            if msg.role == RoleType.USER:
                chat_history.append(HumanMessage(content=msg.content))
            elif msg.role == RoleType.ASSISTANT:
                chat_history.append(AIMessage(content=msg.content))
        
        logger.info(f"Loaded {len(chat_history)} history messages for context")

        normalized_hint_level = (hint_level or "L0").upper().strip()
        if normalized_hint_level not in {"L0", "L1", "L2", "L3", "L4"}:
            normalized_hint_level = "L0"
        logger.info(f"ask_stream hint_level={normalized_hint_level}")

        async def generate():
            def _sse_event(data: str):
                safe_data = (data or "").replace("\r\n", "\n").replace("\r", "\n")
                for line in safe_data.split("\n"):
                    yield f"data: {line}\n"
                yield "\n"

            full_response = ""
            try:
                async for chunk in tutor_service.process_question_stream(
                    question,
                    image_path,
                    chat_history,
                    normalized_hint_level,
                ):
                    full_response += chunk
                    for line in _sse_event(chunk):
                        yield line

                for line in _sse_event("[DONE]"):
                    yield line
            finally:
                # 保存 AI 回复到数据库（即使中途中断也尽量保存已生成内容）
                if full_response:
                    ai_message = ChatMessage(
                        session_id=chat_session.id,
                        user_id=current_user.id,
                        role=RoleType.ASSISTANT,
                        content=full_response,
                        message_type=MessageType.TEXT,
                    )
                    db.add(ai_message)
                    chat_session.total_messages += 1
                    await db.commit()
                    logger.info(f"AI response saved, session_id={chat_session.id}")

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except Exception as e:
        logger.error(f"Tutor service error: {e}")
        raise HTTPException(status_code=500, detail="Tutor service error")


# ---------------------------------------------------------------------------
# 大题 AI 批改接口（非流式，返回 JSON）
# ---------------------------------------------------------------------------

from pydantic import BaseModel as PydanticModel

class GradeAnswerRequest(PydanticModel):
    question_content: str
    standard_answer: Optional[str] = None
    user_answer: str
    knowledge_points: Optional[list] = None


@router.post("/grade-answer")
async def grade_answer(
    payload: GradeAnswerRequest,
    current_user: User = Depends(get_current_user),
):
    """
    使用大模型批改主观题/大题。
    返回：{ is_correct: bool, score: float, feedback: str }
    """
    try:
        kp_str = "、".join(payload.knowledge_points) if payload.knowledge_points else "数列与不等式"
        std_hint = f"\n【参考答案】{payload.standard_answer}" if payload.standard_answer else ""

        prompt = (
            f"你是一位高中数学老师，请批改以下学生作答。\n\n"
            f"【题目】{payload.question_content}\n"
            f"【知识点】{kp_str}"
            f"{std_hint}\n\n"
            f"【学生答案】{payload.user_answer}\n\n"
            "请按以下格式严格回复（不要输出其他内容）：\n"
            "CORRECT: true 或 false\n"
            "SCORE: 0到100之间的整数\n"
            "FEEDBACK: （一段简洁的批改说明，指出对错原因、关键步骤是否正确，100字以内）"
        )

        from agent.instructor import instructor_agent
        full_text = ""
        async for chunk in instructor_agent.llm.astream(prompt):
            full_text += chunk.content

        # 解析结构化输出
        import re
        is_correct = False
        score = 0
        feedback = full_text.strip()

        m_correct = re.search(r"CORRECT:\s*(true|false)", full_text, re.IGNORECASE)
        m_score   = re.search(r"SCORE:\s*(\d+)", full_text)
        m_fb      = re.search(r"FEEDBACK:\s*(.+)", full_text, re.DOTALL)

        if m_correct:
            is_correct = m_correct.group(1).lower() == "true"
        if m_score:
            score = min(100, max(0, int(m_score.group(1))))
        if m_fb:
            feedback = m_fb.group(1).strip()

        logger.info(
            f"[GradeAnswer] uid={current_user.id} correct={is_correct} score={score}"
        )
        return {"is_correct": is_correct, "score": score, "feedback": feedback}

    except Exception as e:
        logger.error(f"grade_answer error: {e}")
        raise HTTPException(status_code=500, detail=f"批改失败: {e}")


# ---------------------------------------------------------------------------
# 答错后诊断接口：指出学生问题所在 + 正确解题思路
# ---------------------------------------------------------------------------

class DiagnoseRequest(PydanticModel):
    question_content: str
    standard_answer: Optional[str] = None
    user_answer: str          # 学生作答（选择题填选项字母，大题填解题过程）
    knowledge_points: Optional[list] = None


@router.post("/diagnose")
async def diagnose_answer(
    payload: DiagnoseRequest,
    current_user: User = Depends(get_current_user),
):
    """
    答错后调用，AI 指出学生的具体错误并给出正确解题思路。
    返回：{ diagnosis: str }
    """
    try:
        kp_str = "、".join(payload.knowledge_points) if payload.knowledge_points else "数列与不等式"
        std_hint = f"\n【参考答案/正确选项】{payload.standard_answer}" if payload.standard_answer else ""

        prompt = (
            f"你是高中数学老师，学生在下面这道题中答错了，请简要指出：\n"
            f"1. 学生最可能犯了什么错误（概念误解、计算错误、解题思路偏差等）\n"
            f"2. 正确的解题思路/关键步骤\n\n"
            f"【题目】{payload.question_content}\n"
            f"【知识点】{kp_str}"
            f"{std_hint}\n"
            f"【学生作答】{payload.user_answer}\n\n"
            f"请用3-5句话简洁回答，直接给出分析，不要重复题目内容。"
        )

        from agent.instructor import instructor_agent
        full_text = ""
        async for chunk in instructor_agent.llm.astream(prompt):
            full_text += chunk.content

        logger.info(f"[Diagnose] uid={current_user.id} diagnosis generated")
        return {"diagnosis": full_text.strip()}

    except Exception as e:
        logger.error(f"diagnose_answer error: {e}")
        raise HTTPException(status_code=500, detail=f"诊断失败: {e}")
