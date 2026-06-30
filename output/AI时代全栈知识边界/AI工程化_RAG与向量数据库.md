---
title: AI时代全栈知识边界·29|RAG与向量数据库
book: AI时代全栈知识边界
chapter: AI工程化
event: RAG与向量数据库
sort: 2
chapter_sort: 14
created_at: 2026-06-30
source_agents: [fullstack-expert]
---
# AI时代全栈知识边界·29|RAG与向量数据库

> 前置知识:读过本专栏第 28 章「Prompt 工程基础」、理解 LLM 输入输出是文本到文本的函数调用、能读 Python 基本语法、知道向量与余弦相似度的几何含义
> 学完你能:① 一句话讲清 RAG(Retrieval-Augmented Generation,检索增强生成)的本质与完整七步流程 ② 区分 RAG 与 Fine-tuning(微调)各自的适用场景,不再"什么都去训一遍" ③ 解释 Embedding(向量表示)为何能捕捉语义、ANN(Approximate Nearest Neighbor,近似最近邻)为何牺牲精度换速度 ④ 在 FAISS / Milvus / Pinecone / Chroma / pgvector 之间按场景选型 ⑤ 用 LangChain 写出最小可运行的 RAG 流程,并叠加 Hybrid Retrieval(混合检索)与 Reranking(重排) ⑥ 判断知识库搭建里哪些环节能交给 AI、哪些必须自己握住

### 一、概念

RAG 的一句话定义:**在 LLM 生成之前,先从外部知识库检索相关片段,把片段拼进 Prompt,让模型"开卷答题"**。它的核心动机是弥补 LLM 参数化知识的两个先天缺陷——训练数据有截止时间(过时)、训练语料有盲区(企业内部文档模型从没见过)。

先对齐术语。Embedding 是把文本映射成固定维度的浮点向量,语义相近的文本向量在空间里也相近。Vector Database(向量数据库)是专门存储与检索这些向量的系统。Chunking(切分)是把长文档切成可被检索的小段落。Cosine Similarity(余弦相似度)是衡量两个向量方向一致性的指标,取值 -1 到 1,越接近 1 越相似。Fine-tuning 是在预训练模型权重之上继续训练,把新知识"焊"进参数。Reranking 是用更重但更准的模型对初筛候选重新打分排序。

理解 RAG 的关键,是分清"知识"存在哪里。LLM 的参数化知识存在模型权重里,更新一次要重训或微调,成本极高;RAG 把知识存在外部文档库里,更新一次只是增删几个文件。前者像是把答案背进脑子里,后者像是带一本可随时翻阅的参考书进考场。考场规则允许翻书,且参考书可以随时换新版——这就是 RAG 在工程上胜过 Fine-tuning 的根本原因。

### 二、原理

#### 1. 为什么不能直接 Fine-tune

很多人遇到"模型不知道公司内部知识"的第一反应是去微调。这条路在特定场景下成立,但在"知识更新频繁、来源需要可追溯"的场景里几乎是错的。三个根本问题。

第一,成本高。Fine-tuning 需要准备上千条高质量样本、租 GPU、调超参,一次完整的微调从准备到上线常以周计;而 RAG 增量知识只需把新文档丢进向量库,分钟级生效。

第二,知识更新慢。Fine-tuning 把知识焊进权重,知识一旦过期(产品手册改版、价格调整、法规更新),要么重训要么忍受模型答错;RAG 改一条文档,下一次检索就拿到新内容。

第三,灾难性遗忘(Catastrophic Forgetting)。在新增知识上微调,模型会部分遗忘旧能力,这是神经网络权重的固有特性,目前没有根治办法。

更关键的是来源可追溯。Fine-tuning 后模型给一个答案,你无法说出它依据哪份文档;RAG 每次检索都返回具体片段,可以连同引用一起输出,在合规、审计、医疗法律等场景是硬要求。

要强调的是,RAG 与 Fine-tuning 并不对立。RAG 解决"知识",Fine-tuning 解决"风格、格式、能力"。让模型用公司口吻写作、固定输出 JSON、学会调用工具,这些是 Fine-tuning(或更轻的 Prompt 工程)的事;让模型知道公司有哪些产品,这是 RAG 的事。两者经常配合使用,不是二选一。

