#!/usr/bin/env python3
"""
测试 LLM API 连接
"""

from agents.alchemy_agent import llm_generate, USE_LLM, LLM_MODEL

if __name__ == '__main__':
    if not USE_LLM:
        print("警告：ALCHEMY_USE_LLM=false，请在 .env 中设置 ALCHEMY_USE_LLM=true")

    print(f"使用模型：{LLM_MODEL}")
    print("发送测试请求...")

    try:
        result = llm_generate('你好，请用一句话介绍你自己')
        print('✅ LLM 调用成功！')
        print(f'回复：{result}')
    except ImportError as e:
        print(f'❌ 缺少依赖：{e}')
        print('请运行：pip install anthropic')
    except Exception as e:
        print(f'❌ LLM 调用失败：{e}')
