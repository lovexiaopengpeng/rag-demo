#!/usr/bin/env python3
# 测试不同场景的问题回答准确率

import requests
import json

# API地址
API_URL = "http://localhost:8000/ask"

# 测试问题列表，包含不同场景
test_questions = [
    # 科学知识
    "什么是黑洞？",
    "光合作用的过程是什么？",
    "量子力学的基本原理是什么？",
    
    # 历史知识
    "第二次世界大战开始于哪一年？",
    "中国的四大发明是什么？",
    "埃及金字塔是如何建造的？",
    
    # 地理知识
    "世界上最长的河流是什么？",
    "南极洲的气候特点是什么？",
    "中国的邻国都有哪些？",
    
    # 文化艺术
    "《蒙娜丽莎》的作者是谁？",
    "贝多芬的代表作有哪些？",
    "中国的传统节日有哪些？",
    
    # 技术知识
    "人工智能的发展历程是什么？",
    "区块链技术的原理是什么？",
    "5G技术的优势是什么？",
    
    # 生活常识
    "如何健康饮食？",
    "怎样提高睡眠质量？",
    "紧急情况下的急救措施有哪些？"
]

# 测试参数
user_id = "9527"
conversation_id = "b3e54dcf-3295-4023-ab9d-90cc624e6661"

def test_different_scenarios():
    print("开始测试不同场景的问题回答...\n")
    
    for i, question in enumerate(test_questions, 1):
        print(f"测试问题 {i}: {question}")
        
        # 构建请求数据
        data = {
            "question": question,
            "user_id": user_id,
            "conversation_id": conversation_id
        }
        
        try:
            # 发送请求
            response = requests.post(API_URL, json=data, timeout=30)
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
        
        print("-" * 50)

if __name__ == "__main__":
    test_different_scenarios()