#### 2. Embedding 为什么能捕捉语义

文本能变成向量,且语义相近的文本向量也相近,这不是魔法,是对比学习(Contrastive Learning)训练目标的直接结果。

对比学习的训练信号是"正样本对"与"负样本对"。正样本对是语义相同的文本(如"年假几天"与"每年休假天数"),负样本对是语义无关的文本(如"年假几天"与"今天的天气")。训练时,模型被推动去拉近正样本对的向量、推远负样本对的向量,数百万对样本训练下来,向量空间自然形成"语义聚类"——同义表述聚在一起,无关表述被推开。

衡量"相近"用余弦相似度,而不是欧氏距离。原因是余弦只看向量方向、不看长度,文本长短不一不会影响语义相似度判断;欧氏距离会被向量模长干扰,长文本向量模长偏大,会被错误地判为"远"。

工程上的几个数字要记住。Embedding 维度常见 768、1024、1536,维度越高表达能力越强但存储与检索成本也越高;中文文本大致按"1 字 ≈ 1.5 个 Token,1 个 Token ≈ 1 个向量维度位置"来估算占用,百万级文档入库后向量库占用动辄数 GB。

#### 3. ANN 为什么牺牲一点精度换巨大速度提升

最朴素的检索是暴力 KNN(K-Nearest Neighbors,K 近邻):把查询向量与库里所有向量逐一算余弦相似度,取前 K 个。当库里有百万、千万条向量时,O(N) 的逐一比对根本不可行——单次查询几百毫秒到秒级,无法支撑线上服务。

ANN 的思路是:不追求找到绝对最相似的 K 个,而是找到"大概率很相似"的 K 个,把召回率从 100% 降到 95% 左右,换回数十到数百倍的速度。三种主流算法。

HNSW(Hierarchical Navigable Small World,分层可导航小世界图)把向量组织成多层跳表图,上层稀疏、下层稠密;查询时从顶层入口节点贪心走,逐层下沉,类似地图先看高速路网再看城市道路。它是目前综合性能最好的算法,Chroma、Milvus 默认索引就是它。

IVF(Inverted File,倒排文件)先用 K-means 把向量聚成若干簇,查询时先算查询向量离哪个簇心最近,只在该簇(及邻近几个簇)内做精确搜索。簇数与搜索簇数是可调参数,越大越快但召回越低。

LSH(Locality-Sensitive Hashing,局部敏感哈希)用一类特殊哈希函数,让相似向量大概率落到同一桶里。它实现简单,但在高维空间召回率不如 HNSW,工程上已较少作为首选。

### 三、实践

下面三段代码覆盖最小 RAG、向量库直连、混合检索三种最常见的工程模式。运行环境为 Python 3.10+,依赖 `langchain`、`langchain-openai`、`langchain-chroma`、`chromadb`、`rank-bm25`,Embedding 与 LLM 用 OpenAI 兼容接口(DeepSeek、通义千问改 `base_url` 与 `api_key` 即可复用)。

#### 1. LangChain 实现最小 RAG 流程

这段代码串起完整七步:加载 → 切分 → Embedding → 入库 → 检索 → 拼接 Prompt → LLM 生成。

```python
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# 1. 文档加载
docs = TextLoader("hr_handbook.txt").load()

# 2. 切分:递归切分,优先按段落,再按句
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500, chunk_overlap=50,
    separators=["\n\n", "\n", "。", "!", "?", " "],
)
chunks = splitter.split_documents(docs)

# 3. Embedding + 4. 向量入库
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma.from_documents(chunks, embeddings, persist_directory="./chroma_db")

# 5. 检索器:取相似度最高的 4 条
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

# 6. 拼接 Prompt + 7. LLM 生成
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
template = """你是严谨的问答助手。只根据下面上下文回答,上下文没有就说"我不知道",不要编造。

上下文:
{context}

问题: {question}"""
prompt = ChatPromptTemplate.from_template(template)

def format_docs(docs):
    return "\n\n".join(d.page_content for d in docs)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt | llm | StrOutputParser()
)

print(rag_chain.invoke("公司年假有几天?"))
```

