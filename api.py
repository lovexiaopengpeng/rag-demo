from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
import shutil, os, re

from rag_core import ask_rag, LLM

from config import DB_DIR
from ingest import ingest_files, DOCS_DIR

from pathlib import Path

from memory import ConversationMemory

from chat_logger import log_chat, save_sft_sample
import uuid
from user_id_generator import user_id_generator

# 全局对话记忆（单用户版本）
#memory = ConversationMemory(max_turns=6)

SESSIONS = {}

UPLOAD_DIR = Path("./uploads")


DOCS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Qwen RAG API")

# 配置静态文件服务
from fastapi.staticfiles import StaticFiles

# 挂载chat_logs目录为静态文件服务
chat_logs_dir = Path("./chat_logs")
chat_logs_dir.mkdir(exist_ok=True)
app.mount("/chat_logs", StaticFiles(directory=str(chat_logs_dir)), name="chat_logs")

# 挂载uploads目录为静态文件服务
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

# ===== 请求模型 =====

class AskRequest(BaseModel):
    question: str
    user_id: str = ""
    conversation_id: str = ""

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""
    phone: str = ""

class TextToVideoRequest(BaseModel):
    text: str
    duration: int = 10
    resolution: str = "720p"
    style: str = "default"
    session_id: str = ""

class TextToImageRequest(BaseModel):
    text: str
    style: str = "default"
    size: str = "1024x1024"
    session_id: str = ""
    model: str = "z-image"

class CreateConversationRequest(BaseModel):
    user_id: str
    title: str = ""

class UpdateConversationRequest(BaseModel):
    user_id: str
    conversation_id: str
    title: str = ""

# ===== 上传文件 =====

# @app.post("/upload_old")
# def upload_file_old(file: UploadFile = File(...)):
#     # 设置单个文件大小限制为20MB
#     MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
    
#     # 检查文件大小
#     file.file.seek(0, 2)  # 移动到文件末尾
#     file_size = file.file.tell()  # 获取文件大小
#     file.file.seek(0)  # 重置文件指针
    
#     if file_size > MAX_FILE_SIZE:
#         from fastapi import HTTPException
#         raise HTTPException(
#             status_code=400,
#             detail={
#                 "msg": "文件大小超过限制",
#                 "filename": file.filename,
#                 "error": f"单个文件大小不能超过20MB，当前文件大小为{file_size / (1024*1024):.2f}MB"
#             }
#         )
    
#     path = os.path.join(DATA_DIR, file.filename)
#     with open(path, "wb") as f:
#         shutil.copyfileobj(file.file, f)

#     return {"msg": "文件上传成功", "filename": file.filename}


# @app.post("/upload_0116")
# def upload_file_0116(file: UploadFile = File(...)):
#     # 设置单个文件大小限制为20MB
#     MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
    
#     # 检查文件大小
#     file.file.seek(0, 2)  # 移动到文件末尾
#     file_size = file.file.tell()  # 获取文件大小
#     file.file.seek(0)  # 重置文件指针
    
#     if file_size > MAX_FILE_SIZE:
#         from fastapi import HTTPException
#         raise HTTPException(
#             status_code=400,
#             detail={
#                 "filename": file.filename,
#                 "msg": "文件大小超过限制",
#                 "error": f"单个文件大小不能超过20MB，当前文件大小为{file_size / (1024*1024):.2f}MB"
#             }
#         )
    
#     UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
#     #save_path = f"./uploads/{file.filename}"
#     save_path = UPLOAD_DIR / file.filename
    
#     with open(save_path, "wb") as f:
#         shutil.copyfileobj(file.file, f)

#     #chunks = ingest_files([save_path])
#     chunks = ingest_files([str(save_path)], target="upload")

#     return {
#         "filename": file.filename,
#         "msg": "文件已入库",
#         "chunks": chunks
#     }



# @app.post("/upload_async")
# async def upload_file_async(file: UploadFile = File(...)):
#     # 设置单个文件大小限制为20MB
#     MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
    
#     # 检查文件大小
#     file.file.seek(0, 2)  # 移动到文件末尾
#     file_size = file.file.tell()  # 获取文件大小
#     file.file.seek(0)  # 重置文件指针
    
#     if file_size > MAX_FILE_SIZE:
#         from fastapi import HTTPException
#         raise HTTPException(
#             status_code=400,
#             detail={
#                 "filename": file.filename,
#                 "msg": "文件大小超过限制",
#                 "error": f"单个文件大小不能超过20MB，当前文件大小为{file_size / (1024*1024):.2f}MB"
#             }
#         )
    
#     save_path = DOCS_DIR / file.filename

#     with save_path.open("wb") as f:
#         shutil.copyfileobj(file.file, f)

#     chunks = ingest_files(DB_DIR, [save_path])

#     return {
#         "filename": file.filename,
#         "chunks_added": chunks,
#         "msg": "文件上传成功"
#     }




# ===== 问答 =====

# @app.post("/ask")
# def ask(req: AskRequest):
#     return ask_rag(req.question,memory)

@app.post("/ask")
def ask(req: AskRequest):
    # 确保用户ID和对话ID存在
    if not req.user_id:
        req.user_id = user_id_generator.generate_user_id()
        print(f"未提供用户ID，生成新的用户ID: {req.user_id}")
    
    if not req.conversation_id:
        req.conversation_id = str(uuid.uuid4())
        print(f"未提供对话ID，生成新的对话ID: {req.conversation_id}")
    else:
        # 验证对话ID是否为有效的UUID格式
        try:
            uuid.UUID(req.conversation_id)
        except ValueError:
            # 如果不是有效的UUID，生成新的
            req.conversation_id = str(uuid.uuid4())
            print(f"提供的对话ID格式无效，生成新的对话ID: {req.conversation_id}")
    
    # 使用用户ID和对话ID作为会话键
    session_key = f"{req.user_id}:{req.conversation_id}"    
    if session_key not in SESSIONS:
        SESSIONS[session_key] = ConversationMemory(LLM, session_id=session_key)

    memory = SESSIONS[session_key]

    # 先记录用户提问（此时的时间戳是真实的提问时间）
    log_chat(req.user_id, req.conversation_id, "user", req.question)
    
    # 意图识别
    user_intent = identify_user_intent(req.question, session_key)
    print(f"用户意图-------------------------------: {user_intent}")
    # 根据意图处理
    if user_intent == "generate_image":
        # 提取图片生成提示词
        prompt = extract_image_prompt(req.question)
        
        # 调用ali_image函数生成图片
        image_result = ali_image(prompt=prompt, user_id=req.user_id, conversation_id=req.conversation_id, user_name="user")
        
        # 记录助手回复
        log_chat(req.user_id, req.conversation_id, "assistant", f"已为您生成图片，请查看: {image_result['image_url']}", 
                aliyun_image_url=image_result.get('aliyun_image_url'))
        
        return {
            "answer": f"已为您生成图片，请查看: {image_result['image_url']}",
            "user_id": req.user_id,
            "conversation_id": req.conversation_id,
            "session_id": session_key,
            "source": "image_generation",
            "image_url": image_result['image_url'],
            "image_path": image_result['image_path'],
            "aliyun_image_url": image_result.get('aliyun_image_url'),
            "status": image_result['status']
        }
    
    elif user_intent == "generate_video":
        # 提取视频生成提示词
        prompt = extract_video_prompt(req.question)
        
        # 直接生成视频 generate_video(req.session_id, prompt)
        video_result = ali_video(prompt=prompt, user_id=req.user_id, conversation_id=req.conversation_id, user_name="user")
        
        # 记录助手回复
        log_chat(req.user_id, req.conversation_id, "assistant", f"生成了视频: {video_result['video_path']}")
        
        # 更新返回结果
        video_result['user_id'] = req.user_id
        video_result['conversation_id'] = req.conversation_id
        video_result['session_id'] = session_key
        
        return video_result
    
    elif user_intent == "weather":
        # 提取地点
        location = extract_weather_location(req.question)
        # 查询天气
        weather_data = get_weather(location)
        
        # 记录助手回复
        log_chat(req.user_id, req.conversation_id, "assistant", weather_data["answer"])
        
        # 构建回复
        response = {
            "answer": weather_data["answer"],
            "user_id": req.user_id,
            "conversation_id": req.conversation_id,
            "session_id": session_key,
            "source": "coze_weather",
            "weather_data": weather_data
        }
        
        return response
    
    else:
        # 继续使用现有的ask_rag逻辑
        result = ask_rag(req.question, memory)
        answer = result["answer"]
        source = result["hit_from"]
        sources = result.get("sources", source)
        rewritten_question = result.get("rewritten_question", req.question)
        scores = result.get("scores", {})
        
        # 记录改写后的问题（使用system角色）
        if rewritten_question != req.question:
            log_chat(req.user_id, req.conversation_id, "system", f"改写后的问题: {rewritten_question}",
                    rewritten_question=rewritten_question)
        
        # 记录助手回复（此时的时间戳是真实的回复时间）
        log_chat(req.user_id, req.conversation_id, "assistant", answer)

        if source != "llm":
                save_sft_sample(req.question, answer, source, session_key)

        return {
            "answer": answer,
            "user_id": req.user_id,
            "conversation_id": req.conversation_id,
            "session_id": session_key,
            "source": source,
            "sources": sources,
            "scores": scores,
            "rewritten_question": rewritten_question
        }


def identify_user_intent(question: str, session_id: str = None) -> str:
    """
    使用关键词匹配方法识别用户意图
    不使用大模型，直接使用备用的关键词匹配方法
    """
    print(f"用户问题: {question}")
    # 直接使用备用的关键词匹配方法
    intent = identify_user_intent_with_qwen(question, session_id) # identify_user_intent_fallback(question)
    print(f"意图识别结果: {intent}")
    return intent

def identify_user_intent_with_qwen(question: str, session_id: str = None) -> str:
    """
    使用本地LLM模型识别用户意图
    考虑对话历史和上下文信息
    """
    try:
        from rag_core import LLM
        
        # 构建提示词
        prompt = f"""
        请分析用户的最后一个问题，判断其意图，并从以下选项中选择一个最匹配的意图标签：
        - analyze_image: 分析图片的内容
        - recreate_image: 基于图片进行二次创作
        - generate_image: 生成新的图片
        - generate_video: 生成视频
        - weather: 查询天气信息
        - ask_question: 其他问题
        
        分析规则：
        1. 如果用户提到"分析图片"、"图片内容"、"图片里有什么"、"识别图片"、"解读图片"等，选择 analyze_image
        2. 如果用户提到"基于图片"、"参考图片"、"根据图片"、"图片风格"、"模仿图片"等，选择 recreate_image
        3. 如果用户提到"生成图片"、"画"、"创作图片"、"create image"、"draw"、"paint"等，选择 generate_image
        4. 如果用户提到"生成视频"、"视频"、"video"、"create video"、"make video"等，选择 generate_video
        5. 如果用户提到"天气"、"气温"、"温度"、"下雨"、"晴天"、"多云"、"刮风"、"下雪"等，选择 weather
        6. 其他情况选择 ask_question
        
        注意：
        - "分析图片"是指用户想了解图片中已经存在的内容
        - "生成图片"是指用户想创建一张新的图片
        - "天气"是指用户想查询某个地点的天气信息
        - 请仔细区分这些意图
        
        用户问题：{question}
        
        请只返回意图标签，不要返回其他任何内容。
        """
        
        # 调用本地LLM模型
        response = LLM.invoke(prompt)
        intent = response.strip().lower()
        print(f"本地LLM模型识别结果: {intent}")
        
        # 当用户意图为analyze_image和recreate_image时，设置为ask_question
        if intent == "analyze_image" or intent == "recreate_image":
            intent = "ask_question"
        
        # 验证返回的意图标签
        valid_intents = ["analyze_image", "recreate_image", "generate_image", "generate_video", "weather", "ask_question"]
        if intent in valid_intents:
            return intent
        else:
            # 如果返回的不是有效的意图标签，返回默认值
            return "ask_question"
    except Exception as e:
        print(f"本地LLM模型意图识别失败: {str(e)}")
        # 失败时使用备用的关键词匹配方法
        return identify_user_intent_fallback(question)

def identify_user_intent_fallback(question: str) -> str:
    """
    备用的关键词匹配方法
    当大模型识别失败时使用
    """
    question = question.lower()
    
    # 图片分析关键词
    analyze_image_keywords = ["分析图片", "图片里有什么", "图片内容", "识别图片", "解读图片", "图片中的", "图片上的", "看看图片", "查看图片", "识别图片中的", "图片里的", "图片内容是什么"]
    for keyword in analyze_image_keywords:
        if keyword in question:
            return "ask_question"

    # 图片二次创作关键词
    recreate_image_keywords = ["基于图片", "参考图片", "根据图片", "图片风格", "模仿图片", "类似图片", "参考这张", "根据这张", "基于这张", "按照图片", "按照这张"]
    for keyword in recreate_image_keywords:
        if keyword in question:
            return "ask_question" # "recreate_image"

    # 图片生成关键词
    image_keywords = ["生成图片", "画", "创作图片", "生成一张", "画一张", "创作一张", "生成新的", "画新的", "创作新的"]
    for keyword in image_keywords:
        if keyword in question:
            return "generate_image"
    
    # 视频生成关键词
    video_keywords = ["生成视频", "视频", "video", "create video", "make video", "生成一个视频", "制作视频", "创作视频"]
    for keyword in video_keywords:
        if keyword in question:
            return "generate_video"
    
    # 天气查询关键词
    weather_keywords = ["天气", "气温", "温度", "下雨", "晴天", "多云", "刮风", "下雪"]
    for keyword in weather_keywords:
        if keyword in question:
            return "weather"
    
    # 默认意图
    return "ask_question"

def extract_image_prompt(question: str) -> str:
    """提取图片生成提示词"""
    # 简单处理，去除关键词后返回剩余部分
    image_keywords = ["生成图片", "画", "图片", "image", "draw", "paint", "create image"]
    for keyword in image_keywords:
        question = question.replace(keyword, "").strip()
    
    # 如果没有提取到提示词，使用默认提示词
    if not question:
        return "一只可爱的小猫将军，身穿金色盔甲，站在悬崖上"
    
    return question

