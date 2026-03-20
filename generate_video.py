#!/usr/bin/env python3
"""
生成指定内容的视频
"""

import os
import sys
import requests
from pathlib import Path

# 确保使用正确的Python环境
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "http://localhost:8000"


def generate_video():
    """生成指定内容的视频"""
    print("=== 生成指定内容的视频 ===")
    
    # 用户要求的视频参数
    video_data = {
        "text": "一个阳光明媚的下午，孩子们在公园里玩耍，鸟儿在树上唱歌，花朵盛开，蝴蝶飞舞",
        "duration": 12,  # 用户要求12秒
        "resolution": "720p",
        "style": "cartoon",
        "session_id": "999"  # 使用固定的session_id
    }
    
    print(f"视频内容: {video_data['text']}")
    print(f"视频时长: {video_data['duration']}秒")
    print(f"视频分辨率: {video_data['resolution']}")
    print(f"视频风格: {video_data['style']}")
    print(f"Session ID: {video_data['session_id']}")
    
    # 发送请求生成视频
    print("\n正在生成视频...")
    response = requests.post(f"{BASE_URL}/text-to-video", json=video_data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ 视频生成成功！")
        print(f"视频ID: {result['video_id']}")
        print(f"Session ID: {result['session_id']}")
        print(f"视频保存路径: {result['video_path']}")
        print(f"缩略图保存路径: {result['thumbnail_path']}")
        print(f"视频URL: {result['video_url']}")
        print(f"状态: {result['status']}")
        print(f"消息: {result['msg']}")
        
        # 验证文件是否创建
        video_path = Path(result['video_path'])
        thumbnail_path = Path(result['thumbnail_path'])
        
        if video_path.exists():
            print(f"\n✅ 视频文件已创建: {video_path}")
        else:
            print(f"\n❌ 视频文件未创建: {video_path}")
        
        if thumbnail_path.exists():
            print(f"✅ 缩略图文件已创建: {thumbnail_path}")
        else:
            print(f"❌ 缩略图文件未创建: {thumbnail_path}")
        
        # 验证聊天记录是否更新
        chat_file = Path(f"chat_logs/{result['session_id']}/chat.jsonl")
        if chat_file.exists():
            print(f"✅ 聊天记录文件存在: {chat_file}")
            # 检查是否包含视频记录
            with open(chat_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) > 0:
                    last_line = lines[-1]
                    if result['video_id'] in last_line:
                        print(f"✅ 视频记录已添加到聊天记录")
                    else:
                        print(f"❌ 视频记录未添加到聊天记录")
        else:
            print(f"❌ 聊天记录文件不存在: {chat_file}")
        
        return result
    else:
        print(f"\n❌ 视频生成失败: {response.status_code}")
        print(f"错误信息: {response.json()}")
        return None


def main():
    """主函数"""
    result = generate_video()
    if result:
        print("\n🎉 视频生成任务完成！")
    else:
        print("\n⚠️  视频生成任务失败，请检查错误信息。")


if __name__ == "__main__":
    main()