几个工程要点。`chunk_size` 与 `chunk_overlap` 直接决定检索质量:太大切不全语义,太小上下文断裂,经验值 300 到 800 字符、重叠 10% 到 20%。`temperature=0` 让答案稳定可复现。Prompt 里"上下文没有就说不知道"是压制幻觉的关键约束,缺了它模型会拿参数化知识补全,等于绕过了 RAG。

#### 2. Chroma 向量库的简单调用

不依赖 LangChain 时,直接用 Chroma 原生 SDK 更轻量,适合自己实现检索逻辑的场景。

```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="hr_docs")

# 入库:文档、向量、元数据一起存(不传 embeddings 时 Chroma 用默认模型自动算)
collection.add(
    ids=["doc1", "doc2", "doc3"],
    documents=["年假为 10 天,工龄满 5 年增至 15 天", "试用期 3 个月", "病假需提供三甲医院证明"],
    metadatas=[{"category": "leave"}, {"category": "onboarding"}, {"category": "leave"}],
)

# 查询:返回最相似的 2 条,带距离分数
results = collection.query(
    query_texts=["休假怎么算"],
    n_results=2,
    where={"category": "leave"},  # 元数据过滤,先按类别筛再向量检索
)
print(results["documents"])      # [['年假为 10 天...', '病假需提供...']]
print(results["distances"])      # 距离越小越相似
```

`where` 元数据过滤是工程上极有用的能力:先用结构化字段(类别、时间、部门)把候选范围缩小,再在子集里做向量检索,既快又准。这是"结构化过滤 + 语义检索"组合的基础。

#### 3. Hybrid Retrieval 伪代码:向量 + 关键词 + Reranking

纯向量检索对"专有名词、产品型号、错误码"这类精确匹配反而弱——语义相近但型号不同的两条文档,向量距离可能很近。Hybrid Retrieval 把向量检索与关键词检索(BM25)的结果融合,再用交叉编码器重排,是生产 RAG 的标配。

```python
from rank_bm25 import BM25Okapi
from langchain_chroma import Chroma

def hybrid_retrieve(query, vectorstore, all_chunks, top_k=10, final_k=4):
    # 1. 向量检索
    vec_docs = vectorstore.similarity_search_with_score(query, k=top_k)
    # 距离转相似度并归一化到 [0,1]
    vec_scores = {d.page_content: 1 / (1 + s) for d, s in vec_docs}

    # 2. BM25 关键词检索
    tokenized_corpus = [c.split() for c in all_chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    raw = bm25.get_scores(query.split())
    # 归一化,避免量纲与向量分数不可比
    raw = (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)
    bm25_scores = {c: s for c, s in zip(all_chunks, raw)}

    # 3. 分数融合:加权求和,alpha 控制向量权重
    alpha = 0.6
    candidates = set(vec_scores) | set(bm25_scores)
    fused = {
        c: alpha * vec_scores.get(c, 0) + (1 - alpha) * bm25_scores.get(c, 0)
        for c in candidates
    }
    ranked = sorted(fused, key=fused.get, reverse=True)[:top_k]

    # 4. Reranking:用交叉编码器(query+doc 一起编码)重新打分
    pairs = [(query, c) for c in ranked]
    rerank_scores = cross_encoder.predict(pairs)   # 伪代码,可用 bge-reranker 等
    final = [c for _, c in sorted(zip(rerank_scores, ranked), reverse=True)[:final_k]]
    return final
```

`alpha` 是关键调参点:向量擅长语义匹配,关键词擅长精确匹配,通用知识库 0.5 到 0.7 之间起步,型号/代码库场景往 0.3 调以偏向关键词。Reranking 用的交叉编码器(Cross-Encoder)比双塔 Embedding 慢得多,所以只对初筛的小候选集(top_k 通常 10 到 20)重排,不会拖垮延迟。

### 四、速查/自测

#### 向量数据库选型对照表