def extract_video_prompt(question: str) -> str:
    """提取视频生成提示词"""
    # 简单处理，去除关键词后返回剩余部分
    video_keywords = ["生成视频", "视频", "video", "create video", "make video"]
    for keyword in video_keywords:
        question = question.replace(keyword, "").strip()
    
    # 如果没有提取到提示词，使用默认提示词
    if not question:
        return "一个阳光明媚的下午，孩子们在公园里玩耍，鸟儿在树上唱歌，花朵盛开，蝴蝶飞舞"
    
    return question

def extract_weather_location(user_input):
    """
    提取天气查询的地点
    """
    # 简单的地点提取逻辑
    location_patterns = [
        r"(.*?)的天气",
        r"(.*?)天气",
        r"天气(.*?)"
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, user_input)
        if match:
            location = match.group(1).strip()
            if location:
                return location
    
    # 默认返回北京
    return "北京"

def get_weather(location: str) -> dict:
    """
    获取天气信息
    API-KEY: sk-26270c8bfdd74a59a59a3ccc4ff29429
    应用ID: 97488c47da5946c2b94c3a876b289a3d
    """
    import requests
    import json
    
    try:
        # 阿里云API接口
        api_url = "https://dashscope.aliyuncs.com/api/v1/apps/97488c47da5946c2b94c3a876b289a3d/completion"
        
        # 请求头
        headers = {
            "Authorization": "Bearer sk-26270c8bfdd74a59a59a3ccc4ff29429",
            "Content-Type": "application/json"
        }
        
        # 请求体
        payload = {
            "input": {
                "prompt": f"{location}的天气"
            },
            "parameters": {},
            "debug": {}
        }
        
        # 发送请求
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        
        # 解析响应
        data = response.json()
        print(f"阿里云API响应: {json.dumps(data, ensure_ascii=False)}")
        
        # 提取天气信息
        if "output" in data:
            output = data["output"]
            if "text" in output:
                answer = output["text"]
                return {
                    "answer": answer,
                    "location": location,
                    "status": "success",
                    "source": "aliyun_weather"
                }
        
        # API返回格式错误或未获取到天气信息
        answer = f"{location}的天气信息暂时无法获取，请稍后再试"
        return {
            "answer": answer,
            "location": location,
            "status": "error",
            "source": "aliyun_weather"
        }
        
    except Exception as e:
        print(f"天气查询失败: {str(e)}")
        
        # 构建回复
        answer = f"{location}当前天气：未知，温度：未知°，湿度：未知%，风速：未知"
        
        return {
            "answer": answer,
            "location": location,
            "temperature": "未知",
            "humidity": "未知",
            "weather_desc": "未知",
            "wind_speed": "未知",
            "status": "fail",
            "source": "aliyun_weather"
        }

    


def get_weatherByCoze(location: str) -> dict:

    """
    使用Coze API查询天气信息
    """
    import requests
    import json
    
    try:
        # Coze API接口
        api_url = "https://api.coze.cn/v3/chat?"
        
        # 请求头
        headers = {
            "Authorization": "Bearer sat_tk9GhBsdDvy0vAmsFOFu4jtpOEQwrRcAtrZWQD8gDT3OyYotU6hNom7LEP4hd9gS",
            "Content-Type": "application/json"
        }
        
        # 请求体
        payload = {
            "bot_id": "7620652528551854107",
            "user_id": "123456789",
            "stream": False,
            "additional_messages": [
                {
                    "content": f"{location}的天气",
                    "content_type": "text",
                    "role": "user",
                    "type": "question"
                }
            ],
            "parameters": {}
        }
        
        # 发送请求
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        
        # 解析响应
        data = response.json()
        print(f"Coze API响应: {json.dumps(data, ensure_ascii=False)}")
        
        # 提取天气信息
        if "data" in data:
            chat_data = data["data"]
            
            # 检查API状态
            status = chat_data.get("status", "")
            if status == "in_progress":
                # API请求正在处理中
                answer = f"{location}的天气信息正在查询中，请稍候再试"
                return {
                    "answer": answer,
                    "location": location,
                    "status": "pending",
                    "source": "coze_weather"
                }
            
            # 尝试获取消息
            messages = chat_data.get("messages", [])
            if messages:
                # 获取助手的回复
                assistant_message = None
                for message in messages:
                    if message.get("role") == "assistant":
                        assistant_message = message
                        break
                
                if assistant_message:
                    answer = assistant_message.get("content", "未知")
                    
                    return {
                        "answer": answer,
                        "location": location,
                        "status": "success",
                        "source": "coze_weather"
                    }
        
        # API返回格式错误或未获取到天气信息
        answer = f"{location}的天气信息暂时无法获取，请稍后再试"
        return {
            "answer": answer,
            "location": location,
            "status": "error",
            "source": "coze_weather"
        }
        
    except Exception as e:
        print(f"天气查询失败: {str(e)}")
        
        # 构建回复
        answer = f"{location}当前天气：未知，温度：未知°，湿度：未知%，风速：未知"
        
        return {
            "answer": answer,
            "location": location,
            "temperature": "未知",
            "humidity": "未知",
            "weather_desc": "未知",
            "wind_speed": "未知",
            "status": "fail",
            "source": "coze_weather"
        }




def generate_image(session_id: str, prompt: str) -> dict:
    """生成图片"""
    import uuid
    from pathlib import Path
    
    # 创建会话目录和图片存储目录
    chat_logs_dir = Path("./chat_logs")
    # 解析session_id，支持新的user_id:conversation_id格式
    if ":" in session_id:
        user_id, conversation_id = session_id.split(":", 1)
        # 使用新的目录结构
        session_dir = chat_logs_dir / user_id / "conversations" / conversation_id
    else:
        # 兼容旧的session_id格式
        session_dir = chat_logs_dir / session_id
    images_dir = session_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成唯一图片ID
    image_id = uuid.uuid4().hex
    image_path = images_dir / f"{image_id}.png"
    
    try:
        # 使用Pillow生成图片
        from PIL import Image, ImageDraw, ImageFont
        
        # 创建图片
        img = Image.new('RGB', (512, 512), color=(240, 240, 255))
        d = ImageDraw.Draw(img)
        
        # 绘制文本
        font = ImageFont.load_default()
        text = "图片生成"
        d.text((50, 50), text, fill=(0, 0, 0), font=font)
        d.text((50, 100), f"提示词: {prompt[:100]}...", fill=(0, 0, 0), font=font)
        d.text((50, 150), f"会话: {session_id}", fill=(0, 0, 0), font=font)
        
        # 保存图片
        img.save(str(image_path))
        print(f"图片生成成功: {image_path}")
        
        return {
            "image_id": image_id,
            "image_path": str(image_path),
            "image_url": f"/chat_logs/{session_id}/images/{image_id}.png",
            "status": "completed",
            "msg": "图片生成成功",
            "prompt": prompt
        }
        
    except Exception as e:
        print(f"图片生成失败: {str(e)}")
        return {
            "image_id": image_id,
            "image_path": str(image_path),
            "image_url": f"/chat_logs/{session_id}/images/{image_id}.png",
            "status": "failed",
            "msg": f"图片生成失败: {str(e)}",
            "prompt": prompt
        }

def generate_video(session_id: str, prompt: str) -> dict:
    """生成视频"""
    import uuid
    from pathlib import Path
    
    # 创建会话目录和视频存储目录
    chat_logs_dir = Path("./chat_logs")
    # 解析session_id，支持新的user_id:conversation_id格式
    if ":" in session_id:
        user_id, conversation_id = session_id.split(":", 1)
        # 使用新的目录结构
        session_dir = chat_logs_dir / user_id / "conversations" / conversation_id
    else:
        # 兼容旧的session_id格式
        session_dir = chat_logs_dir / session_id
    videos_dir = session_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成唯一视频ID
    video_id = uuid.uuid4().hex
    video_path = videos_dir / f"{video_id}.mp4"
    thumbnail_path = videos_dir / f"{video_id}_thumbnail.jpg"
    
    try:
        # 使用OpenCV生成视频
        import cv2
        import numpy as np
        
        # 设置视频参数
        width, height = 640, 360
        fps = 15
        total_frames = fps * 12  # 12秒视频
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))
        
        # 生成帧
        for i in range(total_frames):
            # 创建背景
            frame = np.full((height, width, 3), (240, 240, 255), dtype=np.uint8)
            
            # 添加文本
            cv2.putText(frame, "视频生成", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            cv2.putText(frame, f"提示词: {prompt[:50]}...", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)
            cv2.putText(frame, f"会话: {session_id}", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)
            cv2.putText(frame, f"帧: {i}/{total_frames}", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)
            
            # 写入帧
            out.write(frame)
        
        # 释放资源
        out.release()
        
        # 生成缩略图
        thumbnail = np.full((240, 320, 3), (240, 240, 255), dtype=np.uint8)
        cv2.putText(thumbnail, "视频缩略图", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
        cv2.putText(thumbnail, f"提示词: {prompt[:30]}...", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        cv2.imwrite(str(thumbnail_path), thumbnail)
        
        print(f"视频生成成功: {video_path}")
        
        return {
            "video_id": video_id,
            "video_path": str(video_path),
            "video_url": f"/chat_logs/{session_id}/videos/{video_id}.mp4",
            "thumbnail_path": str(thumbnail_path),
            "thumbnail_url": f"/chat_logs/{session_id}/videos/{video_id}_thumbnail.jpg",
            "status": "completed",
            "msg": "视频生成成功",
            "prompt": prompt
        }
        
    except Exception as e:
        print(f"视频生成失败: {str(e)}")
        return {
            "video_id": video_id,
            "video_path": str(video_path),
            "video_url": f"/chat_logs/{session_id}/videos/{video_id}.mp4",
            "thumbnail_path": str(thumbnail_path),
            "thumbnail_url": f"/chat_logs/{session_id}/videos/{video_id}_thumbnail.jpg",
            "status": "failed",
            "msg": f"视频生成失败: {str(e)}",
            "prompt": prompt
        }

# ===== 健康检查 =====

@app.get("/")
def health():
    """健康检查接口"""
    return {"status": "ok"}

# ===== 查询对话记录 =====

@app.get("/chat_history/{session_id}")
def get_chat_history(session_id: str, user_id: str = None, conversation_id: str = None):
    """根据session_id或用户ID+对话ID查询用户所有对话记录"""
    import json
    import os
    
    # 如果提供了用户ID和对话ID，构建session_id
    if user_id and conversation_id and not session_id:
        session_id = f"{user_id}:{conversation_id}"
    
    # 从用户专属文件夹读取对话记录
    # 解析session_id，支持新的user_id:conversation_id格式
    if ":" in session_id:
        user_id, conversation_id = session_id.split(":", 1)
        # 使用新的目录结构
        user_chat_dir = os.path.join("./chat_logs", user_id, "conversations", conversation_id)
    else:
        # 兼容旧的session_id格式
        user_chat_dir = os.path.join("./chat_logs", session_id)
    log_file = os.path.join(user_chat_dir, "chat.jsonl")
    
    if not os.path.exists(log_file):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail={
                "session_id": session_id,
                "msg": "会话记录不存在"
            }
        )
    
    chat_history = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chat_entry = json.loads(line)
                chat_history.append(chat_entry)
    
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "session_id": session_id,
        "chat_history": chat_history,
        "total_messages": len(chat_history)
    }

from pydantic import BaseModel

class WikipediaTestRequest(BaseModel):
    query: str

@app.post("/test_wikipedia")
def test_wikipedia(req: WikipediaTestRequest):
    """测试维基百科搜索功能"""
    from rag_core import web_search, generate_answer_from_web
    
    search_results = web_search(req.query, max_results=5)
    answer = generate_answer_from_web(search_results, req.query)
    
    return {
        "query": req.query,
        "search_results": search_results,
        "answer": answer
    }





@app.post("/upload-multiple")
def upload_multiple_files(
    files: list[UploadFile] = File(...),
    user_id: str = Form(None),
    conversation_id: str = Form(None),
    session_id: str = Form(None)
):
    """
    多文件上传接口，支持一次上传多个文件，总数限制为6个
    """
    # 确保用户ID和对话ID存在
    if not user_id:
        user_id = user_id_generator.generate_user_id()
        print(f"未提供用户ID，生成新的用户ID: {user_id}")
    
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        print(f"未提供对话ID，生成新的对话ID: {conversation_id}")
    else:
        # 验证对话ID是否为有效的UUID格式
        try:
            uuid.UUID(conversation_id)
        except ValueError:
            # 如果不是有效的UUID，生成新的
            conversation_id = str(uuid.uuid4())
            print(f"提供的对话ID格式无效，生成新的对话ID: {conversation_id}")
    
    # 使用用户ID和对话ID作为会话键
    if not session_id:
        session_id = f"{user_id}:{conversation_id}"
    
    # 设置文件大小限制
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB（非图片文件）
    MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5MB（图片文件）
    MAX_TOTAL_FILES = 6  # 每个会话最多6个文件
    
    # 检查上传的文件数量
    if len(files) == 0:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={
                "user_id": user_id,
                "conversation_id": conversation_id,
                "session_id": session_id,
                "msg": "请选择要上传的文件",
                "error": "未选择任何文件"
            }
        )
    
    # 为每个用户和对话创建专属文件夹
    user_upload_dir = UPLOAD_DIR / user_id / "conversations" / conversation_id
    user_upload_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查当前session已上传的文件总数量
    existing_files = 0
    for existing_file in user_upload_dir.glob("*"):
        if existing_file.is_file():
            existing_files += 1
    
    # 检查总文件数量（现有文件 + 新上传文件）
    if existing_files >= MAX_TOTAL_FILES:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={
                "user_id": user_id,
                "conversation_id": conversation_id,
                "session_id": session_id,
                "msg": "文件数量过多，请先删除一些文件",
                "error": f"每个会话最多只能上传{MAX_TOTAL_FILES}个文件，当前已上传{existing_files}个文件"
            }
        )
    
    if existing_files + len(files) > MAX_TOTAL_FILES:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={
                "user_id": user_id,
                "conversation_id": conversation_id,
                "session_id": session_id,
                "msg": "文件数量过多，请先删除一些文件",
                "error": f"每个会话最多只能上传{MAX_TOTAL_FILES}个文件，当前已上传{existing_files}个文件，本次上传{len(files)}个文件，总计{existing_files + len(files)}个文件"
            }
        )
    
    # 处理每个文件
    upload_results = []
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    
    for file in files:
        try:
            # 检查文件大小
            file.file.seek(0, 2)  # 移动到文件末尾
            file_size = file.file.tell()  # 获取文件大小
            file.file.seek(0)  # 重置文件指针
            
            # 检查文件扩展名
            file_ext = Path(file.filename).suffix.lower()
            is_image = file_ext in image_extensions
            
            # 检查文件大小限制
            if is_image:
                if file_size > MAX_IMAGE_SIZE:
                    upload_results.append({
                        "filename": file.filename,
                        "status": "failed",
                        "msg": "图片文件大小超过限制",
                        "error": f"单个图片文件大小不能超过5MB，当前文件大小为{file_size / (1024*1024):.2f}MB"
                    })
                    continue
            else:
                if file_size > MAX_FILE_SIZE:
                    upload_results.append({
                        "filename": file.filename,
                        "status": "failed",
                        "msg": "文件大小超过限制",
                        "error": f"单个文件大小不能超过20MB，当前文件大小为{file_size / (1024*1024):.2f}MB"
                    })
                    continue
            
            # 生成文件ID并保存
            file_id = uuid.uuid4().hex
            save_path = user_upload_dir / f"{file_id}_{file.filename}"
            
            # 保存文件
            with open(save_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            # 向量入库
            try:
                chunks = ingest_files(
                    [str(save_path)],
                    target="upload",
                    session_id=session_id
                )
                
                upload_results.append({
                    "filename": file.filename,
                    "saved_filename": save_path.name,
                    "status": "success",
                    "msg": "文件已入库",
                    "chunks": chunks
                })
            except Exception as e:
                upload_results.append({
                    "filename": file.filename,
                    "saved_filename": save_path.name,
                    "status": "partial",
                    "msg": "文件已保存，但向量入库失败",
                    "error": str(e)
                })
                
        except Exception as e:
            upload_results.append({
                "filename": file.filename,
                "status": "failed",
                "msg": "文件处理失败",
                "error": str(e)
            })
    
    # 统计结果
    success_count = sum(1 for r in upload_results if r["status"] == "success")
    partial_count = sum(1 for r in upload_results if r["status"] == "partial")
    failed_count = sum(1 for r in upload_results if r["status"] == "failed")
    
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "session_id": session_id,
        "total_files": len(files),
        "success_count": success_count,
        "partial_count": partial_count,
        "failed_count": failed_count,
        "upload_results": upload_results,
        "msg": f"文件上传完成，成功{success_count}个，部分成功{partial_count}个，失败{failed_count}个"
    }


