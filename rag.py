import os
from pathlib import Path

import pdfplumber
import pytesseract
from PIL import Image

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_chroma import Chroma

from ingest import load_txt


# ========================
# 路径配置
# ========================
BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "docs"
PERSIST_DIR = BASE_DIR / "chroma_db"

print("📂 项目目录:", BASE_DIR)
print("📄 文档目录:", DOCS_DIR)
print("🧠 向量库目录:", PERSIST_DIR)


# ========================
# PDF OCR 读取
# ========================
def load_pdf_with_ocr(pdf_path: Path):
    print(f"📕 OCR 读取 PDF: {pdf_path.name}")
    docs = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()

            # 扫描 PDF 兜底 OCR
            if not text or not text.strip():
                image = page.to_image(resolution=300).original
                text = pytesseract.image_to_string(image, lang="chi_sim")

            if text and text.strip():
                docs.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": str(pdf_path),
                            "page": page_num + 1,
                        },
                    )
                )

    return docs


# ========================
# 加载文档
# ========================

#修改路径
DOCS_DIR = Path(DOCS_DIR) 
#========


documents = []

files = os.listdir(DOCS_DIR)
print("发现文件:", files)

for filename in files:
    if filename.startswith("."):
        continue
    if filename.lower().endswith(".pdf"):
        documents.extend(load_pdf_with_ocr(DOCS_DIR / filename))

    elif filename.lower().endswith(".txt"):
        print("👉 命中 TXT:", filename, type(DOCS_DIR))
        documents.extend(load_txt(DOCS_DIR / filename))


print(f"\n✅ 已加载文档数量: {len(documents)}")

# 原文调试

#if documents:
#    print("\n====== 原文调试 ======")
#    print(documents[0].page_content[:800])
#    print("metadata:", documents[0].metadata)
#    print("======================")

#print("\n📄 TXT 内容调试：")
for d in documents:
   #if d.metadata.get("source", "").endswith(".txt"):
        print(d.page_content[:500])
        print("metadata:", d.metadata)



# ========================
# 切分
# ========================
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=80,
)

chunks = splitter.split_documents(documents)
print(f"\n✂️ 切分后 chunk 数量: {len(chunks)}")

if chunks:
    print("\n====== Chunk 示例 ======")
    print(chunks[0].page_content)
    print("========================")


# ========================
# 向量库
# ========================
embeddings = OllamaEmbeddings(model="nomic-embed-text")

vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory=str(PERSIST_DIR),
)

print("\n🎉 向量库构建完成")


# ========================
# 问答（RAG）
# ========================
llm = OllamaLLM(model="qwen2.5:7b-instruct")

retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

print("\n💬 进入问答模式（输入 exit 退出）")

while True:
    query = input("\n❓ 你的问题：").strip()
    if query.lower() in {"exit", "quit"}:
        break

    docs = retriever.invoke(query)

    if not docs:
        print("⚠️ 未检索到相关内容")
        continue

    #context = "\n\n".join(
        #f"【第{d.metadata.get('page')}页】{d.page_content}"
        #for d in docs
    #)



    # 去重 + 合并上下文
    seen = set()
    context = ""
    sources = set()

    for d in docs:
        key = d.page_content[:60]
        if key in seen:
            continue
        seen.add(key)

        context += d.page_content[:400] + "\n"
        sources.add(d.metadata["source"])



    prompt = f"""
你是一个公司制度助手，只能基于给定资料回答问题。如果未检索到相关内容，请你回复“抱歉，未找到相关信息”。

规则（必须遵守）：
1. 相同意思只允许出现一次
2. 不要按段落重复总结
3. 不要复述原文
4. 内容出现重复立即合并
5. 请用中文作答
6. 回答要简洁、准确
7. 请直接给出答案，不要说明思考过程

资料：
{context}

问题：
{query}

"""

    answer = llm.invoke(prompt,
                        options={
        "temperature": 0.2,
        "num_predict": 200}
    )
    print("\n✅ 回答：")
    print(answer)

    print("📄 来源文件：", "，".join(sources))
