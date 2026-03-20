#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清除缓存
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag_core import rewrite_cache

def clear_cache():
    """
    清除缓存
    """
    print("开始清除缓存")
    
    # 清除rewrite_cache
    rewrite_cache.clear()
    print(f"成功清除rewrite_cache，当前缓存大小: {len(rewrite_cache)}")
    
    # 清除其他可能的缓存文件
    # 检查是否存在缓存文件
    cache_files = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
    ]
    
    for cache_file in cache_files:
        if os.path.exists(cache_file):
            if os.path.isdir(cache_file):
                import shutil
                shutil.rmtree(cache_file)
                print(f"成功删除缓存目录: {cache_file}")
            else:
                os.remove(cache_file)
                print(f"成功删除缓存文件: {cache_file}")
    
    print("缓存清除完成")

if __name__ == "__main__":
    clear_cache()