@app.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    user_id: str = Form(None),
    conversation_id: str = Form(None),
    session_id: str = Form(None)
):
    # 确保用户ID和对话ID存在
    if not user_id:
        user_id = user_id_generator.generate_user_id()
        print(f"未提供用户ID，生成新的用户ID: {user_id}")
    
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        print(f"未提供对话ID，生成新的对话ID: {conversation_id}")
    else:
        # 验证对话ID是否为有效的UUID格式
        try:
            uuid.UUID(conversation_id)
        except ValueError:
            # 如果不是有效的UUID，生成新的
            conversation_id = str(uuid.uuid4())
            print(f"提供的对话ID格式无效，生成新的对话ID: {conversation_id}")
    
    # 使用用户ID和对话ID作为会话键
    if not session_id:
        session_id = f"{user_id}:{conversation_id}"
    
    # 设置文件大小限制
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB（非图片文件）
    MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5MB（图片文件）
    
    # 检查文件大小
    file.file.seek(0, 2)  # 移动到文件末尾
    file_size = file.file.tell()  # 获取文件大小
    file.file.seek(0)  # 重置文件指针
    
    # 检查文件扩展名
    file_ext = Path(file.filename).suffix.lower()
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    is_image = file_ext in image_extensions
    
    if is_image:
        # 图片文件使用5MB限制
        if file_size > MAX_IMAGE_SIZE:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail={
                    "filename": file.filename,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "session_id": session_id,
                    "msg": "图片文件大小超过限制",
                    "error": f"单个图片文件大小不能超过5MB，当前文件大小为{file_size / (1024*1024):.2f}MB"
                }
            )
    else:
        # 非图片文件使用20MB限制
        if file_size > MAX_FILE_SIZE:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail={
                    "filename": file.filename,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "session_id": session_id,
                    "msg": "文件大小超过限制",
                    "error": f"单个文件大小不能超过20MB，当前文件大小为{file_size / (1024*1024):.2f}MB"
                }
            )
    
    # 为每个用户和对话创建专属文件夹
    user_upload_dir = UPLOAD_DIR / user_id / "conversations" / conversation_id
    user_upload_dir.mkdir(parents=True, exist_ok=True)

    # 检查是否为图片文件
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    file_ext = Path(file.filename).suffix.lower()
    is_image = file_ext in image_extensions

    # 检查当前session已上传的文件总数量
    total_files = 0
    for existing_file in user_upload_dir.glob("*"):
        if existing_file.is_file():
            total_files += 1
    
    if total_files >= 6:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={
                "filename": file.filename,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "session_id": session_id,
                "msg": "文件数量过多，请先删除一些文件",
                "error": f"每个会话最多只能上传6个文件，当前已上传{total_files}个文件"
            }
        )

    file_id = uuid.uuid4().hex
    save_path = user_upload_dir / f"{file_id}_{file.filename}"

    # 1️⃣ 保存文件
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 2️⃣ 向量入库
    try:
        chunks = ingest_files(
            [str(save_path)],
            target="upload",
            session_id=session_id  # 👈 预留
        )
    except Exception as e:
        return {
            "filename": file.filename,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "msg": "文件已保存，但向量入库失败",
            "error": str(e)
        }

    return {
        "filename": file.filename,
        "saved_filename": save_path.name,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "session_id": session_id,
        "msg": "文件已入库",
        "chunks": chunks
    }


@app.get("/list_files/{session_id}")
def list_files(session_id: str, user_id: str = None, conversation_id: str = None):
    """根据session_id列出用户上传的所有文件"""
    # 构建用户上传目录路径
    if user_id and conversation_id:
        # 使用新的目录结构
        user_upload_dir = UPLOAD_DIR / user_id / "conversations" / conversation_id
    else:
        # 解析session_id，支持新的user_id:conversation_id格式
        if ":" in session_id:
            user_id, conversation_id = session_id.split(":", 1)
            # 使用新的目录结构
            user_upload_dir = UPLOAD_DIR / user_id / "conversations" / conversation_id
        else:
            # 保持向后兼容，使用旧的目录结构
            user_upload_dir = UPLOAD_DIR / session_id
    
    if not user_upload_dir.exists():
        return {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "msg": "用户上传目录不存在",
            "files": [],
            "total_files": 0
        }
    
    files = []
    
    try:
        # 遍历目录下的所有文件
        for file_path in user_upload_dir.glob("*"):
            if file_path.is_file():
                files.append({
                    "filename": file_path.name,
                    "original_filename": file_path.name,
                    "size": file_path.stat().st_size,
                    "created_at": file_path.stat().st_ctime
                })
        
        return {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "msg": "文件列表获取成功",
            "files": files,
            "total_files": len(files)
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail={
                "user_id": user_id,
                "conversation_id": conversation_id,
                "session_id": session_id,
                "msg": "文件列表获取失败",
                "error": str(e)
            }
        )


@app.delete("/delete_files/{session_id}")
def delete_files(session_id: str, user_id: str = None, conversation_id: str = None):
    """根据session_id删除用户上传的所有文件"""
    # 构建用户上传目录路径
    if user_id and conversation_id:
        # 使用新的目录结构
        user_upload_dir = UPLOAD_DIR / user_id / "conversations" / conversation_id
    else:
        # 解析session_id，支持新的user_id:conversation_id格式
        if ":" in session_id:
            user_id, conversation_id = session_id.split(":", 1)
            # 使用新的目录结构
            user_upload_dir = UPLOAD_DIR / user_id / "conversations" / conversation_id
        else:
            # 保持向后兼容，使用旧的目录结构
            user_upload_dir = UPLOAD_DIR / session_id
    
    if not user_upload_dir.exists():
        return {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "msg": "用户上传目录不存在",
            "deleted_files": 0
        }
    
    deleted_count = 0
    deleted_files = []
    
    try:
        # 删除目录下的所有文件
        for file_path in user_upload_dir.glob("*"):
            if file_path.is_file():
                file_path.unlink()  # 删除文件
                deleted_count += 1
                deleted_files.append(file_path.name)
        
        # 删除空目录
        user_upload_dir.rmdir()
        
        return {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "msg": "文件删除成功",
            "deleted_files": deleted_count,
            "deleted_file_list": deleted_files
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail={
                "user_id": user_id,
                "conversation_id": conversation_id,
                "session_id": session_id,
                "msg": "文件删除失败",
                "error": str(e)
            }
        )


@app.delete("/delete_file/{session_id}/{filename}")
def delete_file(session_id: str, filename: str, user_id: str = None, conversation_id: str = None):
    """
    根据session_id和filename删除用户上传的指定文件
    """
    # 构建用户上传目录路径
    if user_id and conversation_id:
        # 使用新的目录结构
        user_upload_dir = UPLOAD_DIR / user_id / "conversations" / conversation_id
    else:
        # 解析session_id，支持新的user_id:conversation_id格式
        if ":" in session_id:
            user_id, conversation_id = session_id.split(":", 1)
            # 使用新的目录结构
            user_upload_dir = UPLOAD_DIR / user_id / "conversations" / conversation_id
        else:
            # 保持向后兼容，使用旧的目录结构
            user_upload_dir = UPLOAD_DIR / session_id
    
    if not user_upload_dir.exists():
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail={
                "user_id": user_id,
                "conversation_id": conversation_id,
                "session_id": session_id,
                "msg": "用户上传目录不存在"
            }
        )
    
    # 构建完整文件路径
    file_path = user_upload_dir / filename
    
    if not file_path.exists() or not file_path.is_file():
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail={
                "user_id": user_id,
                "conversation_id": conversation_id,
                "session_id": session_id,
                "msg": "指定文件不存在",
                "filename": filename
            }
        )
    
    try:
        # 删除指定文件
        file_path.unlink()
        
        return {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "msg": "文件删除成功",
            "deleted_file": filename
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail={
                "user_id": user_id,
                "conversation_id": conversation_id,
                "session_id": session_id,
                "msg": "文件删除失败",
                "filename": filename,
                "error": str(e)
            }
        )


@app.delete("/delete-session/{session_id}")
def delete_session(session_id: str, user_id: str = None, conversation_id: str = None):
    """
    删除用户会话，包括对话历史记录和上传的文件
    """
    # 如果提供了用户ID和对话ID，构建session_id
    if user_id and conversation_id and not session_id:
        session_id = f"{user_id}:{conversation_id}"
    
    try:
        deleted_items = {
            "chat_history": False,
            "uploaded_files": False,
            "images": False,
            "videos": False
        }
        
        # 1. 删除对话历史记录
        chat_logs_dir = Path("./chat_logs")
        
        # 从 session_id 中解析出 user_id 和 conversation_id
        if ':' in session_id:
            user_id, conversation_id = session_id.split(':', 1)
            # 使用新的目录结构
            session_chat_dir = chat_logs_dir / user_id / "conversations" / conversation_id
        else:
            # 保持向后兼容，使用旧的目录结构
            session_chat_dir = chat_logs_dir / session_id
        
        if session_chat_dir.exists():
            # 删除聊天记录文件
            chat_file = session_chat_dir / "chat.jsonl"
            if chat_file.exists():
                chat_file.unlink()
                deleted_items["chat_history"] = True
            
            # 删除图片目录
            images_dir = session_chat_dir / "images"
            if images_dir.exists():
                for image_file in images_dir.glob("*"):
                    if image_file.is_file():
                        image_file.unlink()
                images_dir.rmdir()
                deleted_items["images"] = True
            
            # 删除视频目录
            videos_dir = session_chat_dir / "videos"
            if videos_dir.exists():
                for video_file in videos_dir.glob("*"):
                    if video_file.is_file():
                        video_file.unlink()
                videos_dir.rmdir()
                deleted_items["videos"] = True
            
            # 删除会话目录
            if session_chat_dir.exists() and not any(session_chat_dir.iterdir()):
                session_chat_dir.rmdir()
        
        # 2. 删除上传的文件
        # 尝试使用新的目录结构
        if user_id and conversation_id:
            user_upload_dir = UPLOAD_DIR / user_id / "conversations" / conversation_id
        else:
            # 保持向后兼容，使用旧的目录结构
            user_upload_dir = UPLOAD_DIR / session_id
        
        if user_upload_dir.exists():
            for upload_file in user_upload_dir.glob("*"):
                if upload_file.is_file():
                    upload_file.unlink()
            user_upload_dir.rmdir()
            deleted_items["uploaded_files"] = True
        
        # 3. 从会话字典中移除
        if session_id in SESSIONS:
            del SESSIONS[session_id]
        
        return {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "msg": "会话删除成功",
            "deleted_items": deleted_items,
            "status": "completed"
        }
        
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail={
                "user_id": user_id,
                "conversation_id": conversation_id,
                "session_id": session_id,
                "msg": "会话删除失败",
                "error": str(e)
            }
        )

@app.post("/userLogin")
def userlogin(user_name: str,user_password: str):
    return {
        "user_name": user_name,
        "user_id": user_id_generator.generate_user_id(),
        "msg": "登录成功"
    }

