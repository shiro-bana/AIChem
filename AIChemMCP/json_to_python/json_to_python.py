import json
import os
import sys
from string import Template


def sanitize_name(name):
    """将名称中的连字符/特殊字符替换为下划线，确保符合Python命名规范"""
    return name.replace("-", "_").replace(".", "_").replace(" ", "_")


def generate_unified_server_code(json_data, sanitize_device_code):
    """
    生成统一能力的工作站MCP服务器代码
    每个工作站只有一个工具，工具名称为工作站名，描述为noteCN
    """
    # 解析JSON核心数据
    device_name = json_data["data"]["name"]
    device_note_cn = json_data["data"].get("noteCn", device_name)
    
    # 1. 生成统一的工具函数
    tool_function = f"""def tool_{sanitize_device_code}(task_description: str, **params):
    \"\"\"
    执行{device_name}的任务
    
    参数:
        task_description: 任务描述，说明要执行的具体操作
        **params: 其他可选参数，根据具体任务需要传递
    \"\"\"
    return tool_manager.tool_{sanitize_device_code}(task_description, **params)
"""

    # 2. 工具映射字典（只有一个工具）
    tool_mappings = [f'    "{device_name}": tool_{sanitize_device_code}']
    tool_mappings_str = ",\n".join(tool_mappings)

    # 3. 生成广播消息中的工具能力描述
    capabilities_tools = [f"""        {{
            "name": "{device_name}",
            "description": "{device_note_cn}",
            "parameters": {{
                "type": "object",
                "properties": {{
                    "task_description": {{
                        "type": "string",
                        "description": "需要执行的具体任务描述"
                    }}
                }},
                "required": ["task_description"]
            }}
        }}"""]
    capabilities_tools_str = ",\n".join(capabilities_tools)

    # 4. 代码模板
    code_template = Template("""import sys
import json
# 动态导入当前设备对应的工具类
from ${sanitize_device_code}_server_tools_v2 import UnifiedWorkstationTools


# 创建全局工具管理器实例
tool_manager = UnifiedWorkstationTools()


# --- 定义统一的工作站工具函数 ---
$tool_function


AVAILABLE_TOOLS = {
$tool_mappings
}


# --- MCP协议通信主逻辑 ---
def ${sanitize_device_code}_server_main_loop():
    \"\"\"主循环：监听并响应Host的MCP协议请求\"\"\"
    for line in sys.stdin:
        try:
            request = json.loads(line)
            request_id = request.get("id")
            method_name = request.get("method")
            params = request.get("params", {})

            if method_name in AVAILABLE_TOOLS:
                # 调用对应的工具函数
                tool_function = AVAILABLE_TOOLS[method_name]
                result = tool_function(**params)
                response = {
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id
                }
            else:
                # 方法不存在错误
                response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method_name}"
                    },
                    "id": request_id
                }

            # 响应结果
            print(json.dumps(response, ensure_ascii=False), flush=True)
        except Exception as e:
            # 内部错误处理
            error_msg = {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
            response = {
                "jsonrpc": "2.0",
                "error": error_msg,
                "id": request.get("id")
            }
            print(json.dumps(response, ensure_ascii=False), flush=True)
            print(f"--- [${sanitize_device_code}_Server] Error: {str(e)} ---", file=sys.stderr, flush=True)


def ${sanitize_device_code}_server_advertise_capabilities():
    \"\"\"广播当前设备的MCP能力\"\"\"
    adv_message = {
        "jsonrpc": "2.0",
        "method": "protocol/advertise",
        "params": {
            "type": "server",
            "server": {
                "protocolVersion": "0.1.0",
                "displayName": "${device_name}",
                "capabilities": {
                    "tools": [
$capabilities_tools
                    ]
                }
            }
        }
    }
    print(json.dumps(adv_message, ensure_ascii=False), flush=True)
    print(f"--- [${sanitize_device_code}_Server] ${device_name} 已就绪 ---", file=sys.stderr, flush=True)


if __name__ == "__main__":
    # 启动流程：先广播能力，再进入主循环
    ${sanitize_device_code}_server_advertise_capabilities()
    ${sanitize_device_code}_server_main_loop()
""")

    # 填充模板并返回代码
    return code_template.substitute(
        sanitize_device_code=sanitize_device_code,
        device_name=device_name,
        tool_function=tool_function,
        tool_mappings=tool_mappings_str,
        capabilities_tools=capabilities_tools_str
    )