| 维度 | FAISS | Milvus | Pinecone | Chroma | pgvector |
|---|---|---|---|---|---|
| 形态 | 库(进程内) | 分布式服务 | 全托管云服务 | 嵌入式/本地服务 | PostgreSQL 扩展 |
| 适用规模 | 百万到亿级 | 亿级、分布式 | 中到大规模、免运维 | 万到百万级 | 万到百万级 |
| 持久化 | 需自己落盘 | 原生分布式存储 | 云端托管 | 本地文件 | 复用 PG 存储引擎 |
| 增删改 | 较弱 | 强 | 强 | 中 | 强(事务级) |
| 元数据过滤 | 弱 | 强 | 强 | 中 | 强(SQL WHERE) |
| 运维成本 | 低(无服务) | 高(集群) | 极低(全托管) | 低 | 低(已有 PG 即可) |
| 典型场景 | 离线批量检索、研究 | 大规模生产 RAG | 不想自运维的 SaaS | 原型与中小项目 | 已有 PG、想统一存储 |

一句话选型:**离线研究选 FAISS,大规模生产选 Milvus,不想运维选 Pinecone,原型快速起步选 Chroma,已有 PostgreSQL 想少加一个组件选 pgvector**。

#### 切分策略对照

| 策略 | 优点 | 缺点 | 适用 |
|---|---|---|---|
| 固定长度 | 实现最简单 | 易切断语义 | 兜底方案 |
| 按句/按段 | 保留语义边界 | 长度不均 | 结构化文档 |
| 递归切分 | 自适应分隔符 | 需调分隔符优先级 | 通用首选 |
| 按 Markdown 标题 | 保留文档结构 | 依赖标题规范 | 技术文档、手册 |

#### 自测题

**问题一(原理层):** 为什么企业内部知识更新频繁时,RAG 优于 Fine-tuning?给三条理由。

参考答案:第一,更新成本。Fine-tuning 改知识要重训,以周计;RAG 改一条文档分钟级生效。第二,灾难性遗忘。Fine-tuning 学新知识会损失旧能力,RAG 不动模型权重无此问题。第三,来源可追溯。合规审计要求答案能给出依据文档,Fine-tuning 焊进权重无法溯源,RAG 检索片段可直接引用。

**问题二(原理层):** 余弦相似度为什么比欧氏距离更适合做文本相似度?给一个反例。

参考答案:余弦只看向量方向不看模长,文本长短不影响相似度;欧氏距离受模长干扰,长文本模长大,会被错误判为"远"。反例:一段长摘要与一句短核心句语义完全相同,但欧氏距离可能很大,余弦接近 1。此外,余弦相似度取值归一到 -1 到 1,便于跨模型、跨维度设定统一阈值。

**问题三(实践层):** 写出 `chunk_size` 设过大和过小分别会出现什么问题,以及你如何为一份产品手册选切分参数。

参考答案:过大,一个 chunk 包含多个主题,检索时语义被稀释,召回的片段里真正相关的信息占比低,还可能超出 Embedding 模型长度上限;过小,上下文断裂,模型拿到的片段不足以回答问题,且 chunk 数量爆炸增加存储与检索成本。产品手册通常按 Markdown 标题切分优先,辅以递归切分兜底,`chunk_size` 取 400 到 600 字符,`chunk_overlap` 取 10% 到 20%(约 50 到 100 字符)保证跨 chunk 的句子不被截断,同时给每个 chunk 附加标题路径作为元数据便于过滤。

**问题四(思路层):** 纯向量检索在什么场景下会输给关键词检索?Hybrid Retrieval 的 `alpha` 该往哪边调?

参考答案:涉及精确匹配的场景——产品型号(SKU)、错误码(如 `ERR_4023`)、人名、API 名称、版本号。这些 token 的语义相近性会误导向量检索,把型号不同但描述相似的两条文档都拉近。Hybrid Retrieval 的 `alpha`(向量权重)应往小调,例如 0.3,让 BM25 关键词权重占主导;反之,自然语言问答场景(同义表述多)应往大调,例如 0.7。

**问题五(原理层):** HNSW 牺牲了什么换来速度?为什么召回率掉几个百分点在工程上可接受?

参考答案:HNSW 牺牲的是"绝对最近邻保证"——它通过贪心走图找的是近似最近邻,可能漏掉真正的第 1 名,但 Top-K 里大概率仍包含相关项。工程上可接受,是因为 RAG 下游接的是 LLM,LLM 本身对片段的微小排序差异不敏感,只要相关片段进入上下文就能答对;而召回率从 100% 降到 95% 换来几十倍速度提升,直接决定能否上线。这是"检索质量与延迟"的工程权衡,不是数学最优解。

