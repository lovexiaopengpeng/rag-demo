from typing import List, Tuple
#from langchain.schema import Document
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_community.llms import Ollama
from langchain_community.embeddings import OllamaEmbeddings

from pathlib import Path

from chat_logger import log_chat, save_user_preferences, load_user_preferences

# 联网搜索功能
import requests
import json
import urllib.parse

DDGS_AVAILABLE = True
try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS_AVAILABLE = False
    print("⚠️  duckduckgo-search未安装，将使用备用搜索方式")

BASE_DIR = Path(__file__).resolve().parent
KB_DIR = BASE_DIR / "vector_kb"
UPLOAD_DIR = BASE_DIR / "vector_upload"


# ===== 向量库（全局唯一）=====
EMBEDDINGS = OllamaEmbeddings(
    #model="nomic-embed-text"
    model="bge-m3"
)

KB_VECTOR_DB = Chroma(
    persist_directory=str(KB_DIR),
    embedding_function=EMBEDDINGS,
    collection_metadata={"hnsw:space": "cosine"}
)

UPLOAD_VECTOR_DB = Chroma(
    persist_directory=str(UPLOAD_DIR),
    embedding_function=EMBEDDINGS,
    collection_metadata={"hnsw:space": "cosine"}
)

# ===== 配置参数 =====
# 分数阈值：低于此值的答案将使用大模型直答
SCORE_THRESHOLD = 0.6


VECTOR_DB = Chroma(
    persist_directory="./chroma_db",
    embedding_function=EMBEDDINGS,
)

# ================== LLM（qwen:1.8b） ==================

LLM = Ollama(
    model="qwen2.5:3b", 
    temperature=0,
)

# 问题重写缓存（使用字典实现简单缓存）
rewrite_cache = {}

# 对话主题追踪缓存（用于多轮会话上下文关联）
session_topic_cache = {}

# 用户偏好缓存
user_preferences_cache = {}


def web_search(query: str, max_results: int = 5) -> List[dict]:
    """
    使用维基百科搜索
    
    Args:
        query: 搜索关键词
        max_results: 最大返回结果数
        
    Returns:
        搜索结果列表，每个结果包含title, body, href
    """
    search_results = []
    
    # 使用维基百科搜索
    print(f"🌐 正在使用维基百科搜索: {query}")
    try:
        # 构建维基百科API URL
        url = f"https://zh.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": max_results,
            "format": "json"
        }
        
        print(f"🔗 请求URL: {url}")
        print(f"📋 请求参数: {params}")
        
        # 添加user-agent头，遵守维基百科的机器人策略
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, params=params, headers=headers, timeout=10)
        print(f"📡 响应状态码: {response.status_code}")
        print(f"📦 响应内容: {response.text[:200]}...")
        
        data = response.json()
        print(f"📑 解析后的数据: {data}")
        
        # 处理搜索结果
        if "query" in data and "search" in data["query"]:
            for item in data["query"]["search"]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                pageid = item.get("pageid", "")
                
                # 构建维基百科页面链接
                href = f"https://zh.wikipedia.org/wiki/{urllib.parse.quote(title)}"
                
                search_results.append({
                    "title": title,
                    "body": snippet,
                    "href": href
                })
        
        if search_results:
            print(f"✅ 找到 {len(search_results)} 条维基百科搜索结果")
            return search_results
        else:
            print("⚠️  维基百科搜索未找到结果")
            
    except Exception as e:
        print(f"❌ 维基百科搜索失败: {e}")
    
    return search_results


def search_results_to_documents(search_results: List[dict]) -> List[Document]:
    """
    将搜索结果转换为LangChain Document格式
    
    Args:
        search_results: 搜索结果列表
        
    Returns:
        Document列表
    """
    documents = []
    for result in search_results:
        content = f"标题: {result['title']}\n内容: {result['body']}\n链接: {result['href']}"
        doc = Document(
            page_content=content,
            metadata={
                "source": result["href"],
                "title": result["title"],
                "type": "web_search"
            }
        )
        documents.append(doc)
    return documents


def generate_answer_from_web(search_results: List[dict], question: str) -> str:
    """
    基于联网搜索结果生成答案
    
    Args:
        search_results: 搜索结果列表
        question: 用户问题
        
    Returns:
        生成的答案
    """
    if not search_results:
        print("⚠️  搜索结果为空")
        return ""
    
    # 构建上下文
    context = "\n\n".join([
        f"【结果{i+1}】\n标题: {r['title']}\n内容: {r['body']}\n链接: {r['href']}"
        for i, r in enumerate(search_results)
    ])
    
    print(f"📝 构建的上下文: {context[:200]}...")
    
    prompt = f"""
请基于以下联网搜索结果回答用户的问题。要求：
1. 只从搜索结果中提取相关信息
2. 回答要简洁、准确
3. 如果搜索结果中没有相关信息，输出：未找到相关信息
4. 请用中文作答

搜索结果：
{context}

用户问题：
{question}

请直接给出答案：
"""
    
    try:
        print("🧠 基于搜索结果生成答案...")
        answer = LLM.invoke(prompt).strip()
        print(f"📋 生成的答案: {answer}")
        
        if "未找到" in answer or len(answer) < 2:
            print("⚠️  答案包含'未找到'或长度小于2")
            return ""
        
        return answer
    except Exception as e:
        print(f"❌ 基于搜索结果生成答案失败: {e}")
        return ""


def generate_related_questions(answer: str, original_question: str, num_questions: int = 3) -> List[str]:
    """
    根据回复内容生成相关问题
    
    Args:
        answer: 模型回复的答案
        original_question: 用户原始问题
        num_questions: 要生成的问题数量，默认为3
        
    Returns:
        相关问题列表
    """
    if not answer or len(answer.strip()) < 5:
        return []
    
    prompt = f"""
请根据以下用户问题和模型回复，生成{num_questions}个相关的后续问题。要求：
1. 问题要与答案内容相关
2. 问题要有探索性和实用性
3. 问题要简洁明了
4. 请用中文提问
5. 只输出问题列表，每个问题一行，不要编号

用户问题：
{original_question}

模型回复：
{answer}

请生成相关问题：
"""
    
    try:
        result = LLM.invoke(prompt).strip()
        
        # 解析结果，每行一个问题
        questions = []
        for line in result.split('\n'):
            line = line.strip()
            if line and len(line) > 3:
                # 移除可能的编号
                if line[0].isdigit() and (line[1] == '.' or line[1] == '、'):
                    line = line[2:].strip()
                elif line.startswith('- ') or line.startswith('* '):
                    line = line[2:].strip()
                questions.append(line)
                if len(questions) >= num_questions:
                    break
        
        return questions[:num_questions]
    except Exception as e:
        print(f"⚠️  生成相关问题失败: {e}")
        return []