def generate_unified_tools_code(json_data, sanitize_device_code):
    """
    生成统一能力的工作站工具类文件
    """
    device_name = json_data["data"]["name"]
    device_note_cn = json_data["data"].get("noteCn", device_name)
    actions = json_data["data"].get("actions", [])
    
    # 生成可用操作列表字符串
    action_descriptions = []
    for action in actions:
        action_name = action.get("name", "未知操作")
        action_code = action.get("code", "未知代码")
        action_note = action.get("noteCn", "无描述")
        action_descriptions.append(f'        - {action_name} ({action_code}): {action_note}')
    
    actions_list_str = "\n".join(action_descriptions) if action_descriptions else "        无可用操作"
    
    # 生成动作匹配逻辑
    actions_json_str = json.dumps(actions, ensure_ascii=False, indent=4)
    
    # 生成工具方法
    tool_method = f"""    def tool_{sanitize_device_code}(self, task_description: str, **params):
        \"\"\"
        {device_name} - {device_note_cn}
        
        可用操作:
{actions_list_str}
        
        参数:
            task_description: 任务描述
            **params: 其他参数
        \"\"\"
        # 根据任务描述执行相应的操作
        # 这里需要实现任务编排逻辑
        result = {{
            "workstation": "{device_name}",
            "task": task_description,
            "status": "pending_implementation",
            "message": "任务编排功能待实现 - 需要根据任务描述解析并执行相应的动作序列"
        }}
        
        # 简单的任务匹配逻辑
        task_lower = task_description.lower()
        
        # 尝试匹配已有的动作
        matched_actions = []
        actions_list = {actions_json_str}
        
        for action in actions_list:
            action_name = action.get("name", "")
            action_code = action.get("code", "")
            if (action_name and action_name.lower() in task_lower) or (action_code and action_code.lower() in task_lower):
                matched_actions.append({{
                    "action_name": action_name,
                    "action_code": action_code,
                    "description": action.get("noteCn", "")
                }})
        
        if matched_actions:
            result["matched_actions"] = matched_actions
            result["message"] = f"识别到 {{len(matched_actions)}} 个相关操作，请完善任务编排逻辑"
        
        return result"""

    # 组装工具类代码
    tools_code = f"""\"\"\"
{sanitize_device_code} 统一能力工作站工具类
设备名称: {device_name}
设备描述: {device_note_cn}
生成时间: {json_data["data"].get("updateTime", "未知")}
\"\"\"

class UnifiedWorkstationTools:
    \"\"\"统一能力工作站工具管理器\"\"\"
    
{tool_method}
"""
    return tools_code


def process_single_json_v2(file_path):
    """处理单个JSON文件的新版本（统一能力）"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        # 判断是否为 API 响应格式 {"code":200, "data": {...}}
        if isinstance(json_data, dict) and "data" in json_data:
            if json_data.get("code") != 200:
                print(f"跳过非200响应的文件: {os.path.basename(file_path)}")
                return False
            data = json_data["data"]
        else:
            # 纯工作站配置格式
            data = json_data

        # 校验必须字段
        if "code" not in data:
            print(f"跳过格式异常的文件: {os.path.basename(file_path)}")
            return False

        # 设备标识处理
        device_code_raw = data.get("code")
        sanitize_device_code = sanitize_name(device_code_raw)

        # 生成主服务器文件
        server_filename = f"{sanitize_device_code}_server_v2.py"
        server_code = generate_unified_server_code({"data": data}, sanitize_device_code)
        with open(server_filename, "w", encoding="utf-8") as f:
            f.write(server_code)
        print(f"✅ 统一能力服务器文件生成完成：{server_filename}")

        # 生成工具类文件
        tools_filename = f"{sanitize_device_code}_server_tools_v2.py"
        tools_code = generate_unified_tools_code({"data": data}, sanitize_device_code)
        with open(tools_filename, "w", encoding="utf-8") as f:
            f.write(tools_code)
        print(f"✅ 统一能力工具类文件生成完成：{tools_filename}")

        print(f"🎉 统一能力JSON处理完成！设备：{data.get('name')}（{device_code_raw}）")
        print(f"   能力描述：{data.get('noteCn', '无描述')}")
        print()

        return True

    except Exception as e:
        print(f"❌ 处理文件 {os.path.basename(file_path)} 失败：{str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def batch_process_workstations_v2():
    """批量处理工作站JSON文件（新版本）"""
    # 配置待遍历的JSON文件夹路径
    JSON_FOLDER_PATH = r"workstation_data"
    
    # 检查文件夹是否存在
    if not os.path.exists(JSON_FOLDER_PATH):
        print(f"错误：文件夹 {JSON_FOLDER_path} 不存在！", file=sys.stderr)
        return
    
    # 遍历文件夹中的所有JSON文件
    json_files = [
        entry.path for entry in os.scandir(JSON_FOLDER_PATH)
        if entry.is_file() and entry.name.lower().endswith(".json")
    ]
    
    if not json_files:
        print(f"提示：在 {JSON_FOLDER_PATH} 中未找到任何JSON文件", file=sys.stderr)
        return
    
    print(f"📁 找到 {len(json_files)} 个JSON文件，开始批量处理统一能力工作站...")
    print("=" * 60)
    
    success_count = 0
    for i, json_file in enumerate(json_files):
        print(f"处理进度: {i+1}/{len(json_files)} - {os.path.basename(json_file)}")
        if process_single_json_v2(json_file):
            success_count += 1
    
    print("=" * 60)
    print(f"📊 统一能力工作站批量处理完成！")
    print(f"总文件数：{len(json_files)}")
    print(f"成功数：{success_count}")
    print(f"失败数：{len(json_files) - success_count}")


if __name__ == "__main__":
    # 运行新版本的统一能力工作站生成
    batch_process_workstations_v2()