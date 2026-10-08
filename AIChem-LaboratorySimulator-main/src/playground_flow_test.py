#!/usr/bin/env python3
"""
化学实验流程验证脚本 - playground版本
基于playground.ipynb的方式验证工作站流程
"""

import yaml
import json
import re
from sample import Sample

# 工作站名称到详细约束条件的映射
WORKSTATION_CONSTRAINTS = {
    '物料站': {
        'constraints': [],  # 无约束
        'description': '获取50ml离心管'
    },
    '1ml液体进样站': {
        'constraints': [
            ('容器类型', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]),
            ('子容器编号存在', lambda s: s.data['container']['subcontainer']['subcontainer_number'] is not None),
            ('子容器编号范围', lambda s: 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 10),
            ('子容器体积限制', lambda s: s.data['container']['subcontainer']['subcontainer_volume'] <= 30),
            ('相态要求', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] in ['liquid', 'suspension', 'solid'])
        ],
        'description': '添加1ml液体'
    },
    '荧光光谱工作站': {
        'constraints': [
            ('容器类型', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] == "50ml_centrifuge_tube"),
            ('子容器编号范围', lambda s: 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 10),
            ('容器无盖子', lambda s: s.data['container']['subcontainer']['covered'] is not True),
            ('相态要求液体', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] == 'liquid'),
            ('体积范围8-30ml', lambda s: 8 <= s.data['container']['subcontainer']['subcontainer_volume'] <= 30)
        ],
        'description': '荧光光谱分析'
    },
    '磁力搅拌工作站': {
        'constraints': [
            ('容器类型', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]),
            ('子容器编号存在', lambda s: s.data['container']['subcontainer']['subcontainer_number'] is not None),
            ('子容器编号范围', lambda s: 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 10),
            ('相态要求(液体或悬浊液)', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] in ['liquid', 'suspension']),
            ('体积大于0', lambda s: s.data['container']['subcontainer']['subcontainer_volume'] > 0),
            ('体积上限30ml', lambda s: s.data['container']['subcontainer']['subcontainer_volume'] <= 30)
        ],
        'description': '搅拌混合'
    },
    '超声清洗工作站': {
        'constraints': [
            ('容器类型', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]),
            ('相态要求(液体或悬浊液)', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] in ['liquid', 'suspension']),
            ('体积大于0', lambda s: s.data['container']['subcontainer']['subcontainer_volume'] > 0)
        ],
        'description': '超声清洗'
    },
    '离心纯化工作站': {
        'constraints': [
            ('容器类型', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]),
            ('相态要求必须是悬浊液', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] == 'suspension'),
            ('体积大于0', lambda s: s.data['container']['subcontainer']['subcontainer_volume'] > 0)
        ],
        'description': '离心分离'
    },
    '烘干机': {
        'constraints': [
            ('容器类型', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]),
            ('相态要求(固体或悬浊液)', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] in ['solid', 'suspension'])
        ],
        'description': '加热干燥'
    },
    '高通量红外光谱工作站': {
        'constraints': [
            ('容器类型', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]),
            ('相态要求(固体或液体)', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] in ['solid', 'liquid'])
        ],
        'description': '红外光谱分析'
    },
    '高通量XRD工作站': {
        'constraints': [
            ('容器类型', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]),
            ('相态要求必须是固体', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] == 'solid')
        ],
        'description': 'XRD分析'
    },
    '高通量酶标仪工作站': {
        'constraints': [
            ('容器类型', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]),
            ('相态要求必须是液体', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] == 'liquid')
        ],
        'description': '酶标仪分析'
    }
}

def check_constraints(sample, step_name):
    """
    检查工作站的所有约束条件，返回(是否通过, 冲突的约束列表)
    """
    if step_name not in WORKSTATION_CONSTRAINTS:
        return False, [f"未知的工作站: {step_name}"]

    constraints = WORKSTATION_CONSTRAINTS[step_name]['constraints']
    conflicts = []

    # 如果没有约束条件，直接通过
    if not constraints:
        return True, []

    # 逐个检查约束条件
    for constraint_name, constraint_func in constraints:
        try:
            if not constraint_func(sample):
                conflicts.append(constraint_name)
        except Exception as e:
            conflicts.append(f"{constraint_name} (检查时出错: {str(e)})")

    return len(conflicts) == 0, conflicts