### 可交给 AI 的部分

本章"必须掌握"的部分是 **RAG 与 Fine-tuning 的场景判断、Embedding 与 ANN 的原理、切分策略与 Hybrid Retrieval 的调参逻辑、知识库治理的取舍**——这些是工程师在白板上能讲清、在故障时能定位的内核,不能外包给 AI。

以下内容可以交给 AI 辅助:

- **向量库完整接入代码**:Chroma / Milvus / pgvector 的连接、建集合、入库、查询样板代码,AI 写得既快又准,工程师只需校对参数。
- **Agent 流程编排代码**:LangChain / LlamaIndex 的 Chain 编排、工具调用、多步推理的脚手架,模板化程度高,适合 AI 起草。
- **Reranking 与 BM25 的样板封装**:交叉编码器调用、分数归一化、加权融合的模板代码,AI 能给出可运行初版。

**风险提示**:

1. **切分策略不能盲信 AI**:AI 倾向给一组通用默认值(如 `chunk_size=1000`),但不同文档结构的最优切分差异极大,手册类按标题切、对话类按轮次切、代码类按函数切。切分错了,后面 Embedding 与检索再先进也救不回来,这是"文档治理 > Embedding 模型选择"的体现。
2. **Embedding 模型选型要人工把关**:AI 不会替你判断该用中英双语模型还是纯英文、维度选 768 还是 1536、是否要支持指令微调的 Embedding(如 BGE)。选错模型,语义相似度计算系统性偏差,召回率上不去,且很难从日志里直接看出是 Embedding 的锅。
3. **知识库治理是必须自握的内核**:文档去重、版本管理、权限隔离(不同用户能检索不同文档)、增量更新与失效清理,这些是 RAG 上线后真正出问题的地方,且涉及业务规则,AI 只能写脚本不能做决策。尤其权限隔离做错会导致越权读到他人文档,是安全红线。
4. **检索效果评估不能交给 AI 自评**:AI 会"觉得自己答得对",必须用人工标注的评测集(QA 对 + 标准答案)算召回率、答案准确率,定期回归。没有评测集的 RAG 等于没有仪表盘的飞机,改一个参数都不知道是变好还是变坏。

区分"能交"与"不能交"的本质是:**接入代码与编排脚本是机械劳动,AI 强;切分、选型、治理、评估是语义判断与业务决策,AI 弱**。把机械劳动交给 AI,把判断留给自己,这是 RAG 工程在 AI 时代必须握住的知识边界。

## 参考来源

- [1] Patrick Lewis 等:《Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks》2020(RAG 的原始论文,定义了检索-生成联合架构)
- [2] Chip Huyen:《Designing Machine Learning Systems》O'Reilly 2022 年版(第 7 章模型部署与第 9 章持续学习,讨论 RAG 在生产中的更新策略)
- [3] 陈冉等:《RAG 实战:检索增强生成从入门到落地》2024(中文 RAG 工程化落地,涵盖切分、Hybrid Retrieval、Reranking 实践)
- [4] LangChain 官方文档:RAG 教程与 Chroma 集成,https://python.langchain.com/docs/tutorials/rag
- [5] LlamaIndex 官方文档:数据连接与检索,https://docs.llamaindex.ai/
- [6] Milvus 官方文档:向量索引与 HNSW/IVF 参数,https://milvus.io/docs/index.md
- [7] Chroma 官方文档:集合与元数据过滤,https://docs.trychroma.com/
- [8] Jeff Johnson 等:《Billion-scale similarity search with GPUs》2019(FAISS 的原始论文,IVF 与乘积量化原理)
- [9] bge-reranker 与 BGE Embedding 模型卡:Hugging Face BAAI/bge 系列,https://huggingface.co/BAAI
- 本专栏第 28 章「Prompt 工程基础」(RAG 的拼接 Prompt 与幻觉压制约束延续自该章的 Prompt 设计原则)
- 本专栏第 02 章「知识边界的第一性原理」(三条判据"错误识别/选型判断/问题定位"在 RAG 工程中延续为可交与必审的分界)
