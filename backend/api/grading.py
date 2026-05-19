"""AI批改 API 路由"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_db
from utils.auth import get_current_user
from services.grading_service import grading_service
from agent.grader import grader_agent
from utils.logger import logger

router = APIRouter(prefix="/grading", tags=["grading"])


@router.post("/upload")
async def upload_images(
    files: List[UploadFile] = File(...),
    title: str = Form("未命名批改"),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传题目图片，触发OCR识别"""
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一张图片")

    session = await grading_service.create_session(db, user.id, title)

    file_contents = []
    filenames = []
    for f in files:
        content = await f.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"图片 {f.filename} 超过10MB")
        file_contents.append(content)
        filenames.append(f.filename or "image.jpg")

    ocr_results = await grading_service.upload_and_ocr(
        db, session.id, file_contents, filenames
    )

    return {
        "session_id": session.id,
        "title": session.title,
        "ocr_results": ocr_results,
    }


@router.post("/correct")
async def submit_corrections(
    payload: dict,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交用户校对后的文本"""
    session_id = payload.get("session_id")
    corrections = payload.get("corrections") or payload.get("questions", [])

    if not session_id:
        raise HTTPException(status_code=400, detail="缺少 session_id")
    if not corrections:
        raise HTTPException(status_code=400, detail="缺少校对数据")

    questions = await grading_service.submit_corrections(db, session_id, corrections)

    # 逐题调用 Grader Agent 批改
    grading_results = []
    for q in questions:
        result = await grader_agent.grade(
            question_text=q.question_text or "",
            student_answer=q.student_answer or "",
            knowledge_points=None,
        )
        await grading_service.grade_question(db, q.id, result)
        grading_results.append({
            "question_id": q.id,
            "question_index": q.question_index,
            "is_correct": result.get("is_correct"),
            "score": result.get("final_score", 0),
            "error_type": result.get("error", {}).get("primary_type") if result.get("error") else None,
        })

    # 完成批改，计算聚合统计
    summary = await grading_service.complete_session(db, session_id)

    return {
        "session_id": session_id,
        "grading_results": grading_results,
        "summary": summary,
    }


@router.get("/result/{session_id}")
async def get_result(
    session_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取批改结果详情"""
    result = await grading_service.get_result(db, session_id)
    if not result:
        raise HTTPException(status_code=404, detail="批改记录不存在")
    return result


@router.get("/report/{session_id}")
async def get_report(
    session_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取批改报告"""
    report = await grading_service.get_report(db, session_id)
    if not report:
        raise HTTPException(status_code=404, detail="批改报告不存在")
    return report


@router.get("/history")
async def get_history(
    page: int = 1,
    size: int = 10,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取批改历史列表"""
    return await grading_service.get_history(db, user.id, page, size)


@router.get("/trend")
async def get_trend(
    limit: int = 10,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取趋势分析数据"""
    return await grading_service.get_trend(db, user.id, limit)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除批改记录"""
    ok = await grading_service.delete_session(db, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="批改记录不存在")
    return {"success": True}


@router.post("/cancel/{session_id}")
async def cancel_grading(
    session_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消批改"""
    ok = await grading_service.cancel_grading(db, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="批改记录不存在")
    return {"success": True}
