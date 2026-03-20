import streamlit as st
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
import os
import uuid
import tempfile
from pathlib import Path
from ingest import ingest_files

# ========================
# 1. 页面配置
# ========================
st.set_page_config(
    page_title="公司智能问答系统",
    page_icon="📘",
    layout="centered"
)

st.title("📘 公司智能问答系统")
st.caption("基于内部文档 · RAG 检索增强生成")

# ========================
# 2. 会话管理
# ========================
# 生成或获取会话ID
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# 显示会话ID（可选，用于调试）
st.sidebar.write(f"会话ID: {st.session_state.session_id}")
st.sidebar.caption("刷新页面将生成新会话")

# ========================
# 3. 文件上传
# ========================
st.sidebar.header("📁 文件上传")

# 允许用户上传文件
uploaded_files = st.sidebar.file_uploader(
    "上传您的文档（支持PDF、DOCX、TXT、XLSX等）",
    type=None,
    accept_multiple_files=True,
    key="file_uploader"
)

# 处理上传的文件
if uploaded_files:
    with st.spinner("正在处理文件..."):
        for uploaded_file in uploaded_files:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as temp_file:
                temp_file.write(uploaded_file.getvalue())
                temp_file_path = temp_file.name
            
            try:
                # 调用ingest_files函数处理文件，将其向量化并与会话ID关联
                result = ingest_files([temp_file_path], target="upload", session_id=st.session_state.session_id)
                chunks = result.get("chunks", 0)
                st.sidebar.success(f"✅ 成功处理文件: {uploaded_file.name} ({chunks}个片段)")
            except Exception as e:
                st.sidebar.error(f"❌ 处理文件失败: {uploaded_file.name} - {str(e)}")
            finally:
                # 删除临时文件
                os.unlink(temp_file_path)

# ========================
# 4. 加载向量库
# ========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ========================
# 5. 输入问题
# ========================
query = st.text_input(
    "请输入你的问题：",
    placeholder="例如：长沙好玩吗？Python是什么？"
)

# ========================
# 6. 调用ask接口
# ========================
if query:
    with st.spinner("正在查找相关内容..."):
        import requests
        
        try:
            # 调用ask接口
            response = requests.post(
                "http://localhost:8000/ask",
                json={
                    "question": query,
                    "session_id": st.session_state.session_id
                },
                timeout=30
            )
            
            # 检查响应状态
            if response.status_code == 200:
                result = response.json()
                
                # 显示回答
                st.subheader("📌 回答")
                st.write(result.get("answer", "未找到相关内容"))
                
                # 显示来源
                st.subheader("📄 来源")
                st.write(f"• {result.get('source', '未知来源')}")
            else:
                st.error(f"❌ 调用API失败: HTTP {response.status_code} - {response.text}")
        except Exception as e:
            st.error(f"❌ 调用API异常: {str(e)}")
