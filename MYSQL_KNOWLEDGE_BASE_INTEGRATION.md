# Jarvis-Agent 知识库接入 MySQL 记录方案

这份文档只讲三件事：

1. 现在项目的知识库上传和解析链路是什么
2. 如果要接入 MySQL，应该新增什么、改什么、为什么这样改
3. 如何验证改造是否生效

本文不直接修改业务代码，只给出教学向接入说明。

## 1. 当前项目现状

当前知识库主链路如下：

1. 前端 `frontend/chat.html` 调用 `POST /api/v1/upload`
2. 后端接口在 `app/api/file.py`
3. 文件被保存到本地 `./uploads`
4. 接着调用 `app/services/vector_index_service.py`
5. `vector_index_service` 读取文件内容并调用 `document_split_service`
6. `app/services/document_split_service.py` 负责切片
7. `app/services/vector_store_manager.py` 把分片写入 Qdrant

也就是说，当前系统已经有两类存储：

- 本地磁盘：保存原始文件
- Qdrant：保存向量

但没有结构化业务记录存储：

- 没有 MySQL 记录上传历史
- 没有 MySQL 记录解析过程
- 没有 MySQL 记录失败原因

所以现在前端虽然有“上传记录”区域，但它只是页面内存状态。刷新页面后记录就没了。

## 2. 为什么这里要加 MySQL

Qdrant 的职责应该是“向量检索”，不是“业务记录管理”。

知识库上传、解析、失败、重试、时间统计、列表查询，这些都属于结构化数据场景，应该落在 MySQL。

建议职责拆分如下：

- MySQL：记录文件、解析任务、状态、错误、时间、统计字段
- Qdrant：只负责存储向量和检索用 metadata
- 本地磁盘：保存原始文件

这是最稳的分层方式。

## 3. 这次接入的目标

建议把目标明确成下面几项：

1. 每次上传都能在 MySQL 里留一条文件记录
2. 每次解析都能在 MySQL 里留一条解析记录
3. 解析成功或失败时，状态要能回写
4. 失败原因要落库，不能只打日志
5. 后续可以很方便地做“上传列表”“失败重试”“按文件删除向量”“重建索引”

## 4. 推荐表设计

推荐至少两张表：

1. `kb_file`
2. `kb_parse_record`

关系是：

- 一个文件记录对应多次解析记录
- `kb_file` 是主表
- `kb_parse_record` 是过程表

原因很简单：文件本身和某一次解析不是一回事。

## 5. 表一：`kb_file`

这张表记录“上传文件”本身。

建议字段：

- `id`：主键，自增
- `biz_id`：对外文件 ID，建议 UUID
- `original_name`：用户上传时的原始文件名
- `storage_name`：实际落盘文件名
- `storage_path`：实际磁盘路径
- `file_ext`：扩展名
- `mime_type`：文件类型，可选
- `file_size`：文件大小
- `content_hash`：文件内容哈希，建议 SHA256
- `upload_status`：上传状态
- `parse_status`：最近一次解析状态
- `latest_parse_id`：最近一次解析记录主键
- `error_message`：最近一次错误
- `created_at`
- `updated_at`

推荐建表 SQL：

