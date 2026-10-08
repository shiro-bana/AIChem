#!/usr/bin/env python3
"""
自动化脚本：为所有服务器工具文件添加 constraints 集成

这个脚本会自动修改服务器工具文件，添加 constraints 验证逻辑。
"""

import os
import re
import sys

# 定义服务器工具文件与服务器名称的映射
SERVER_TOOL_MAPPINGS = {
    'magnetic_stirring_server_tools_v2.py': 'magnetic_stirring_server_tools',
    'electrochemical_workstation_dual_server_tools_v2.py': 'electrochemical_workstation_dual_server_tools',
    'ultrasonic_cleaning_server_tools_v2.py': 'ultrasonic_cleaning_server_tools',
    'dryer_server_tools_v2.py': 'dryer_server_tools',
    'new_centrifugation_server_tools_v2.py': 'new_centrifugation_server_tools',
    'ustc_photocatalysis_server_tools_v2.py': 'ustc_photocatalysis_server_tools',
    'microplate_reader_server_tools_v2.py': 'high_throughput_microplate_reader_server_tools',
    'high_flux_ir_workstation_server_tools_v2.py': 'high_throughput_ftir_workstation',
    'high_flux_xrd_workstation_server_tools_v2.py': 'high_throughput_xrd_workstation',
    # 新增遗漏的服务器工具
    'solid_dispensing_server_tools_v2.py': 'solid_dispensing_server_tools',
    'ustc_mul_solid_server_tools_v2.py': 'ustc_mul_solid_server_tools',
    'starting_station_server_tools_v2.py': 'starting_station_server_tools',
    'pure_server_tools_v2.py': 'pure_server_tools',
    'liquid_handling_workstation_server_tools_v2.py': 'liquid_handling_workstation_server_tools',
    'liquid_dispensing_server_tools_v2.py': 'liquid_dispensing_server_tools',
    'toLC_server_tools_v2.py': 'toLC_server_tools',
    'transfer_workstation_server_tools_v2.py': 'transfer_workstation_server_tools',
}

# 需要添加的导入语句
IMPORT_STATEMENT = '''import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constraints_mapping import validate_sample_constraints

'''

# constraints 验证代码模板
CONSTRAINTS_TEMPLATE = '''        # 添加constraints验证
        if 'sample' in params:
            server_name = '{server_name}'
            if not validate_sample_constraints(server_name, params['sample']):
                result = {{
                    "workstation": "{workstation_name}",
                    "task": task_description,
                    "status": "failed",
                    "message": "样品不满足{workstation_name}的约束条件，无法执行操作",
                    "error": "constraints_validation_failed"
                }}
                return result

'''

def get_workstation_name_from_filename(filename):
    """从文件名推断工作站名称"""
    name_mapping = {
        'magnetic_stirring': '磁力搅拌工作站',
        'electrochemical_workstation_dual': '双工位电化学工作站',
        'ultrasonic_cleaning': '超声清洗工作站',
        'dryer': '干燥工作站',
        'new_centrifugation': '离心工作站',
        'ustc_photocatalysis': '光催化工作站',
        'microplate_reader': '高通量酶标仪工作站',
        'high_flux_ir': '高通量红外光谱工作站',
        'high_flux_xrd': '高通量XRD工作站',
        'solid_dispensing': '固体进样工作站',
        'ustc_mul_solid': '多通道固体进样器',
        'starting_station': '物料站',
        'pure': '离心纯化工作站',
        'liquid_handling_workstation': '离心管架分液站',
        'liquid_dispensing': '1ml液体进样站',
        'toLC': '液相色谱仪',
        'transfer_workstation': '转移工作站',
    }

    for key, value in name_mapping.items():
        if key in filename:
            return value
    return "工作站"

def add_constraints_to_file(file_path, server_name):
    """为单个文件添加 constraints 集成"""
    print(f"正在处理文件: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否已经导入了 constraints_mapping
        if 'from constraints_mapping import validate_sample_constraints' in content:
            print(f"  - 文件已经包含 constraints 导入，跳过")
            return False

        # 检查是否已经有 constraints 验证逻辑
        if 'constraints_validation_failed' in content:
            print(f"  - 文件已经包含 constraints 验证逻辑，跳过")
            return False

        # 在文件开头的注释后添加导入语句
        docstring_end = content.find('"""') + 3
        second_docstring = content.find('"""', docstring_end) + 3

        if second_docstring > 3:
            insertion_point = second_docstring
        else:
            # 如果没有找到第二个文档字符串，在 class 声明前添加
            class_pos = content.find('class')
            insertion_point = class_pos if class_pos != -1 else len(content)

        content = content[:insertion_point] + '\n' + IMPORT_STATEMENT + content[insertion_point:]

        # 查找所有工具函数并添加 constraints 验证
        tool_function_pattern = r'(def tool_[^(]+\([^)]*\s*:\s*[^)]*\)\s*:\s*"""[^"]*"""[^}]*?)(\s*# 根据任务描述执行相应的操作)'

        def add_constraints_to_function(match):
            function_prefix = match.group(1)
            execution_start = match.group(2)

            # 提取工作站名称
            workstation_name = get_workstation_name_from_filename(os.path.basename(file_path))
            constraints_code = CONSTRAINTS_TEMPLATE.format(
                server_name=server_name,
                workstation_name=workstation_name
            )

            return function_prefix + constraints_code + execution_start

        new_content = re.sub(tool_function_pattern, add_constraints_to_function, content, flags=re.DOTALL)

        # 如果正则匹配没有找到任何工具函数，尝试手动查找
        if new_content == content:
            print(f"  - 警告：未能通过正则表达式找到工具函数，尝试手动处理")
            # 在这里可以添加更多的处理逻辑

        # 写入修改后的内容
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"  - 成功添加 constraints 集成")
        return True

    except Exception as e:
        print(f"  - 错误：处理文件时出现异常: {e}")
        return False

def main():
    """主函数：处理所有服务器工具文件"""
    servers_dir = "servers_and_tools"

    if not os.path.exists(servers_dir):
        print(f"错误：目录 {servers_dir} 不存在")
        return

    processed_count = 0
    skipped_count = 0

    for filename, server_name in SERVER_TOOL_MAPPINGS.items():
        file_path = os.path.join(servers_dir, filename)

        if os.path.exists(file_path):
            if add_constraints_to_file(file_path, server_name):
                processed_count += 1
            else:
                skipped_count += 1
        else:
            print(f"警告：文件 {file_path} 不存在，跳过")
            skipped_count += 1

    print(f"\n处理完成！")
    print(f"成功处理: {processed_count} 个文件")
    print(f"跳过: {skipped_count} 个文件")

if __name__ == "__main__":
    main()