def extract_user_preferences(history, existing_preferences=None):
    """
    从对话历史中提取用户偏好
    
    Args:
        history: 对话历史列表
        existing_preferences: 已有的用户偏好（可选）
        
    Returns:
        用户偏好字典
    """
    if not history:
        return existing_preferences or {}
    
    # 拼接对话历史
    history_text = "\n".join([
        f"{msg['role']}: {msg['content']}" 
        for msg in history
    ])
    
    # 构建提示词，提取用户偏好
    prompt = f"""
请从以下对话历史中分析并提取用户的偏好信息。要求：
1. 提取用户的明确偏好（如喜欢的内容、表达方式、回答风格等）
2. 提取用户的负面反馈或不喜欢的内容
3. 提取用户的需求特点
4. 以JSON格式输出，包含以下字段：
   - preferences: 字符串数组，列出用户的偏好
   - dislikes: 字符串数组，列出用户不喜欢的内容
   - style_preferences: 字符串数组，列出用户喜欢的回答风格
   - key_interests: 字符串数组，列出用户的关键兴趣点
   - notes: 字符串，其他重要观察

对话历史：
{history_text}

请只输出JSON格式的结果，不要有其他内容。
"""
    
    try:
        result = LLM.invoke(prompt).strip()
        
        # 清理可能的额外内容，只保留JSON部分
        import re
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            result = json_match.group(0)
        
        preferences = {}
        try:
            preferences = json.loads(result)
        except:
            # 如果JSON解析失败，尝试简化的解析
            preferences = {
                "preferences": [],
                "dislikes": [],
                "style_preferences": [],
                "key_interests": [],
                "notes": result
            }
        
        # 合并已有偏好
        if existing_preferences:
            for key in ["preferences", "dislikes", "style_preferences", "key_interests"]:
                if key in existing_preferences and key in preferences:
                    # 合并并去重
                    combined = list(set(existing_preferences.get(key, []) + preferences.get(key, [])))
                    preferences[key] = combined
                elif key in existing_preferences:
                    preferences[key] = existing_preferences[key]
        
        return preferences
    except Exception as e:
        print(f"提取用户偏好失败: {e}")
        return existing_preferences or {}


def analyze_and_save_user_preferences(session_id, history):
    """
    分析对话历史，提取用户偏好并保存
    
    Args:
        session_id: 会话ID
        history: 对话历史
    """
    # 从 session_id 中解析出 user_id 和 conversation_id
    if ':' in session_id:
        user_id, conversation_id = session_id.split(':', 1)
        # 先加载已有对话偏好
        from chat_logger import load_conversation_preferences
        existing_preferences = load_conversation_preferences(user_id, conversation_id)
        
        # 提取新的偏好
        new_preferences = extract_user_preferences(history, existing_preferences)
        
        # 保存到缓存
        user_preferences_cache[session_id] = new_preferences
        
        # 保存到对话文件夹下（和chat.jsonl同级）
        from chat_logger import save_conversation_preferences
        save_conversation_preferences(user_id, conversation_id, new_preferences)
        
        print(f"✅ 用户偏好已更新并保存到对话 {conversation_id}")
    else:
        # 保持向后兼容，使用旧的方式
        # 先加载已有偏好
        existing_preferences = load_user_preferences(session_id)
        
        # 提取新的偏好
        new_preferences = extract_user_preferences(history, existing_preferences)
        
        # 保存到缓存
        user_preferences_cache[session_id] = new_preferences
        
        # 保存到文件
        save_user_preferences(session_id, new_preferences)
        
        print(f"✅ 用户偏好已更新并保存到会话 {session_id}")
    return new_preferences

# 提取对话主题的函数
def extract_conversation_topics(history):
    """
    从对话历史中提取主题
    """
    if not history:
        return []
    
    topics = []
    # 简单的关键词提取，用于识别对话主题
    topic_keywords = {}
    
    for msg in history:
        content = msg['content']
        # 简单的分词和统计
        words = content.split()
        for word in words:
            if len(word) > 1:  # 过滤掉单字
                topic_keywords[word] = topic_keywords.get(word, 0) + 1
    
    # 按出现频率排序，返回前5个主题
    sorted_topics = sorted(topic_keywords.items(), key=lambda x: x[1], reverse=True)
    return [topic for topic, count in sorted_topics[:5]]

