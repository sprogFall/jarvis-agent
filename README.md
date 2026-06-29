<div align="center">

# Jarvis-Agent

**基于 LangGraph 的企业级 RAG 知识库智能助手**

混合检索 · 多模态文档解析 · 流式对话 · 会话持久化

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-ff6b6b.svg)](https://langchain-ai.github.io/langgraph/)
[![LangChain](https://img.shields.io/badge/LangChain-1.3+-1c3c3c.svg)](https://www.langchain.com/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-DC382D.svg?logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![Redis](https://img.shields.io/badge/Redis-Checkpointer-DC382D.svg?logo=redis&logoColor=white)](https://redis.io/)
[![MySQL](https://img.shields.io/badge/MySQL-8.x-4479A1.svg?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![uv](https://img.shields.io/badge/uv-Package_Manager-de5c77.svg?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)]()

</div>

---

## 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [设计亮点](#设计亮点)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [配置说明](#配置说明)
- [API 一览](#api-一览)
- [Roadmap](#roadmap)
- [更新记录](#更新记录)
- [许可协议](#许可协议)

---

## 项目简介

Jarvis-Agent 是一个开箱即用的 **RAG（Retrieval-Augmented Generation）知识库智能助手**。用户上传企业或个人文档后，即可获得一个能够**精准引用来源、支持多轮对话、可追溯会话历史**的 AI 助手。

它不只是一个"向量库 + LLM"的 Demo，而是在工程上做了完整闭环：

```
文档上传 → 自动解析（含扫描件 OCR）→ 智能分片 → 向量化入库
    ↓
用户提问 → Agent 自主决策 → 混合检索 → Rerank 精排 → 引用式回答
    ↓
全程会话持久化，刷新页面、重启服务都不丢上下文
```

适用于企业内部知识库、技术文档问答、个人资料助理等场景。

---

## 功能特性

### 智能对话

| 能力 | 说明 |
| --- | --- |
| **Agent 自主检索** | 基于 LangGraph `create_agent`，由 LLM 自主判断是否调用知识库工具，避免无意义检索 |
| **流式响应** | SSE（Server-Sent Events）流式输出，首字延迟低，支持长回答 |
| **多轮对话** | 基于 Redis Checkpoint 的会话状态持久化，支持跨会话、跨重启的上下文延续（默认 7 天 TTL） |
| **引用规范** | 回答自动以 `[1][2]` 角标标注来源，并在末尾生成"参考来源"板块 |
| **会话管理** | 多会话切换、会话列表、会话重启、会话删除，首条消息自动摘要为会话标题 |

### 知识库检索

| 能力 | 说明 |
| --- | --- |
| **混合检索（Hybrid Search）** | 向量检索 + BM25 关键词检索，通过 **RRF（Reciprocal Rank Fusion）** 融合排序 |
| **中文优化 BM25** | jieba 分词 + 字符 bigram 补充，针对人名等未登录词显著提升 IDF 区分度 |
| **Rerank 精排** | 基于 Qwen3-Reranker 对 RRF 结果二次排序，提升 Top-K 准确率 |
| **可配置检索策略** | 支持纯向量 / 混合检索切换，权重、Top-K、候选数均可通过 `.env` 调节 |
| **优雅降级** | BM25 未就绪自动回退纯向量检索；Rerank 失败自动回退 Top-K 截断 |

### 文档处理

| 能力 | 说明 |
| --- | --- |
| **多格式支持** | TXT、Markdown、PDF、PNG、JPG/JPEG |
| **扫描件 OCR** | 自动识别 PDF 是否为扫描件（空页占比 ≥ 50% 判定），调用 PaddleOCR-VL 进行版面识别并提取 Markdown |
| **智能分片** | Markdown 按 H1/H2 标题分片，普通文本递归字符分片，保留标题层级上下文 |
| **增量索引** | 基于文件 MD5 哈希去重，重复上传自动跳过，同名变更自动覆盖向量 |
| **文档管理** | 文档列表查询（模糊搜索）、按文档删除（同时清理向量索引和本地文件） |

---

## 技术栈

### 后端

| 分类 | 技术 | 用途 |
| --- | --- | --- |
| **Web 框架** | FastAPI + Uvicorn | 高性能异步 API，支持 SSE 流式响应 |
| **Agent 框架** | LangGraph (`create_agent`) | Agent 编排、工具调用、消息流转 |
| **LLM 接入** | LangChain + OpenAI 兼容接口 | 支持 DeepSeek、Qwen 等任意 OpenAI 兼容模型 |
| **向量数据库** | Qdrant | 高性能 ANN 向量检索，支持 Payload 过滤与索引 |
| **Embedding** | OpenAI 兼容 Embedding | 默认 Qwen3-Embedding-8B（4096 维） |
| **关键词检索** | rank-bm25 + jieba | BM25 稀疏检索，中文分词优化 |
| **Rerank** | Qwen3-Reranker（HTTP API） | 检索结果精排 |
| **会话持久化** | LangGraph Redis Checkpoint (`AsyncRedisSaver`) | Agent 状态持久化到 Redis |
| **关系数据库** | MySQL + SQLAlchemy 2.0 + PyMySQL | 文档记录、会话/消息持久化 |
| **OCR** | PaddleOCR-VL（HTTP API） | 扫描件、图片文字识别 |
| **PDF 解析** | pypdf | PDF 文本提取与扫描件判定 |
| **配置管理** | pydantic-settings + python-dotenv | 类型安全的环境变量配置 |
| **日志** | loguru | 结构化日志 |
| **依赖管理** | uv | 极速的 Python 包管理器 |

### 前端

单文件 `frontend/chat.html`，零构建依赖，CDN 引入：

- **marked.js**：Markdown 渲染
- **highlight.js**：代码高亮
- 原生 SSE `EventSource`：流式接收
- 双 Tab 布局：💬 聊天 / 📚 知识库

### 基础设施

- Python 3.13+
- Redis 7.x（Checkpointer）
- MySQL 8.x（业务记录）
- Qdrant 1.x（向量库）

---

## 设计亮点

### 1. Agent 自主决策，按需检索

并非每轮对话都触发检索。基于 LangGraph `create_agent`，由 LLM 根据用户意图自主判断是否调用 `retrieve_knowledge` 工具，闲聊无需检索，专业知识才入知识库，兼顾响应速度与准确性。

### 2. 混合检索 + RRF 融合排序

向量检索擅长语义匹配，BM25 擅长关键词命中，二者互补。通过 **RRF（Reciprocal Rank Fusion）** 公式 `score = Σ wᵢ / (60 + rankᵢ)` 融合两路结果，权重可通过 `vector_weight` 灵活调节。

### 3. 中文 BM25 的 bigram 增强

`jieba` 对未登录词（如人名"章佳豪"）会被切成单字，导致 IDF 区分度不足。在 jieba 词结果之上额外补充**字符 bigram**（"章佳"、"佳豪"），这类组合在语料中极罕见，命中时 BM25 分数显著拉开，有效提升短词与人名的召回准确率。

### 4. 三级检索流水线，逐级精排

```
向量检索 (k=10) ┐
                ├→ RRF 融合 → Rerank (候选 20) → Top-K (k=5) → LLM
BM25 检索 (k=10)┘
```

每一级均可通过 `.env` 独立配置，且每级都设有降级策略，保证可用性。

### 5. 双层持久化架构

- **Redis**：LangGraph Checkpoint，保存 Agent 运行时状态（消息序列、工具调用），实现跨重启的上下文延续
- **MySQL**：业务层持久化，保存会话元信息、消息记录、文档索引记录，支持历史回溯与管理

两层各司其职，Checkpoint 负责实时续接，MySQL 负责可查询的业务数据。

### 6. 增量索引与一致性保障

文件上传时计算 MD5 哈希，与数据库记录比对：

- 文件名 + 哈希一致 → 跳过，避免重复索引
- 文件名相同但哈希变更 → 先删除旧向量，再重新索引，保证一致性

### 7. 扫描件智能识别

PDF 解析时统计空页占比，当超过 50% 页面无法提取文本时自动判定为扫描件，无缝切换至 PaddleOCR-VL 进行版面识别，输出结构化 Markdown，无需人工干预。

### 8. 全链路可观测

`debug=True` 时，检索阶段会打印每篇文档的 RRF 分数、来源通道（vector/bm25）、Rerank 前后排名对比，便于调参与问题定位。

---

## 快速开始

### 环境要求

| 组件 | 版本 | 说明 |
| --- | --- | --- |
| Python | ≥ 3.13 | 推荐 3.13+ |
| uv | latest | 依赖管理工具 |
| Redis | ≥ 7.x | Agent 会话持久化 |
| MySQL | ≥ 8.x | 业务数据存储 |
| Qdrant | ≥ 1.x | 向量数据库 |

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/jarvis-agent.git
cd jarvis-agent
```

### 2. 安装依赖

```bash
# 安装 uv（如未安装）
pip install uv

# 进入应用目录并同步依赖
cd app
uv sync
```

### 3. 准备基础设施

启动 Redis、MySQL、Qdrant 服务，并创建数据库：

```sql
CREATE DATABASE `jarvis-agent` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

> 数据表会在应用首次启动时通过 `Base.metadata.create_all` 自动创建。

### 4. 配置环境变量

在 `app/core/` 目录下创建 `.env` 文件：

```dotenv
# ===== LLM 配置 =====
ai_base_url=https://api.deepseek.com
ai_api_key=your-api-key
ai_model=deepseek-chat
ai_temperature=0.7

# ===== Embedding 配置 =====
embedding_model=Qwen/Qwen3-Embedding-8B
embedding_api_key=your-embedding-api-key
embedding_api_base=https://api.siliconflow.cn/v1
embedding_dimension=4096

# ===== Rerank 配置 =====
rerank_enabled=True
rerank_api_url=https://api.siliconflow.cn/v1/rerank
rerank_api_key=your-rerank-api-key
rerank_model=Qwen/Qwen3-Reranker-8B
rerank_candidate_k=20

# ===== Qdrant 配置 =====
qdrant_url=http://localhost:6333
qdrant_api_key=

# ===== Redis 配置 =====
redis_conn_string=redis://localhost:6379/0

# ===== MySQL 配置 =====
mysql_url=mysql+pymysql://root:password@localhost:3306/jarvis-agent?charset=utf8mb4

# ===== OCR 配置 =====
ocr_enabled=True
ocr_api_url=https://paddleocr.aistudio-app.com/api/v2/ocr/jobs
ocr_api_key=your-ocr-api-key
ocr_model=PaddleOCR-VL-1.6

# ===== 检索策略 =====
hybrid_search_enabled=True
vector_search_k=10
bm25_search_k=10
final_top_k=5
vector_weight=0.5

# ===== 其他 =====
stream_chunk_timeout=300
sqlalchemy_echo=False
debug=False
```

### 5. 启动服务

```bash
cd app
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. 访问应用

打开 `frontend/chat.html` 即可使用，或在浏览器中直接访问该 HTML 文件。

服务启动后可访问以下地址：

- API 文档（Swagger）：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

---

## 项目结构

```
jarvis-agent/
├── app/                        # 后端应用主目录
│   ├── api/                    # API 路由层
│   │   ├── chat.py             # 对话接口（普通 + 流式）
│   │   ├── file.py             # 文件上传与文档管理
│   │   ├── chat_history.py     # 会话与消息管理
│   │   └── router.py           # 路由聚合
│   ├── core/                   # 核心配置
│   │   ├── config.py           # 全局配置（pydantic-settings）
│   │   └── .env                # 环境变量（不入库）
│   ├── db/                     # 数据库层
│   │   ├── base.py             # ORM 基类（含时间戳字段）
│   │   └── session.py          # 引擎与会话工厂
│   ├── model/                  # 数据模型（SQLAlchemy）
│   │   ├── document.py         # 知识库文档记录表
│   │   └── chat.py             # 会话表 + 消息表
│   ├── schema/                 # 请求/响应模型
│   │   └── request.py          # Pydantic 请求体
│   ├── services/               # 业务服务层
│   │   ├── ai_chat_service.py     # Agent 编排与对话
│   │   ├── vector_index_service.py# 文件读取 → 解析 → 索引
│   │   ├── vector_store_manager.py# Qdrant + BM25 管理
│   │   ├── document_split_service.py# 文档智能分片
│   │   ├── rerank_service.py      # Rerank 精排
│   │   ├── ocr_service.py         # OCR 识别
│   │   ├── chat_history_service.py# 会话/消息持久化
│   │   └── document_record_service.py# 文档记录管理
│   ├── tools/                  # Agent 工具
│   │   └── knowledge_tool.py   # 知识库检索工具（混合检索）
│   ├── uploads/                # 上传文件存储
│   ├── test/                   # 测试目录
│   ├── main.py                 # 应用入口（FastAPI app）
│   ├── pyproject.toml          # 依赖声明
│   └── uv.lock                 # 依赖锁定
├── frontend/
│   └── chat.html               # 单文件前端（聊天 + 知识库）
├── MYSQL_KNOWLEDGE_BASE_INTEGRATION.md  # MySQL 接入说明
└── README.md
```

---

## 配置说明

所有配置通过环境变量注入，定义于 `app/core/config.py`，读取 `app/core/.env`。

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `ai_base_url` / `ai_api_key` / `ai_model` | - | LLM 接入地址、密钥、模型名 |
| `ai_temperature` | `0.7` | 采样温度 |
| `embedding_*` | - | Embedding 模型与维度 |
| `rerank_enabled` | `True` | 是否启用 Rerank |
| `rerank_candidate_k` | `20` | 送入 Rerank 的候选数 |
| `qdrant_url` / `qdrant_api_key` | - | Qdrant 连接信息 |
| `redis_conn_string` | - | Redis 连接字符串 |
| `mysql_url` | - | MySQL 连接字符串 |
| `ocr_enabled` | `True` | 是否启用 OCR |
| `hybrid_search_enabled` | `True` | 是否启用混合检索（False 则纯向量） |
| `vector_weight` | `0.5` | 向量检索权重，BM25 权重 = 1 - 此值 |
| `vector_search_k` / `bm25_search_k` | `10` | 各检索器返回数量 |
| `final_top_k` | `5` | 最终送入 LLM 的文档数 |
| `chunk_max_size` / `chunk_overlap` | `800` / `100` | 分片大小与重叠 |
| `stream_chunk_timeout` | `300` | 流式 chunk 超时（秒） |
| `debug` | `False` | 调试模式，打印检索明细 |

---

## API 一览

所有接口统一前缀 `/api/v1`。

### 对话

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/chat` | 普通对话（非流式） |
| `POST` | `/stream_chat` | 流式对话（SSE） |

### 会话管理

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/sessions` | 创建新会话 |
| `GET` | `/sessions` | 获取会话列表 |
| `GET` | `/sessions/{id}/messages` | 获取会话消息列表 |
| `DELETE` | `/sessions/{id}` | 删除会话 |
| `POST` | `/sessions/{id}/restart` | 重启会话 |

### 知识库

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/upload` | 上传文档并自动创建向量索引 |
| `GET` | `/documents` | 查询文档列表（支持模糊搜索） |
| `DELETE` | `/documents/{id}` | 删除文档（含向量与本地文件） |

### 其他

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 健康检查 |

> 完整的请求/响应结构请访问 `/docs` 查看 Swagger 文档。

---

## Roadmap

- [ ] 文档分片合并策略优化（过小分片自动合并）
- [ ] 支持更多文档格式（DOCX、PPTX、XLSX）
- [ ] 多知识库/多集合管理
- [ ] 检索效果评测面板
- [ ] Docker Compose 一键部署
- [ ] 流式响应中断恢复

---

## 更新记录

### v0.1.0 — 2026-06-29

首次发布。

#### 新增

- **智能对话**：基于 LangGraph `create_agent` 的 Agent 自主检索，SSE 流式响应，Redis Checkpoint 多轮会话持久化，回答自动生成引用角标与参考来源
- **混合检索**：向量检索 + BM25 关键词检索，RRF 融合排序；中文 BM25 采用 jieba 分词 + 字符 bigram 增强，提升未登录词 IDF 区分度
- **Rerank 精排**：基于 Qwen3-Reranker 对 RRF 结果二次排序，支持优雅降级
- **文档处理**：支持 TXT / Markdown / PDF / PNG / JPG；扫描件自动识别并调用 PaddleOCR-VL；Markdown 按 H1/H2 标题分片，普通文本递归字符分片；基于 MD5 哈希的增量索引去重
- **知识库管理**：文档上传、列表查询（模糊搜索）、按文档删除（同步清理向量与本地文件）
- **会话管理**：多会话切换、列表、重启、删除，首条消息自动摘要为会话标题
- **持久化**：MySQL 存储文档记录、会话与消息；Redis 存储 Agent 运行时状态
- **前端**：单文件 `chat.html`，零构建依赖，双 Tab 布局（聊天 / 知识库）
- **配置**：pydantic-settings 类型安全配置，全链路检索参数可调，debug 模式打印检索明细

---

## 许可协议

本项目基于 [MIT License](LICENSE) 开源，欢迎自由使用与贡献。
