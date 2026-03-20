#!/usr/bin/env python3
"""
生成史诗级可爱的小猫将军视频
"""
import requests
import json

API_URL = "http://localhost:8000"

def generate_epic_cat_video():
    """生成史诗级可爱的小猫将军视频"""
    print("生成史诗级可爱的小猫将军视频...")
    
    # 视频内容描述
    video_text = "一幅史诗级可爱的场景。一只小巧可爱的卡通小猫将军，身穿细节精致的金色盔甲，头戴一个稍大的头盔，勇敢地站在悬崖上。他骑着一匹虽小但英勇的战马，说：\"青海长云暗雪山，孤城遥望玉门关。黄沙百战穿金甲，不破楼兰终不还\"。悬崖下方，一支由老鼠组成的、数量庞大、无穷无尽的军队正带着临时制作的武器向前冲锋。这是一个戏剧性的、大规模的战斗场景，灵感来自中国古代的战争史诗。远处的雪山上空，天空乌云密布。整体氛围是\"可爱\"与\"霸气\"的搞笑和史诗般的融合。"
    
    # 测试数据
    test_data = {
        "text": video_text,
        "duration": 15,  # 稍微延长时间以容纳更多内容
        "resolution": "720p",
        "style": "default",
        "session_id": "999"
    }
    
    try:
        # 发送请求
        response = requests.post(
            f"{API_URL}/text-to-video",
            json=test_data,
            timeout=120  # 增加超时时间以处理较长的视频生成
        )
        
        # 检查响应状态码
        if response.status_code == 200:
            result = response.json()
            print("视频生成成功！")
            print(f"视频ID: {result['video_id']}")
            print(f"会话ID: {result['session_id']}")
            print(f"视频URL: {API_URL}{result['video_url']}")
            print(f"视频路径: {result['video_path']}")
            print(f"状态: {result['status']}")
            print(f"消息: {result['msg']}")
            
            # 测试视频文件是否可访问
            video_full_url = f"{API_URL}{result['video_url']}"
            print(f"\n视频访问地址: {video_full_url}")
            
            # 验证视频文件
            video_response = requests.get(video_full_url, timeout=60)
            if video_response.status_code == 200:
                print("✅ 视频文件可正常访问！")
                print(f"视频文件大小: {len(video_response.content) / 1024 / 1024:.2f} MB")
                return result
            else:
                print(f"❌ 视频文件访问失败，状态码: {video_response.status_code}")
                return None
        else:
            print(f"❌ API调用失败，状态码: {response.status_code}")
            print(f"错误信息: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 生成过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("开始生成史诗级可爱的小猫将军视频...")
    print("=" * 80)
    
    result = generate_epic_cat_video()
    
    print("=" * 80)
    if result:
        print("🎉 视频生成完成！")
        print(f"您可以通过以下地址访问视频:")
        print(f"http://localhost:8000{result['video_url']}")
    else:
        print("❌ 视频生成失败！")