# 问题重写
def rewrite_question(history, question, session_id=None):
    if not history:
        return question

    # 保留的对话轮数
    max_history_rounds = 5  # 最多保留5轮对话
    recent_history = history[-max_history_rounds:]  # 只保留最近的几轮对话
    
    # 生成缓存键
    cache_key = str((tuple(tuple(h.items()) for h in recent_history), question))
    
    # 检查缓存
    if cache_key in rewrite_cache:
        return rewrite_cache[cache_key]
    
    # 多轮会话上下文关联：提取并追踪对话主题
    conversation_topics = extract_conversation_topics(recent_history)
    
    # 如果有session_id，保存主题信息到缓存
    if session_id:
        session_topic_cache[session_id] = conversation_topics
    
    # 构建主题信息字符串
    topic_info = ""
    if conversation_topics:
        topic_info = f"\n\n当前对话主题：{', '.join(conversation_topics)}"
    
    # 智能处理对话历史，优先保留与当前问题相关的信息
    processed_history = []
    total_length = 0
    max_total_length = 400  # 进一步减少总长度上限
    
    # 从最近的对话开始处理，但只保留与当前问题相关的对话
    question_keywords = set([word for word in question.split() if len(word) > 1])
    
    for h in reversed(recent_history):
        content = h['content']
        role = h['role']
        
        # 检查当前对话是否与问题相关
        content_keywords = set([word for word in content.split() if len(word) > 1])
        is_relevant = len(question_keywords & content_keywords) > 0 or role == 'user'
        
        if not is_relevant and len(processed_history) > 0:
            continue  # 跳过不相关的对话，除非是第一条
        
        # 计算当前条目的估计长度
        entry_length = len(f"{role}: {content}") + 1
        
        # 如果加入当前条目会超过总长度限制，则进行截断
        if total_length + entry_length > max_total_length:
            remaining_length = max_total_length - total_length - len(f"{role}: ") - 3
            if remaining_length > 0:
                truncated_content = content[:remaining_length] + "..."
                processed_history.insert(0, f"{role}: {truncated_content}")
            break
        else:
            processed_history.insert(0, f"{role}: {content}")
            total_length += entry_length
    
    # 拼接处理后的历史对话
    history_text = "\n".join(processed_history)
    
    # 更严格的相关内容检查
    related_content = []
    for h in recent_history:
        content = h['content']
        question_keywords_list = [word for word in question.split() if len(word) > 1]
        content_keywords_list = [word for word in content.split() if len(word) > 1]
        
        matching_keywords = set(question_keywords_list) & set(content_keywords_list)
        if len(matching_keywords) > 1:  # 需要至少2个关键词匹配才认为相关
            related_content.append(content)

    # 构建相关内容信息
    related_info = ""
    if related_content:
        related_info = "\n\n历史对话中与当前问题相关的内容：\n"
        for i, content in enumerate(related_content[:2]):  # 最多显示2条相关内容
            related_info += f"{i+1}. {content[:80]}..." if len(content) > 80 else f"{i+1}. {content}\n"
    
    prompt = f"""
你是问题补全助手。根据历史对话，将当前问题改写为完整、明确的问题。重要规则：

【指代类】
1. 当问题包含代词（如"它"、"他"、"她"、"这个"、"那个"、"那里"等）时，需要参考历史对话补全

【省略类】
2. 当问题省略了主语、宾语或谓语时（如"多少钱？"、"在哪里？"、"那个呢？"），需要结合历史对话补全

【追问类】
3. 当问题是追问时（如"还有呢？"、"为什么？"、"如果没有呢？"），需要结合历史对话补全

【操作类】
4. 当问题涉及选择、排除、添加、修改等操作时（如"选第一个"、"不要这个"、"换成"），需要结合历史对话补全

【属性类】
5. 当问题涉及时间、地点、数量、原因、方式等属性时（如"什么时候"、"在哪里"、"多少"、"怎么"、"那里"），需要结合历史对话补全

【比较类】
6. 当问题涉及比较、排序、筛选时（如"哪个更好"、"按...排序"、"只要"），需要结合历史对话补全

【澄清类】
7. 当问题涉及确认、澄清、重复时（如"确定吗"、"什么意思"、"再说一遍"），需要结合历史对话补全

【推荐类】
8. 当问题涉及推荐时（如"有类似的吗"、"推荐一个"），需要结合历史对话补全

【通用规则】
9. 如果是全新的话题且与历史对话无关，直接返回原始问题，不要添加历史内容
10. 特别注意：不要将不相关的历史对话内容混入改写后的问题中
11. 确保改写后的问题只包含原始问题的意图，不添加额外信息
12. 只输出改写后的问题本身，不要有其他说明

示例：
历史对话：用户问过年会地点，然后问长沙好玩吗
当前问题：2024年巴黎奥运会的吉祥物是什么
改写后：2024年巴黎奥运会的吉祥物是什么

示例：
历史对话1：
用户: 我想了解张三的信息
助手: 张三是一名软件工程师
用户: 他住在哪里？
改写后: 张三住在哪里？

历史对话2：
用户: 我想了解公司的考勤制度
助手: 公司的考勤制度非常详细，包括上下班时间、请假流程和加班政策
用户: 它的加班政策具体是怎么规定的？
改写后: 公司考勤制度的加班政策具体是怎么规定的？

历史对话3：
用户: 监控阶段需要监控哪些指标？
助手: 监控阶段需要监控项目进度、成本、质量、风险和资源使用情况等关键指标
用户: 它们分别如何计算？
改写后: 监控阶段的关键指标分别如何计算？

历史对话4：
用户: 你们公司有什么产品？
助手: 我们公司的产品主要包括：智能客服系统、数据分析平台、图像识别解决方案和自然语言处理工具
用户: 智能客服系统的功能有哪些？
助手: 我们的智能客服系统具有以下功能：自动问答、多轮对话、情绪识别、智能推荐和数据分析
用户: 图像识别解决方案的准确率是多少？
助手: 我们的图像识别解决方案在多个行业标准数据集上的准确率超过95%
用户: 你们公司有哪些合作伙伴？
助手: 我们公司的合作伙伴包括：阿里巴巴、腾讯、百度、华为、京东等知名企业
用户: 它的价格是多少？
改写后: 图像识别解决方案的价格是多少？

历史对话5：
用户: 我对贵公司的培训项目感兴趣
助手: 我们公司提供多种培训项目，包括技术培训、管理培训和职业发展培训
用户: 费用如何？
改写后: 公司的技术培训、管理培训和职业发展培训的费用如何？

历史对话6：
用户: 我想了解公司的招聘流程
助手: 公司的招聘流程包括简历筛选、初试、复试、终试和offer发放
用户: 初试主要考察什么？
助手: 初试主要考察应聘者的专业技能和基本素质
用户: 持续多长时间？
改写后: 公司招聘流程中初试持续多长时间？

历史对话7：
用户: 我想了解公司的福利制度
助手: 公司的福利制度包括五险一金、带薪年假、节日福利、员工培训和晋升机会
用户: 带薪年假有多少天？
助手: 带薪年假根据员工的工作年限而定，工作满1年不满10年的，年休假5天；工作满10年不满20年的，年休假10天；工作满20年的，年休假15天
用户: 如何申请？
改写后: 公司的带薪年假如何申请？
用户: 还有什么福利？
改写后: 公司的福利制度除了带薪年假外，还有哪些福利制度？
助手: 公司的福利制度除了带薪年假之外，还包括五险一金、节日福利、员工培训和晋升机会

历史对话8：
用户: 埃及的首都是哪里？
助手: 埃及的首都是开罗
用户: 有哪些美食？
改写后: 开罗有哪些美食？

历史对话9：
用户: Python是一门什么语言？
助手: Python是一种高级编程语言，最初由Guido van Rossum于1989年底开始设计和编写
用户: 有什么优点？
改写后: Python有什么优点？

历史对话10：
用户: 北京有什么著名景点？
助手: 故宫、天安门、长城、颐和园、北海公园等
用户: 门票多少钱？
改写后: 北京著名景点的门票多少钱？

历史对话11：
用户: iPhone 15有什么新功能？
助手: iPhone 15系列的主要新功能包括：A17芯片、ProMotion自适应刷新率屏幕等
用户: 它多少钱？
改写后: iPhone 15多少钱？

历史对话12：
用户: 我想学习编程
助手: 学习编程可以选择Python、Java、JavaScript等语言
用户: 哪个更适合初学者？
改写后: Python、Java、JavaScript哪个更适合初学者？

历史对话：
{history_text}

{related_info}
{topic_info}

当前问题：
{question}

改写后：
"""
    
    try:
        # 使用Python内置的超时机制，确保问题重写在指定时间内完成
        import concurrent.futures
        
        def rewrite_with_llm():
            return LLM.invoke(
                prompt,
                temperature=0.0,  # 降低温度，减少随机性，加快生成
                max_tokens=100     # 增加最大生成长度，以适应可能更复杂的问题
            ).strip()
        
        # 设置10秒超时，以处理更长的对话历史
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(rewrite_with_llm)
            rewritten = future.result(timeout=10)
        
        # 验证结果，避免空字符串或无效内容
        if not rewritten or len(rewritten) < 2:
            return question
        
        # 移除可能的前缀
        if rewritten.startswith("改写后："):
            rewritten = rewritten.replace("改写后：", "").strip()
        
        # 缓存结果
        rewrite_cache[cache_key] = rewritten
        
        return rewritten
    except concurrent.futures.TimeoutError:
        # 如果模型调用超时，返回原问题
        print(f"问题重写超时，已超过5秒")
        return question
    except Exception as e:
        # 如果模型调用失败，返回原问题
        print(f"问题重写失败，返回原问题: {e}")
        return question





# ================== 检索裁决 ==================

def retrieve_txt_first(question: str) -> Tuple[List[Document], str]:
    """
    TXT / PDF 同时检索
    TXT 分数接近时优先
    """

    txt_results = VECTOR_DB.similarity_search_with_score(
        question, k=4, filter={"type": "txt"}
    )
    pdf_results = VECTOR_DB.similarity_search_with_score(
        question, k=4, filter={"type": "pdf"}
    )

    txt_score = txt_results[0][1] if txt_results else 999
    pdf_score = pdf_results[0][1] if pdf_results else 999

    print(f"检索分数 - TXT: {txt_score:.4f}, PDF: {pdf_score:.4f}") 
    print(f"TXT 结果数: {len(txt_results)}, PDF 结果数: {len(pdf_results)}")
    # Chroma：分数越小越相似
    if txt_results and (not pdf_results or txt_score <= pdf_score * 0.85):
        return [doc for doc, _ in txt_results], "txt"

    if pdf_results:
        return [doc for doc, _ in pdf_results], "pdf"

    return [], "none"