def parse_plan_log(log_file_path):
    """
    解析plan log文件，提取工作站步骤
    """
    steps = []
    with open(log_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取每个步骤的方法名
    pattern = r"'method': '([^']+)'"
    matches = re.findall(pattern, content)

    for match in matches:
        steps.append(match)

    return steps

def simulate_step(sample, step_name):
    """
    模拟执行一个工作站步骤
    """
    # 根据不同的工作站调整样品状态
    if step_name == '物料站':
        # 获取50ml离心管
        sample.data['container']['container_name'] = "rack"
        sample.data['container']['subcontainer']['subcontainer_name'] = '50ml_centrifuge_tube'
        sample.data['container']['subcontainer']['subcontainer_number'] = 1
        sample.data['container']['subcontainer']['subcontainer_volume'] = 0
        sample.data['container']['subcontainer']['subcontainer_phase'] = 'solid'  # 初始为空固体

    elif step_name == '1ml液体进样站':
        # 添加1ml液体
        if sample.data['container']['subcontainer']['subcontainer_phase'] == 'solid':
            sample.data['container']['subcontainer']['subcontainer_phase'] = 'suspension'
        sample.data['container']['subcontainer']['subcontainer_volume'] += 1

    elif step_name == '磁力搅拌工作站':
        # 搅拌使混合更均匀
        if sample.data['container']['subcontainer']['subcontainer_phase'] == 'suspension':
            pass  # 保持悬浊液状态

    elif step_name == '超声清洗工作站':
        # 超声处理，仍为悬浊液
        pass

    elif step_name == '离心纯化工作站':
        # 离心后分离，底部有固体沉淀
        pass  # 保持悬浊液状态，实际应该是固液分层

    elif step_name == '烘干机':
        # 烘干后变为固体
        sample.data['temperature'] = 60  # 加热
        sample.data['container']['subcontainer']['subcontainer_phase'] = 'solid'

    elif step_name == '高通量红外光谱工作站':
        # 红外分析，不改变状态
        pass

    elif step_name == '高通量XRD工作站':
        # XRD分析，需要固体样品
        pass

    elif step_name == '高通量酶标仪工作站':
        # 酶标仪分析，需要液体样品
        pass

    return sample

def print_sample_state(step_name, sample, step_num):
    """
    打印当前步骤的样品状态
    """
    print(f"\n=== 步骤 {step_num}: {step_name} ===")
    print(f"容器类型: {sample.data['container']['container_name']}")
    print(f"子容器: {sample.data['container']['subcontainer']['subcontainer_name']}")
    print(f"子容器数量: {sample.data['container']['subcontainer']['subcontainer_number']}")
    print(f"子容器体积: {sample.data['container']['subcontainer']['subcontainer_volume']} ml")
    print(f"相态: {sample.data['container']['subcontainer']['subcontainer_phase']}")
    print(f"是否覆盖: {sample.data['container']['subcontainer']['covered']}")
    print(f"温度: {sample.data['temperature']}°C")

def validate_flow(steps):
    """
    验证整个工作流程的可行性
    """
    print("=== 化学实验流程验证开始 ===")
    print(f"总步骤数: {len(steps)}")

    # 创建初始样品
    sample = Sample()
    print_sample_state("初始状态", sample, 0)

    for i, step_name in enumerate(steps, 1):
        print(f"\n{'='*50}")
        print(f"正在执行步骤 {i}: {step_name}")

        # 获取工作站信息
        if step_name not in WORKSTATION_CONSTRAINTS:
            print(f"❌ 错误: 未知的工作站 '{step_name}'")
            return False

        workstation_info = WORKSTATION_CONSTRAINTS[step_name]
        print(f"工作站描述: {workstation_info['description']}")

        # 检查约束条件
        print(f"检查约束条件...")
        try:
            passed, conflicts = check_constraints(sample, step_name)
            if passed:
                print(f"✅ 所有约束条件通过")

                # 模拟执行工作站能力
                print(f"模拟执行工作站操作...")
                sample = simulate_step(sample, step_name)
                print_sample_state(step_name, sample, i)
                print(f"✅ 步骤 {i} 执行成功")
            else:
                print(f"❌ 步骤 {i} 约束条件不满足")
                print(f"以下约束条件冲突:")
                for conflict in conflicts:
                    print(f"  - {conflict}")
                print_sample_state(f"{step_name} (失败前)", sample, i)
                return False
        except Exception as e:
            print(f"❌ 步骤 {i} 检查约束时出错: {str(e)}")
            return False

    print(f"\n{'='*50}")
    print("✅ 整个流程验证成功！")
    print_sample_state("最终状态", sample, len(steps))
    return True

def main():
    """
    主函数
    """
    # 解析plan_1.log
    log_file = "./plan_logs_withRAG/1/plan_1.log"

    try:
        steps = parse_plan_log(log_file)
        print("从日志文件解析的工作站步骤:")
        for i, step in enumerate(steps, 1):
            print(f"  {i}. {step}")

        # 验证流程
        success = validate_flow(steps)

        if success:
            print("\n🎉 化学实验流程验证完成 - 成功!")
        else:
            print("\n❌ 化学实验流程验证失败!")

    except FileNotFoundError:
        print(f"❌ 错误: 找不到日志文件 {log_file}")
    except Exception as e:
        print(f"❌ 解析日志文件时出错: {str(e)}")

if __name__ == "__main__":
    main()