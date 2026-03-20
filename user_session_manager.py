#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户会话管理模块 - 支持一个用户拥有多个对话列表
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


# 基础目录 - 使用现有的chat_logs文件夹
BASE_DIR = Path(__file__).resolve().parent
USER_SESSIONS_DIR = BASE_DIR / "chat_logs"
os.makedirs(USER_SESSIONS_DIR, exist_ok=True)


class UserSession:
    """单个对话会话"""
    
    def __init__(self, user_id: str, conversation_id: str, title: str = ""):
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.title = title or f"对话 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.message_count = 0
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "UserSession":
        session = cls(data["user_id"], data["conversation_id"], data.get("title", ""))
        session.created_at = data.get("created_at", session.created_at)
        session.updated_at = data.get("updated_at", session.updated_at)
        session.message_count = data.get("message_count", 0)
        return session


class UserSessionManager:
    """用户会话管理器"""
    
    def __init__(self):
        pass
    
    def _get_user_dir(self, user_id: str) -> Path:
        """获取用户目录"""
        user_dir = USER_SESSIONS_DIR / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    
    def _get_session_list_file(self, user_id: str) -> Path:
        """获取用户会话列表文件"""
        return self._get_user_dir(user_id) / "sessions.json"
    
    def _get_conversation_dir(self, user_id: str, conversation_id: str) -> Path:
        """获取对话目录 - 兼容新老结构
        
        新结构: chat_logs/{user_id}/conversations/{conversation_id}/
        旧结构: chat_logs/{user_id}/ (直接存放chat.jsonl)
        """
        user_dir = self._get_user_dir(user_id)
        
        # 检查是否是旧结构（会话ID等于用户ID，且直接有chat.jsonl）
        if conversation_id == user_id:
            old_chat_file = user_dir / "chat.jsonl"
            if old_chat_file.exists():
                return user_dir
        
        # 新结构
        conv_dir = user_dir / "conversations" / conversation_id
        conv_dir.mkdir(parents=True, exist_ok=True)
        return conv_dir
    
    def _get_conversation_file(self, user_id: str, conversation_id: str) -> Path:
        """获取对话文件 - 兼容新老结构"""
        conv_dir = self._get_conversation_dir(user_id, conversation_id)
        
        # 如果是旧结构（在用户根目录下）
        if conv_dir.name == user_id:
            return conv_dir / "chat.jsonl"
        
        # 新结构
        return conv_dir / "chat.jsonl"
    
    def _get_user_preferences_file(self, user_id: str) -> Path:
        """获取用户偏好文件（用户级）"""
        return self._get_user_dir(user_id) / "user_preferences.json"
    
    def _get_conversation_preferences_file(self, user_id: str, conversation_id: str) -> Path:
        """获取对话偏好文件（对话级，和chat.jsonl同级）"""
        conv_dir = self._get_conversation_dir(user_id, conversation_id)
        return conv_dir / "user_preferences.json"
    
    def create_conversation(self, user_id: str, title: str = "") -> UserSession:
        """
        创建新的对话
        
        Args:
            user_id: 用户ID
            title: 对话标题
            
        Returns:
            UserSession对象
        """
        import uuid
        conversation_id = str(uuid.uuid4())
        
        session = UserSession(user_id, conversation_id, title)
        
        # 保存到会话列表
        sessions = self.list_conversations(user_id)
        sessions.insert(0, session)
        self._save_session_list(user_id, sessions)
        
        # 创建空的对话文件
        conv_file = self._get_conversation_file(user_id, conversation_id)
        conv_file.touch()
        
        print(f"✅ 为用户 {user_id} 创建新对话: {conversation_id}")
        return session
    
    def list_conversations(self, user_id: str) -> List[UserSession]:
        """
        列出用户的所有对话 - 兼容新老结构
        
        Args:
            user_id: 用户ID
            
        Returns:
            UserSession列表，按更新时间倒序排列
        """
        session_list_file = self._get_session_list_file(user_id)
        user_dir = self._get_user_dir(user_id)
        
        sessions = []
        
        # 首先尝试从sessions.json加载
        if session_list_file.exists():
            try:
                with open(session_list_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions = [UserSession.from_dict(s) for s in data]
            except Exception as e:
                print(f"⚠️  加载会话列表失败: {e}")
        
        # 检查是否有旧结构的对话（直接在用户目录下的chat.jsonl）
        old_chat_file = user_dir / "chat.jsonl"
        if old_chat_file.exists():
            # 检查是否已经在sessions列表中
            has_old_conv = any(s.conversation_id == user_id for s in sessions)
            
            if not has_old_conv:
                # 创建旧对话的UserSession对象
                try:
                    # 统计消息数
                    msg_count = 0
                    with open(old_chat_file, "r", encoding="utf-8") as f:
                        msg_count = sum(1 for _ in f)
                    
                    # 获取文件时间
                    stat = old_chat_file.stat()
                    
                    old_session = UserSession(user_id, user_id, "历史对话")
                    old_session.created_at = datetime.fromtimestamp(stat.st_ctime).isoformat()
                    old_session.updated_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
                    old_session.message_count = msg_count
                    
                    sessions.insert(0, old_session)
                    
                    print(f"✅ 发现旧结构对话: {user_id}，已自动加入会话列表")
                    
                except Exception as e:
                    print(f"⚠️  处理旧结构对话失败: {e}")
        
        # 按更新时间倒序排列
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        
        return sessions
    
    def _save_session_list(self, user_id: str, sessions: List[UserSession]):
        """保存会话列表"""
        session_list_file = self._get_session_list_file(user_id)
        
        try:
            with open(session_list_file, "w", encoding="utf-8") as f:
                json.dump([s.to_dict() for s in sessions], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  保存会话列表失败: {e}")
    
    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[UserSession]:
        """
        获取指定的对话
        
        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            
        Returns:
            UserSession对象，如果不存在返回None
        """
        sessions = self.list_conversations(user_id)
        for session in sessions:
            if session.conversation_id == conversation_id:
                return session
        return None
    
    def update_conversation(self, user_id: str, conversation_id: str, 
                           title: Optional[str] = None, 
                           message_count: Optional[int] = None) -> bool:
        """
        更新对话信息
        
        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            title: 新标题（可选）
            message_count: 消息数量（可选）
            
        Returns:
            是否更新成功
        """
        sessions = self.list_conversations(user_id)
        updated = False
        
        for i, session in enumerate(sessions):
            if session.conversation_id == conversation_id:
                if title is not None:
                    session.title = title
                if message_count is not None:
                    session.message_count = message_count
                session.updated_at = datetime.now().isoformat()
                # 移到最前面
                sessions.pop(i)
                sessions.insert(0, session)
                updated = True
                break
        
        if updated:
            self._save_session_list(user_id, sessions)
        
        return updated
    
    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        删除对话 - 兼容新老结构
        
        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            
        Returns:
            是否删除成功
        """
        sessions = self.list_conversations(user_id)
        original_count = len(sessions)
        
        # 从列表中移除
        sessions = [s for s in sessions if s.conversation_id != conversation_id]
        
        if len(sessions) < original_count:
            self._save_session_list(user_id, sessions)
            
            # 检查是否是旧结构的对话
            if conversation_id == user_id:
                # 旧结构：只删除chat.jsonl，保留用户目录和user_preferences.json
                user_dir = self._get_user_dir(user_id)
                old_chat_file = user_dir / "chat.jsonl"
                if old_chat_file.exists():
                    old_chat_file.unlink()
                    print(f"✅ 删除旧结构对话: {conversation_id}")
            else:
                # 新结构：删除整个对话目录
                conv_dir = self._get_conversation_dir(user_id, conversation_id)
                import shutil
                if conv_dir.exists():
                    shutil.rmtree(conv_dir)
                    print(f"✅ 删除对话: {conversation_id}")
            
            return True
        
        return False
    
    def log_message(self, user_id: str, conversation_id: str, 
                   role: str, content: str, rewritten_question: str = None, **kwargs) -> bool:
        """
        记录对话消息
        
        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            role: 角色（user/assistant）
            content: 内容
            rewritten_question: 重写后的问题（可选）
            **kwargs: 其他参数
            
        Returns:
            是否记录成功
        """
        conv_file = self._get_conversation_file(user_id, conversation_id)
        
        message = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "conversation_id": conversation_id,
            "session_id": conversation_id,
            "role": role,
            "content": content
        }
        if rewritten_question:
            message["rewritten_question"] = rewritten_question
        message.update(kwargs)
        
        try:
            with open(conv_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(message, ensure_ascii=False) + "\n")
            
            # 更新会话信息
            self._update_message_count(user_id, conversation_id)
            
            return True
        except Exception as e:
            print(f"⚠️  记录消息失败: {e}")
            return False
    
    def _update_message_count(self, user_id: str, conversation_id: str):
        """更新消息数量"""
        conv_file = self._get_conversation_file(user_id, conversation_id)
        
        count = 0
        if conv_file.exists():
            with open(conv_file, "r", encoding="utf-8") as f:
                count = sum(1 for _ in f)
        
        self.update_conversation(user_id, conversation_id, message_count=count)
    
    def load_conversation_history(self, user_id: str, conversation_id: str) -> List[dict]:
        """
        加载对话历史
        
        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            
        Returns:
            消息列表
        """
        conv_file = self._get_conversation_file(user_id, conversation_id)
        
        if not conv_file.exists():
            return []
        
        messages = []
        try:
            with open(conv_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        messages.append(json.loads(line))
        except Exception as e:
            print(f"⚠️  加载对话历史失败: {e}")
        
        return messages
    
    def save_user_preferences(self, user_id: str, preferences: dict) -> bool:
        """
        保存用户偏好
        
        Args:
            user_id: 用户ID
            preferences: 用户偏好字典
            
        Returns:
            是否保存成功
        """
        prefs_file = self._get_user_preferences_file(user_id)
        
        preferences["updated_at"] = datetime.now().isoformat()
        preferences["user_id"] = user_id
        
        try:
            with open(prefs_file, "w", encoding="utf-8") as f:
                json.dump(preferences, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"⚠️  保存用户偏好失败: {e}")
            return False
    
    def load_user_preferences(self, user_id: str) -> dict:
        """
        加载用户偏好
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户偏好字典
        """
        prefs_file = self._get_user_preferences_file(user_id)
        
        if not prefs_file.exists():
            return {}
        
        try:
            with open(prefs_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  加载用户偏好失败: {e}")
            return {}
    
    def save_conversation_preferences(self, user_id: str, conversation_id: str, preferences: dict) -> bool:
        """
        保存对话偏好到对话文件夹下（和chat.jsonl同级）
        
        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            preferences: 对话偏好字典
            
        Returns:
            是否保存成功
        """
        prefs_file = self._get_conversation_preferences_file(user_id, conversation_id)
        
        preferences["updated_at"] = datetime.now().isoformat()
        preferences["user_id"] = user_id
        preferences["conversation_id"] = conversation_id
        
        try:
            with open(prefs_file, "w", encoding="utf-8") as f:
                json.dump(preferences, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"⚠️  保存对话偏好失败: {e}")
            return False
    
    def load_conversation_preferences(self, user_id: str, conversation_id: str) -> dict:
        """
        从对话文件夹加载对话偏好
        
        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            
        Returns:
            对话偏好字典，如果不存在返回空字典
        """
        prefs_file = self._get_conversation_preferences_file(user_id, conversation_id)
        
        if not prefs_file.exists():
            return {}
        
        try:
            with open(prefs_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  加载对话偏好失败: {e}")
            return {}


# 全局管理器实例
session_manager = UserSessionManager()