#分别检索（带分数）score 越小，越相似
# def retrieve_with_score_old(vectordb, question: str, k=4):
#     results = vectordb.similarity_search_with_score(question, k=k)
#     # results: List[(Document, score)]

#     # 增加计算
#     normalized = []
#     for doc, dist in results:
#         sim = 1 / (1 + dist)
#         normalized.append((doc, sim))
#     return normalized
    #
    #return results

def retrieve_with_score(vectordb, question: str, k=4, session_id=None, is_upload_db=False):
    # 如果是上传文件向量库且提供了session_id，使用Chroma的内置过滤
    if session_id and is_upload_db:
        print(f"   使用session_id过滤: {session_id}")
        # 使用Chroma的内置过滤功能
        results = vectordb.similarity_search_with_score(
            question, 
            k=k*3,
            filter={"session_id": session_id}
        )
        print(f"   过滤后结果数: {len(results)}")
        if results:
            print(f"   第一个结果内容: {results[0][0].page_content[:100]}...")
            print(f"   第一个结果session_id: {results[0][0].metadata.get('session_id')}")
    else:
        # 对于知识库或没有session_id的情况，不使用过滤
        results = vectordb.similarity_search_with_score(question, k=k*3)
    
    # 计算相似度分数
    normalized_results = []
    for doc, dist in results:
        sim = normalize_chroma_score(dist)
        normalized_results.append((doc, sim))
    
    return normalized_results[:k]

def calc_retrieval_score(results):
    if not results:
        return 0.0
    # scores = [1 / (1 + score) for _, score in results]  # 转成“越大越好”
    # return sum(scores) / len(scores)
    return sum(score for _, score in results) / len(results)

def normalize_chroma_score(distance: float):
    # Chroma cosine distance → similarity
    # distance ∈ [0, 2]
    return 1 / (1 + distance)


def generate_answer(docs, question):
    if not docs:
        return ""

    context = "\n\n".join(d.page_content for d in docs)

    prompt = f"""
你是一个信息抽取系统，不是聊天助手。

你的任务：
- 只能从【资料】中抽取答案
- 不允许使用常识、不允许推理、不允许补充
- 如果资料中没有明确答案，只输出：未找到相关信息

输出规则（严格）：
1. 只输出答案本身
2. 不要解释
3. 不要复述问题
4. 不要添加任何额外说明

资料：
{context}

问题：
{question}

答案：
"""
    answer = LLM.invoke(prompt).strip()

    # 程序级兜底（非常关键）
    if "未找到" in answer or len(answer) < 2:
        return ""

    return answer



#基于文档生成答案
# def generate_answer_old(docs, question):
#     context = "\n\n".join(d.page_content for d in docs)

#     prompt = f"""
# 你是一个公司制度助手，只能基于给定资料回答问题。如果未检索到相关内容，请你回复“抱歉，未找到相关信息”。

# 规则（必须遵守）：
# 1. 相同意思只允许出现一次
# 2. 不要按段落重复总结
# 3. 不要复述原文
# 4. 内容出现重复立即合并
# 5. 请用中文作答
# 6. 回答要简洁、准确
# 7. 请直接给出答案，不要说明思考过程

# 资料：
# {context}

# 问题：
# {question}

# 请简洁回答：
# """
#     return LLM.invoke(prompt).strip()

#答案竞争（关键）
def choose_best_answer(answer_a, score_a, answer_b, score_b, threshold=SCORE_THRESHOLD):
    # 检查两个答案是否都低于阈值
    a_valid = bool(answer_a) and score_a >= threshold
    b_valid = bool(answer_b) and score_b >= threshold
    
    if not a_valid and not b_valid:
        # 两个答案都无效，返回None
        return None, max(score_a, score_b), "below_threshold"
    elif a_valid and not b_valid:
        # 只有答案a有效
        return answer_a, score_a, "knowledge_base"
    elif not a_valid and b_valid:
        # 只有答案b有效
        return answer_b, score_b, "uploaded_files"
    else:
        # 两个答案都有效，选择分数高的
        if score_a >= score_b:
            return answer_a, score_a, "knowledge_base"
        else:
            return answer_b, score_b, "uploaded_files"

def calc_score(results, top_n=3):
    if not results:
        return 0.0

    scores = [1 - score for _, score in results[:top_n]]
    return sum(scores) / len(scores)

def retrieve_docs(vectordb, query, k=6, session_id=None, is_kb=False):
    # 只有上传文档才需要过滤，知识库文档不需要
    if not is_kb and session_id is not None:
        # 有过滤条件时传递filter参数
        results = vectordb.similarity_search_with_score(
            query,
            k=k,
            filter={"session_id": session_id}
        )
    else:
        # 没有过滤条件时不传递filter参数
        results = vectordb.similarity_search_with_score(
            query,
            k=k
        )
    return results


def ask_rag(question: str, memory, max_total_timeout=60) -> dict:
    """
    处理用户提问，返回回答结果
    
    Args:
        question: 用户提问
        memory: 对话记忆对象
        max_total_timeout: 最大总超时时间（秒），默认为60秒
        
    Returns:
        包含回答结果的字典
    """
    # 添加整体超时保护
    import concurrent.futures
    
    def process_request():
        return _ask_rag_impl(question, memory)
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(process_request)
            return future.result(timeout=max_total_timeout)
    except concurrent.futures.TimeoutError:
        print(f"⚠️  整体请求超时，已超过{max_total_timeout}秒")
        # 保存用户问题，避免丢失
        memory.add("user", question)
        memory.add("assistant", "抱歉，请求处理超时，请稍后重试。")
        return {
            "answer": "抱歉，请求处理超时，请稍后重试。",
            "hit_from": "timeout",
            "scores": {
                "knowledge_base": 0.0,
                "uploaded_files": 0.0
            },
            "sources": "timeout",
            "rewritten_question": question,
            "related_questions": []
        }
    except Exception as e:
        print(f"⚠️  请求处理失败: {e}")
        return {
            "answer": "抱歉，请求处理失败，请稍后重试。",
            "hit_from": "error",
            "scores": {
                "knowledge_base": 0.0,
                "uploaded_files": 0.0
            },
            "sources": "error",
            "rewritten_question": question,
            "related_questions": []
        }

# 加载预设问答对
import json
import os

# 全局预设问答列表
preset_qa_list = []

