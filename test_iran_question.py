#!/usr/bin/env python3
# 测试伊朗和美国冲突的问题

import requests
import json

# API地址
API_URL = "http://localhost:8000/ask"

# 测试问题
question = "伊朗现在和美国大战，被封锁的海峡叫什么名字以及什么时候解封？"

# 测试参数
user_id = "9527"
conversation_id = "b3e54dcf-3295-4023-ab9d-90cc624e6661"

def test_iran_question():
    print("测试伊朗和美国冲突的问题...\n")
    print(f"测试问题: {question}")
    
    # 构建请求数据
    data = {
        "question": question,
        "user_id": user_id,
        "conversation_id": conversation_id
    }
    
    try:
        # 发送请求
        response = requests.post(API_URL, json=data, timeout=60)
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        
        # 打印结果
        print(f"📋 回答: {result.get('answer', '无回答')}")
        print(f"📡 来源: {result.get('source', '未知')}")
        if 'rewritten_question' in result and result['rewritten_question'] != question:
            print(f"🔄 改写后的问题: {result['rewritten_question']}")
        
    except Exception as e:
        print(f"❌ 请求失败: {str(e)}")

if __name__ == "__main__":
    test_iran_question()
