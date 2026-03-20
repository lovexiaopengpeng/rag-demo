#!/usr/bin/env python3
# 脚本：重新发起用户提问

import os
import sys
import json
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).resolve().parent))

from api import ask
from pydantic import BaseModel

# 定义测试请求模型
class TestAskRequest(BaseModel):
    question: str
    user_id: str = ""
    conversation_id: str = ""

# 提取用户提问
user_id = "9527"
conversation_id = "7dbf28fc-e53a-4228-b2e4-f242ba79bc1b"

# 用户提问列表
user_questions = [
    "公司加班补贴是怎样的？",
    "公司加班有工资吗？",
    "公司加班可以调休吗？",
    "公司加班有加班费吗？",
    "公司什么时候上班吗？",
    "公司一天需要打卡几次？",
    "公司如何请假？",
    "事假呢？",
    "公司怎么请事假？",
    "公司年会地点在哪里？",
    "公司年会时间？",
    "公司年会怎么参与？",
    "公司年会什么时候开始？",
    "多少人参加？",
    "参会人数？",
    "年会参会人数？",
    "年会参会人数？",
    "出差如何打卡？",
    "周报有什么要求？",
    "公司叫什么名字？",
    "公司叫什么？",
    "在哪里？",
    "年会在哪里举行？",
    "公司一天需要打卡几次？",
    "公司主营业务？",
    "公司主营业务是什么？",
    "主营业务是什么？",
    "公司年会在哪里举行什么？",
    "长沙好玩吗？"
]

# 重新发起提问
def replay_questions():
    """重新发起用户提问"""
    print(f"开始重新发起用户 {user_id} 在对话 {conversation_id} 中的提问...")
    
    for i, question in enumerate(user_questions, 1):
        print(f"\n=== 第 {i} 个问题 ===")
        print(f"用户提问: {question}")
        
        # 创建请求
        test_request = TestAskRequest(
            question=question,
            user_id=user_id,
            conversation_id=conversation_id
        )
        
        try:
            # 调用ask函数
            result = ask(test_request)
            print(f"助手回答: {result['answer']}")
        except Exception as e:
            print(f"调用失败: {e}")
    
    print("\n所有问题已重新发起完成！")

if __name__ == "__main__":
    replay_questions()