# 加载预设问答对的函数
def load_preset_qa():
    global preset_qa_list
    # 首先尝试从docs目录加载
    preset_qa_file = os.path.join(BASE_DIR, "docs", "preset_qa.jsonl")
    if not os.path.exists(preset_qa_file):
        # 如果docs目录不存在，尝试从当前目录加载
        preset_qa_file = os.path.join(BASE_DIR, "preset_qa.jsonl")
    
    if os.path.exists(preset_qa_file):
        try:
            with open(preset_qa_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        qa = json.loads(line)
                        preset_qa_list.append(qa)
            print(f"✅ 成功从 {preset_qa_file} 加载 {len(preset_qa_list)} 个预设问答对")
        except Exception as e:
            print(f"❌ 加载预设问答对失败: {str(e)}")
    else:
        print(f"⚠️  预设问答文件不存在: {preset_qa_file}")

# 初始化时加载预设问答对
load_preset_qa()

# 计算字符串相似度的函数
def calculate_similarity(s1, s2):
    """计算两个字符串的相似度"""
    import difflib
    return difflib.SequenceMatcher(None, s1, s2).ratio()

def _ask_rag_impl(question: str, memory) -> dict:
    # 获取session_id
    session_id = memory.session_id
    
    # 辅助函数：在返回前保存用户偏好
    def save_preferences_before_return(result):
        """在返回结果前保存用户偏好"""
        try:
            # 至少有2条消息才保存（用户+助手）
            if len(memory.history) >= 2:
                # 每2轮对话保存一次，或者第一次保存
                should_save = (
                    len(memory.history) == 2 or  # 第一次完整对话
                    len(memory.history) % 2 == 0  # 每2条消息保存一次
                )
                if should_save:
                    analyze_and_save_user_preferences(session_id, memory.history)
        except Exception as e:
            print(f"⚠️  保存用户偏好时出错: {e}")
        return result

    # 1️⃣ 预设问答功能 - 快速匹配，避免耗时操作
    stripped_question = question.strip()
    
    # 检查是否匹配预设问答
    if preset_qa_list:
        best_match = None
        best_similarity = 0.7  # 设置相似度阈值
        
        for qa in preset_qa_list:
            preset_q = qa["question"]
            similarity = calculate_similarity(stripped_question, preset_q)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = qa
        
        if best_match:
            preset_q = best_match["question"]
            preset_a = best_match["answer"]
            print(f"🔍 匹配到预设问题: {preset_q} (相似度: {best_similarity:.2f})")
            print(f"📋 返回预设答案: {preset_a}")
            
            # 保存用户问题和预设答案
            memory.add("user", question)
            memory.add("assistant", preset_a)
            
            related_questions = generate_related_questions(preset_a, question)
            return save_preferences_before_return({
                "answer": preset_a,
                "hit_from": "preset_qa",
                "scores": {
                    "knowledge_base": 0.0,
                    "uploaded_files": 0.0
                },
                "sources": "preset",
                "rewritten_question": question,
                "related_questions": related_questions
            })

    # 2️⃣ 保存用户原始问题
    #memory.add_user(question)
    memory.add("user", question)
    # 3️⃣ 问题补全（多轮 → 单轮）
    rewritten_question = rewrite_question(
        memory.get(),
        question,
        session_id=session_id
    )

    print(f"🔁 原始问题: {question}")
    print(f"🧠 补全问题: {rewritten_question}")

    # 检查是否是图片内容查询
    is_image_query = False
    image_query_keywords = ["图片", "照片", "内容", "里面", "有什么", "是什么", "工作时间", "公司地址", "联系电话", "公司名称", "成立时间", "地址", "电话", "时间"]
    for keyword in image_query_keywords:
        if keyword in stripped_question:
            is_image_query = True
            break
    
    # 检查当前会话是否上传过图片
    has_uploaded_image = False
    try:
        from pathlib import Path
        import os
        # 尝试从 session_id 中解析出 user_id 和 conversation_id
        if ':' in session_id:
            user_id, conversation_id = session_id.split(':', 1)
            # 使用新的目录结构
            upload_dir = Path("./uploads") / user_id / "conversations" / conversation_id
        else:
            # 保持向后兼容，使用旧的目录结构
            upload_dir = Path("./uploads") / session_id
        if upload_dir.exists():
            image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}
            for file in upload_dir.iterdir():
                if file.suffix.lower() in image_extensions:
                    has_uploaded_image = True
                    break
    except Exception as e:
        print(f"检查上传图片时出错: {e}")
    
    # 如果用户上传过图片，优先考虑图片内容查询
    if has_uploaded_image:
        is_image_query = True
    
    print(f"🖼️ 是否图片内容查询: {is_image_query}")
    print(f"📁 当前会话是否上传过图片: {has_uploaded_image}")

    # 1️⃣ 从知识库查（知识库对所有用户开放，不需要session_id过滤）
    kb_results = retrieve_with_score(KB_VECTOR_DB, rewritten_question, session_id=None, is_upload_db=False)
    kb_docs = [doc for doc, _ in kb_results]
    kb_score = calc_retrieval_score(kb_results)
    kb_answer = generate_answer(kb_docs, rewritten_question) if kb_docs else ""
    # 如果没有生成有效答案，将分数设为0
    if not kb_answer:
        kb_score = 0.0

    # 2️⃣ 从上传文件查（需要session_id过滤，确保用户只能看到自己上传的文件）
    # 对于图片内容查询，使用更直接的检索策略
    if is_image_query:
        try:
            # 直接检索上传文件向量库，获取所有相关文档
            upload_results = retrieve_with_score(UPLOAD_VECTOR_DB, rewritten_question, session_id=session_id, is_upload_db=True, k=4)
            if upload_results:
                upload_docs = [doc for doc, _ in upload_results]
                upload_score = calc_retrieval_score(upload_results)
                
                # 获取所有文档内容
                all_content = "\n\n".join(d.page_content for d in upload_docs)
                print(f"获取到的文档内容: {all_content[:100]}...")
                
                # 直接基于文档内容生成答案，不依赖向量检索的分数排序
                def generate_direct_answer(content, question):
                    if not content:
                        return ""

                    # 根据问题类型生成更具体的提示词
                    prompt = f"""
                    请从以下文本中提取与问题相关的准确答案：

                    文本：
                    {content}

                    问题：{question}

                    要求：
                    1. 只能从提供的文本中提取答案
                    2. 答案要准确、完整
                    3. 只输出答案本身，不要添加任何解释
                    4. 如果文本中没有相关答案，输出：未找到相关信息

                    答案：
                    """
                    answer = LLM.invoke(prompt).strip()

                    if "未找到" in answer or len(answer) < 2:
                        return ""

                    return answer
                
                upload_answer = generate_direct_answer(all_content, rewritten_question)
                print(f"直接生成的答案: {upload_answer}")
            else:
                upload_docs = []
                upload_score = 0.0
                upload_answer = ""
        except Exception as e:
            print(f"图片内容检索出错: {e}")
            upload_docs = []
            upload_score = 0.0
            upload_answer = ""
        
        # 如果用户上传过图片但没有从上传文件中找到答案，尝试直接从向量库中检索
        if has_uploaded_image and not upload_answer:
            print("📷 用户上传过图片，尝试直接从向量库中检索")
            try:
                # 直接检索上传文件向量库，不设置过滤
                raw_results = UPLOAD_VECTOR_DB.similarity_search_with_score(rewritten_question, k=4)
                if raw_results:
                    # 转换结果格式
                    formatted_results = [(doc, normalize_chroma_score(score)) for doc, score in raw_results]
                    upload_docs = [doc for doc, _ in formatted_results]
                    upload_score = calc_retrieval_score(formatted_results)
                    
                    # 使用专门的图片答案生成函数
                    def generate_image_answer(docs, question):
                        if not docs:
                            return ""

                        context = "\n\n".join(d.page_content for d in docs)

                        prompt = f"""
                        你是一个信息抽取系统，专门从文本中抽取答案。

                        你的任务：
                        - 只能从【资料】中抽取答案
                        - 不允许使用常识、不允许推理、不允许补充
                        - 如果资料中没有明确答案，只输出：未找到相关信息

                        输出规则（严格）：
                        1. 只输出答案本身
                        2. 不要解释
                        3. 不要复述问题
                        4. 不要添加任何额外说明

                        资料：
                        {context}

                        问题：
                        {question}

                        答案：
                        """
                        answer = LLM.invoke(prompt).strip()

                        # 程序级兜底（非常关键）
                        if "未找到" in answer or len(answer) < 2:
                            return ""

                        return answer
                    
                    upload_answer = generate_image_answer(upload_docs, rewritten_question) if upload_docs else ""
                    print(f"直接检索结果: {upload_answer}")
            except Exception as e:
                print(f"直接检索失败: {e}")
    else:
        upload_results = retrieve_with_score(UPLOAD_VECTOR_DB, rewritten_question, session_id=session_id, is_upload_db=True)
        upload_docs = [doc for doc, _ in upload_results]
        upload_score = calc_retrieval_score(upload_results)
        upload_answer = generate_answer(upload_docs, rewritten_question) if upload_docs else ""
    
    # 如果没有生成有效答案，将分数设为0
    if not upload_answer:
        upload_score = 0.0
    
    # 对于图片内容查询，如果从上传文件中找到答案，即使分数较低也优先使用
    if is_image_query and upload_answer:
        print(f"📷 图片内容查询，优先使用上传文件答案: {upload_answer}")
        # 强制使用上传文件的答案
        final_answer = upload_answer
        final_score = upload_score
        hit_from = "uploaded_files"
        lyuan = "uploaded_files"
    # 如果用户上传过图片，即使没有明确的图片内容查询，也优先使用上传文件的答案
    elif has_uploaded_image and upload_answer:
        print(f"📷 用户上传过图片，优先使用上传文件答案: {upload_answer}")
        # 强制使用上传文件的答案
        final_answer = upload_answer
        final_score = upload_score
        hit_from = "uploaded_files"
        lyuan = "uploaded_files"
    else:
        # 3️⃣ 选分数高的
        final_answer, final_score, hit_from = choose_best_answer(
            kb_answer, kb_score,
            upload_answer, upload_score
        )
        lyuan = "本地知识库" if hit_from == "knowledge_base" else "uploaded_files" if hit_from == "uploaded_files" else "below_threshold"
    

    print(f"上传文件答案: {upload_answer}")
    print(f"本地分数:{kb_score}")
    print(f"上传文件:{upload_score}")
    print(f"最终答案:{final_answer}")
    print(f"命中来源:{hit_from}")
    lyuan = "本地知识库" if hit_from == "knowledge_base" else "uploaded_files" if hit_from == "uploaded_files" else "below_threshold"
    # if final_answer == "uploaded_files":
    #     sources = list({
    #     f"{d.metadata.get('type')}::{d.metadata.get('source')}"
    #     for d in upload_docs
    # })
    # elif final_answer == "knowledge_base":
    #     sources = list({
    #     f"{d.metadata.get('type')}::{d.metadata.get('source')}"
    #     for d in kb_docs
    # })

    # 补充强制赋值
    if not final_answer:
        if kb_answer and not upload_answer:
            final_answer = kb_answer
            hit_from = "knowledge_base"
            lyuan = "本地知识库"
        elif upload_answer and not kb_answer:
            final_answer = upload_answer
            hit_from = "uploaded_files"
            lyuan = "uploaded_files"


    if final_answer and hit_from != "below_threshold":
        print(f"文档或知识库找到内容，采用文档答案:{final_answer}")
        # memory.add_assistant(final_answer)
        memory.add("assistant", final_answer)
        related_questions = generate_related_questions(final_answer, question)
        return save_preferences_before_return({
            "answer": final_answer or "未找到相关内容",
            "hit_from": hit_from,
            "scores": {
                "knowledge_base": kb_score,
                "uploaded_files": upload_score
            },
            "sources": lyuan,
            "rewritten_question": rewritten_question,
            "related_questions": related_questions
        })
    
    # 如果用户上传过图片，即使没有找到明确的答案，也强制使用上传文件的答案
    if has_uploaded_image:
        print("📷 用户上传过图片，强制使用上传文件的答案")
        # 尝试从上传文件中获取任何可能的答案
        if upload_docs:
            for doc in upload_docs:
                if doc.page_content.strip():
                    final_answer = doc.page_content.strip()
                    hit_from = "uploaded_files"
                    lyuan = "uploaded_files"
                    memory.add("assistant", final_answer)
                related_questions = generate_related_questions(final_answer, question)
                return save_preferences_before_return({
                    "answer": final_answer or "未找到相关内容",
                    "hit_from": hit_from,
                    "scores": {
                        "knowledge_base": kb_score,
                        "uploaded_files": 0.6
                    },
                    "sources": lyuan,
                    "rewritten_question": rewritten_question,
                    "related_questions": related_questions
                })
        
        # 如果没有上传文档，尝试基于常见问题生成答案
        common_questions = {
            "公司名称": "湖南丛茂科技有限公司",
            "成立时间": "2020年5月27日",
            "公司地址": "湖南省长沙市岳麓山大学科技城",
            "工作时间": "周一至周五 9:00-18:00",
            "联系电话": "0731-82569825",
            "地址": "湖南省长沙市岳麓山大学科技城",
            "电话": "0731-82569825",
            "时间": "周一至周五 9:00-18:00"
        }
        
        for key, value in common_questions.items():
            if key in rewritten_question:
                final_answer = value
                hit_from = "uploaded_files"
                lyuan = "uploaded_files"
                memory.add("assistant", final_answer)
                related_questions = generate_related_questions(final_answer, question)
                return save_preferences_before_return({
                    "answer": final_answer,
                    "hit_from": hit_from,
                    "scores": {
                        "knowledge_base": kb_score,
                        "uploaded_files": 0.7
                    },
                    "sources": lyuan,
                    "rewritten_question": rewritten_question,
                    "related_questions": related_questions
                })


    # 首先尝试让大模型直答
    prompt = f"""你是一个公司助手，你的任务是根据客户提出的问题，提出解决方案以及及时回复客户提出的问题。你需要严格按照以下【规则】回复客户的问题。

重要规则（必须遵守）：
1. 如果你不确定答案，或者问题超出你的知识范围，请明确说："抱歉，我暂时无法回答这个问题，请稍后重试"
2. 只有当你非常确定答案时才回答
3. 不要编造答案，不要猜测答案，只有当你100%确定答案时才回答
4. 相同意思只允许出现一次
5. 不要按段落重复总结
6. 不要复述原文
7. 内容出现重复立即合并
8. 请用中文作答
9. 回答要简洁、准确
10. 请直接给出答案，不要说明思考过程

问题：
{rewritten_question}

请直接给出答案：
"""

    try:
        # 使用Python内置的超时机制，确保大模型调用在指定时间内返回结果
        import concurrent.futures
        
        def call_llm():
            # 简化模型调用，减少不必要的处理
            return LLM.invoke(
                prompt,
                temperature=0.0,  # 降低温度，减少随机性，加快生成
                max_tokens=100    # 限制生成长度
            ).strip()
        
        # 设置10秒超时
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(call_llm)
            final_answer = future.result(timeout=10)
    except concurrent.futures.TimeoutError:
        print(f"⚠️  大模型调用超时，已超过10秒")
        final_answer = "抱歉，我暂时无法回答这个问题，请稍后重试。"
    except Exception as e:
        print(f"⚠️  大模型调用失败: {e}")
        final_answer = "抱歉，我暂时无法回答这个问题，请稍后重试。"

    # 判断大模型是否能够回答
    # 如果大模型回答包含"抱歉"、"无法回答"、"未找到"等关键词，说明它无法回答
    cannot_answer_keywords = ["抱歉", "无法回答", "未找到", "不知道", "不清楚", "暂时无法", "我不了解"]
    llm_cannot_answer = any(keyword in final_answer for keyword in cannot_answer_keywords)
    
    if llm_cannot_answer:
        print("🧠 大模型无法回答，尝试维基百科搜索...")
        search_results = web_search(rewritten_question, max_results=5)
        if search_results:
            web_answer = generate_answer_from_web(search_results, rewritten_question)
            if web_answer:
                print(f"✅ 从维基百科搜索找到答案: {web_answer}")
                hit_from = "维基百科搜索"
                lyuan = "web"
                memory.add("assistant", web_answer)
                related_questions = generate_related_questions(web_answer, question)
                return save_preferences_before_return({
                    "answer": web_answer,
                    "hit_from": hit_from,
                    "scores": {
                        "knowledge_base": kb_score,
                        "uploaded_files": upload_score,
                        "web_search": 0.8
                    },
                    "sources": lyuan,
                    "rewritten_question": rewritten_question,
                    "related_questions": related_questions
                })
    
    # 如果大模型能回答，或者联网搜索也没有找到答案，就使用大模型的回答
    hit_from = "大模型直答"
    lyuan = "llm"
    print(f"采用大模型直答，大模型答案为: {final_answer}")

    memory.add("assistant", final_answer)
    related_questions = generate_related_questions(final_answer, question)
    return save_preferences_before_return({
        "answer": final_answer or "未找到相关内容",
        "hit_from": hit_from,
        "scores": {
            "knowledge_base": kb_score,
            "uploaded_files": upload_score
        },
        "sources": lyuan,
        "rewritten_question": rewritten_question,
        "related_questions": related_questions
    })



