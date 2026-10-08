#!/usr/bin/env python3
"""
测试兼容性检查功能
"""

import sys
import os

# 添加路径
sys.path.append(os.path.dirname(__file__))

from agent import Agent

def test_compatibility_checking():
    """测试兼容性检查功能"""
    agent = Agent()

    print("=" * 50)
    print("测试工作流兼容性检查功能")
    print("=" * 50)

    # 测试用例1：已知的不兼容序列
    print("\n测试用例1：烘干机 → 电化学工作站 (应该检测到不兼容)")
    test_plan_1 = [
        {'method': '物料站', 'params': {}},
        {'method': '多通道固体进样器', 'params': {}},
        {'method': '烘干机', 'params': {}},
        {'method': '双工位电化学工作站', 'params': {}}
    ]

    result_1 = agent.check_plan_compatibility(test_plan_1)
    print(f"兼容性: {result_1['compatible']}")
    print("问题:")
    for issue in result_1['issues']:
        print(f"  - {issue}")

    # 测试用例2：兼容的序列
    print("\n测试用例2：固体进样 → 液体处理 → 电化学工作站 (应该兼容)")
    test_plan_2 = [
        {'method': '物料站', 'params': {}},
        {'method': '固体进样站', 'params': {}},
        {'method': '液体进样站', 'params': {}},
        {'method': '磁力搅拌工作站', 'params': {}},
        {'method': '双工位电化学工作站', 'params': {}}
    ]

    result_2 = agent.check_plan_compatibility(test_plan_2)
    print(f"兼容性: {result_2['compatible']}")
    if result_2['issues']:
        print("问题:")
        for issue in result_2['issues']:
            print(f"  - {issue}")
    else:
        print("✅ 没有兼容性问题")

    # 测试用例3：单步计划 (应该兼容)
    print("\n测试用例3：单步计划 (应该兼容)")
    test_plan_3 = [
        {'method': '物料站', 'params': {}}
    ]

    result_3 = agent.check_plan_compatibility(test_plan_3)
    print(f"兼容性: {result_3['compatible']}")

    # 测试用例4：空计划 (应该兼容)
    print("\n测试用例4：空计划 (应该兼容)")
    result_4 = agent.check_plan_compatibility([])
    print(f"兼容性: {result_4['compatible']}")

    # 测试用例5：问题1 - 磁力搅拌 → 光催化工作站 (应该检测到不兼容)
    print("\n测试用例5：问题1 - 磁力搅拌 → 光催化工作站 (应该检测到不兼容)")
    test_plan_5 = [
        {'method': '物料站', 'params': {}},
        {'method': '1ml液体进样站', 'params': {}},
        {'method': '磁力搅拌工作站', 'params': {}},
        {'method': '光催化工作站', 'params': {}}
    ]

    result_5 = agent.check_plan_compatibility(test_plan_5)
    print(f"兼容性: {result_5['compatible']}")
    print("问题:")
    for issue in result_5['issues']:
        print(f"  - {issue}")

    # 测试用例6：问题5 - 烘干机 → 超声清洗工作站 (应该检测到不兼容)
    print("\n测试用例6：问题5 - 烘干机 → 超声清洗工作站 (应该检测到不兼容)")
    test_plan_6 = [
        {'method': '物料站', 'params': {}},
        {'method': '多通道固体进样器', 'params': {}},
        {'method': '烘干机', 'params': {}},
        {'method': '超声清洗工作站', 'params': {}}
    ]

    result_6 = agent.check_plan_compatibility(test_plan_6)
    print(f"兼容性: {result_6['compatible']}")
    print("问题:")
    for issue in result_6['issues']:
        print(f"  - {issue}")

    # 测试用例7：新问题 - 离心纯化 → 高通量红外光谱工作站 (应该检测到不兼容)
    print("\n测试用例7：新问题 - 离心纯化 → 高通量红外光谱工作站 (应该检测到不兼容)")
    test_plan_7 = [
        {'method': '物料站', 'params': {}},
        {'method': '1ml液体进样站', 'params': {}},
        {'method': '磁力搅拌工作站', 'params': {}},
        {'method': '超声清洗工作站', 'params': {}},
        {'method': '离心纯化工作站', 'params': {}},
        {'method': '高通量红外光谱工作站', 'params': {}}
    ]

    result_7 = agent.check_plan_compatibility(test_plan_7)
    print(f"兼容性: {result_7['compatible']}")
    print("问题:")
    for issue in result_7['issues']:
        print(f"  - {issue}")

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)

if __name__ == "__main__":
    test_compatibility_checking()