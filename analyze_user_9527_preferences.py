#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析9527用户的用户偏好
"""
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_core import extract_user_preferences, analyze_and_save_user_preferences
from chat_logger import load_user_preferences, save_user_preferences


def load_chat_history(session_id):
    """加载用户对话历史"""
    from chat_logger import CHAT_LOG_DIR
    chat_file = Path(CHAT_LOG_DIR) / session_id / "chat.jsonl"
    
    history = []
    if chat_file.exists():
        with open(chat_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    # 只保留user和assistant的消息，过滤system消息
                    if entry['role'] in ['user', 'assistant']:
                        history.append({
                            'role': entry['role'],
                            'content': entry['content']
                        })
                except Exception as e:
                    print(f"解析行时出错: {e}")
    
    return history


def main():
    print("=" * 60)
    print("分析9527用户的用户偏好")
    print("=" * 60)
    
    session_id = "9527"
    
    # 1. 加载对话历史
    print(f"\n1. 加载 {session_id} 用户的对话历史...")
    history = load_chat_history(session_id)
    print(f"   对话历史条数: {len(history)}")
    
    # 2. 显示前几条对话
    print("\n2. 前几条对话:")
    for i, msg in enumerate(history[:6]):
        print(f"   {i+1}. {msg['role']}: {msg['content'][:50]}...")
    
    # 3. 分析用户偏好
    print(f"\n3. 分析用户偏好...")
    preferences = analyze_and_save_user_preferences(session_id, history)
    
    # 4. 显示分析结果
    print("\n4. 用户偏好分析结果:")
    print("-" * 60)
    print(json.dumps(preferences, ensure_ascii=False, indent=2))
    
    # 5. 验证文件已保存
    from chat_logger import CHAT_LOG_DIR, USER_PREFERENCES_FILENAME
    prefs_file = Path(CHAT_LOG_DIR) / session_id / USER_PREFERENCES_FILENAME
    print(f"\n5. 用户偏好文件已保存到: {prefs_file}")
    
    print("\n" + "=" * 60)
    print("分析完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
