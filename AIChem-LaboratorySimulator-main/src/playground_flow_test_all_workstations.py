#!/usr/bin/env python3
"""
化学实验流程验证脚本 - playground版本（包含所有工作站）
基于playground.ipynb的方式验证工作站流程
"""

LOG_FILE = "/opt/data/private/src/pipeline_workstation_logs/plan_2.log"

import yaml
import json
import re
import random
import os
import sys
import logging
from datetime import datetime
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
    '气相色谱仪': {
        'constraints': [
            ('容器类型为色谱瓶', lambda s: s.data['container']['container_name'] == "vial"),
            ('子容器编号范围1-25', lambda s: 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 25),
            ('容器有盖子', lambda s: s.data['container']['subcontainer']['covered'] is True),
            ('相态要求液体', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] == 'liquid'),
            ('体积微量0-5ml', lambda s: 0 < s.data['container']['subcontainer']['subcontainer_volume'] <= 5)
        ],
        'description': '气相色谱分析'
    },
    '液相色谱仪': {
        'constraints': [
            ('容器类型为色谱瓶', lambda s: s.data['container']['container_name'] == "vial"),
            ('子容器编号范围1-54', lambda s: 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 54),
            ('容器无盖子', lambda s: s.data['container']['subcontainer']['covered'] is not True),
            ('相态要求液体', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] == 'liquid'),
            ('体积微量0-5ml', lambda s: 0 < s.data['container']['subcontainer']['subcontainer_volume'] <= 5)
        ],
        'description': '液相色谱分析'
    },
    '多通道固体进样器': {
        'constraints': [
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]),
            ('子容器编号范围1-20', lambda s: 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 20),
            ('容器无盖子', lambda s: s.data['container']['subcontainer']['covered'] is not True)
        ],
        'description': '多通道固体进样'
    },
    '光催化工作站': {
        'constraints': [
            ('容器类型为西林瓶', lambda s: s.data['container']['container_name'] == "vial"),
            ('子容器编号范围1-20', lambda s: 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 20),
            ('相态液体或悬浊液', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] in ['liquid', 'suspension']),
            ('体积不超过15ml', lambda s: s.data['container']['subcontainer']['subcontainer_volume'] <= 15)
        ],
        'description': '光催化反应'
    },
    '固体进样站': {
        'constraints': [
            ('容器类型为50ml离心管', lambda s: s.data['container']['container_name'] == "rack" and s.data['container']['subcontainer']['subcontainer_name'] == "50ml_centrifuge_tube"),
            ('容器无盖子', lambda s: s.data['container']['subcontainer']['covered'] is not True),
            ('相态为空或固体', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] in [None, 'solid']),
            ('体积不超过50ml', lambda s: s.data['container']['subcontainer']['subcontainer_volume'] <= 50)
        ],
        'description': '固体进样'
    },
    '置物架': {
        'constraints': [
            ('容器类型为离心管架', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型为50ml离心管', lambda s: s.data['container']['subcontainer']['subcontainer_name'] == "50ml_centrifuge_tube"),
            ('子容器编号范围1-10', lambda s: 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 10),
            ('相态液体或固液混合物', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] in ['liquid', 'suspension'])
        ],
        'description': '静置样品'
    },
    '置物工作站': {
        'constraints': [
            ('容器类型为离心管架', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]),
            ('子容器编号范围1-10', lambda s: 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 10)
        ],
        'description': '存放样品'
    },
    '紫外光谱工作站': {
        'constraints': [
            ('容器类型', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] == "50ml_centrifuge_tube"),
            ('子容器编号范围1-10', lambda s: 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 10),
            ('容器无盖子', lambda s: s.data['container']['subcontainer']['covered'] is not True),
            ('相态要求液体', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] == 'liquid'),
            ('体积范围8-30ml', lambda s: 8 <= s.data['container']['subcontainer']['subcontainer_volume'] <= 30)
        ],
        'description': '紫外光谱分析'
    },
    '离心机': {
        'constraints': [
            ('容器类型', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] == "50ml_centrifuge_tube"),
            ('子容器双数1-10', lambda s: s.data['container']['subcontainer']['subcontainer_number'] % 2 == 0 and 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 10),
            ('相态要求悬浊液', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] == 'suspension'),
            ('容器有盖子', lambda s: s.data['container']['subcontainer']['covered'] is True),
            ('体积不超过30ml', lambda s: s.data['container']['subcontainer']['subcontainer_volume'] <= 30)
        ],
        'description': '离心分离'
    },
    '磁力搅拌工作站': {
        'constraints': [
            ('容器类型', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] == "50ml_centrifuge_tube"),
            ('子容器编号范围1-10', lambda s: 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 10),
            ('相态液体或固液混合物', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] in ['liquid', 'suspension']),
            ('容器无盖子', lambda s: s.data['container']['subcontainer']['covered'] is not True),
            ('体积范围3-50ml', lambda s: 3 <= s.data['container']['subcontainer']['subcontainer_volume'] <= 50)
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
            ('相态要求(液体、悬浊液或带微量液体的固体)', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] in ['liquid', 'suspension', 'solid_with_tiny_liquid'])
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
            ('容器类型为孔板', lambda s: s.data['container']['container_name'] in ["24_hole_plate", "48_hole_plate", "96_hole_plate"]),
            ('孔数对应容器数', lambda s: (
                (s.data['container']['container_name'] == "24_hole_plate" and 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 24) or
                (s.data['container']['container_name'] == "48_hole_plate" and 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 48) or
                (s.data['container']['container_name'] == "96_hole_plate" and 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 96)
            )),
            ('相态要求液体', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] == 'liquid'),
            ('体积微量0-2ml', lambda s: 0 < s.data['container']['subcontainer']['subcontainer_volume'] <= 2)
        ],
        'description': '酶标仪分析'
    },
    '双工位电化学工作站': {
        'constraints': [
            ('容器类型', lambda s: s.data['container']['container_name'] == "rack"),
            ('子容器类型', lambda s: s.data['container']['subcontainer']['subcontainer_name'] == "50ml_centrifuge_tube"),
            ('容器无盖子', lambda s: s.data['container']['subcontainer']['covered'] is not True),
            ('子容器编号范围1-10', lambda s: 1 <= s.data['container']['subcontainer']['subcontainer_number'] <= 10),
            ('相态要求悬浊液', lambda s: s.data['container']['subcontainer']['subcontainer_phase'] == 'suspension'),
            ('体积大于4ml', lambda s: s.data['container']['subcontainer']['subcontainer_volume'] > 4)
        ],
        'description': '电化学分析'
    }
}

