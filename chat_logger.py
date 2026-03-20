import json
import os
from datetime import datetime
from pathlib import Path

# 基础目录 - 使用现有的chat_logs文件夹
BASE_DIR = Path(__file__).resolve().parent
USER_SESSIONS_DIR = BASE_DIR / "chat_logs"
SFT_SAMPLES_DIR = BASE_DIR / "sft_samples"
USER_PREFERENCES_FILENAME = "user_preferences.json"
SESSIONS_LIST_FILENAME = "sessions.json"

# 创建目录
os.makedirs(USER_SESSIONS_DIR, exist_ok=True)
os.makedirs(SFT_SAMPLES_DIR, exist_ok=True)


def log_chat(user_id: str, conversation_id: str, role: str, content: str, 
              aliyun_image_url: str = None, rewritten_question: str = None):
    """
    记录聊天内容（更新为用户-对话结构）
    
    Args:
        user_id: 用户ID
        conversation_id: 对话ID
        role: 角色
        content: 内容
        aliyun_image_url: 阿里云图片URL（可选）
        rewritten_question: 重写后的问题（可选）
    """
    # 使用新的用户会话管理器
    try:
        from user_session_manager import session_manager
        session_manager.log_message(user_id, conversation_id, role, content, 
                                    rewritten_question=rewritten_question,
                                    aliyun_image_url=aliyun_image_url)
    except Exception as e:
        print(f"⚠️  使用会话管理器记录失败，使用备用方式: {e}")
        # 备用方式
        user_chat_dir = USER_SESSIONS_DIR / user_id / "conversations" / conversation_id
        user_chat_dir.mkdir(parents=True, exist_ok=True)
        log_file = user_chat_dir / "chat.jsonl"
        
        chat_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content
        }
        
        if rewritten_question:
            chat_entry["rewritten_question"] = rewritten_question
        
        if aliyun_image_url:
            chat_entry["aliyun_image_url"] = aliyun_image_url
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(chat_entry, ensure_ascii=False) + "\n")


def log_chat_legacy(session_id: str, role: str, content: str, aliyun_image_url: str = None):
    """
    兼容旧接口的聊天记录函数（使用session_id作为user_id）
    """
    # 为了兼容旧代码，使用session_id作为user_id
    # 但实际上应该使用新的用户-对话结构
    import uuid
    conversation_id = str(uuid.uuid4())
    log_chat(session_id, conversation_id, role, content, aliyun_image_url)

def save_sft_sample(question: str, answer: str, source: str, session_id: str):
    """保存SFT样本"""
    # 解析session_id，支持新的user_id:conversation_id格式
    if ":" in session_id:
        user_id, conversation_id = session_id.split(":", 1)
        # 使用新的目录结构
        user_sft_dir = SFT_SAMPLES_DIR / user_id / conversation_id
    else:
        # 兼容旧的session_id格式
        user_sft_dir = SFT_SAMPLES_DIR / session_id
    
    user_sft_dir.mkdir(parents=True, exist_ok=True)
    
    sample_file = user_sft_dir / f"sample_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    sample = {
        "question": question,
        "answer": answer,
        "source": source,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat()
    }
    
    with open(sample_file, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)


def save_user_preferences(user_id: str, preferences: dict):
    """
    保存用户偏好到用户文件夹下
    
    Args:
        user_id: 用户ID
        preferences: 用户偏好字典
    """
    # 使用新的用户会话管理器
    try:
        from user_session_manager import session_manager
        session_manager.save_user_preferences(user_id, preferences)
    except Exception as e:
        print(f"⚠️  使用会话管理器保存偏好失败，使用备用方式: {e}")
        # 备用方式
        user_dir = USER_SESSIONS_DIR / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        prefs_file = user_dir / USER_PREFERENCES_FILENAME
        
        preferences["updated_at"] = datetime.now().isoformat()
        preferences["user_id"] = user_id
        
        with open(prefs_file, "w", encoding="utf-8") as f:
            json.dump(preferences, f, ensure_ascii=False, indent=2)


def load_user_preferences(user_id: str) -> dict:
    """
    从用户文件夹加载用户偏好
    
    Args:
        user_id: 用户ID
        
    Returns:
        用户偏好字典，如果不存在返回空字典
    """
    try:
        from user_session_manager import session_manager
        return session_manager.load_user_preferences(user_id)
    except Exception as e:
        print(f"⚠️  使用会话管理器加载偏好失败，使用备用方式: {e}")
        # 备用方式
        user_dir = USER_SESSIONS_DIR / user_id
        prefs_file = user_dir / USER_PREFERENCES_FILENAME
        
        if not prefs_file.exists():
            return {}
        
        try:
            with open(prefs_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载用户偏好失败: {e}")
            return {}


def save_user_preferences_legacy(session_id: str, preferences: dict):
    """
    兼容旧接口的保存用户偏好函数
    """
    save_user_preferences(session_id, preferences)


def load_user_preferences_legacy(session_id: str) -> dict:
    """
    兼容旧接口的加载用户偏好函数
    """
    return load_user_preferences(session_id)


def save_conversation_preferences(user_id: str, conversation_id: str, preferences: dict):
    """
    保存对话偏好到对话文件夹下（和chat.jsonl同级）
    
    Args:
        user_id: 用户ID
        conversation_id: 对话ID
        preferences: 对话偏好字典
    """
    try:
        from user_session_manager import session_manager
        session_manager.save_conversation_preferences(user_id, conversation_id, preferences)
    except Exception as e:
        print(f"⚠️  使用会话管理器保存对话偏好失败，使用备用方式: {e}")
        # 备用方式
        user_chat_dir = USER_SESSIONS_DIR / user_id / "conversations" / conversation_id
        user_chat_dir.mkdir(parents=True, exist_ok=True)
        prefs_file = user_chat_dir / "user_preferences.json"
        
        preferences["updated_at"] = datetime.now().isoformat()
        preferences["user_id"] = user_id
        preferences["conversation_id"] = conversation_id
        
        with open(prefs_file, "w", encoding="utf-8") as f:
            json.dump(preferences, f, ensure_ascii=False, indent=2)


def load_conversation_preferences(user_id: str, conversation_id: str) -> dict:
    """
    从对话文件夹加载对话偏好
    
    Args:
        user_id: 用户ID
        conversation_id: 对话ID
        
    Returns:
        对话偏好字典，如果不存在返回空字典
    """
    try:
        from user_session_manager import session_manager
        return session_manager.load_conversation_preferences(user_id, conversation_id)
    except Exception as e:
        print(f"⚠️  使用会话管理器加载对话偏好失败，使用备用方式: {e}")
        # 备用方式
        user_chat_dir = USER_SESSIONS_DIR / user_id / "conversations" / conversation_id
        prefs_file = user_chat_dir / "user_preferences.json"
        
        if not prefs_file.exists():
            return {}
        
        try:
            with open(prefs_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载对话偏好失败: {e}")
            return {}
