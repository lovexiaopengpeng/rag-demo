#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证用户会话文件结构是否正确
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from user_session_manager import session_manager


def verify_structure():
    """验证文件结构"""
    print("=" * 70)
    print("验证用户会话文件结构")
    print("=" * 70)
    
    # 基础目录
    BASE_DIR = Path(__file__).resolve().parent
    USER_SESSIONS_DIR = BASE_DIR / "user_sessions"
    
    print(f"\n📁 基础目录: {BASE_DIR}")
    print(f"📁 用户会话目录: {USER_SESSIONS_DIR}")
    
    # 检查用户会话目录是否存在
    if not USER_SESSIONS_DIR.exists():
        print(f"❌ 用户会话目录不存在")
        return False
    
    print(f"\n✅ 用户会话目录存在")
    
    # 列出所有用户
    print(f"\n👥 发现的用户:")
    user_dirs = [d for d in USER_SESSIONS_DIR.iterdir() if d.is_dir()]
    
    if not user_dirs:
        print(f"   (暂无用户)")
    else:
        for user_dir in user_dirs:
            user_id = user_dir.name
            print(f"\n   👤 用户: {user_id}")
            
            # 检查用户目录结构
            sessions_file = user_dir / "sessions.json"
            prefs_file = user_dir / "user_preferences.json"
            conv_dir = user_dir / "conversations"
            
            # 检查会话列表文件
            if sessions_file.exists():
                print(f"      ✅ sessions.json 存在")
                import json
                with open(sessions_file, "r", encoding="utf-8") as f:
                    sessions = json.load(f)
                    print(f"         包含 {len(sessions)} 个对话")
            else:
                print(f"      ⚠️  sessions.json 不存在")
            
            # 检查用户偏好文件
            if prefs_file.exists():
                print(f"      ✅ user_preferences.json 存在")
            else:
                print(f"      ⚠️  user_preferences.json 不存在")
            
            # 检查对话目录
            if conv_dir.exists():
                print(f"      ✅ conversations/ 目录存在")
                conv_subdirs = [d for d in conv_dir.iterdir() if d.is_dir()]
                print(f"         包含 {len(conv_subdirs)} 个对话文件夹")
                
                for conv_subdir in conv_subdirs:
                    conv_id = conv_subdir.name
                    chat_file = conv_subdir / "chat.jsonl"
                    if chat_file.exists():
                        print(f"         ✅ {conv_id}/chat.jsonl 存在")
                        # 统计消息数
                        with open(chat_file, "r", encoding="utf-8") as f:
                            msg_count = sum(1 for _ in f)
                            print(f"            包含 {msg_count} 条消息")
                    else:
                        print(f"         ⚠️  {conv_id}/chat.jsonl 不存在")
            else:
                print(f"      ⚠️  conversations/ 目录不存在")
    
    print(f"\n{'='*70}")
    print("文件结构验证完成!")
    print(f"{'='*70}")
    print(f"\n📂 正确的文件结构应该是:")
    print(f"""
user_sessions/
└── {{user_id}}/
    ├── sessions.json              # 用户对话列表
    ├── user_preferences.json       # 用户偏好（可选）
    └── conversations/
        ├── {{conversation_id_1}}/
        │   └── chat.jsonl
        ├── {{conversation_id_2}}/
        │   └── chat.jsonl
        └── ...
    """)
    
    return True


if __name__ == "__main__":
    verify_structure()
