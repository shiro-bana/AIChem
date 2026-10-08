#!/usr/bin/env python3
"""
测试agent的工作流规划功能（带兼容性检查）
"""

import sys
import os

# 添加路径
sys.path.append(os.path.dirname(__file__))

from agent import Agent

def test_agent_workflow():
    """测试agent的工作流规划功能"""

    print("=" * 60)
    print("测试Agent工作流规划（带兼容性检查）")
    print("=" * 60)

    # 创建agent但不启动服务器
    agent = Agent()

    # 模拟工具可用
    agent.tools = {
        '物料站': {'description': '物料站 - 提供空容器'},
        '多通道固体进样器': {'description': '多通道固体进样器 - 固体进样'},
        '烘干机': {'description': '烘干机 - 干燥处理'},
        '双工位电化学工作站': {'description': '双工位电化学工作站 - 电化学测试，要求悬浊液'},
        '液体进样站': {'description': '液体进样站 - 液体进样'},
        '磁力搅拌工作站': {'description': '磁力搅拌工作站 - 混合搅拌，可形成悬浊液'}
    }

    # 模拟一个简单的工作流规划
    print("\n模拟生成一个兼容的工作流:")

    # 这个计划应该是兼容的
    compatible_plan = [
        {'method': '物料站', 'params': {}},
        {'method': '多通道固体进样器', 'params': {}},
        {'method': '液体进样站', 'params': {}},
        {'method': '磁力搅拌工作站', 'params': {}},
        {'method': '双工位电化学工作站', 'params': {}}
    ]

    result = agent.check_plan_compatibility(compatible_plan)
    print(f"兼容性检查结果: {result['compatible']}")
    if not result['compatible']:
        print("发现的问题:")
        for issue in result['issues']:
            print(f"  - {issue}")
    else:
        print("✅ 计划兼容！")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_agent_workflow()