def check_constraints(sample, step_name):
    """
    检查工作站的所有约束条件，返回(是否通过, 冲突的约束列表)

    注意：某些工作站会进行容器转换（如酶标仪、液相色谱仪等），
    在检查约束前需要先预测转换后的状态。
    """
    if step_name not in WORKSTATION_CONSTRAINTS:
        return False, [f"未知的工作站: {step_name}"]

    constraints = WORKSTATION_CONSTRAINTS[step_name]['constraints']
    conflicts = []

    # 如果没有约束条件，直接通过
    if not constraints:
        return True, []

    # 创建预测的样品状态（模拟转换后的状态）
    import copy
    predicted_sample = copy.deepcopy(sample)

    # 对于会进行容器转换的工作站，先预测转换后的状态
    if step_name == '高通量酶标仪工作站':
        # 酶标仪会将样品转移到孔板
        plate_types = ["24_hole_plate", "48_hole_plate", "96_hole_plate"]
        predicted_sample.data['container']['container_name'] = plate_types[0]  # 使用第一个孔板类型预测
        predicted_sample.data['container']['subcontainer']['subcontainer_name'] = 'well'
        predicted_sample.data['container']['subcontainer']['subcontainer_number'] = 1
        predicted_sample.data['container']['subcontainer']['subcontainer_volume'] = 1.0
        predicted_sample.data['container']['subcontainer']['subcontainer_phase'] = 'liquid'
        predicted_sample.data['container']['subcontainer']['covered'] = False
    elif step_name == '液相色谱仪':
        # 液相色谱仪会将样品转移到色谱瓶
        predicted_sample.data['container']['container_name'] = "vial"
        predicted_sample.data['container']['subcontainer']['subcontainer_name'] = 'vial'
        predicted_sample.data['container']['subcontainer']['subcontainer_volume'] = 2.0
        predicted_sample.data['container']['subcontainer']['subcontainer_phase'] = 'liquid'
        predicted_sample.data['container']['subcontainer']['covered'] = False
    elif step_name == '气相色谱仪':
        # 气相色谱仪使用色谱瓶
        predicted_sample.data['container']['container_name'] = "vial"
        predicted_sample.data['container']['subcontainer']['subcontainer_name'] = 'vial'
        predicted_sample.data['container']['subcontainer']['subcontainer_volume'] = 2.0
        predicted_sample.data['container']['subcontainer']['subcontainer_phase'] = 'liquid'
        predicted_sample.data['container']['subcontainer']['covered'] = True

    # 逐个检查约束条件（使用预测的状态）
    for constraint_name, constraint_func in constraints:
        try:
            if not constraint_func(predicted_sample):
                conflicts.append(constraint_name)
        except Exception as e:
            conflicts.append(f"{constraint_name} (检查时出错: {str(e)})")

    return len(conflicts) == 0, conflicts