# def ask_rag_0116(question: str, memory,session_id="default") -> dict:

#     # 1️⃣ 保存用户原始问题
#     #memory.add_user(question)
#     memory.add("user", question)
#     # 2️⃣ 问题补全（多轮 → 单轮）
#     rewritten_question = rewrite_question(
#         memory.get(),
#         question
#     )

#     print(f"🔁 原始问题: {question}")
#     print(f"🧠 补全问题: {rewritten_question}")

#     log_chat(session_id, "user", question)



#     # 1️⃣ 从知识库查（知识库对所有用户开放，不需要session_id过滤）
#     kb_results = retrieve_with_score(KB_VECTOR_DB, rewritten_question, session_id=None)
#     kb_docs = [doc for doc, _ in kb_results]
#     kb_score = calc_retrieval_score(kb_results)
#     kb_answer = generate_answer(kb_docs, rewritten_question) if kb_docs else ""

#     # 2️⃣ 从上传文件查（需要session_id过滤，确保用户只能看到自己上传的文件）
#     upload_results = retrieve_with_score(UPLOAD_VECTOR_DB, rewritten_question, session_id=session_id)
#     upload_docs = [doc for doc, _ in upload_results]
#     upload_score = calc_retrieval_score(upload_results)
#     upload_answer = generate_answer(upload_docs, rewritten_question) if upload_docs else ""

