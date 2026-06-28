import hashlib
from pathlib import Path

from services.document_record_service import DocumentRecordService
from services.ocr_service import ocr_service
from services.vector_store_manager import vector_store_manager
from services.document_split_service import document_split_service
from db.session import Session
from loguru import logger


class VectorIndexService:
    """
    向量索引服务
    负责读取文件、生成向量、存储到向量数据库
    """

    def index_single_file(self, file_path: str, db: Session):
        """
        索引单个文件

        :param file_path: 文件路径
        :param db: 数据库对象
        """
        try:
            # 1.读取文件内容
            normalized_path, doc_name, doc_hash, content, suffix = self.read_file(file_path)
            # 2.是否存在文件名和hash一致的文件
            same_name_doc = DocumentRecordService.get_by_name(db, doc_name)
            if same_name_doc:
                if same_name_doc.doc_hash == doc_hash:
                    logger.info(f"文件{file_path}已存在，跳过索引")
                    raise RuntimeError("当前知识库已有相同文件存在，无需重复索引")
                else:
                    vector_store_manager.delete_documents_by_name(doc_name)

            # 3.使用分割器
            docs = document_split_service.split_document(content, normalized_path)
            # 4.生成向量并存储
            if docs:
                vector_store_manager.add_documents(docs)
                # 存储文档记录
                DocumentRecordService.save_or_update_document(db, doc_name=doc_name,
                                                              doc_path=file_path, doc_hash=doc_hash,
                                                              doc_type=Path(normalized_path).suffix,
                                                              doc_source="file_upload",
                                                              chunk_count=len(docs), status="active")
            else:
                logger.info(f"文件{file_path}没有可索引的内容")
                raise RuntimeError("当前文件没有可索引的内容")

        except Exception as e:
            logger.error(f"索引文件{file_path}时出错:{e}")
            raise RuntimeError(f"索引文件失败: {e}") from e

    def read_file(self, file_path: str):
        """
        读取文件
        """
        path = Path(file_path).resolve()

        if not path.exists() or not path.is_file():
            raise ValueError(f"文件不存在:{path}")
        logger.info(f"开始索引文件:{path}")
        # 分块读取二进制流 计算hash值
        doc_hash = self.get_hash(path)

        # 根据后缀提取文档内容
        suffix = path.suffix.lower()
        normalized_path = path.as_posix()
        doc_name = Path(normalized_path).name
        content = self.do_read(path, suffix)

        logger.info(f"读取文件{file_path}, 内容长度: {len(content)}字符, 哈希值：{doc_hash}")
        return normalized_path, doc_name, doc_hash, content, suffix

    def get_hash(self, path: Path) -> str:
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def do_read(self, path: Path, suffix: str) -> str:
        """
        根据文件类型，按策略读取文件内容
        :param path 文件路径
        :param suffix 文件后缀
        """
        if suffix in [".txt", ".md"]:
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                raise ValueError(f"文件编码非UTF-8")
        elif suffix in [".png", ".jpg", ".jpeg"]:
            content = ocr_service.ocr(path)
        elif suffix == ".pdf":
            content = self.read_from_pdf(path)
        else:
            raise ValueError(f"不支持的文件类型:{suffix}")

        return content

    def read_from_pdf(self, path: Path) -> str:
        """
        从pdf文件中读取内容
        """
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        text_part = []
        empty_page_count = 0
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_part.append(page_text)
            else:
                # 空页+1
                empty_page_count += 1
        total_pages = len(reader.pages)
        extracted_text = "\n".join(text_part).strip()
        # 判定是否为扫描件：
        # 1. 完全提取不到文本
        # 2. 或超过半数页面无文本，且总文本量低于阈值
        is_scanned = (
                not extracted_text
                or (
                        total_pages > 0
                        and empty_page_count / total_pages >= 0.5
                )
        )
        if not is_scanned:
            if not text_part:
                raise ValueError(f"PDF文件{path}无有效文本")
            return extracted_text

        # 执行OCR扫描
        logger.info(
            f"PDF文件{path}疑似扫描件（共{total_pages}页，"
            f"其中{empty_page_count}页无文本，提取到{len(extracted_text)}字符），"
            f"尝试使用OCR识别"
        )
        return ocr_service.ocr(path)

vector_index_service = VectorIndexService()
