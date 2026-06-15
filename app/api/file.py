
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger

router = APIRouter()

# 文件上传目录
UPLOAD_DIR = Path("./uploads")

# 支持的文件类型
ALLOWED_EXTENSTIONS = ["txt", 'md']

# 文件大小限制 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload")
async def upload(file: UploadFile = File(...)) -> JSONResponse:
    """
    上传文件，并自动创建向量索引

    :param file: 上传的文件
    :return: 上传结果
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    safe_filename = file.filename

    # TODO 校验文件扩展名

    # 创建上传目录
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 保存文件
    file_path = UPLOAD_DIR / safe_filename
    if file_path.exists():
        logger.info(f"文件已存在，将覆盖{file_path}")
        # 删除已存在的文件
        file_path.unlink()
    # 读取并保存文件内容
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件大小不能超过限制{MAX_FILE_SIZE}字节")
    
    file_path.write_bytes(content)
    logger.info(f"文件上传成功，路径：{file_path}")

    # 创建向量索引
    try:
        logger.info(f"开始为上传文件{file_path}创建向量索引")
        # TODO 创建向量索引
        logger.info(f"向量索引创建完成，文件：{file_path}")
    except Exception as e:
        logger.error(f"向量索引创建失败，文件：{file_path}, 错误信息：{e}")
        raise HTTPException(status_code=500, detail="向量索引创建失败")

    # 返回响应
    return JSONResponse(
        status_code=200,
        content={
            "code": 200,
            "message": "success",
            "data": {
                "file_name": safe_filename,
                "file_path": str(file_path),
                "file_size": len(content)
            }
        }
    )