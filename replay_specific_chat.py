import json
import requests
import time

# 从chat.jsonl文件中提取用户提问
def extract_user_questions(file_path):
    user_questions = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print(f"文件共有{len(lines)}行")
            for i, line in enumerate(lines, 1):
                if line.strip():
                    try:
                        entry = json.loads(line)
                        role = entry.get('role')
                        content = entry.get('content')
                        print(f"第{i}行: role={role}, content={content[:20]}...")
                        if role == 'user':
                            user_questions.append(content)
                    except json.JSONDecodeError as e:
                        print(f"第{i}行解析失败: {e}")
    except Exception as e:
        print(f"读取文件失败: {e}")
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

if __name__ == "__main__":
    # 配置参数
    chat_log_file = "/Users/zlhh/Desktop/训练工具/脚本/上传文件+自动触发/rag_demo/chat_logs/9527/conversations/7dbf28fc-e53a-4228-b2e4-f242ba79bc1b/chat.jsonl"
    user_id = "9527"
    conversation_id = "7dbf28fc-e53a-4228-b2e4-f242ba79bc1b"
    
    # 提取用户提问
    user_questions = extract_user_questions(chat_log_file)
    
    print(f"原始提取的问题: {user_questions}")
    
    # 过滤掉第一个问题（"你好，我是用户9527"），因为这是问候语
    if user_questions and user_questions[0] == "你好，我是用户9527":
        user_questions = user_questions[1:]
    
    print(f"过滤后的问题: {user_questions}")
    
    # 重新发起提问
    replay_questions(user_id, conversation_id, user_questions)
