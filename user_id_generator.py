#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户ID生成器 - 生成1-99999范围内的唯一数字用户ID
"""

import os
import json
from pathlib import Path

# 存储用户ID的文件
USER_ID_STORE = Path(__file__).resolve().parent / "user_id_store.json"
USER_SESSIONS_DIR = Path(__file__).resolve().parent / "chat_logs"

class UserIDGenerator:
    """用户ID生成器"""
    
    def __init__(self):
        self._load_last_id()
    
    def _load_last_id(self):
        """加载最后使用的用户ID"""
        if USER_ID_STORE.exists():
            try:
                with open(USER_ID_STORE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.last_id = data.get("last_id", 0)
            except Exception as e:
                print(f"加载用户ID存储失败: {e}")
                self.last_id = 0
        else:
            self.last_id = 0
    
    def _save_last_id(self):
        """保存最后使用的用户ID"""
        try:
            with open(USER_ID_STORE, "w", encoding="utf-8") as f:
                json.dump({"last_id": self.last_id}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存用户ID存储失败: {e}")
    
    def _get_existing_user_ids(self) -> set:
        """获取已存在的用户ID"""
        existing_ids = set()
        
        if USER_SESSIONS_DIR.exists():
            for user_dir in USER_SESSIONS_DIR.iterdir():
                if user_dir.is_dir():
                    try:
                        user_id = user_dir.name
                        # 检查是否是数字
                        if user_id.isdigit():
                            existing_ids.add(user_id)
                    except Exception as e:
                        print(f"检查用户目录失败: {e}")
        
        return existing_ids
    
    def generate_user_id(self) -> str:
        """
        生成新的用户ID
        
        Returns:
            1-99999范围内的数字字符串
        """
        existing_ids = self._get_existing_user_ids()
        
        # 从last_id + 1开始查找
        for i in range(1, 100000):  # 最多尝试100000次
            candidate_id = (self.last_id + i) % 100000
            if candidate_id == 0:
                candidate_id = 100000
            
            candidate_id_str = str(candidate_id)
            
            if candidate_id_str not in existing_ids:
                self.last_id = candidate_id
                self._save_last_id()
                return candidate_id_str
        
        # 如果所有ID都被使用了，返回一个随机ID
        import random
        while True:
            candidate_id = random.randint(1, 99999)
            candidate_id_str = str(candidate_id)
            if candidate_id_str not in existing_ids:
                self.last_id = candidate_id
                self._save_last_id()
                return candidate_id_str

# 全局实例
user_id_generator = UserIDGenerator()

if __name__ == "__main__":
    # 测试生成用户ID
    generator = UserIDGenerator()
    print("已存在的用户ID:", generator._get_existing_user_ids())
    
    for i in range(10):
        user_id = generator.generate_user_id()
        print(f"生成的用户ID {i+1}: {user_id}")
