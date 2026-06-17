
from pathlib import Path
from services.vector_store_manager import vector_store_manager
from services.document_split_service import document_split_service
from loguru import logger


class VectorIndexService:
    """
    向量索引服务
    负责读取文件、生成向量、存储到向量数据库
    """
    def __init__(self):
        """
        初始化向量索引服务
        """
        self.upload_path = "./uploads"
        logger.info("初始化向量索引服务完成")

    
    def index_single_file(self, file_path: str):
        """
        索引单个文件
        
        :param file_path: 文件路径
        """
        path = Path(file_path).resolve()

        if not path.exists() or not path.is_file():
            raise ValueError(f"文件不存在:{path}")
        logger.info(f"开始索引文件:{path}")

        try:
            # 1.读取文件内容
            content = path.read_text(encoding="utf-8")
            logger.info(f"读取文件{file_path}, 内容长度: {len(content)}字符")

            # 2.删除该文件的旧数据(如果存在)
            # 2.1 获取文件的规范化路径
            
            normalized_path = path.as_posix()
            # 3.使用分割器
            docs = document_split_service.split_document(content, normalized_path)
            # 4.生成向量并存储
            if docs:
                vector_store_manager.add_documents(docs)
            else:
                logger.info(f"文件{file_path}没有可索引的内容")

        except Exception as e:
            logger.error(f"索引文件{file_path}时出错:{e}")
            raise RuntimeError(f"索引文件失败: {e}") from e

vector_index_service = VectorIndexService()