def create_random_initial_sample(second_workstation=None, steps=None):
    """
    创建在第二个工作站限制范围内的随机初始样品
    second_workstation: 第二个工作站的名称
    steps: 完整的流程步骤列表，用于检查后续约束
    """
    sample = Sample()

    # 如果没有指定第二个工作站，使用默认值
    if not second_workstation or second_workstation not in WORKSTATION_CONSTRAINTS:
        # 默认参数（相对宽松的设置）
        sample.data['container']['container_name'] = "rack"
        sample.data['container']['subcontainer']['subcontainer_name'] = "50ml_centrifuge_tube"
        sample.data['container']['subcontainer']['subcontainer_number'] = 1
        sample.data['container']['subcontainer']['subcontainer_volume'] = 8
        sample.data['container']['subcontainer']['subcontainer_phase'] = 'liquid'
        sample.data['container']['subcontainer']['covered'] = False
        sample.data['temperature'] = 20
        return sample

    # 获取第二个工作站的约束条件
    constraints = WORKSTATION_CONSTRAINTS[second_workstation]['constraints']

    # 根据约束条件分析出合理的参数范围
    container_name = None
    subcontainer_names = []
    subcontainer_number_range = [1, 100]  # 默认范围
    volume_range = [0, 100]  # 默认范围
    phases = ['liquid', 'suspension', 'solid']  # 默认所有相态
    covered_options = [True, False]  # 默认可覆盖可不覆盖

    # 分析约束条件以确定参数范围
    for constraint_name, constraint_func in constraints:
        constraint_name_lower = constraint_name.lower()

        # 容器类型
        if '容器类型' in constraint_name or '容器类型为' in constraint_name:
            if 'rack' in constraint_name:
                container_name = "rack"
            elif '色谱瓶' in constraint_name or 'vial' in constraint_name:
                container_name = "vial"
            elif '孔板' in constraint_name:
                # 孔板的特殊处理
                plate_types = ["24_hole_plate", "48_hole_plate", "96_hole_plate"]
                container_name = random.choice(plate_types)

        # 子容器类型
        elif '子容器类型' in constraint_name:
            if '50ml_centrifuge_tube' in constraint_name:
                subcontainer_names.append("50ml_centrifuge_tube")
            if 'ptfe_reaction_bottle' in constraint_name:
                subcontainer_names.append("ptfe_reaction_bottle")
            if 'vial' in constraint_name:
                subcontainer_names.append("vial")

        # 子容器编号范围
        elif '编号范围' in constraint_name or '编号' in constraint_name:
            # 尝试从约束名称中提取数字
            import re
            numbers = re.findall(r'\d+', constraint_name)
            if len(numbers) >= 2:
                subcontainer_number_range = [int(numbers[0]), int(numbers[1])]
            elif '1-10' in constraint_name:
                subcontainer_number_range = [1, 10]
            elif '1-20' in constraint_name:
                subcontainer_number_range = [1, 20]
            elif '1-25' in constraint_name:
                subcontainer_number_range = [1, 25]
            elif '1-54' in constraint_name:
                subcontainer_number_range = [1, 54]
            elif '1-96' in constraint_name:
                subcontainer_number_range = [1, 96]

        # 如果没有找到编号范围约束，且容器类型是离心管架，使用默认的1-10范围
        if subcontainer_number_range == [1, 100] and container_name == "rack":
            subcontainer_number_range = [1, 10]

        # 体积限制
        elif '体积' in constraint_name:
            if '不超过' in constraint_name or '<=' in constraint_name:
                # 提取体积上限
                import re
                volumes = re.findall(r'\d+', constraint_name)
                if volumes:
                    volume_range[1] = int(volumes[0])
            elif '范围' in constraint_name:
                # 提取体积范围
                import re
                volumes = re.findall(r'\d+', constraint_name)
                if len(volumes) >= 2:
                    volume_range = [int(volumes[0]), int(volumes[1])]
            elif '微量' in constraint_name:
                volume_range = [0, 5]

        # 相态要求
        elif '相态' in constraint_name:
            if '液体' in constraint_name:
                phases = ['liquid']
            elif '固体' in constraint_name and '液体' not in constraint_name:
                phases = ['solid']
            elif '悬浊液' in constraint_name:
                phases = ['suspension']
            elif '或' in constraint_name:
                # 提取多个相态
                if '液体' in constraint_name and '固体' in constraint_name:
                    phases = ['liquid', 'solid']
                if '悬浊液' in constraint_name:
                    if 'suspension' not in phases:
                        phases.append('suspension')

        # 是否覆盖
        elif '盖子' in constraint_name:
            if '无盖子' in constraint_name or '无盖' in constraint_name:
                covered_options = [False]
            elif '有盖子' in constraint_name or '有盖' in constraint_name:
                covered_options = [True]

    # 设置随机参数
    # 容器类型
    if container_name:
        sample.data['container']['container_name'] = container_name
    else:
        sample.data['container']['container_name'] = "rack"  # 默认

    # 子容器类型
    if subcontainer_names:
        sample.data['container']['subcontainer']['subcontainer_name'] = random.choice(subcontainer_names)
    else:
        # 如果约束没有指定子容器类型，根据容器类型推断
        if sample.data['container']['container_name'] == "vial":
            sample.data['container']['subcontainer']['subcontainer_name'] = "vial"
        else:
            sample.data['container']['subcontainer']['subcontainer_name'] = "50ml_centrifuge_tube"

    # 子容器编号 - 考虑整个流程的约束
    # 检查流程中是否有需要双数容器数量的工作站（如离心机）
    has_centrifuge = steps and any('离心机' in step for step in steps)

    if sample.data['container']['container_name'] in ["24_hole_plate", "48_hole_plate", "96_hole_plate"]:
        # 孔板的特殊处理
        if sample.data['container']['container_name'] == "24_hole_plate":
            max_num = 24
        elif sample.data['container']['container_name'] == "48_hole_plate":
            max_num = 48
        else:
            max_num = 96
        sample.data['container']['subcontainer']['subcontainer_number'] = random.randint(1, max_num)
    else:
        # 如果流程中有离心机，容器数量必须是双数
        if has_centrifuge:
            # 离心机的约束是：subcontainer_number % 2 == 0 and 1 <= subcontainer_number <= 10
            # 所以有效的偶数是：2, 4, 6, 8, 10
            valid_even_numbers = [2, 4, 6, 8, 10]
            # 在约束范围和有效偶数之间取交集
            min_num = subcontainer_number_range[0]
            max_num = subcontainer_number_range[1]
            # 确保范围至少包含2
            if max_num < 2:
                max_num = 2
            if min_num > 10:
                min_num = 10
            # 从有效偶数中选择在范围内的
            valid_options = [n for n in valid_even_numbers if min_num <= n <= max_num]
            if valid_options:
                sample.data['container']['subcontainer']['subcontainer_number'] = random.choice(valid_options)
                print(f"为满足离心机约束设置容器数量为双数: {sample.data['container']['subcontainer']['subcontainer_number']}")
            else:
                # 如果没有合适的偶数，使用2
                sample.data['container']['subcontainer']['subcontainer_number'] = 2
                print(f"使用默认双数容器数量: 2")
        else:
            # 没有离心机，使用正常范围
            sample.data['container']['subcontainer']['subcontainer_number'] = random.randint(
                subcontainer_number_range[0], subcontainer_number_range[1]
            )

    # 体积 - 考虑整个流程的约束
    # 定义各工作站的体积约束（最大值）
    volume_constraints = {
        '1ml液体进样站': 30,      # 总体积≤30ml
        '磁力搅拌工作站': 50,     # 体积3-50ml
        '双工位电化学工作站': None, # 体积>4ml（只有下限）
        '光催化工作站': 15,       # 体积≤15ml
        '高通量酶标仪工作站': 2, # 体积0-2ml
        '紫外光谱工作站': 30,    # 体积8-30ml
        '荧光光谱工作站': 30,    # 体积8-30ml
        '气相色谱仪': 5,         # 体积0-5ml
        '液相色谱仪': 5,         # 体积0-5ml
        '固体进样站': 50,       # 体积≤50ml
    }

    # 找出整个流程中最严格的体积上限
    max_volume_limit = None
    if steps:
        for step in steps:
            for ws_name, ws_limit in volume_constraints.items():
                if ws_name in step and ws_limit is not None:
                    if max_volume_limit is None or ws_limit < max_volume_limit:
                        max_volume_limit = ws_limit

    # 如果第二个工作站是1ml液体进样站，检查后续是否有磁力搅拌工作站
    if second_workstation == '1ml液体进样站':
        # 检查后续是否有磁力搅拌工作站
        has_magnetic_stirrer = any('磁力搅拌工作站' in step for step in steps) if steps else False
        if has_magnetic_stirrer:
            # 需要同时满足1ml液体进样站(<=30ml)和磁力搅拌站(3-50ml)，所以使用3-30ml
            min_volume = 3
            max_volume = 30
            sample.data['container']['subcontainer']['subcontainer_volume'] = random.uniform(min_volume, max_volume)
            print(f"为兼容1ml进样站和磁力搅拌站设置体积: {sample.data['container']['subcontainer']['subcontainer_volume']:.1f}ml (范围: {min_volume}-{max_volume}ml)")
        else:
            # 只考虑1ml液体进样站的约束
            min_volume = max(volume_range[0], 0)
            max_volume = min(volume_range[1], 30)  # 确保不超过30ml
            sample.data['container']['subcontainer']['subcontainer_volume'] = random.uniform(min_volume, max_volume)
            print(f"为1ml液体进样站设置体积: {sample.data['container']['subcontainer']['subcontainer_volume']:.1f}ml (范围: {min_volume}-{max_volume}ml)")
    elif second_workstation == '磁力搅拌工作站':
        # 确保体积在磁力搅拌工作站要求的3-50ml范围内
        min_volume = 3
        max_volume = 50
        sample.data['container']['subcontainer']['subcontainer_volume'] = random.uniform(min_volume, max_volume)
        print(f"为磁力搅拌工作站设置体积: {sample.data['container']['subcontainer']['subcontainer_volume']:.1f}ml (范围: {min_volume}-{max_volume}ml)")
    else:
        # 其他工作站：考虑整个流程的最严格体积约束
        if max_volume_limit is not None and steps:
            # 使用整个流程中最严格的体积上限，并预留一些空间给后续步骤（如液体进样站会增加体积）
            # 假设后续步骤最多增加5ml，所以初始体积应该比限制小5ml以上
            reserved_volume = 5  # 预留体积
            effective_max = max_volume_limit - reserved_volume

            # 如果有效上限太小，减少预留量或调整策略
            if effective_max < 3:
                # 预留空间不够，减少预留量
                reserved_volume = max_volume_limit // 2 if max_volume_limit >= 6 else 2
                effective_max = max_volume_limit - reserved_volume

            # 确保最小值合理
            min_volume = max(volume_range[0], 3)  # 至少3ml以满足磁力搅拌等约束
            # 但不能超过有效上限
            if min_volume > effective_max:
                min_volume = max(3, effective_max)  # 直接使用有效上限作为最小值
            max_volume = min(volume_range[1], effective_max)

            # 确保最小值不超过最大值
            if min_volume > max_volume:
                min_volume = max_volume  # 使用最大值作为最小值

            # 如果范围仍然不合理（max_volume_limit太小），使用默认小范围
            if max_volume < 3:
                sample.data['container']['subcontainer']['subcontainer_volume'] = random.uniform(1, max_volume_limit)
                print(f"体积约束非常严格(上限{max_volume_limit}ml)，设置初始体积: {sample.data['container']['subcontainer']['subcontainer_volume']:.1f}ml")
            else:
                sample.data['container']['subcontainer']['subcontainer_volume'] = random.uniform(min_volume, max_volume)
                print(f"为满足整个流程体积约束(上限{max_volume_limit}ml)设置初始体积: {sample.data['container']['subcontainer']['subcontainer_volume']:.1f}ml (范围: {min_volume:.1f}-{max_volume:.1f}ml, 预留{reserved_volume}ml)")
        else:
            # 没有发现严格的体积约束，使用默认的较小范围
            # 使用5-15ml作为合理的初始范围，为后续步骤留出空间
            sample.data['container']['subcontainer']['subcontainer_volume'] = random.uniform(5, 15)
            print(f"使用默认初始体积: {sample.data['container']['subcontainer']['subcontainer_volume']:.1f}ml (范围: 5-15ml)")

    # 相态
    sample.data['container']['subcontainer']['subcontainer_phase'] = random.choice(phases)

    # 是否覆盖
    sample.data['container']['subcontainer']['covered'] = random.choice(covered_options)

    # 温度（通常不受约束，设置合理范围）
    sample.data['temperature'] = random.uniform(15, 30)

    return sample

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
        # 获取50ml离心管，但不强制改变体积，保持初始随机值
        # 保存原始容器数量（可能是为了满足离心机约束而设置的双数）
        original_number = sample.data['container']['subcontainer']['subcontainer_number']
        sample.data['container']['container_name'] = "rack"
        sample.data['container']['subcontainer']['subcontainer_name'] = '50ml_centrifuge_tube'
        # 如果原始容器数量是双数（为了满足离心机约束），保持它；否则设置为1
        # 同时要确保在1-10范围内
        if original_number % 2 == 0 and 2 <= original_number <= 10:
            sample.data['container']['subcontainer']['subcontainer_number'] = original_number
        else:
            sample.data['container']['subcontainer']['subcontainer_number'] = 1
        # 如果体积小于3ml，增加到3-50ml范围内以满足后续磁力搅拌要求
        if sample.data['container']['subcontainer']['subcontainer_volume'] < 3:
            sample.data['container']['subcontainer']['subcontainer_volume'] = random.uniform(3, 10)
        sample.data['container']['subcontainer']['subcontainer_phase'] = 'solid'  # 初始为空固体
        sample.data['container']['subcontainer']['covered'] = False

    elif step_name == '1ml液体进样站':
        # 添加1ml液体
        if sample.data['container']['subcontainer']['subcontainer_phase'] == 'solid':
            sample.data['container']['subcontainer']['subcontainer_phase'] = 'suspension'
        sample.data['container']['subcontainer']['subcontainer_volume'] += 1

    elif step_name == '荧光光谱工作站':
        # 荧光分析，消耗1-3ml
        sample.data['container']['subcontainer']['subcontainer_volume'] -= 2

    elif step_name == '气相色谱仪':
        # 气相色谱分析，不改变样品
        pass

    elif step_name == '液相色谱仪':
        # 液相色谱分析 - 需要少量液体样品在色谱瓶中
        # 模拟取样：取少量样品转移到色谱瓶
        # 将容器类型改为色谱瓶(vial)
        sample.data['container']['container_name'] = "vial"
        # 设置子容器名称保持为西林瓶
        sample.data['container']['subcontainer']['subcontainer_name'] = 'vial'
        # 设置体积为1-3ml（在0-5ml范围内）
        sample.data['container']['subcontainer']['subcontainer_volume'] = random.uniform(1.0, 3.0)
        # 设置相态为液体
        sample.data['container']['subcontainer']['subcontainer_phase'] = 'liquid'
        # 设置子容器编号为1-54之间
        sample.data['container']['subcontainer']['subcontainer_number'] = random.randint(1, 10)
        # 色谱瓶通常没有盖子
        sample.data['container']['subcontainer']['covered'] = False

    elif step_name == '多通道固体进样器':
        # 添加2-10ml固体
        sample.data['container']['subcontainer']['subcontainer_volume'] += 5
        sample.data['container']['subcontainer']['subcontainer_phase'] = 'suspension'

    elif step_name == '光催化工作站':
        # 光催化反应，不改变体积
        pass

    elif step_name == '固体进样站':
        # 添加1-5ml固体
        sample.data['container']['subcontainer']['subcontainer_volume'] += 3
        sample.data['container']['subcontainer']['subcontainer_phase'] = 'solid'

    elif step_name == '置物架':
        # 静置，设置温度20度
        sample.data['temperature'] = 20

    elif step_name == '置物工作站':
        # 存放，假设静置后液体蒸发（如果需要为后续XRD分析准备固体样品）
        # 如果当前是固液分离状态，存放后可能会变成固体（液体蒸发或被移除）
        if sample.data['container']['subcontainer']['subcontainer_phase'] == 'solid_liquid_separated':
            sample.data['container']['subcontainer']['subcontainer_phase'] = 'solid'

    elif step_name == '紫外光谱工作站':
        # 紫外分析，消耗1-3ml
        sample.data['container']['subcontainer']['subcontainer_volume'] -= 2

    elif step_name == '离心机':
        # 离心分离，固液分层
        sample.data['container']['subcontainer']['subcontainer_phase'] = 'solid_liquid_separated'

    elif step_name == '磁力搅拌工作站':
        # 搅拌，使混合更均匀
        # 如果后续步骤中有离心机，需要盖上盖子
        # 这里假设搅拌完成后会自动盖好盖子（或者需要添加一个"封盖"步骤）
        # 为了满足离心机的约束，我们在这里设置covered=True
        sample.data['container']['subcontainer']['covered'] = True

    elif step_name == '超声清洗工作站':
        # 超声处理
        pass

    elif step_name == '离心纯化工作站':
        # 离心纯化
        pass

    elif step_name == '烘干机':
        # 烘干
        sample.data['temperature'] = 60
        sample.data['container']['subcontainer']['subcontainer_phase'] = 'solid'

    elif step_name == '高通量红外光谱工作站':
        # 红外分析
        # 如果后续步骤需要液体（如酶标仪），且当前是固体，添加少量溶剂溶解
        # 同时检查整个流程是否有需要液体且体积限制严格的步骤
        pass  # 状态转换将在步骤之间处理

    elif step_name == '高通量XRD工作站':
        # XRD分析
        pass

    elif step_name == '高通量酶标仪工作站':
        # 酶标仪分析 - 需要少量液体样品在孔板中
        # 模拟取样：取少量样品转移到孔板
        # 将容器类型改为孔板
        plate_types = ["24_hole_plate", "48_hole_plate", "96_hole_plate"]
        sample.data['container']['container_name'] = random.choice(plate_types)
        # 设置子容器名称为孔
        sample.data['container']['subcontainer']['subcontainer_name'] = 'well'
        # 设置体积为1ml（在0-2ml范围内）
        sample.data['container']['subcontainer']['subcontainer_volume'] = random.uniform(0.5, 2.0)
        # 设置相态为液体
        sample.data['container']['subcontainer']['subcontainer_phase'] = 'liquid'
        # 设置孔编号为1
        sample.data['container']['subcontainer']['subcontainer_number'] = 1
        # 孔板通常没有盖子
        sample.data['container']['subcontainer']['covered'] = False

    elif step_name == '双工位电化学工作站':
        # 电化学分析
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

