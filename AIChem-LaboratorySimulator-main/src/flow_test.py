#!/usr/bin/env python3
"""
化学实验流程验证脚本
用于验证从plan_logs中读取的工作站顺序是否可行
"""

import yaml
import json
import re
from sample import Sample

# 导入工作站模块
from workstation_instances.material_station import material_station_get_tube
from workstation_instances.oneml_liquid_sampling_station import liquid_sampling_station
from workstation_instances.magnetic_stirring_workstation import magnetic_stirring_workstation
from workstation_instances.ultrasonic_cleaning_workstation import ultrasonic_cleaning_workstation
from workstation_instances.centrifugal_purification_workstation import centrifugal_purification_without_wash_liquid
from workstation_instances.drying_station import drying_station
from workstation_instances.high_throughput_ftir_workstation import high_throughput_ftir_workstation
from workstation_instances.high_throughput_xrd_workstation import high_throughput_xrd_workstation

# 工作站名称映射
WORKSTATION_MAP = {
    '物料站': material_station_get_tube,
    '1ml液体进样站': liquid_sampling_station,
    '磁力搅拌工作站': magnetic_stirring_workstation,
    '超声清洗工作站': ultrasonic_cleaning_workstation,
    '离心纯化工作站': centrifugal_purification_without_wash_liquid,
    '烘干机': drying_station,
    '高通量红外光谱工作站': high_throughput_ftir_workstation,
    '高通量XRD工作站': high_throughput_xrd_workstation,
}

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
    sample.data['container']['container_name'] = "rack"
    sample.data['container']['subcontainer']['subcontainer_name'] = "50ml_centrifuge_tube"
    sample.data['container']['subcontainer']['subcontainer_number'] = 1
    sample.data['container']['subcontainer']['subcontainer_volume'] = 10
    sample.data['container']['subcontainer']['subcontainer_phase'] = 'liquid'
    sample.data['container']['subcontainer']['covered'] = False
    sample.data['temperature'] = 20
    
    print_sample_state("初始状态", sample, 0)

    for i, step_name in enumerate(steps, 1):
        print(f"\n{'='*50}")
        print(f"正在执行步骤 {i}: {step_name}")

        # 获取对应的工作站
        if step_name not in WORKSTATION_MAP:
            print(f"❌ 错误: 未知的工作站 '{step_name}'")
            return False

        workstation = WORKSTATION_MAP[step_name]

        # 检查约束条件
        print(f"检查约束条件...")
        if workstation.check_constraints(sample):
            print(f"✅ 约束条件通过")

            # 执行工作站能力
            print(f"执行工作站操作...")
            try:
                sample = workstation(sample)
                print_sample_state(step_name, sample, i)
                print(f"✅ 步骤 {i} 执行成功")
            except Exception as e:
                print(f"❌ 步骤 {i} 执行失败: {str(e)}")
                return False
        else:
            print(f"❌ 步骤 {i} 约束条件不满足")
            print_sample_state(f"{step_name} (失败前)", sample, i)
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