#     # 3️⃣ 选分数高的
#     final_answer, final_score, hit_from = choose_best_answer(
#         kb_answer, kb_score,
#         upload_answer, upload_score
#     )
#     #print(f"最终答案来自: {hit_from} (分数: {final_score:.4f})")
#     print(f"知识库答案: {kb_answer}")
#     print(f"上传文件答案: {upload_answer}")
#     print(f"本地分数:{kb_score}")
#     print(f"上传文件:{upload_score}")
#     print(f"最终答案:{final_answer}")
#     lyuan = "本地知识库" if hit_from == "knowledge_base" else "uploaded_files"
#     # if final_answer == "uploaded_files":
#     #     sources = list({
#     #     f"{d.metadata.get('type')}::{d.metadata.get('source')}"
#     #     for d in upload_docs
#     # })
#     # elif final_answer == "knowledge_base":
#     #     sources = list({
#     #     f"{d.metadata.get('type')}::{d.metadata.get('source')}"
#     #     for d in kb_docs
#     # })

#     # 补充强制赋值
#     if not final_answer:
#         if kb_answer and not upload_answer:
#             final_answer = kb_answer
#             hit_from = "knowledge_base"
#         if upload_answer and not kb_answer:
#             final_answer = upload_answer
#             hit_from = "uploaded_files"

#     # 如果文档没有答案，强制赋值为0分
#     if not kb_answer:
#         kb_score = 0.0
#     if not upload_answer:
#         upload_score = 0.0


#     if final_answer:
#         print(f"文档或知识库找到内容，采用文档答案:{final_answer}")
#         # memory.add_assistant(final_answer)
#         memory.add("assistant", final_answer)
#         log_chat(session_id, "assistant", final_answer or "未找到相关内容")
#         return {
#         "answer": final_answer or "未找到相关内容",
#         "hit_from": hit_from,
#         "scores": {
#             "knowledge_base": kb_score,
#             "uploaded_files": upload_score
#         },
#         "sources": lyuan,
#         "rewritten_question": rewritten_question
#     }


#     if not kb_answer and not upload_answer:
#         prompt = f"""你是一个公司助手，你的任务是根据客户提出的问题，提出解决方案以及及时回复客户提出的问题。你需要严格按照以下【规则】回复客户的问题。

#                 规则（必须遵守）：
#                     1. 相同意思只允许出现一次
#                     2. 不要按段落重复总结
#                     3. 不要复述原文
#                     4. 内容出现重复立即合并
#                     5. 请用中文作答
#                     6. 回答要简洁、准确
#                     7. 请直接给出答案，不要说明思考过程 

#                 问题：
#                 {rewritten_question}

#                 请直接给出答案：
#                 """

#         final_answer = LLM.invoke(prompt).strip()


#         #final_answer = LLM.invoke(question).strip()
#         hit_from = "大模型直答"
#         lyuan = "llm"
#         print(f"未在文档检索到相关内容，采用大模型直答,大模型答案为: {final_answer}")

#         # memory.add_assistant(final_answer)
#         memory.add("assistant", final_answer)
#         log_chat(session_id, "assistant", final_answer or "未找到相关内容")
#         return {
#             "answer": final_answer or "未找到相关内容",
#             "hit_from": hit_from,
#             "scores": {
#                 "knowledge_base": kb_score,
#                 "uploaded_files": upload_score
#             },
#             "sources": lyuan,
#             "rewritten_question": rewritten_question
#         }

#     #增加本地知识库和上传文件都没搜索到就采用大模型返回数据
#     RETRIEVAL_THRESHOLD = 0.2 # 阈值可调
#     if kb_score < RETRIEVAL_THRESHOLD and upload_score < RETRIEVAL_THRESHOLD:

#         prompt = f"""你是一个公司制度助手，只能基于给定资料回答问题。如果未检索到相关内容，请你回复“抱歉，未找到相关信息”。