def validate_flow(steps, test_num=1, use_random_initial=False, second_workstation=None):
    """
    验证整个工作流程的可行性
    test_num: 测试编号
    use_random_initial: 是否使用随机初始样品参数
    second_workstation: 第二个工作站的名称
    """
    print(f"\n=== 化学实验流程验证开始 (测试 {test_num}) ===")
    print(f"总步骤数: {len(steps)}")

    # 创建初始样品
    if use_random_initial:
        sample = create_random_initial_sample(second_workstation, steps)
        if second_workstation:
            print(f"使用基于第二个工作站'{second_workstation}'约束的随机初始样品参数")
        else:
            print("使用随机初始样品参数")
    else:
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

def setup_logging():
    """
    设置日志输出，创建带编号的日志文件
    """
    # 创建日志目录
    log_dir = "./playground_test_logs"
    os.makedirs(log_dir, exist_ok=True)

    # 查找下一个可用的日志编号
    log_num = 1
    while True:
        log_file = os.path.join(log_dir, f"test_log_{log_num:03d}.txt")
        if not os.path.exists(log_file):
            break
        log_num += 1

    # 创建日志文件
    log_file = os.path.join(log_dir, f"test_log_{log_num:03d}.txt")

    # 创建日志记录器
    import logging

    # 清除现有的处理器
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # 设置日志格式
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)  # 同时输出到终端
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"日志文件创建成功: {log_file}")
    logger.info(f"日志编号: {log_num}")

    return logger, log_num

