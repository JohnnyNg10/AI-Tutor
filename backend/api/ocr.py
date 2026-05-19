import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException

from multimodal.image_parser import image_parser
from utils.config import settings

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


@router.post("/parse")
async def parse_handwritten_answer(file: UploadFile = File(...)):
    """OCR 手写答案识别

    接收学生拍照上传的草稿纸图片，调用视觉模型识别手写内容。
    支持 jpg/png/gif/webp 格式。
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片格式")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过10MB")

    ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "jpg"
    unique_name = f"ocr_{uuid.uuid4().hex[:12]}.{ext}"
    os.makedirs(settings.upload_dir, exist_ok=True)
    file_path = os.path.join(settings.upload_dir, unique_name)

    with open(file_path, "wb") as f:
        f.write(contents)

    try:
        result = await image_parser.parse_image(file_path)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    if result is None:
        raise HTTPException(status_code=500, detail="OCR 解析服务异常")

    return result