```sql
CREATE TABLE `kb_file` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `biz_id` CHAR(36) NOT NULL COMMENT '对外文件ID(UUID)',
  `original_name` VARCHAR(255) NOT NULL COMMENT '原始文件名',
  `storage_name` VARCHAR(255) NOT NULL COMMENT '物理文件名',
  `storage_path` VARCHAR(1024) NOT NULL COMMENT '物理路径',
  `file_ext` VARCHAR(16) NOT NULL COMMENT '扩展名',
  `mime_type` VARCHAR(128) DEFAULT NULL COMMENT 'MIME类型',
  `file_size` BIGINT NOT NULL COMMENT '字节大小',
  `content_hash` CHAR(64) NOT NULL COMMENT 'SHA256',
  `upload_status` VARCHAR(32) NOT NULL DEFAULT 'RECEIVED',
  `parse_status` VARCHAR(32) NOT NULL DEFAULT 'PENDING',
  `latest_parse_id` BIGINT UNSIGNED DEFAULT NULL,
  `error_message` TEXT DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_kb_file_biz_id` (`biz_id`),
  KEY `idx_kb_file_hash` (`content_hash`),
  KEY `idx_kb_file_parse_status` (`parse_status`),
  KEY `idx_kb_file_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 为什么这样设计

- `biz_id` 不建议直接暴露数据库自增主键
- `content_hash` 方便后续做去重、幂等、版本判断
- `upload_status` 和 `parse_status` 要分开，因为“文件保存成功”不代表“解析成功”

## 6. 表二：`kb_parse_record`

这张表记录“某一次解析行为”。

建议字段：

- `id`：主键，自增
- `parse_id`：对外解析任务 ID，建议 UUID
- `file_id`：关联 `kb_file.id`
- `parse_status`：本次解析状态
- `chunk_count`：切片数量
- `vector_count`：写入向量数量
- `embedding_model`：本次使用的 embedding 模型
- `vector_collection`：Qdrant collection 名称
- `chunk_size`：本次切片大小快照
- `chunk_overlap`：本次切片重叠大小快照
- `started_at`
- `finished_at`
- `duration_ms`
- `error_message`
- `created_at`
- `updated_at`

推荐建表 SQL：

```sql
CREATE TABLE `kb_parse_record` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `parse_id` CHAR(36) NOT NULL COMMENT '对外解析ID(UUID)',
  `file_id` BIGINT UNSIGNED NOT NULL COMMENT '关联文件主键',
  `parse_status` VARCHAR(32) NOT NULL DEFAULT 'RUNNING',
  `chunk_count` INT NOT NULL DEFAULT 0,
  `vector_count` INT NOT NULL DEFAULT 0,
  `embedding_model` VARCHAR(128) DEFAULT NULL,
  `vector_collection` VARCHAR(128) DEFAULT NULL,
  `chunk_size` INT DEFAULT NULL,
  `chunk_overlap` INT DEFAULT NULL,
  `started_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `finished_at` DATETIME DEFAULT NULL,
  `duration_ms` BIGINT DEFAULT NULL,
  `error_message` TEXT DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_kb_parse_record_parse_id` (`parse_id`),
  KEY `idx_kb_parse_record_file_id` (`file_id`),
  KEY `idx_kb_parse_record_status` (`parse_status`),
  CONSTRAINT `fk_kb_parse_record_file_id`
    FOREIGN KEY (`file_id`) REFERENCES `kb_file` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 为什么要单独建解析记录表

因为同一个文件可能出现这些情况：

- 第一次解析失败
- 第二次重试成功
- 后面更新文件后再次重建索引

如果只用一张表，你只能看到当前状态，看不到过程。

## 7. 推荐状态流转

建议分两套状态：

### 上传状态 `upload_status`

- `RECEIVED`：请求已接收，数据库记录已创建
- `SAVED`：文件已成功写入本地
- `FAILED`：上传阶段失败

### 解析状态 `parse_status`

- `PENDING`：尚未开始解析
- `RUNNING`：正在切片、生成向量、写入 Qdrant
- `SUCCESS`：解析完成
- `FAILED`：解析失败

推荐流转顺序：

1. 创建 `kb_file`，状态 `RECEIVED + PENDING`
2. 文件成功落盘后，更新为 `SAVED`
3. 创建 `kb_parse_record`，状态 `RUNNING`
4. 调用向量索引逻辑
5. 成功则回写 `SUCCESS`
6. 失败则回写 `FAILED` 和错误信息

## 8. 依赖怎么加

文件：`app/pyproject.toml`

当前项目已经有：

- `sqlalchemy`

但还没有 MySQL 驱动。

建议新增：

```toml
"pymysql>=1.1.1",
```

如果后面要正式管理表结构迁移，再加：

```toml
"alembic>=1.17.0",
```

### 为什么这里推荐 PyMySQL

因为你当前上传链路整体是同步式的：

- 本地写文件是同步
- 文本读取是同步
- 切片和写向量也是同步调用风格

所以这里优先推荐“同步 SQLAlchemy + PyMySQL”，改动最小。

## 9. 配置怎么加

文件：`app/core/config.py`

建议新增配置：

```python
mysql_url: str = ""
sqlalchemy_echo: bool = False
upload_dir: str = str((BASE_DIR.parent / "uploads").resolve())
```

`.env` 文件在当前项目里是：

- `app/core/.env`

建议增加：

```env
MYSQL_URL=mysql+pymysql://root:password@127.0.0.1:3306/jarvis_agent?charset=utf8mb4
SQLALCHEMY_ECHO=false
UPLOAD_DIR=D:/Projects/ai/jarvis-agent/app/uploads
```

### 为什么顺手把上传目录也配置化

现在代码里用的是 `Path("./uploads")`。这是相对路径，依赖启动目录。

如果你换目录启动服务，真实落盘位置可能会变化。对文件记录来说，这不稳定。

