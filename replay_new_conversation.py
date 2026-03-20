import json
import requests
import time
import uuid

# 手动从chat.jsonl文件中提取用户提问
def extract_user_questions():
    # 直接硬编码用户提问列表
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
    return user_questions

# 重新发起用户提问
def replay_questions(user_id, conversation_id, questions):
    base_url = "http://localhost:8000/ask"
    
    print(f"开始重新发起用户提问，用户ID: {user_id}，对话ID: {conversation_id}")
    print(f"共{len(questions)}个问题需要重新发起\n")
    
    for i, question in enumerate(questions, 1):
        print(f"发起第{i}个问题: {question}")
        
        # 构建请求数据
        data = {
            "question": question,
            "user_id": user_id,
            "conversation_id": conversation_id
        }
        
        try:
            # 发送请求
            response = requests.post(base_url, json=data, timeout=30)
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            print(f"响应: {result.get('answer', '无响应内容')}")
            print(f"状态: 成功")
        except Exception as e:
            print(f"状态: 失败 - {str(e)}")
        
        print("-" * 50)
        # 间隔1秒，避免请求过快
        time.sleep(1)
    
    print(f"\n所有{len(questions)}个问题已重新发起完成")
    print(f"新对话ID: {conversation_id}")
    print(f"对话保存路径: chat_logs/{user_id}/conversations/{conversation_id}/chat.jsonl")

if __name__ == "__main__":
    # 配置参数
    user_id = "9527"
    # 生成新的对话ID
    conversation_id = str(uuid.uuid4())
    
    # 提取用户提问
    user_questions = extract_user_questions()
    
    print(f"提取的问题数量: {len(user_questions)}")
    print(f"生成的新对话ID: {conversation_id}")
    
    # 重新发起提问
    replay_questions(user_id, conversation_id, user_questions)
