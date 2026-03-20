import json
import os
from collections import deque
from typing import List, Optional
from langchain_core.documents import Document
from pathlib import Path

# 对话历史存储目录
BASE_DIR = Path(__file__).resolve().parent
CONVERSATION_HISTORY_DIR = BASE_DIR / "conversation_history"

class ConversationMemory:
    def __init__(self, llm, max_turns=6, session_id=None):
        self.llm = llm
        self.max_turns = max_turns
        self.session_id = session_id
        self.history: List[dict] = []
        self.summary = ""
        
        # 加载已有的对话历史
        if session_id:
            self._load_history()

    def add(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        self._maybe_summarize()
        
        # 保存对话历史
        if self.session_id:
            self._save_history()

    def _maybe_summarize(self):
        if len(self.history) <= self.max_turns * 2:
            return

        text = "\n".join(
            f"{m['role']}: {m['content']}" for m in self.history
        )

        prompt = f"""
请将以下对话压缩为【关键信息摘要】，保留事实、结论、条件，不要细节：

{text}

摘要：
"""
        self.summary = self.llm.invoke(prompt).strip()
        self.history = self.history[-2:]  # 只留最近一轮

    def get_context(self) -> str:
        dialog = "\n".join(
            f"{m['role']}: {m['content']}" for m in self.history
        )
        return f"对话摘要：{self.summary}\n\n当前对话：\n{dialog}" if self.summary else dialog
    
    def _get_history_file_path(self):
        """获取对话历史文件路径"""
        if not self.session_id:
            return None
        
        # 解析session_id，支持user_id:conversation_id格式
        if ":" in self.session_id:
            user_id, conversation_id = self.session_id.split(":", 1)
            # 使用新的目录结构
            user_history_dir = CONVERSATION_HISTORY_DIR / user_id / "conversations" / conversation_id
        else:
            # 兼容旧的session_id格式
            user_history_dir = CONVERSATION_HISTORY_DIR / self.session_id
        
        # 创建目录
        user_history_dir.mkdir(parents=True, exist_ok=True)
        
        return user_history_dir / "history.json"
    
    def _save_history(self):
        """保存对话历史到文件"""
        history_file = self._get_history_file_path()
        if not history_file:
            return
            
        history_data = {
            "summary": self.summary,
            "history": self.history,
            "max_turns": self.max_turns
        }
        
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
    
    def _load_history(self):
        """从文件加载对话历史"""
        history_file = self._get_history_file_path()
        if not history_file or not history_file.exists():
            return
            
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history_data = json.load(f)
                self.summary = history_data.get("summary", "")
                self.history = history_data.get("history", [])
                self.max_turns = history_data.get("max_turns", self.max_turns)
        except Exception as e:
            print(f"加载对话历史失败: {e}")
    
    def clear(self):
        """清空对话历史"""
        self.history.clear()
        self.summary = ""
        
        # 删除历史文件
        history_file = self._get_history_file_path()
        if history_file and history_file.exists():
            try:
                history_file.unlink()
            except Exception as e:
                print(f"删除对话历史文件失败: {e}")

# ====== 兼容旧接口 ======
    def add_user(self, text: str):
        self.add("用户", text)

    def add_assistant(self, text: str):
        self.add("助手", text)

    def get(self):
        return self.history