## 10. 建议新增的文件

建议在 `app/db/` 和 `app/services/` 下补这些文件：

- `app/db/base.py`
- `app/db/session.py`
- `app/db/models/__init__.py`
- `app/db/models/knowledge_file.py`
- `app/db/models/knowledge_parse_record.py`
- `app/db/init_db.py`
- `app/services/knowledge_record_service.py`

职责建议如下：

- `base.py`：SQLAlchemy Base
- `session.py`：engine、session 工厂、事务上下文
- `models/*.py`：ORM 模型
- `init_db.py`：初始化建表
- `knowledge_record_service.py`：封装上传记录和解析记录的数据库操作

## 11. 数据库层推荐写法

### 11.1 `app/db/base.py`

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

### 11.2 `app/db/session.py`

```python
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings


engine = create_engine(
    settings.mysql_url,
    echo=settings.sqlalchemy_echo,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### 为什么推荐 `session_scope()`

你当前项目不是“严格按 FastAPI 依赖注入组织的数据库请求模型”，而是服务之间直接调用更多。

所以这里用显式事务上下文最贴合现状，改动也最小。

## 12. ORM 模型建议

### `knowledge_file.py`

至少包含这些字段：

- `id`
- `biz_id`
- `original_name`
- `storage_name`
- `storage_path`
- `file_ext`
- `mime_type`
- `file_size`
- `content_hash`
- `upload_status`
- `parse_status`
- `latest_parse_id`
- `error_message`
- `created_at`
- `updated_at`

### `knowledge_parse_record.py`

至少包含这些字段：

- `id`
- `parse_id`
- `file_id`
- `parse_status`
- `chunk_count`
- `vector_count`
- `embedding_model`
- `vector_collection`
- `chunk_size`
- `chunk_overlap`
- `started_at`
- `finished_at`
- `duration_ms`
- `error_message`
- `created_at`
- `updated_at`

## 13. 初始化建表

文件：`app/db/init_db.py`

可以先用最简单的方式：

```python
from db.base import Base
from db.session import engine
from db.models.knowledge_file import KnowledgeFile
from db.models.knowledge_parse_record import KnowledgeParseRecord


def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
```

### 说明

- 开发阶段：`create_all()` 足够
- 生产阶段：建议改用 Alembic

## 14. 业务服务怎么拆

建议新增：

- `app/services/knowledge_record_service.py`

这个服务不要做向量化，只负责数据库记录。

建议至少提供这些方法：

1. `create_file_record(...)`
2. `mark_upload_saved(...)`
3. `mark_upload_failed(...)`
4. `create_parse_record(...)`
5. `mark_parse_success(...)`
6. `mark_parse_failed(...)`

### 为什么要单独拆一个 service

因为后面这些场景都会复用同一套记录逻辑：

- 上传文件
- 重试解析
- 删除文件
- 重建索引
- 查询历史

如果把数据库操作散写在 API 里，后面会很乱。

## 15. 现有文件具体怎么改

这部分是最关键的。

### 15.1 修改 `app/api/file.py`

这是接入 MySQL 的第一入口。

建议改成下面这条顺序：

1. 校验文件名
2. 校验扩展名
3. 读取文件内容
4. 校验文件大小
5. 计算 `content_hash`
6. 生成 `biz_id`
7. 生成唯一 `storage_name`
8. 先创建一条 `kb_file`
9. 把文件写入磁盘
10. 更新 `upload_status=SAVED`
11. 创建一条 `kb_parse_record`
12. 调用 `vector_index_service.index_single_file(...)`
13. 成功则回写成功状态
14. 失败则回写失败状态和错误信息

### 为什么不要继续直接用原文件名落盘

现在代码里同名文件会覆盖旧文件。

这会带来几个问题：

- 历史记录失真
- 很难做版本管理
- MySQL 中的 `file_path` 可能无法代表当时那份真实文件

更稳的方式是：

```python
storage_name = f"{biz_id}{suffix}"
```

然后：

- `original_name` 保存用户上传名
- `storage_name` 保存真实物理文件名
- `storage_path` 保存真实路径

### `app/api/file.py` 的伪代码

```python
content = await file.read()
suffix = Path(file.filename).suffix.lower()
content_hash = sha256(content).hexdigest()
biz_id = str(uuid.uuid4())
storage_name = f"{biz_id}{suffix}"
storage_path = upload_dir / storage_name