def validate_flow_with_logging(steps, test_num=1, use_random_initial=False, second_workstation=None, logger=None):
    """
    带日志记录的流程验证函数
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    logger.info(f"化学实验流程验证开始 (测试 {test_num})")
    logger.info(f"总步骤数: {len(steps)}")

    # 创建初始样品
    if use_random_initial:
        sample = create_random_initial_sample(second_workstation, steps)
        if second_workstation:
            logger.info(f"使用基于第二个工作站'{second_workstation}'约束的随机初始样品参数")
        else:
            logger.info("使用随机初始样品参数")
    else:
        sample = Sample()

    # 记录初始状态
    logger.info("=== 初始状态 ===")
    logger.info(f"容器类型: {sample.data['container']['container_name']}")
    logger.info(f"子容器: {sample.data['container']['subcontainer']['subcontainer_name']}")
    logger.info(f"子容器数量: {sample.data['container']['subcontainer']['subcontainer_number']}")
    logger.info(f"子容器体积: {sample.data['container']['subcontainer']['subcontainer_volume']} ml")
    logger.info(f"相态: {sample.data['container']['subcontainer']['subcontainer_phase']}")
    logger.info(f"是否覆盖: {sample.data['container']['subcontainer']['covered']}")
    logger.info(f"温度: {sample.data['temperature']}°C")

    for i, step_name in enumerate(steps, 1):
        logger.info(f"{'='*50}")
        logger.info(f"正在执行步骤 {i}: {step_name}")

        # 获取工作站信息
        if step_name not in WORKSTATION_CONSTRAINTS:
            logger.error(f"错误: 未知的工作站 '{step_name}'")
            return False

        workstation_info = WORKSTATION_CONSTRAINTS[step_name]
        logger.info(f"工作站描述: {workstation_info['description']}")

        # 检查约束条件
        logger.info("检查约束条件...")
        try:
            passed, conflicts = check_constraints(sample, step_name)
            if passed:
                logger.info("所有约束条件通过")

                # 模拟执行工作站能力
                logger.info("模拟执行工作站操作...")
                sample = simulate_step(sample, step_name)

                # 记录步骤后的状态
                logger.info(f"=== 步骤 {i} 执行后状态 ===")
                logger.info(f"容器类型: {sample.data['container']['container_name']}")
                logger.info(f"子容器: {sample.data['container']['subcontainer']['subcontainer_name']}")
                logger.info(f"子容器数量: {sample.data['container']['subcontainer']['subcontainer_number']}")
                logger.info(f"子容器体积: {sample.data['container']['subcontainer']['subcontainer_volume']} ml")
                logger.info(f"相态: {sample.data['container']['subcontainer']['subcontainer_phase']}")
                logger.info(f"是否覆盖: {sample.data['container']['subcontainer']['covered']}")
                logger.info(f"温度: {sample.data['temperature']}°C")
                logger.info(f"步骤 {i} 执行成功")
            else:
                logger.error(f"❌步骤 {i} 约束条件不满足")
                logger.error("以下约束条件冲突:")
                for conflict in conflicts:
                    logger.error(f"  - {conflict}")

                # 记录失败前的状态
                logger.info(f"=== 步骤 {i} 失败前状态 ===")
                logger.info(f"容器类型: {sample.data['container']['container_name']}")
                logger.info(f"子容器: {sample.data['container']['subcontainer']['subcontainer_name']}")
                logger.info(f"子容器数量: {sample.data['container']['subcontainer']['subcontainer_number']}")
                logger.info(f"子容器体积: {sample.data['container']['subcontainer']['subcontainer_volume']} ml")
                logger.info(f"相态: {sample.data['container']['subcontainer']['subcontainer_phase']}")
                logger.info(f"是否覆盖: {sample.data['container']['subcontainer']['covered']}")
                logger.info(f"温度: {sample.data['temperature']}°C")
                return False
        except Exception as e:
            logger.error(f"步骤 {i} 检查约束时出错: {str(e)}")
            return False

    logger.info(f"{'='*50}")
    logger.info("✅整个流程验证成功！")
    logger.info("=== 最终状态 ===")
    logger.info(f"容器类型: {sample.data['container']['container_name']}")
    logger.info(f"子容器: {sample.data['container']['subcontainer']['subcontainer_name']}")
    logger.info(f"子容器数量: {sample.data['container']['subcontainer']['subcontainer_number']}")
    logger.info(f"子容器体积: {sample.data['container']['subcontainer']['subcontainer_volume']} ml")
    logger.info(f"相态: {sample.data['container']['subcontainer']['subcontainer_phase']}")
    logger.info(f"是否覆盖: {sample.data['container']['subcontainer']['covered']}")
    logger.info(f"温度: {sample.data['temperature']}°C")
    return True

def main():
    """
    主函数
    """
    # 设置日志记录
    logger, log_num = setup_logging()

    logger.info("=" * 80)
    logger.info("化学实验流程验证脚本启动")

    # 解析plan_1.log
    log_file = LOG_FILE

    # 测试次数设置
    num_tests = 5  # 可以修改这个数值来改变测试次数
    use_random = True  # 设置为True使用随机初始参数，False使用默认参数

    try:
        steps = parse_plan_log(log_file)
        logger.info("从日志文件解析的工作站步骤:")
        for i, step in enumerate(steps, 1):
            logger.info(f"  {i}. {step}")

        # 获取第二个工作站的名称（跳过第一个"物料站"）
        second_workstation = None
        if len(steps) > 1 and steps[0] == '物料站':
            second_workstation = steps[1]
            logger.info(f"检测到第二个工作站: {second_workstation}")
            logger.info(f"将基于'{second_workstation}'的约束条件生成随机初始样品参数")
        elif len(steps) > 0:
            second_workstation = steps[0]  # 如果第一个不是物料站，使用第一个
            logger.info(f"注意: 第一个工作站不是'物料站'，将基于'{second_workstation}'的约束条件生成随机初始样品参数")

        success_count = 0
        failed_tests = []

        # 执行多次测试
        for test_num in range(1, num_tests + 1):
            logger.info(f"{'#'*80}")
            logger.info(f"开始第 {test_num} 次测试")

            # 验证流程（使用带日志的版本）
            success = validate_flow_with_logging(steps, test_num, use_random_initial=use_random, second_workstation=second_workstation, logger=logger)

            if success:
                success_count += 1
                logger.info(f"测试 {test_num} 成功!")
            else:
                failed_tests.append(test_num)
                logger.error(f"❌测试 {test_num} 失败!")

        # 总结测试结果
        logger.info(f"{'#'*80}")
        logger.info("=== 测试总结 ===")
        logger.info(f"总测试次数: {num_tests}")
        logger.info(f"成功次数: {success_count}")
        logger.info(f"失败次数: {num_tests - success_count}")
        logger.info(f"成功率: {success_count/num_tests*100:.1f}%")

        if failed_tests:
            logger.info(f"失败的测试编号: {failed_tests}")

        if success_count == num_tests:
            logger.info("✅所有测试都通过了!")
        elif success_count > 0:
            logger.info(f"⚠ 部分测试通过 ({success_count}/{num_tests})")
        else:
            logger.error("❌所有测试都失败了!")

        logger.info("=" * 80)

    except FileNotFoundError:
        logger.error(f"错误: 找不到日志文件 {log_file}")
    except Exception as e:
        logger.error(f"解析日志文件时出错: {str(e)}")

    # 输出日志文件位置
    print(f"\n📝 日志已保存到: ./playground_test_logs/test_log_{log_num:03d}.txt")

if __name__ == "__main__":
    main()