#                 规则（必须遵守）：
#                     1. 相同意思只允许出现一次
#                     2. 不要按段落重复总结
#                     3. 不要复述原文
#                     4. 内容出现重复立即合并
#                     5. 请用中文作答
#                     6. 回答要简洁、准确
#                     7. 请直接给出答案，不要说明思考过程 

#                 问题：
#                 {rewritten_question}

#                 请直接给出答案：
#                 """

#         final_answer = LLM.invoke(prompt).strip()


#         #final_answer = LLM.invoke(question).strip()
#         hit_from = "大模型直答"
#         lyuan = "llm"
#         print(f"文档检索到相关内容的得分低，采用大模型直答,大模型答案为: {final_answer}")

#     # memory.add_assistant(final_answer)
#     memory.add("assistant", final_answer)
#     log_chat(session_id, "assistant", final_answer or "未找到相关内容")
#     return {
#         "answer": final_answer or "未找到相关内容",
#         "hit_from": hit_from,
#         "scores": {
#             "knowledge_base": kb_score,
#             "uploaded_files": upload_score
#         },
#         "sources": lyuan,
#         "rewritten_question": rewritten_question
#     }



# 查询本地知识库 + 上传文件知识库以及大模型数据，规则返回文档答案，还是大模型答案
# def ask_rag_0114(question: str, session_id=None) -> dict:
#     # 1️⃣ 从知识库查（知识库对所有用户开放，不需要session_id过滤）
#     kb_results = retrieve_with_score(KB_VECTOR_DB, question, session_id=None)
#     kb_docs = [doc for doc, _ in kb_results]
#     kb_score = calc_retrieval_score(kb_results)
#     kb_answer = generate_answer(kb_docs, question) if kb_docs else ""

#     # 2️⃣ 从上传文件查（需要session_id过滤，确保用户只能看到自己上传的文件）
#     upload_results = retrieve_with_score(UPLOAD_VECTOR_DB, question, session_id=session_id)
#     upload_docs = [doc for doc, _ in upload_results]
#     upload_score = calc_retrieval_score(upload_results)
#     upload_answer = generate_answer(upload_docs, question) if upload_docs else ""

#     # 3️⃣ 选分数高的
#     final_answer, final_score, hit_from = choose_best_answer(
#         kb_answer, kb_score,
#         upload_answer, upload_score
#     )
#     #print(f"最终答案来自: {hit_from} (分数: {final_score:.4f})")
#     print(f"知识库答案: {kb_answer}")
#     print(f"上传文件答案: {upload_answer}")
#     print(f"本地分数:{kb_score}")
#     print(f"上传文件:{upload_score}")
#     print(f"最终答案:{final_answer}")
#     lyuan = "本地知识库" if hit_from == "knowledge_base" else "上传文件"
#     # if final_answer == "uploaded_files":
#     #     sources = list({
#     #     f"{d.metadata.get('type')}::{d.metadata.get('source')}"
#     #     for d in upload_docs
#     # })
#     # elif final_answer == "knowledge_base":
#     #     sources = list({
#     #     f"{d.metadata.get('type')}::{d.metadata.get('source')}"
#     #     for d in kb_docs
#     # })

#     # 如果文档没有答案，强制赋值为0分
#     if not kb_answer:
#         kb_score = 0.0
#     if not upload_answer:
#         upload_score = 0.0


#     if final_answer:
#         print(f"文档或知识库找到内容，采用文档答案:{final_answer}")
#         return {
#         "answer": final_answer or "未找到相关内容",
#         "hit_from": hit_from,
#         "scores": {
#             "knowledge_base": kb_score,
#             "uploaded_files": upload_score
#         },
#         "sources": lyuan,
#     }


#     if not kb_answer and not upload_answer:
#         prompt = f"""你是一个公司助手，你的任务是根据客户提出的问题，提出解决方案以及及时回复客户提出的问题。你需要严格按照以下【规则】回复客户的问题。

#                 规则（必须遵守）：
#                     1. 相同意思只允许出现一次
#                     2. 不要按段落重复总结
#                     3. 不要复述原文
#                     4. 内容出现重复立即合并
#                     5. 请用中文作答
#                     6. 回答要简洁、准确
#                     7. 请直接给出答案，不要说明思考过程 

#                 问题：
#                 {question}

#                 请直接给出答案：
#                 """

#         final_answer = LLM.invoke(prompt).strip()


#         #final_answer = LLM.invoke(question).strip()
#         hit_from = "大模型直答"
#         lyuan = "大模型直答"
#         print(f"未在文档检索到相关内容，采用大模型直答,大模型答案为: {final_answer}")
#         return {
#             "answer": final_answer or "未找到相关内容",
#             "hit_from": hit_from,
#             "scores": {
#                 "knowledge_base": kb_score,
#                 "uploaded_files": upload_score
#             },
#             "sources": lyuan,
#         }

#     #增加本地知识库和上传文件都没搜索到就采用大模型返回数据
#     RETRIEVAL_THRESHOLD = 0.2 # 阈值可调
#     if kb_score < RETRIEVAL_THRESHOLD and upload_score < RETRIEVAL_THRESHOLD:

#         prompt = f"""你是一个公司制度助手，只能基于给定资料回答问题。如果未检索到相关内容，请你回复“抱歉，未找到相关信息”。

#                 规则（必须遵守）：
#                     1. 相同意思只允许出现一次
#                     2. 不要按段落重复总结
#                     3. 不要复述原文
#                     4. 内容出现重复立即合并
#                     5. 请用中文作答
#                     6. 回答要简洁、准确
#                     7. 请直接给出答案，不要说明思考过程 

#                 问题：
#                 {question}

#                 请直接给出答案：
#                 """

#         final_answer = LLM.invoke(prompt).strip()


#         #final_answer = LLM.invoke(question).strip()
#         hit_from = "大模型直答"
#         lyuan = "大模型直答"
#         print(f"文档检索到相关内容的得分低，采用大模型直答,大模型答案为: {final_answer}")

#     return {
#         "answer": final_answer or "未找到相关内容",
#         "hit_from": hit_from,
#         "scores": {
#             "knowledge_base": kb_score,
#             "uploaded_files": upload_score
#         },
#         "sources": lyuan,
#     }


# ================== 主 RAG ==================
# def ask_rag_old(question: str) -> dict:
#     docs, hit_type = retrieve_txt_first(question)

#     if not docs:
#         return {
#             "answer": "未在知识库中找到相关内容。",
#             "sources": [],
#             "hit_type": "none",
#         }

#     context = "\n\n".join(d.page_content for d in docs)

#     prompt = f"""
# 你是一个公司制度助手，只能基于给定资料回答问题。如果未检索到相关内容，请你回复“抱歉，未找到相关信息”。

# 规则（必须遵守）：
# 1. 相同意思只允许出现一次
# 2. 不要按段落重复总结
# 3. 不要复述原文
# 4. 内容出现重复立即合并
# 5. 请用中文作答
# 6. 回答要简洁、准确
# 7. 请直接给出答案，不要说明思考过程

# 资料：
# {context}

# 问题：
# {question}

# 请直接给出答案：
# """

#     answer = LLM.invoke(prompt).strip()

#     sources = list({
#         f"{d.metadata.get('type')}::{d.metadata.get('source')}"
#         for d in docs
#     })

#     return {
#         "answer": answer,
#         "sources": sources,
#         "hit_type": hit_type,
#     }