file_record = knowledge_record_service.create_file_record(
    biz_id=biz_id,
    original_name=file.filename,
    storage_name=storage_name,
    storage_path=str(storage_path),
    file_ext=suffix,
    file_size=len(content),
    content_hash=content_hash,
    upload_status="RECEIVED",
    parse_status="PENDING",
)

try:
    storage_path.write_bytes(content)
    knowledge_record_service.mark_upload_saved(file_record.id)

    parse_record = knowledge_record_service.create_parse_record(
        file_id=file_record.id,
        parse_status="RUNNING",
    )

    result = vector_index_service.index_single_file(
        file_path=storage_path,
        file_id=file_record.id,
        file_biz_id=file_record.biz_id,
        parse_record_id=parse_record.id,
        parse_id=parse_record.parse_id,
        content_hash=content_hash,
    )

    knowledge_record_service.mark_parse_success(
        file_id=file_record.id,
        parse_record_id=parse_record.id,
        chunk_count=result.chunk_count,
        vector_count=result.vector_count,
    )
except Exception as e:
    knowledge_record_service.mark_parse_failed(
        file_id=file_record.id,
        parse_record_id=parse_record.id if 'parse_record' in locals() else None,
        error_message=str(e),
    )
    raise
```

### 一个关键原则

不要试图把“写文件、调 embedding、写 Qdrant、写 MySQL”包成一个数据库事务。

原因是：

- 文件系统不可回滚
- 外部模型调用不可回滚
- Qdrant 也不是 MySQL 事务的一部分

这里应该采用“阶段性落状态”的思路，而不是追求伪事务。

### 15.2 修改 `app/services/vector_index_service.py`

这层当前只负责执行，没有结构化返回值。

但接入 MySQL 后，上传接口需要知道：

- 切了多少块
- 写了多少向量
- 是否成功

所以建议把 `index_single_file()` 改成返回一个结果对象。

推荐：

```python
from dataclasses import dataclass


@dataclass
class IndexResult:
    normalized_path: str
    chunk_count: int
    vector_count: int
    vector_ids: list[str]
```

然后把方法签名改成类似这样：

```python
def index_single_file(
    self,
    file_path: str,
    file_id: int,
    file_biz_id: str,
    parse_record_id: int,
    parse_id: str,
    content_hash: str,
) -> IndexResult:
```

### 为什么要把这些 ID 继续往下传

因为建议你把这些标识也写进每个分片的 metadata：

- `_file_id`
- `_file_biz_id`
- `_parse_record_id`
- `_parse_id`
- `_content_hash`

这样后续才能做到：

- 按文件删除旧向量
- 定位某次解析到底写入了什么
- 让 Qdrant 和 MySQL 里的记录能对上

### 这一层的处理顺序建议

1. 读取文件内容
2. 调用切片服务
3. 给每个 `doc.metadata` 补充文件和解析标识
4. 调用 `vector_store_manager.add_documents(docs)`
5. 返回 `IndexResult`

示意代码：

```python
docs = document_split_service.split_document(content, normalized_path)

for doc in docs:
    doc.metadata["_file_id"] = file_id
    doc.metadata["_file_biz_id"] = file_biz_id
    doc.metadata["_parse_record_id"] = parse_record_id
    doc.metadata["_parse_id"] = parse_id
    doc.metadata["_content_hash"] = content_hash

vector_ids = vector_store_manager.add_documents(docs) if docs else []

