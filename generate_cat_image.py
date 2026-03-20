#!/usr/bin/env python3
"""
生成小猫将军图片
"""
import requests
import json

API_URL = "http://localhost:8000"

def generate_cat_image():
    """生成小猫将军图片"""
    print("生成小猫将军图片...")
    
    # 测试数据
    test_data = {
        "text": "一只可爱的小猫将军，身穿金色盔甲，站在悬崖上",
        "style": "default",
        "size": "512x512",
        "session_id": "999"
    }
    
    try:
        # 发送请求
        response = requests.post(
            f"{API_URL}/text-to-image",
            json=test_data,
            timeout=60
        )
        
        # 检查响应状态码
        if response.status_code == 200:
            result = response.json()
            print("API调用成功！")
            print(f"图片ID: {result['image_id']}")
            print(f"会话ID: {result['session_id']}")
            print(f"图片URL: {API_URL}{result['image_url']}")
            print(f"图片路径: {result['image_path']}")
            print(f"状态: {result['status']}")
            print(f"消息: {result['msg']}")
            
            return result
        else:
            print(f"API调用失败，状态码: {response.status_code}")
            print(f"错误信息: {response.text}")
            return None
            
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("开始生成小猫将军图片...")
    print("=" * 60)
    
    result = generate_cat_image()
    
    print("=" * 60)
    if result:
        print("🎉 图片生成成功！")
        print(f"您可以通过以下地址访问图片:")
        print(f"http://localhost:8000{result['image_url']}")
    else:
        print("❌ 图片生成失败！")
