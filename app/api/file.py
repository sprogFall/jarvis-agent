import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from fastapi.responses import JSONResponse
from services.vector_index_service import vector_index_service
from services.vector_store_manager import vector_store_manager
from services.document_record_service import DocumentRecordService
from loguru import logger
from core.config import settings
from db.session import get_session, Session
router = APIRouter()

# 文件上传目录
UPLOAD_DIR = Path(settings.upload_dir)

# 支持的文件类型
ALLOWED_EXTENSIONS = [".txt", '.md', ".pdf", ".png", ".jpg", ".jpeg"]

# 文件大小限制 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload")
async def upload(file: UploadFile = File(...), db: Session = Depends(get_session)) -> JSONResponse:
    """
    上传文件，并自动创建向量索引

    :param file: 上传的文件
    :param db: 数据库操作对象
    :return: 上传结果
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    safe_filename = file.filename

    # 校验文件扩展名
    file_ext = os.path.splitext(safe_filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="当前文件类型不支持")

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
        # 创建向量索引
        vector_index_service.index_single_file(file_path, db=db)
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


@router.get("/documents")
async def list_documents(
    doc_name: Optional[str] = Query(None, description="文档名称(模糊搜索)"),
    db: Session = Depends(get_session)
) -> JSONResponse:
    """
    查询知识库上传记录列表
    """
    try:
        documents = DocumentRecordService.get_by_name_like(db, doc_name or "")
        data = [
            {
                "id": doc.id,
                "doc_name": doc.doc_name,
                "doc_path": doc.doc_path,
                "doc_type": doc.doc_type,
                "doc_source": doc.doc_source,
                "chunk_count": doc.chunk_count,
                "version": doc.version,
                "status": doc.status,
            }
            for doc in documents
        ]
        return JSONResponse(
            status_code=200,
            content={"code": 200, "message": "success", "data": data}
        )
    except Exception as e:
        logger.error(f"查询文档列表失败: {e}")
        raise HTTPException(status_code=500, detail="查询文档列表失败")


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int, db: Session = Depends(get_session)) -> JSONResponse:
    """
    删除知识库文档（同时删除向量索引和本地文件）
    """
    try:
        # 查询文档记录
        from model.document import Document
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="文档记录不存在")

        doc_name = doc.doc_name
        doc_path = doc.doc_path

        # 删除向量索引
        try:
            vector_store_manager.delete_documents_by_name(doc_name)
            logger.info(f"向量索引删除成功: {doc_name}")
        except Exception as e:
            logger.warning(f"向量索引删除失败(可能不存在): {doc_name}, 错误: {e}")

        # 删除本地文件
        file_path = Path(doc_path)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"本地文件删除成功: {doc_path}")

        # 删除数据库记录
        DocumentRecordService.delete_by_id(db, doc_id)
        logger.info(f"数据库记录删除成功: {doc_name}")

        return JSONResponse(
            status_code=200,
            content={"code": 200, "message": "success", "data": {"doc_name": doc_name}}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail="删除文档失败")