return IndexResult(
    normalized_path=normalized_path,
    chunk_count=len(docs),
    vector_count=len(vector_ids),
    vector_ids=vector_ids,
)
```

### 15.3 修改 `app/services/document_split_service.py`

这层不是必须改，但建议做两种方案里的其中一种。

#### 方案 A：最小改动

不改切片服务签名。

切完之后，在 `vector_index_service` 里给 `doc.metadata` 补充字段。

#### 方案 B：更干净

给 `split_text()`、`split_markdown()`、`split_document()` 增加 `extra_metadata` 参数。

例如：

```python
def split_document(
    self,
    content: str,
    file_path: str = "",
    extra_metadata: dict | None = None,
) -> list[Document]:
```

这样切片服务内部就能统一合并 metadata。

### 为什么这层不是必须改

MySQL 接入的核心不在切片本身，而在：

- 上传入口建记录
- 索引服务返回结果
- 解析状态回写数据库

### 15.4 修改 `app/services/vector_store_manager.py`

这里当前已经有一个很有用的能力：

```python
add_documents() -> List[str]
```

也就是它已经会返回向量 ID 列表。

这很好，因为你可以直接用：

- `len(vector_ids)` 作为 `vector_count`
- `vector_ids` 作为后续排查依据

### 这里建议再补一个能力：删除旧向量

当前代码里，同一个文件重复上传时，旧向量并不会自动删。

结果就是：

- Qdrant 里会堆叠旧版本内容
- 检索结果可能混入历史内容

建议增加一个“按文件标识删除旧向量”的能力，例如按 `_file_id` 或 `_file_biz_id` 删除。

这一步虽然不是 MySQL 必需项，但非常建议一起规划。

### 15.5 修改 `app/main.py`

这里有两个选择：

#### 选择 A：启动时自动建表

优点：开发方便  
缺点：生产环境不够规范

#### 选择 B：手动执行初始化脚本

优点：更可控  
缺点：部署时要多一步

如果你后面准备接 Alembic，我更建议选择 B。

## 16. 前端如果也要显示真实历史记录

如果只是把数据写进 MySQL，但前端不改，那么页面刷新后还是看不到历史上传记录。

因为现在 `frontend/chat.html` 里的上传记录只是 DOM 状态，不是后端返回的历史数据。

如果要真正显示历史记录，建议后续补两个接口：

1. `GET /api/v1/knowledge/files`
2. `GET /api/v1/knowledge/files/{biz_id}/parse-records`

然后前端在进入知识库页时主动请求这些接口。

## 17. 建议的落地顺序

不要一口气全改，按下面顺序做最稳：

1. 给 `app/pyproject.toml` 增加 `pymysql`
2. 给 `app/core/config.py` 增加 `mysql_url` 和 `upload_dir`
3. 在 `app/db/` 下补 `base.py`、`session.py`、`models`
4. 先把建表跑通
5. 新增 `knowledge_record_service.py`
6. 修改 `app/api/file.py`，先打通上传记录落库
7. 修改 `vector_index_service.py`，让它返回结构化结果
8. 补解析成功和失败的状态回写
9. 再处理删除旧向量
10. 最后补查询接口和前端展示

## 18. 你需要改动的文件清单

### 新增文件

- `app/db/base.py`
- `app/db/session.py`
- `app/db/models/__init__.py`
- `app/db/models/knowledge_file.py`
- `app/db/models/knowledge_parse_record.py`
- `app/db/init_db.py`
- `app/services/knowledge_record_service.py`

### 修改文件

- `app/pyproject.toml`
- `app/core/config.py`
- `app/api/file.py`
- `app/services/vector_index_service.py`
- `app/services/document_split_service.py`（可选）
- `app/services/vector_store_manager.py`（建议）
- `app/main.py`（可选）
- `frontend/chat.html`（如果你要展示历史记录）

## 19. 最小可行版本

如果你想先做一个最小版本，建议先完成这些：

- 建 `kb_file`
- 建 `kb_parse_record`
- 加 `pymysql`
- 配 `mysql_url`
- 上传时写 `kb_file`
- 解析时写 `kb_parse_record`
- 成功失败状态回写

下面这些可以放第二阶段：

- Alembic
- 前端历史列表
- 删除旧向量
- 去重策略
- 重试接口
- 删除文件接口

## 20. 联调验证怎么做

建议至少验证下面这些点：

1. 上传一个 `txt` 文件
2. 确认 `kb_file` 有记录
3. 确认 `upload_status=SAVED`
4. 确认 `kb_parse_record` 有记录
5. 确认 `parse_status=SUCCESS`
6. 确认 `chunk_count > 0`
7. 确认 `vector_count > 0`
8. 再上传一个同名文件，确认不会覆盖历史记录
9. 人为制造一次解析失败，确认 MySQL 能看到错误信息

可直接用下面两条 SQL 检查：

```sql
SELECT
  id,
  biz_id,
  original_name,
  upload_status,
  parse_status,
  created_at
FROM kb_file
ORDER BY id DESC;
```

```sql
SELECT
  id,
  parse_id,
  file_id,
  parse_status,
  chunk_count,
  vector_count,
  started_at,
  finished_at,
  error_message
FROM kb_parse_record
ORDER BY id DESC;
```

## 21. 最后的实现原则

这次改造的重点，不是“把 MySQL 硬塞进上传接口”，而是把职责拆干净：

1. MySQL 负责记录
2. Qdrant 负责向量
3. 本地磁盘负责原文件
4. 上传接口负责状态串联
5. 索引服务负责返回解析结果
6. metadata 要带上文件和解析标识

按这个思路改完，后续再做这些功能会顺很多：

- 上传历史
- 失败重试
- 删除文件
- 重建索引
- 向量去重
- 后台统计