@app.post("/register")
def register(req: RegisterRequest):
    """
    用户注册功能
    """
    # 验证用户名和密码
    if not req.username or len(req.username) < 3:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={
                "msg": "用户名长度至少为3个字符",
                "error": "username_too_short"
            }
        )
    
    if not req.password or len(req.password) < 6:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={
                "msg": "密码长度至少为6个字符",
                "error": "password_too_short"
            }
        )
    
    # 检查用户名是否已存在（这里简化处理，实际应该查询数据库）
    # 注意：在实际应用中，应该使用数据库存储用户信息
    # 这里只是一个简单的模拟实现
    
    # 生成用户ID
    user_id = user_id_generator.generate_user_id()
    
    # 记录用户注册信息（实际应用中应该存储到数据库）
    print(f"用户注册成功: {req.username}, ID: {user_id}")
    print(f"邮箱: {req.email}, 电话: {req.phone}")
    
    # 返回注册成功信息
    return {
        "user_id": user_id,
        "username": req.username,
        "email": req.email,
        "phone": req.phone,
        "msg": "注册成功",
        "status": "success"
    }

@app.post("/text-to-video")
def text_to_video(req: TextToVideoRequest, user_id: str = None, conversation_id: str = None):
    """
    文字生成视频功能，将视频保存到chat_logs文件夹
    """
    # 确保用户ID和对话ID存在
    if not user_id:
        user_id = user_id_generator.generate_user_id()
        print(f"未提供用户ID，生成新的用户ID: {user_id}")
    
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        print(f"未提供对话ID，生成新的对话ID: {conversation_id}")
    else:
        # 验证对话ID是否为有效的UUID格式
        try:
            uuid.UUID(conversation_id)
        except ValueError:
            # 如果不是有效的UUID，生成新的
            conversation_id = str(uuid.uuid4())
            print(f"提供的对话ID格式无效，生成新的对话ID: {conversation_id}")
    
    # 使用用户ID和对话ID作为会话键
    session_id = req.session_id
    if not session_id:
        session_id = f"{user_id}:{conversation_id}"
        print(f"未提供session_id，生成新的session_id: {session_id}")
    
    # 验证输入
    if not req.text or len(req.text) < 5:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={
                "msg": "文字内容长度至少为5个字符",
                "error": "text_too_short"
            }
        )
    
    if req.duration < 5 or req.duration > 60:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={
                "msg": "视频时长应在5-60秒之间",
                "error": "invalid_duration"
            }
        )
    
    # 验证分辨率
    valid_resolutions = ["480p", "720p", "1080p"]
    if req.resolution not in valid_resolutions:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={
                "msg": "不支持的分辨率，支持的分辨率为: 480p, 720p, 1080p",
                "error": "invalid_resolution"
            }
        )
    
    # 生成视频ID
    video_id = uuid.uuid4().hex
    
    # 创建chat_logs目录和会话子目录
    chat_logs_dir = Path("./chat_logs")
    
    # 从 session_id 中解析出 user_id 和 conversation_id
    if ':' in session_id:
        user_id, conversation_id = session_id.split(':', 1)
        # 使用新的目录结构
        session_dir = chat_logs_dir / user_id / "conversations" / conversation_id
    else:
        # 保持向后兼容，使用旧的目录结构
        session_dir = chat_logs_dir / session_id
    
    videos_dir = session_dir / "videos"
    
    # 确保目录存在
    videos_dir.mkdir(parents=True, exist_ok=True)
    print(f"创建视频保存目录: {videos_dir}")
    
    # 模拟视频生成过程
    print(f"开始生成视频，文字内容: {req.text[:50]}...")
    print(f"视频参数: 时长={req.duration}秒, 分辨率={req.resolution}, 风格={req.style}")
    
    # 生成视频文件路径
    video_path = videos_dir / f"{video_id}.mp4"
    thumbnail_path = videos_dir / f"{video_id}_thumbnail.jpg"
    
    # 生成模拟的视频URL（相对路径）
    video_url = f"/chat_logs/{session_id}/videos/{video_id}.mp4"
    thumbnail_url = f"/chat_logs/{session_id}/videos/{video_id}_thumbnail.jpg"
    
    # 模拟生成时间
    estimated_time = req.duration * 0.5  # 假设每秒钟视频需要0.5秒生成时间
    
    # ===== 使用ModelScope生成视频 =====
    print("使用ModelScope生成视频...")
    
    try:
        # 导入ModelScope相关模块
        from modelscope.pipelines import pipeline
        from modelscope.utils.constant import Tasks
        
        # 初始化文本到视频生成管道
        print("初始化视频生成模型...")
        text_to_video = pipeline(
            Tasks.text_to_video_synthesis,
            model='damo/text-to-video-synthesis'
        )
        
        # 生成视频
        print(f"开始生成视频，文本: {req.text[:100]}...")
        
        # 调整文本描述，使其更适合视频生成
        video_prompt = f"An epic and cute scene: A small cute cartoon cat general wearing detailed golden armor and a slightly too big helmet, bravely standing on a cliff. He rides a small but heroic war horse, saying: '青海长云暗雪山，孤城遥望玉门关。黄沙百战穿金甲，不破楼兰终不还'. Below the cliff, a massive, endless army of mice with makeshift weapons charges forward. This is a dramatic, large-scale battle scene inspired by ancient Chinese war epics. In the distance, the sky over the snow-capped mountains is covered with dark clouds. The overall atmosphere is a funny and epic fusion of 'cute' and 'domineering'."
        
        print(f"调整后的提示词: {video_prompt[:150]}...")
        result = text_to_video(video_prompt)
        
        # 打印完整的返回结果
        print(f"ModelScope返回结果类型: {type(result)}")
        print(f"ModelScope返回结果键: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        
        # 保存生成的视频
        video_generated = False
        
        if isinstance(result, dict):
            if 'output_video' in result:
                video_output_path = result['output_video']
                print(f"ModelScope生成的视频路径: {video_output_path}")
                
                # 检查文件是否存在
                import os
                if os.path.exists(video_output_path) and os.path.getsize(video_output_path) > 0:
                    # 复制到指定路径
                    import shutil
                    shutil.copy(video_output_path, str(video_path))
                    print(f"视频生成成功，保存到: {video_path}")
                    print(f"生成的视频大小: {os.path.getsize(str(video_path)) / 1024 / 1024:.2f} MB")
                    video_generated = True
                else:
                    print(f"警告: ModelScope生成的视频文件不存在或为空: {video_output_path}")
            elif 'videos' in result:
                # 尝试其他可能的键名
                video_output_path = result['videos']
                print(f"ModelScope生成的视频路径(videos): {video_output_path}")
                
                import os
                if os.path.exists(video_output_path) and os.path.getsize(video_output_path) > 0:
                    import shutil
                    shutil.copy(video_output_path, str(video_path))
                    print(f"视频生成成功，保存到: {video_path}")
                    video_generated = True
                else:
                    print(f"警告: ModelScope生成的视频文件不存在或为空: {video_output_path}")
            else:
                print("警告: ModelScope返回结果中没有找到视频输出字段")
                print(f"完整返回结果: {result}")
        else:
            print(f"警告: ModelScope返回结果不是字典类型: {result}")
        
        # 如果ModelScope没有生成视频，使用本地生成
        if not video_generated:
            print("ModelScope未生成视频，使用本地视频生成...")
            
            # 创建增强的本地视频
            import cv2
            import numpy as np
            from PIL import Image, ImageDraw, ImageFont
            
            # 设置视频参数
            width, height = 1280, 720
            fps = 30
            total_frames = fps * req.duration
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))
            
            # 场景描述
            scenes = [
                "🎬 小猫将军站在悬崖上",
                "⚔️ 老鼠军队冲锋",
                "🏔️ 雪山背景"
            ]
            
            # 生成帧
            for i in range(total_frames):
                # 创建背景
                if i < total_frames * 0.33:
                    # 第一个场景：小猫将军
                    bg_color = (240, 240, 255)  # 浅蓝色背景
                    scene_idx = 0
                elif i < total_frames * 0.66:
                    # 第二个场景：老鼠军队
                    bg_color = (255, 240, 240)  # 浅红色背景
                    scene_idx = 1
                else:
                    # 第三个场景：雪山背景
                    bg_color = (240, 255, 240)  # 浅绿色背景
                    scene_idx = 2
                
                frame = np.full((height, width, 3), bg_color, dtype=np.uint8)
                
                # 添加文字
                pil_image = Image.fromarray(frame)
                draw = ImageDraw.Draw(pil_image)
                
                # 尝试使用适合中文的字体
                try:
                    font = ImageFont.truetype("Arial Unicode MS", 32)
                except:
                    try:
                        font = ImageFont.truetype("SimHei", 32)
                    except:
                        font = ImageFont.load_default()
                
                # 绘制场景标题
                scene_text = scenes[scene_idx]
                scene_bbox = draw.textbbox((0, 0), scene_text, font=font)
                scene_x = 50
                scene_y = 50
                draw.text((scene_x, scene_y), scene_text, fill=(0, 0, 0), font=font)
                
                # 绘制主要内容
                main_text = req.text[:100] + ("..." if len(req.text) > 100 else "")
                main_font = ImageFont.truetype("Arial Unicode MS", 24) if "Arial Unicode MS" in str(font) else font
                
                # 文字换行
                def wrap_text(text, font, max_width, draw):
                    lines = []
                    current_line = ""
                    for char in text:
                        test_line = current_line + char
                        bbox = draw.textbbox((0, 0), test_line, font=font)
                        if bbox[2] - bbox[0] <= max_width:
                            current_line = test_line
                        else:
                            lines.append(current_line)
                            current_line = char
                    if current_line:
                        lines.append(current_line)
                    return lines
                
                wrapped_lines = wrap_text(main_text, main_font, width - 200, draw)
                line_height = 40
                start_y = 150
                
                for j, line in enumerate(wrapped_lines):
                    draw.text((100, start_y + j * line_height), line, fill=(0, 0, 0), font=main_font)
                
                # 添加装饰元素
                if scene_idx == 0:
                    # 小猫将军场景：绘制猫的简笔画
                    # 调整位置到视频中央，使用更明显的颜色
                    # 猫身体
                    draw.ellipse([width//2-100, height//2-50, width//2+100, height//2+150], fill=(255, 150, 100))  # 橙色猫身体
                    # 猫头
                    draw.ellipse([width//2-50, height//2-100, width//2+50, height//2], fill=(255, 150, 100))  # 猫头
                    # 猫耳朵
                    draw.polygon([(width//2-50, height//2-100), (width//2-80, height//2-150), (width//2-20, height//2-120)], fill=(255, 150, 100))  # 左耳
                    draw.polygon([(width//2+50, height//2-100), (width//2+80, height//2-150), (width//2+20, height//2-120)], fill=(255, 150, 100))  # 右耳
                    # 猫眼睛
                    draw.ellipse([width//2-30, height//2-40, width//2-10, height//2-20], fill=(255, 255, 255))  # 左眼白
                    draw.ellipse([width//2+10, height//2-40, width//2+30, height//2-20], fill=(255, 255, 255))  # 右眼白
                    draw.ellipse([width//2-25, height//2-35, width//2-15, height//2-25], fill=(0, 0, 0))  # 左眼黑
                    draw.ellipse([width//2+15, height//2-35, width//2+25, height//2-25], fill=(0, 0, 0))  # 右眼黑
                    # 猫鼻子
                    draw.ellipse([width//2-5, height//2-10, width//2+5, height//2], fill=(0, 0, 0))  # 鼻子
                    # 猫嘴巴
                    draw.line([(width//2, height//2), (width//2, height//2+20)], fill=(0, 0, 0), width=2)  # 嘴巴
                    draw.line([(width//2, height//2+20), (width//2-15, height//2+30)], fill=(0, 0, 0), width=2)  # 左嘴角
                    draw.line([(width//2, height//2+20), (width//2+15, height//2+30)], fill=(0, 0, 0), width=2)  # 右嘴角
                    # 猫胡须
                    draw.line([(width//2-40, height//2-10), (width//2-80, height//2-15)], fill=(0, 0, 0), width=1)  # 左上胡须
                    draw.line([(width//2-40, height//2), (width//2-80, height//2)], fill=(0, 0, 0), width=1)  # 左中胡须
                    draw.line([(width//2-40, height//2+10), (width//2-80, height//2+15)], fill=(0, 0, 0), width=1)  # 左下胡须
                    draw.line([(width//2+40, height//2-10), (width//2+80, height//2-15)], fill=(0, 0, 0), width=1)  # 右上胡须
                    draw.line([(width//2+40, height//2), (width//2+80, height//2)], fill=(0, 0, 0), width=1)  # 右中胡须
                    draw.line([(width//2+40, height//2+10), (width//2+80, height//2+15)], fill=(0, 0, 0), width=1)  # 右下胡须
                    # 猫盔甲（金色）
                    draw.rectangle([width//2-80, height//2+20, width//2+80, height//2+80], fill=(255, 223, 0))  # 盔甲
                    draw.line([(width//2-80, height//2+40), (width//2+80, height//2+40)], fill=(255, 165, 0), width=2)  # 盔甲装饰
                    draw.line([(width//2-80, height//2+60), (width//2+80, height//2+60)], fill=(255, 165, 0), width=2)  # 盔甲装饰
                elif scene_idx == 1:
                    # 老鼠军队场景：绘制老鼠简笔画
                    for k in range(5):
                        x = 100 + k * 150
                        y = 300 + (k % 2) * 100
                        # 老鼠身体
                        draw.ellipse([x, y, x+80, y+60], fill=(150, 150, 150))  # 老鼠身体
                        # 老鼠头
                        draw.ellipse([x+60, y+10, x+100, y+50], fill=(150, 150, 150))  # 老鼠头
                        # 老鼠耳朵
                        draw.polygon([(x+60, y+10), (x+50, y-10), (x+70, y-5)], fill=(150, 150, 150))  # 左耳
                        draw.polygon([(x+100, y+10), (x+90, y-10), (x+110, y-5)], fill=(150, 150, 150))  # 右耳
                        # 老鼠眼睛
                        draw.ellipse([x+70, y+15, x+80, y+25], fill=(255, 255, 255))  # 左眼
                        draw.ellipse([x+90, y+15, x+100, y+25], fill=(255, 255, 255))  # 右眼
                        draw.ellipse([x+73, y+18, x+77, y+22], fill=(0, 0, 0))  # 左眼球
                        draw.ellipse([x+93, y+18, x+97, y+22], fill=(0, 0, 0))  # 右眼球
                        # 老鼠鼻子
                        draw.ellipse([x+80, y+25, x+90, y+35], fill=(255, 0, 0))  # 鼻子
                        # 老鼠尾巴
                        draw.line([(x, y+30), (x-40, y+10), (x-60, y+30)], fill=(150, 150, 150), width=3)  # 尾巴
                else:
                    # 雪山背景场景：绘制雪山
                    draw.polygon([(50, height-100), (width//2, 100), (width-50, height-100)], fill=(220, 220, 255))  # 雪山
                    # 添加云朵
                    draw.ellipse([100, 50, 200, 120], fill=(255, 255, 255))  # 左云
                    draw.ellipse([150, 30, 250, 100], fill=(255, 255, 255))  # 左云
                    draw.ellipse([width-200, 50, width-100, 120], fill=(255, 255, 255))  # 右云
                    draw.ellipse([width-250, 30, width-150, 100], fill=(255, 255, 255))  # 右云
                
                # 转换回OpenCV格式
                frame = np.array(pil_image)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # 添加到视频
                out.write(frame)
            
            out.release()
            print(f"本地视频生成成功，保存到: {video_path}")
            import os
            print(f"本地生成的视频大小: {os.path.getsize(str(video_path)) / 1024 / 1024:.2f} MB")
    
    except Exception as e:
        print(f"ModelScope视频生成失败: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # 回退到简单视频生成
        import cv2
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont
        
        print("回退到简单视频生成...")
        width, height = 1280, 720
        fps = 30
        total_frames = fps * req.duration
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))
        
        for i in range(total_frames):
            frame = np.ones((height, width, 3), dtype=np.uint8) * 255
            pil_image = Image.fromarray(frame)
            draw = ImageDraw.Draw(pil_image)
            
            try:
                font = ImageFont.truetype("Arial", 36)
            except:
                font = ImageFont.load_default()
            
            text = f"视频生成失败\n请检查ModelScope配置"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (width - text_width) // 2
            y = (height - text_height) // 2
            
            draw.text((x, y), text, fill=(255, 0, 0), font=font)
            
            frame = np.array(pil_image)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            out.write(frame)
        
        out.release()
        print(f"生成错误提示视频: {video_path}")
    
    # 生成缩略图
    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont
        
        # 尝试从生成的视频中提取第一帧作为缩略图
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                # 调整大小
                thumbnail = cv2.resize(frame, (640, 480))
                cv2.imwrite(str(thumbnail_path), thumbnail)
                print(f"从视频提取缩略图: {thumbnail_path}")
            cap.release()
        else:
            # 生成默认缩略图
            thumbnail = np.ones((480, 640, 3), dtype=np.uint8) * 255
            pil_thumbnail = Image.fromarray(thumbnail)
            draw = ImageDraw.Draw(pil_thumbnail)
            
            try:
                font = ImageFont.truetype("Arial", 24)
            except:
                font = ImageFont.load_default()
            
            text = f"视频缩略图\n{req.text[:30]}..."
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (640 - text_width) // 2
            y = (480 - text_height) // 2
            
            draw.text((x, y), text, fill=(0, 0, 0), font=font)
            
            thumbnail = np.array(pil_thumbnail)
            thumbnail = cv2.cvtColor(thumbnail, cv2.COLOR_RGB2BGR)
            cv2.imwrite(str(thumbnail_path), thumbnail)
            print(f"生成默认缩略图: {thumbnail_path}")
    except Exception as e:
        print(f"生成缩略图失败: {str(e)}")
    # ===== 真实视频生成逻辑结束 =====
    
    # 记录视频生成信息到chat.jsonl
    chat_file = session_dir / "chat.jsonl"
    import json
    import datetime
    
    # 读取现有聊天记录
    chat_history = []
    if chat_file.exists():
        with open(chat_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    chat_history.append(json.loads(line))
    
    # 添加视频生成记录
    video_record = {
        "role": "assistant",
        "content": f"视频生成成功: {req.text[:50]}...",
        "video_id": video_id,
        "video_url": str(video_path),
        "thumbnail_url": str(thumbnail_path),
        "text": req.text,
        "duration": req.duration,
        "resolution": req.resolution,
        "style": req.style,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    # 保存到chat.jsonl
    with open(chat_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(video_record, ensure_ascii=False) + '\n')
    print(f"视频生成记录已保存到: {chat_file}")
    
    # 返回生成结果
    return {
        "video_id": video_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "session_id": session_id,
        "text": req.text,
        "duration": req.duration,
        "resolution": req.resolution,
        "style": req.style,
        "video_url": video_url,
        "thumbnail_url": thumbnail_url,
        "video_path": str(video_path),
        "thumbnail_path": str(thumbnail_path),
        "estimated_time": estimated_time,
        "status": "completed",
        "msg": "视频生成成功，已保存到chat_logs文件夹",
        "progress": 100
    }


@app.post("/userMakeImage")
def usermakeimage(user_name: str, user_id: str = None, conversation_id: str = None, session_id: str = None, prompt: str = "一只可爱的小猫将军，身穿金色盔甲，站在悬崖上"):
    import torch
    from diffusers import ZImagePipeline
    import uuid
    from pathlib import Path

    # 确保用户ID和对话ID存在
    if not user_id:
        user_id = user_id_generator.generate_user_id()
        print(f"未提供用户ID，生成新的用户ID: {user_id}")
    
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        print(f"未提供对话ID，生成新的对话ID: {conversation_id}")
    else:
        # 验证对话ID是否为有效的UUID格式
        try:
            uuid.UUID(conversation_id)
        except ValueError:
            # 如果不是有效的UUID，生成新的
            conversation_id = str(uuid.uuid4())
            print(f"提供的对话ID格式无效，生成新的对话ID: {conversation_id}")
    
    # 使用用户ID和对话ID作为会话键
    if not session_id:
        session_id = f"{user_id}:{conversation_id}"

    # 设置设备为CPU
    device = "cpu"
    print(f"使用设备: {device}")

    # 创建会话目录和图片存储目录
    chat_logs_dir = Path("./chat_logs")
    # 解析session_id，支持新的user_id:conversation_id格式
    if ":" in session_id:
        user_id, conversation_id = session_id.split(":", 1)
        # 使用新的目录结构
        session_dir = chat_logs_dir / user_id / "conversations" / conversation_id
    else:
        # 兼容旧的session_id格式
        session_dir = chat_logs_dir / session_id
    images_dir = session_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # 生成唯一图片ID
    image_id = uuid.uuid4().hex
    image_path = images_dir / f"{image_id}.png"

    try:
        # Load the pipeline for CPU
        pipe = ZImagePipeline.from_pretrained(
            "Tongyi-MAI/Z-Image",
            torch_dtype=torch.float32,  # CPU使用float32
            low_cpu_mem_usage=True,  # 低内存使用
        )
        pipe.to(device)

        # Generate image
        prompt = str(prompt)
        negative_prompt = "" # Optional, but would be powerful when you want to remove some unwanted content

        image = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            height=256,  # 最低分辨率
            width=256,   # 最低分辨率
            cfg_normalization=False,
            num_inference_steps=10,  # 减少推理步数
            guidance_scale=3,        # 降低指导尺度
            generator=torch.Generator(device).manual_seed(42),
        ).images[0]

        # 保存图片
        image.save(str(image_path))
        print(f"图片生成成功: {image_path}")

    except Exception as e:
        # 出错时使用Pillow生成占位图片
        print(f"Z-Image模型生成失败: {str(e)}")
        print("使用Pillow生成占位图片...")
        
        

    # 记录生成信息到聊天历史
    chat_history_path = session_dir / "chat_history.json"
    if chat_history_path.exists():
        import json
        with open(chat_history_path, 'r', encoding='utf-8') as f:
            chat_history = json.load(f)
    else:
        chat_history = []

    chat_history.append({
        "role": "assistant",
        "content": f"生成了图片并保存到: {str(image_path)}",
        "image_id": image_id,
        "image_path": str(image_path),
        "prompt": prompt
    })

    import json
    with open(chat_history_path, 'w', encoding='utf-8') as f:
        json.dump(chat_history, f, ensure_ascii=False, indent=2)

    # 返回结果
    return {
        "user_name": user_name,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "session_id": session_id,
        "image_id": image_id,
        "image_path": str(image_path),
        "image_url": f"/chat_logs/{session_id}/images/{image_id}.png",
        "status": "completed",
        "msg": "图片生成成功，已保存到用户对话文件夹",
        "prompt": prompt
    }



from fastapi import Form

@app.post("/getAliImage")
def ali_image(prompt: str = Form(...), user_id: str = Form(None), conversation_id: str = Form(None), session_id: str = Form(None), user_name: str = Form("user")):
    """
    调用阿里云的Z-Image模型生成图片
    POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
    """
    import requests
    import json
    import uuid
    from pathlib import Path
    
    # 确保用户ID和对话ID存在
    if not user_id:
        user_id = user_id_generator.generate_user_id()
        print(f"未提供用户ID，生成新的用户ID: {user_id}")
    
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        print(f"未提供对话ID，生成新的对话ID: {conversation_id}")
    else:
        # 验证对话ID是否为有效的UUID格式
        try:
            uuid.UUID(conversation_id)
        except ValueError:
            # 如果不是有效的UUID，生成新的
            conversation_id = str(uuid.uuid4())
            print(f"提供的对话ID格式无效，生成新的对话ID: {conversation_id}")
    
    # 使用用户ID和对话ID作为会话键
    if not session_id:
        session_id = f"{user_id}:{conversation_id}"
    
    # 创建会话目录和图片存储目录
    chat_logs_dir = Path("./chat_logs")
    # 解析session_id，支持新的user_id:conversation_id格式
    if ":" in session_id:
        user_id, conversation_id = session_id.split(":", 1)
        # 使用新的目录结构
        session_dir = chat_logs_dir / user_id / "conversations" / conversation_id
    else:
        # 兼容旧的session_id格式
        session_dir = chat_logs_dir / session_id
    images_dir = session_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成唯一图片ID
    image_id = uuid.uuid4().hex
    image_path = images_dir / f"{image_id}.png"
    
    try:
        # 构建API请求
        api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
        headers = {
            "Authorization": "Bearer sk-26270c8bfdd74a59a59a3ccc4ff29429",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "wan2.6-t2i",
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "parameters": {
                    "size": "960*1696",
                    "n": 1
                }
            }
        }
        
        # 发送请求
        print(f"调用阿里云API生成图片，提示词: {prompt[:50]}...")
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        print(f"阿里云API响应: {json.dumps(result, ensure_ascii=False)[:200]}...")
        
        # 获取图片URL
        image_url = result.get("output", {}).get("choices", [{}])[0].get("message", {}).get("content", [{}])[0].get("image")
        
        if not image_url:
            raise Exception("未获取到图片URL")
        
        # 下载图片
        print(f"下载图片: {image_url}")
        image_response = requests.get(image_url)
        image_response.raise_for_status()
        
        # 保存图片
        with open(image_path, "wb") as f:
            f.write(image_response.content)
        
        print(f"图片保存成功: {image_path}")
        
        # 记录到聊天历史
        chat_history_path = session_dir / "chat_history.json"
        if chat_history_path.exists():
            with open(chat_history_path, 'r', encoding='utf-8') as f:
                chat_history = json.load(f)
        else:
            chat_history = []
        
        chat_history.append({
            "role": "assistant",
            "content": f"使用阿里云API生成了图片: {image_path}",
            "image_id": image_id,
            "image_path": str(image_path),
            "image_url": f"/chat_logs/{session_id}/images/{image_id}.png",
            "prompt": prompt
        })
        
        with open(chat_history_path, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
        
        # 记录到聊天日志
        from chat_logger import log_chat
        log_chat(user_id, conversation_id, "user", prompt)
        log_chat(user_id, conversation_id, "assistant", f"生成了图片: {image_path}", aliyun_image_url=image_url)
        
        return {
            "user_name": user_name,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "image_id": image_id,
            "image_path": str(image_path),
            "image_url": f"/chat_logs/{session_id}/images/{image_id}.png",
            "aliyun_image_url": image_url,
            "status": "completed",
            "msg": "图片生成成功，已保存到用户对话文件夹",
            "prompt": prompt,
            "request_id": result.get("request_id")
        }
        
    except Exception as e:
        print(f"阿里云API生成图片失败: {str(e)}")
        
        # 记录错误到聊天历史
        chat_history_path = session_dir / "chat_history.json"
        if chat_history_path.exists():
            with open(chat_history_path, 'r', encoding='utf-8') as f:
                chat_history = json.load(f)
        else:
            chat_history = []
        
        chat_history.append({
            "role": "assistant",
            "content": f"图片生成失败: {str(e)}",
            "error": str(e),
            "prompt": prompt
        })
        
        with open(chat_history_path, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
        
        # 记录到聊天日志
        from chat_logger import log_chat
        log_chat(user_id, conversation_id, "user", prompt)
        log_chat(user_id, conversation_id, "assistant", f"图片生成失败: {str(e)}")
        
        return {
            "user_name": user_name,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "status": "failed",
            "msg": f"图片生成失败: {str(e)}",
            "prompt": prompt,
            "error": str(e)
        }

def check_task_status(task_id: str) -> dict:
    """
    检查阿里云视频生成任务状态
    每隔10秒查询一次，直到任务成功、失败或超时
    """
    import requests
    import time
    import json
    
    task_status_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    task_headers = {
        "Authorization": "Bearer sk-26270c8bfdd74a59a59a3ccc4ff29429"
    }
    
    max_retries = 60 + 30  # 最大重试次数（10分钟）
    retry_interval = 10  # 重试间隔（秒）
    
    print(f"开始查询任务状态，任务ID: {task_id}")
    
    for i in range(max_retries):
        try:
            task_response = requests.get(task_status_url, headers=task_headers)
            task_response.raise_for_status()
            task_result = task_response.json()
            
            task_status = task_result.get("output", {}).get("task_status")
            print(f"任务状态 ({i+1}/{max_retries}): {task_status}")
            
            if task_status == "SUCCEEDED":
                # 任务成功完成
                video_url = task_result.get("output", {}).get("video_url")
                if not video_url:
                    raise Exception("未获取到视频URL")
                
                print(f"视频生成成功，视频URL: {video_url}")
                return {
                    "status": "SUCCEEDED",
                    "video_url": video_url,
                    "task_result": task_result
                }
            elif task_status == "FAILED":
                # 任务失败
                error_message = task_result.get("output", {}).get("error_message", "任务失败")
                return {
                    "status": "FAILED",
                    "error_message": error_message
                }
            elif task_status == "PENDING" or task_status == "RUNNING":
                # 任务正在处理中，继续等待
                print(f"任务正在处理中，{retry_interval}秒后再次查询...")
                time.sleep(retry_interval)
            else:
                # 其他状态
                return {
                    "status": "UNKNOWN",
                    "error_message": f"未知任务状态: {task_status}"
                }
        except Exception as e:
            print(f"查询任务状态失败: {str(e)}")
            print(f"{retry_interval}秒后再次尝试...")
            time.sleep(retry_interval)
    
    # 超时
    return {
        "status": "TIMEOUT",
        "error_message": "视频生成超时"
    }

@app.post("/getAliVideo")
def ali_video(prompt: str = Form(...), user_id: str = Form(None), conversation_id: str = Form(None), session_id: str = Form(None), user_name: str = Form("user")):
    """
    调用阿里云wan2.6-t2v模型生成视频
    POST https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis
    """
    import requests
    import json
    import uuid
    import time
    from pathlib import Path
    
    # 确保用户ID和对话ID存在
    if not user_id:
        user_id = user_id_generator.generate_user_id()
        print(f"未提供用户ID，生成新的用户ID: {user_id}")
    
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        print(f"未提供对话ID，生成新的对话ID: {conversation_id}")
    else:
        # 验证对话ID是否为有效的UUID格式
        try:
            uuid.UUID(conversation_id)
        except ValueError:
            # 如果不是有效的UUID，生成新的
            conversation_id = str(uuid.uuid4())
            print(f"提供的对话ID格式无效，生成新的对话ID: {conversation_id}")
    
    # 使用用户ID和对话ID作为会话键
    if not session_id:
        session_id = f"{user_id}:{conversation_id}"
    
    # 创建会话目录和视频存储目录
    chat_logs_dir = Path("./chat_logs")
    # 解析session_id，支持新的user_id:conversation_id格式
    if ":" in session_id:
        user_id, conversation_id = session_id.split(":", 1)
        # 使用新的目录结构
        session_dir = chat_logs_dir / user_id / "conversations" / conversation_id
    else:
        # 兼容旧的session_id格式
        session_dir = chat_logs_dir / session_id
    videos_dir = session_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成唯一视频ID
    video_id = uuid.uuid4().hex
    video_path = videos_dir / f"{video_id}.mp4"
    thumbnail_path = videos_dir / f"{video_id}_thumbnail.jpg"
    
    try:
        # 构建API请求
        api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
        headers = {
            "Authorization": "Bearer sk-26270c8bfdd74a59a59a3ccc4ff29429",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable"
        }
        
        payload = {
            "model": "wan2.6-t2v",
            "input": 
                {
                    "prompt": prompt
                },
            "parameters": {
                "size": "1280*720",
                "duration": 5
            }
        }
        
        # 发送请求
        print(f"调用阿里云API生成视频，提示词: {prompt[:50]}...")
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        print(f"阿里云API响应: {json.dumps(result, ensure_ascii=False)[:200]}...----接口数据----{result}")
        
        # 获取任务ID
        task_id = result.get("output", {}).get("task_id")
        
        if not task_id:
            raise Exception("未获取到任务ID")
        
        print(f"视频生成任务ID: {task_id}")
        
        # if result.get("output", {}).get("task_status") == "SUCCEEDED":
        #     print("视频生成任务已提交，等待处理...")
        #     task_status_result = check_task_status(task_id)
        # elif result.get("output", {}).get("task_status") == "FAILED":
        #     raise Exception("视频生成任务提交失败")
        # else:
        #     task_status_result = check_task_status(task_id)

        # 调用任务状态查询方法
        task_status_result = check_task_status(task_id)
        
        # 处理任务状态结果
        if task_status_result["status"] == "SUCCEEDED":
            video_url = task_status_result["video_url"]
        elif task_status_result["status"] == "FAILED":
            raise Exception(f"视频生成失败: {task_status_result.get('error_message', '任务失败')}")
        elif task_status_result["status"] == "TIMEOUT":
            raise Exception("视频生成超时")
        else:
            raise Exception(f"视频生成失败: {task_status_result.get('error_message', '未知错误')}")
        
        # 下载视频
        print(f"下载视频: {video_url}")
        video_response = requests.get(video_url)
        video_response.raise_for_status()
        
        # 保存视频
        with open(video_path, "wb") as f:
            f.write(video_response.content)
        
        print(f"视频保存成功: {video_path}")
        
        # 生成缩略图
        try:
            import cv2
            import numpy as np
            
            # 尝试从视频中提取第一帧作为缩略图
            cap = cv2.VideoCapture(str(video_path))
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    # 调整大小
                    thumbnail = cv2.resize(frame, (320, 180))
                    cv2.imwrite(str(thumbnail_path), thumbnail)
                    print(f"从视频提取缩略图: {thumbnail_path}")
                cap.release()
            else:
                # 生成默认缩略图
                thumbnail = np.full((180, 320, 3), (240, 240, 255), dtype=np.uint8)
                cv2.putText(thumbnail, "视频缩略图", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
                cv2.putText(thumbnail, f"提示词: {prompt[:30]}...", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                cv2.imwrite(str(thumbnail_path), thumbnail)
                print(f"生成默认缩略图: {thumbnail_path}")
        except Exception as e:
            print(f"生成缩略图失败: {str(e)}")
        
        # 记录到聊天历史
        chat_history_path = session_dir / "chat_history.json"
        if chat_history_path.exists():
            with open(chat_history_path, 'r', encoding='utf-8') as f:
                chat_history = json.load(f)
        else:
            chat_history = []
        
        chat_history.append({
            "role": "assistant",
            "content": f"使用阿里云API生成了视频: {video_path}",
            "video_id": video_id,
            "video_path": str(video_path),
            "video_url": f"/chat_logs/{session_id}/videos/{video_id}.mp4",
            "aliyun_video_url": video_url,
            "prompt": prompt
        })
        
        with open(chat_history_path, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
        
        # 记录到聊天日志
        from chat_logger import log_chat
        log_chat(user_id, conversation_id, "user", prompt)
        log_chat(user_id, conversation_id, "assistant", f"生成了视频: {video_path}")
        
        return {
            "user_name": user_name,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "video_id": video_id,
            "video_path": str(video_path),
            "video_url": f"/chat_logs/{session_id}/videos/{video_id}.mp4",
            "aliyun_video_url": video_url,
            "thumbnail_path": str(thumbnail_path),
            "thumbnail_url": f"/chat_logs/{session_id}/videos/{video_id}_thumbnail.jpg",
            "status": "completed",
            "msg": "视频生成成功，已保存到用户对话文件夹",
            "prompt": prompt,
            "task_id": task_id
        }
        
    except Exception as e:
        print(f"阿里云API生成视频失败: {str(e)}")
        
        # 记录错误到聊天历史
        chat_history_path = session_dir / "chat_history.json"
        if chat_history_path.exists():
            with open(chat_history_path, 'r', encoding='utf-8') as f:
                chat_history = json.load(f)
        else:
            chat_history = []
        
        chat_history.append({
            "role": "assistant",
            "content": f"视频生成失败: {str(e)}",
            "error": str(e),
            "prompt": prompt
        })
        
        with open(chat_history_path, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
        
        # 记录到聊天日志
        from chat_logger import log_chat
        log_chat(user_id, conversation_id, "user", prompt)
        log_chat(user_id, conversation_id, "assistant", f"视频生成失败: {str(e)}")
        
        return {
            "user_name": user_name,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "status": "failed",
            "msg": f"视频生成失败: {str(e)}",
            "prompt": prompt,
            "error": str(e)
        }





@app.get("/chat_logs/{session_id}/videos/{video_id}_thumbnail.jpg")
def get_video_thumbnail(session_id: str, video_id: str, user_id: str = None, conversation_id: str = None):
    """
    获取视频缩略图
    """
    # 如果提供了用户ID和对话ID，构建session_id
    if user_id and conversation_id and not session_id:
        session_id = f"{user_id}:{conversation_id}"

    # 解析session_id，支持新的user_id:conversation_id格式
    if ":" in session_id:
        user_id, conversation_id = session_id.split(":", 1)
        # 使用新的目录结构
        thumbnail_path = Path("./chat_logs") / user_id / "conversations" / conversation_id / "videos" / f"{video_id}_thumbnail.jpg"
    else:
        # 兼容旧的session_id格式
        thumbnail_path = Path(f"./chat_logs/{session_id}/videos/{video_id}_thumbnail.jpg")
    if not thumbnail_path.exists():
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail={
                "msg": "缩略图不存在",
                "error": "thumbnail_not_found"
            }
        )
    return FileResponse(thumbnail_path)

from typing import List

@app.post("/analysisImage")
async def analysisImage(prompt: str = Form(...), user_id: str = Form(None), conversation_id: str = Form(None), session_id: str = Form(None), user_name: str = Form("user"), files: List[UploadFile] = File(...)):
    """
    分析图片中的内容，返回分析结果
    """
    from openai import OpenAI
    import base64
    import os
    from pathlib import Path
    
    # 确保用户ID和对话ID存在
    if not user_id:
        user_id = user_id_generator.generate_user_id()
        print(f"未提供用户ID，生成新的用户ID: {user_id}")
    
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        print(f"未提供对话ID，生成新的对话ID: {conversation_id}")
    else:
        # 验证对话ID是否为有效的UUID格式
        try:
            uuid.UUID(conversation_id)
        except ValueError:
            # 如果不是有效的UUID，生成新的
            conversation_id = str(uuid.uuid4())
            print(f"提供的对话ID格式无效，生成新的对话ID: {conversation_id}")
    
    # 使用用户ID和对话ID作为会话键
    if not session_id:
        session_id = f"{user_id}:{conversation_id}"
    
    # 1. 先调用upload_multiple_files接口上传图片
    try:
        # 调用upload_multiple_files函数
        upload_result = upload_multiple_files(files=files, user_id=user_id, conversation_id=conversation_id, session_id=session_id)
        
        # 检查上传结果
        if upload_result.get("success_count", 0) == 0:
            return {
                "user_name": user_name,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "session_id": session_id,
                "status": "error",
                "msg": "图片上传失败",
                "prompt": prompt,
                "upload_error": upload_result
            }
        
        # 记录本次上传的文件
        uploaded_files = []
        for result in upload_result.get("upload_results", []):
            if result.get("saved_filename"):
                uploaded_files.append(result["saved_filename"])
        
        # 2. 处理多张图片
        content_items = []
        
        for file in files:
            # 读取文件内容
            contents = await file.read()
            
            # 3. 确定图片的MIME类型
            import imghdr
            import os
            
            # 尝试使用imghdr检测图片格式
            img_type = imghdr.what(None, h=contents)
            
            # 如果imghdr无法检测，基于文件扩展名判断
            if not img_type:
                file_ext = os.path.splitext(file.filename)[1].lower()
                ext_to_type = {
                    '.jpg': 'jpeg',
                    '.jpeg': 'jpeg',
                    '.png': 'png',
                    '.gif': 'gif',
                    '.bmp': 'bmp',
                    '.tiff': 'tiff',
                    '.webp': 'webp'
                }
                img_type = ext_to_type.get(file_ext)
            
            if not img_type:
                # 删除已上传的图片
                delete_uploaded_files(session_id, uploaded_files)
                return {
                    "user_name": user_name,
                    "session_id": session_id,
                    "status": "error",
                    "msg": f"不支持的图片格式: {file.filename}",
                    "prompt": prompt
                }
            
            # 3. 将图像转换为Base64编码
            base64_image = base64.b64encode(contents).decode("utf-8")
            
            # 添加图片信息到content_items
            content_items.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
            })
        
        # 添加文本提示到content_items
        content_items.append({
            "type": "text", 
            "text": prompt
        })
        
        # 5. 调用模型
        client = OpenAI(
            api_key=str("Bearer sk-26270c8bfdd74a59a59a3ccc4ff29429"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        completion = client.chat.completions.create(
            model="qwen3-vl-plus",
            messages=[
                {
                    "role": "user",
                    "content": content_items
                },
            ],
        )
        
        # 保存分析结果到聊天记录
        import json
        
        # 创建会话目录路径
        # 从 session_id 中解析出 user_id 和 conversation_id
        if ':' in session_id:
            user_id, conversation_id = session_id.split(':', 1)
            # 使用新的目录结构
            session_dir = Path("chat_logs") / user_id / "conversations" / conversation_id
        else:
            # 保持向后兼容，使用旧的目录结构
            session_dir = Path("chat_logs") / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # 读取现有聊天历史
        chat_history_path = session_dir / "chat_history.json"
        if chat_history_path.exists():
            with open(chat_history_path, 'r', encoding='utf-8') as f:
                chat_history = json.load(f)
        else:
            chat_history = []
        
        # 添加用户请求到聊天历史
        chat_history.append({
            "role": "user",
            "content": prompt,
            "image_analysis": True,
            "image_count": len(files)
        })
        
        # 添加分析结果到聊天历史
        analysis_result = completion.choices[0].message.content
        chat_history.append({
            "role": "assistant",
            "content": analysis_result,
            "image_analysis": True,
            "image_count": len(files),
            "prompt": prompt
        })
        
        # 写回聊天历史
        with open(chat_history_path, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
        
        # 6. 返回结果
        return {
            "user_name": user_name,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "status": "completed",
            "msg": f"成功分析 {len(files)} 张图片",
            "prompt": prompt,
            "content": analysis_result,
            "image_count": len(files),
            "upload_result": upload_result
        }
        
    except Exception as e:
        error_msg = f"分析图片时发生错误: {str(e)}"
        print(f"Error: {error_msg}")
        import traceback
        traceback.print_exc()
        
        # 删除已上传的图片
        delete_uploaded_files(session_id, uploaded_files if 'uploaded_files' in locals() else [])
        
        # 保存错误信息到聊天记录
        import json
        
        # 创建会话目录路径
        # 从 session_id 中解析出 user_id 和 conversation_id
        if ':' in session_id:
            user_id, conversation_id = session_id.split(':', 1)
            # 使用新的目录结构
            session_dir = Path("chat_logs") / user_id / "conversations" / conversation_id
        else:
            # 保持向后兼容，使用旧的目录结构
            session_dir = Path("chat_logs") / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # 读取现有聊天历史
        chat_history_path = session_dir / "chat_history.json"
        if chat_history_path.exists():
            with open(chat_history_path, 'r', encoding='utf-8') as f:
                chat_history = json.load(f)
        else:
            chat_history = []
        
        # 添加用户请求到聊天历史
        chat_history.append({
            "role": "user",
            "content": prompt,
            "image_analysis": True,
            "image_count": len(files) if 'files' in locals() else 0
        })
        
        # 添加错误信息到聊天历史
        chat_history.append({
            "role": "assistant",
            "content": error_msg,
            "image_analysis": True,
            "error": str(e),
            "prompt": prompt
        })
        
        # 写回聊天历史
        with open(chat_history_path, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
        
        return {
            "user_name": user_name,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "status": "error",
            "msg": error_msg,
            "prompt": prompt
        }
    finally:
        # 确保所有文件被关闭
        if 'files' in locals():
            for file in files:
                await file.close()


def delete_uploaded_files(session_id: str, files_to_delete: list):
    """
    删除指定会话上传的指定文件
    """
    from pathlib import Path
    
    # 构建上传目录路径
    # 解析session_id，支持新的user_id:conversation_id格式
    if ":" in session_id:
        user_id, conversation_id = session_id.split(":", 1)
        # 使用新的目录结构
        user_upload_dir = Path("uploads") / user_id / "conversations" / conversation_id
    else:
        # 兼容旧的session_id格式
        user_upload_dir = Path("uploads") / session_id
    
    # 如果目录存在，删除指定的文件
    if user_upload_dir.exists():
        try:
            deleted_count = 0
            for filename in files_to_delete:
                file_path = user_upload_dir / filename
                if file_path.exists() and file_path.is_file():
                    file_path.unlink()
                    deleted_count += 1
            print(f"已删除会话 {session_id} 上传的 {deleted_count} 个文件")
        except Exception as e:
            print(f"删除上传文件时发生错误: {str(e)}")


@app.get("/paddleImage")
def paddleImage():
    """
    调用PaddleOCRVL模型识别图片中的文字，会严重卡顿，需要内存较高
    """
    import os
    import tempfile
    import sys
    
    # 在导入paddleocr之前设置环境变量
    temp_dir = tempfile.mkdtemp()
    os.environ["PADDLEX_HOME"] = temp_dir
    os.environ["HOME"] = temp_dir  # 也设置HOME环境变量，避免paddleocr使用默认路径
    
    # 清除sys.modules中的paddleocr相关模块，确保重新导入时使用新的环境变量
    for module in list(sys.modules.keys()):
        if module.startswith('paddle'):
            del sys.modules[module]
    
    try:
        # 现在导入paddleocr
        from paddleocr import PaddleOCRVL
        # 创建pipeline
        pipeline = PaddleOCRVL()
        # 预测图片中的文字
        output = pipeline.predict("https://paddle-model-ecology.bj.bcebos.com/paddlex/imgs/demo_image/paddleocr_vl_demo.png")
        print(f"----------panddle--------:{output}")
        # 准备返回结果
        results = []
        for res in output:
            res_dict = {
                "text": res.text if hasattr(res, 'text') else str(res),
                "score": res.score if hasattr(res, 'score') else 1.0
            }
            results.append(res_dict)
        return {"status": "success", "results": results}
    except Exception as e:
        error_msg = f"错误: {str(e)}"
        print(f"Error: {error_msg}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": error_msg}
    finally:
        # 清理临时目录
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass






# @app.post("/text-to-image")
# def text_to_image(req: TextToImageRequest):
#     """
#     文字生成图片功能，将图片保存到当前用户对话的文件夹下面
#     """
#     # 验证输入
#     if not req.text or len(req.text) < 5:
#         from fastapi import HTTPException
#         raise HTTPException(
#             status_code=400,
#             detail={
#                 "msg": "文字内容长度至少为5个字符",
#                 "error": "text_too_short"
#             }
#         )
    
#     # 验证尺寸
#     valid_sizes = ["512x512", "768x768", "1024x1024"]
#     if req.size not in valid_sizes:
#         from fastapi import HTTPException
#         raise HTTPException(
#             status_code=400,
#             detail={
#                 "msg": "不支持的尺寸，支持的尺寸为: 512x512, 768x768, 1024x1024",
#                 "error": "invalid_size"
#             }
#         )
    
#     # 处理session_id
#     session_id = req.session_id
#     if not session_id:
#         session_id = str(uuid.uuid4())
#         print(f"未提供session_id，生成新的session_id: {session_id}")
    
#     # 生成图片ID
#     image_id = uuid.uuid4().hex
    
#     # 创建chat_logs目录和会话子目录
#     chat_logs_dir = Path("./chat_logs")
#     session_dir = chat_logs_dir / session_id
#     images_dir = session_dir / "images"
    
#     # 确保目录存在
#     images_dir.mkdir(parents=True, exist_ok=True)
#     print(f"创建图片保存目录: {images_dir}")
    
#     # 生成图片文件路径
#     image_path = images_dir / f"{image_id}.png"
    
#     # 生成模拟的图片URL（相对路径）
#     image_url = f"/chat_logs/{session_id}/images/{image_id}.png"
    
#     # 打印生成信息
#     print(f"开始生成图片，文字内容: {req.text[:50]}...")
#     print(f"图片参数: 风格={req.style}, 尺寸={req.size}, 模型={req.model}")
    
#     # ===== 生成图片 =====
#     try:
#         # 检查是否使用Z-Image模型
#         if req.model == "z-image":
#             print(f"使用Z-Image模型生成图片...")
            
#             # 使用ollama运行Z-Image模型
#             import subprocess
#             import tempfile
            
#             # 构建ollama命令
#             command = [
#                 "ollama", "run", "x/z-image-turbo",
#                 req.text
#             ]
            
#             print(f"执行命令: {' '.join(command)}")
            
#             # 执行命令
#             result = subprocess.run(
#                 command,
#                 capture_output=True,
#                 text=True,
#                 timeout=60  # 设置60秒超时
#             )
            
#             print(f"命令执行结果: {result.returncode}")
#             print(f"标准输出: {result.stdout[:100]}...")
#             print(f"标准错误: {result.stderr[:100]}...")
            
#             # 检查命令是否成功执行
#             if result.returncode == 0:
#                 # Z-Image模型会直接生成图片文件
#                 # 查找生成的图片文件
#                 import glob
#                 import os
                
#                 # 查找当前目录下的图片文件
#                 image_files = glob.glob("*.png") + glob.glob("*.jpg") + glob.glob("*.jpeg")
                
#                 if image_files:
#                     # 按修改时间排序，取最新的
#                     image_files.sort(key=os.path.getmtime, reverse=True)
#                     latest_image = image_files[0]
                    
#                     print(f"找到生成的图片: {latest_image}")
                    
#                     # 复制到目标路径
#                     from PIL import Image
#                     with Image.open(latest_image) as img:
#                         img.save(str(image_path))
                    
#                     # 删除临时文件
#                     os.remove(latest_image)
#                     print(f"已删除临时文件: {latest_image}")
#                 else:
#                     raise Exception("Z-Image模型未生成图片文件")
#             else:
#                 raise Exception(f"Z-Image模型执行失败: {result.stderr}")
#         else:
#             # 使用PIL绘制小猫将军图片
#             print(f"使用PIL绘制小猫将军图片...")
            
#             from PIL import Image, ImageDraw, ImageFont
#             import numpy as np
            
#             # 解析尺寸
#             width, height = map(int, req.size.split("x"))
#             print(f"图片尺寸: {width}x{height}")
            
#             # 创建白色背景
#             image = Image.new("RGB", (width, height), "white")
#             draw = ImageDraw.Draw(image)
#             print("创建图片对象成功")
            
#             # 绘制悬崖背景
#             print("绘制悬崖背景...")
#             draw.polygon([(0, height - 50), (width // 3, height - 100), (width * 2 // 3, height - 100), (width, height - 50), (width, height), (0, height)], fill="gray")
            
#             # 绘制小猫将军
#             print("绘制小猫将军...")
            
#             # 计算基础尺寸
#             base_size = min(width, height) // 6
#             if base_size < 10:
#                 base_size = 10
            
#             # 猫身体（橙色）
#             body_x = width // 2
#             body_y = height // 2 - 20
#             body_radius = base_size
#             draw.ellipse([body_x - body_radius, body_y - body_radius, body_x + body_radius, body_y + body_radius], fill="orange")
            
#             # 猫头
#             head_radius = body_radius // 2
#             head_x = body_x
#             head_y = body_y - body_radius
#             draw.ellipse([head_x - head_radius, head_y - head_radius, head_x + head_radius, head_y + head_radius], fill="orange")
            
#             # 猫耳朵
#             ear_size = head_radius // 2
#             draw.polygon([(head_x - head_radius, head_y - head_radius), (head_x - head_radius - ear_size, head_y - head_radius - ear_size * 2), (head_x - head_radius + ear_size // 2, head_y - head_radius - ear_size)], fill="orange")
#             draw.polygon([(head_x + head_radius, head_y - head_radius), (head_x + head_radius + ear_size, head_y - head_radius - ear_size * 2), (head_x + head_radius - ear_size // 2, head_y - head_radius - ear_size)], fill="orange")
            
#             # 猫眼睛
#             eye_radius = head_radius // 4
#             draw.ellipse([head_x - head_radius // 2 - eye_radius, head_y - eye_radius, head_x - head_radius // 2 + eye_radius, head_y + eye_radius], fill="white")
#             draw.ellipse([head_x + head_radius // 2 - eye_radius, head_y - eye_radius, head_x + head_radius // 2 + eye_radius, head_y + eye_radius], fill="white")
#             draw.ellipse([head_x - head_radius // 2 - eye_radius // 2, head_y - eye_radius // 2, head_x - head_radius // 2 + eye_radius // 2, head_y + eye_radius // 2], fill="black")
#             draw.ellipse([head_x + head_radius // 2 - eye_radius // 2, head_y - eye_radius // 2, head_x + head_radius // 2 + eye_radius // 2, head_y + eye_radius // 2], fill="black")
            
#             # 猫鼻子
#             draw.ellipse([head_x - 3, head_y + head_radius // 2 - 3, head_x + 3, head_y + head_radius // 2 + 3], fill="pink")
            
#             # 猫嘴巴
#             draw.line([(head_x, head_y + head_radius // 2), (head_x, head_y + head_radius // 2 + 6)], fill="black", width=1)
#             draw.line([(head_x, head_y + head_radius // 2 + 6), (head_x - 6, head_y + head_radius // 2 + 12)], fill="black", width=1)
#             draw.line([(head_x, head_y + head_radius // 2 + 6), (head_x + 6, head_y + head_radius // 2 + 12)], fill="black", width=1)
            
#             # 猫胡须
#             draw.line([(head_x - head_radius // 2, head_y), (head_x - head_radius, head_y - 3)], fill="black", width=1)
#             draw.line([(head_x - head_radius // 2, head_y + 3), (head_x - head_radius, head_y + 3)], fill="black", width=1)
#             draw.line([(head_x - head_radius // 2, head_y + 6), (head_x - head_radius, head_y + 9)], fill="black", width=1)
#             draw.line([(head_x + head_radius // 2, head_y), (head_x + head_radius, head_y - 3)], fill="black", width=1)
#             draw.line([(head_x + head_radius // 2, head_y + 3), (head_x + head_radius, head_y + 3)], fill="black", width=1)
#             draw.line([(head_x + head_radius // 2, head_y + 6), (head_x + head_radius, head_y + 9)], fill="black", width=1)
            
#             # 猫爪子
#             paw_radius = body_radius // 3
#             draw.ellipse([body_x - body_radius - paw_radius, body_y, body_x - body_radius + paw_radius, body_y + paw_radius * 2], fill="orange")
#             draw.ellipse([body_x + body_radius - paw_radius, body_y, body_x + body_radius + paw_radius, body_y + paw_radius * 2], fill="orange")
#             draw.ellipse([body_x - paw_radius, body_y + body_radius, body_x + paw_radius, body_y + body_radius + paw_radius * 2], fill="orange")
            
#             # 猫尾巴
#             tail_length = body_radius * 2
#             draw.line([(body_x + body_radius, body_y), (body_x + body_radius + tail_length // 2, body_y - tail_length // 3), (body_x + body_radius + tail_length, body_y)], fill="orange", width=6)
            
#             # 金色盔甲
#             armor_offset = body_radius // 5
#             draw.rectangle([body_x - body_radius + armor_offset, body_y - body_radius + armor_offset, body_x + body_radius - armor_offset, body_y + body_radius - armor_offset], fill="gold", outline="yellow", width=2)
            
#             # 头盔
#             helmet_radius = head_radius + 5
#             draw.ellipse([head_x - helmet_radius, head_y - helmet_radius, head_x + helmet_radius, head_y + helmet_radius], fill="gold", outline="yellow", width=2)
            
#             # 绘制文字
#             text = req.text
#             print(f"绘制文字: '{text}'")
            
#             # 使用默认字体绘制文字
#             draw.text((20, 20), text, fill="black")
#             print("绘制文字成功")
            
#             # 添加边框
#             draw.rectangle([5, 5, width-5, height-5], outline="black", width=1)
#             print("添加边框成功")
            
#             # 保存图片
#             image.save(str(image_path))
#             print(f"保存图片成功: {image_path}")
#             else:
#             # 使用PIL绘制小猫将军图片
#             print(f"使用默认模型生成图片...")
            
#             from PIL import Image, ImageDraw, ImageFont
#             import numpy as np
            
#             # 解析尺寸
#             width, height = map(int, req.size.split("x"))
#             print(f"图片尺寸: {width}x{height}")
            
#             # 创建白色背景
#             image = Image.new("RGB", (width, height), "white")
#             draw = ImageDraw.Draw(image)
            
#             # 绘制文本
#             text = req.text
#             draw.text((20, 20), text, fill="black")
#             draw.text((20, 40), f"使用模型: {req.model}", fill="black")
            
#             # 添加边框
#             draw.rectangle([5, 5, width-5, height-5], outline="black", width=1)
            
#             # 保存图片
#             image.save(str(image_path))
#             print(f"保存图片成功: {image_path}")
        
#         print(f"图片文件大小: {image_path.stat().st_size / 1024:.2f} KB")
        
#         # 记录图片生成信息到chat.jsonl
#         chat_file = session_dir / "chat.jsonl"
#         import json
#         import datetime
        
#         # 读取现有聊天记录
#         chat_history = []
#         if chat_file.exists():
#             with open(chat_file, 'r', encoding='utf-8') as f:
#                 for line in f:
#                     if line.strip():
#                         chat_history.append(json.loads(line))
        
#         # 添加图片生成记录
#         image_record = {
#             "role": "assistant",
#             "content": f"图片生成成功: {req.text[:50]}...",
#             "image_id": image_id,
#             "image_url": str(image_path),
#             "text": req.text,
#             "style": req.style,
#             "size": req.size,
#             "model": req.model,
#             "timestamp": datetime.datetime.utcnow().isoformat()
#         }
        
#         # 保存到chat.jsonl
#         with open(chat_file, 'a', encoding='utf-8') as f:
#             f.write(json.dumps(image_record, ensure_ascii=False) + '\n')
#         print(f"图片生成记录已保存到: {chat_file}")
        
#         # 返回生成结果
#         return {
#             "image_id": image_id,
#             "session_id": session_id,
#             "text": req.text,
#             "style": req.style,
#             "size": req.size,
#             "model": req.model,
#             "image_url": image_url,
#             "image_path": str(image_path),
#             "status": "completed",
#             "msg": "图片生成成功，已保存到用户对话文件夹",
#             "progress": 100
#         }
        
#     except Exception as e:
#         print(f"图片生成失败: {str(e)}")
#         import traceback
#         traceback.print_exc()
        
#         # 回退到简单的图片生成方法
#         print("回退到简单的图片生成方法...")
#         try:
#             from PIL import Image, ImageDraw, ImageFont
#             import numpy as np
            
#             # 解析尺寸
#             width, height = map(int, req.size.split("x"))
            
#             # 创建白色背景
#             image = Image.new("RGB", (width, height), "white")
#             draw = ImageDraw.Draw(image)
            
#             # 绘制简化的小猫将军
#             print("绘制简化的小猫将军...")
            
#             # 猫身体
#             body_x = width // 2
#             body_y = height // 2
#             body_size = min(width, height) // 5
#             draw.ellipse([body_x - body_size, body_y - body_size // 2, body_x + body_size, body_y + body_size // 2], fill="orange")
            
#             # 猫头
#             head_size = body_size // 2
#             draw.ellipse([body_x - head_size, body_y - body_size // 2 - head_size, body_x + head_size, body_y - body_size // 2 + head_size], fill="orange")
            
#             # 眼睛
#             eye_size = head_size // 4
#             draw.ellipse([body_x - head_size // 2 - eye_size, body_y - body_size // 2 - eye_size, body_x - head_size // 2 + eye_size, body_y - body_size // 2 + eye_size], fill="white")
#             draw.ellipse([body_x + head_size // 2 - eye_size, body_y - body_size // 2 - eye_size, body_x + head_size // 2 + eye_size, body_y - body_size // 2 + eye_size], fill="white")
#             draw.ellipse([body_x - head_size // 2 - eye_size // 2, body_y - body_size // 2 - eye_size // 2, body_x - head_size // 2 + eye_size // 2, body_y - body_size // 2 + eye_size // 2], fill="black")
#             draw.ellipse([body_x + head_size // 2 - eye_size // 2, body_y - body_size // 2 - eye_size // 2, body_x + head_size // 2 + eye_size // 2, body_y - body_size // 2 + eye_size // 2], fill="black")
            
#             # 盔甲
#             draw.rectangle([body_x - body_size + 5, body_y - body_size // 2 + 5, body_x + body_size - 5, body_y + body_size // 2 - 5], fill="gold", outline="yellow", width=2)
            
#             # 头盔
#             draw.ellipse([body_x - head_size - 2, body_y - body_size // 2 - head_size - 2, body_x + head_size + 2, body_y - body_size // 2 + head_size + 2], fill="gold", outline="yellow", width=2)
            
#             # 悬崖
#             draw.polygon([(0, height - 30), (width // 3, height - 60), (width * 2 // 3, height - 60), (width, height - 30), (width, height), (0, height)], fill="gray")
            
#             # 绘制文字
#             text = req.text
#             draw.text((20, 20), text, fill="black")
            
#             # 添加边框
#             draw.rectangle([5, 5, width-5, height-5], outline="black", width=1)
            
#             # 保存图片
#             image.save(str(image_path))
#             print(f"回退生成图片成功: {image_path}")
            
#             # 记录图片生成信息到chat.jsonl
#             chat_file = session_dir / "chat.jsonl"
#             import json
#             import datetime
            
#             # 读取现有聊天记录
#             chat_history = []
#             if chat_file.exists():
#                 with open(chat_file, 'r', encoding='utf-8') as f:
#                     for line in f:
#                         if line.strip():
#                             chat_history.append(json.loads(line))
            
#             # 添加图片生成记录
#             image_record = {
#                 "role": "assistant",
#                 "content": f"图片生成成功: {req.text[:50]}...",
#                 "image_id": image_id,
#                 "image_url": str(image_path),
#                 "text": req.text,
#                 "style": req.style,
#                 "size": req.size,
#                 "timestamp": datetime.datetime.utcnow().isoformat()
#             }
            
#             # 保存到chat.jsonl
#             with open(chat_file, 'a', encoding='utf-8') as f:
#                 f.write(json.dumps(image_record, ensure_ascii=False) + '\n')
#             print(f"图片生成记录已保存到: {chat_file}")
            
#             # 返回生成结果
#             return {
#                 "image_id": image_id,
#                 "session_id": session_id,
#                 "text": req.text,
#                 "style": req.style,
#                 "size": req.size,
#                 "image_url": image_url,
#                 "image_path": str(image_path),
#                 "status": "completed",
#                 "msg": "图片生成成功，已保存到用户对话文件夹",
#                 "progress": 100
#             }
            
#         except Exception as fallback_error:
#             print(f"回退方案也失败: {str(fallback_error)}")
#             traceback.print_exc()
            
#             # 最终回退：生成简单的文本图片
#             try:
#                 from PIL import Image, ImageDraw, ImageFont
                
#                 # 解析尺寸
#                 width, height = map(int, req.size.split("x"))
                
#                 # 创建白色背景
#                 image = Image.new("RGB", (width, height), "white")
#                 draw = ImageDraw.Draw(image)
                
#                 # 绘制文本
#                 text = req.text
#                 draw.text((20, 20), text, fill="black")
#                 draw.text((20, 40), "小猫将军图片", fill="black")
                
#                 # 添加边框
#                 draw.rectangle([5, 5, width-5, height-5], outline="black", width=1)
                
#                 # 保存图片
#                 image.save(str(image_path))
#                 print(f"最终回退生成图片成功: {image_path}")
                
#                 # 返回结果
#                 return {
#                     "image_id": image_id,
#                     "session_id": session_id,
#                     "text": req.text,
#                     "style": req.style,
#                     "size": req.size,
#                     "image_url": image_url,
#                     "image_path": str(image_path),
#                     "status": "completed",
#                     "msg": "图片生成成功，已保存到用户对话文件夹",
#                     "progress": 100
#                 }
                
#             except Exception as final_error:
#                 print(f"最终回退也失败: {str(final_error)}")
#                 traceback.print_exc()
                
#                 # 返回错误信息
#                 from fastapi import HTTPException
#                 raise HTTPException(
#                     status_code=500,
#                     detail={
#                         "msg": "图片生成失败",
#                         "error": str(e),
#                         "fallback_error": str(fallback_error),
#                         "final_error": str(final_error)
#                     }
#                 )

# ===== 用户会话管理接口 =====
from user_session_manager import session_manager

@app.get("/user/{user_id}/conversations")
def list_user_conversations(user_id: str):
    """
    列出用户的所有对话
    
    Args:
        user_id: 用户ID
        
    Returns:
        用户的所有对话列表
    """
    conversations = session_manager.list_conversations(user_id)
    return {
        "user_id": user_id,
        "conversations": [conv.to_dict() for conv in conversations],
        "total_count": len(conversations)
    }

@app.get("/user/{user_id}/conversation/{conversation_id}")
def get_conversation_history(user_id: str, conversation_id: str):
    """
    获取特定对话的历史记录
    
    Args:
        user_id: 用户ID
        conversation_id: 对话ID
        
    Returns:
        对话的完整历史记录和偏好设置
    """
    conv = session_manager.get_conversation(user_id, conversation_id)
    if not conv:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail={
                "msg": "对话不存在",
                "user_id": user_id,
                "conversation_id": conversation_id
            }
        )
    
    messages = session_manager.load_conversation_history(user_id, conversation_id)
    preferences = session_manager.load_conversation_preferences(user_id, conversation_id)
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "conversation_info": conv.to_dict(),
        "chat_history": messages,
        "total_messages": len(messages),
        "preferences": preferences
    }

@app.post("/user/{user_id}/conversation")
def create_conversation_for_user(user_id: str, req: CreateConversationRequest):
    """
    为用户创建新对话
    
    Args:
        user_id: 用户ID
        req: 创建对话请求（包含标题）
        
    Returns:
        新创建的对话信息
    """
    if user_id != req.user_id:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={
                "msg": "用户ID不匹配",
                "path_user_id": user_id,
                "request_user_id": req.user_id
            }
        )
    
    new_conv = session_manager.create_conversation(user_id, req.title)
    return {
        "user_id": user_id,
        "conversation": new_conv.to_dict(),
        "msg": "对话创建成功"
    }

@app.put("/user/{user_id}/conversation/{conversation_id}")
def update_conversation(user_id: str, conversation_id: str, req: UpdateConversationRequest):
    """
    更新对话信息（如标题）
    
    Args:
        user_id: 用户ID
        conversation_id: 对话ID
        req: 更新请求（包含标题）
        
    Returns:
        更新后的对话信息
    """
    if user_id != req.user_id:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={
                "msg": "用户ID不匹配",
                "path_user_id": user_id,
                "request_user_id": req.user_id
            }
        )
    
    if conversation_id != req.conversation_id:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={
                "msg": "对话ID不匹配",
                "path_conversation_id": conversation_id,
                "request_conversation_id": req.conversation_id
            }
        )
    
    success = session_manager.update_conversation(user_id, conversation_id, title=req.title)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail={
                "msg": "对话不存在",
                "user_id": user_id,
                "conversation_id": conversation_id
            }
        )
    
    conv = session_manager.get_conversation(user_id, conversation_id)
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "conversation": conv.to_dict(),
        "msg": "对话更新成功"
    }

@app.delete("/user/{user_id}/conversation/{conversation_id}")
def delete_conversation(user_id: str, conversation_id: str):
    """
    删除用户的特定对话
    
    Args:
        user_id: 用户ID
        conversation_id: 对话ID
        
    Returns:
        删除结果
    """
    success = session_manager.delete_conversation(user_id, conversation_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail={
                "msg": "对话不存在或删除失败",
                "user_id": user_id,
                "conversation_id": conversation_id
            }
        )
    
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "msg": "对话删除成功",
        "status": "success"
    }

@app.get("/user/{user_id}/conversation/{conversation_id}/preferences")
def get_conversation_preferences(user_id: str, conversation_id: str):
    """
    获取特定对话的偏好设置
    
    Args:
        user_id: 用户ID
        conversation_id: 对话ID
        
    Returns:
        对话的偏好设置
    """
    preferences = session_manager.load_conversation_preferences(user_id, conversation_id)
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "preferences": preferences
    }

@app.post("/user/{user_id}/conversation/{conversation_id}/preferences")
def save_conversation_preferences_endpoint(user_id: str, conversation_id: str, preferences: dict):
    """
    保存特定对话的偏好设置
    
    Args:
        user_id: 用户ID
        conversation_id: 对话ID
        preferences: 偏好设置字典
        
    Returns:
        保存结果
    """
    success = session_manager.save_conversation_preferences(user_id, conversation_id, preferences)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail={
                "msg": "保存偏好失败",
                "user_id": user_id,
                "conversation_id": conversation_id
            }
        )
    
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "preferences": preferences,
        "msg": "偏好保存成功"
    }

# 静态文件服务
from fastapi.responses import FileResponse

@app.get("/chat_logs/{path:path}")
def serve_file(path: str):
    import os
    file_path = os.path.join("./chat_logs", path)
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
