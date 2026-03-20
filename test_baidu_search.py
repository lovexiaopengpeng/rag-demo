#!/usr/bin/env python3
# 测试百度搜索功能

from rag_core import web_search

# 测试百度搜索
def test_baidu_search():
    print("测试百度搜索功能...")
    
    # 测试搜索关键词
    test_queries = [
        "Python编程",
        "2026年最新科技趋势",
        "如何学习人工智能"
    ]
    
    for query in test_queries:
        print(f"\n测试搜索: {query}")
        results = web_search(query, max_results=3)
        
        if results:
            print(f"找到 {len(results)} 条结果:")
            for i, result in enumerate(results, 1):
                print(f"\n结果 {i}:")
                print(f"标题: {result['title']}")
                print(f"摘要: {result['body'][:100]}...")  # 只显示前100个字符
                print(f"链接: {result['href']}")
        else:
            print("没有找到搜索结果")

if __name__ == "__main__":
    test_baidu_search()
