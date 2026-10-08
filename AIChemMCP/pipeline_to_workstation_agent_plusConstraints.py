#!/usr/bin/env python3
"""
使用 Agent 形式调用 OpenAI API 将 Pipelines 中的 Markdown 文件转换为工作站流程
模仿 AIChemMCP/agent.py 的结构
"""

import os
import sys
import json
import re
import importlib.util
from pathlib import Path
from typing import List, Dict, Optional
from openai import OpenAI
import httpx

# 导入 RAGDatabase 和 OpenAI 客户端配置
sys.path.append('/opt/data/private/src/AIChemMCP')
from rag_database import RAGDatabase
from openai_client_config import create_openai_client, sleep_between_requests


def load_workstation_notes(workstation_dir: str = "/opt/data/private/src/AIChem-LaboratorySimulator-main/src/workstation_instances") -> Dict[str, str]:
    """
    动态加载工作站目录中所有工作站的 noteCN 描述

    Args:
        workstation_dir: 工作站实例目录路径

    Returns:
        Dict[str, str]: 工作站名称到 noteCN 的映射
    """
    workstation_notes = {}

    if not os.path.exists(workstation_dir):
        print(f"[WARNING] 工作站目录不存在: {workstation_dir}")
        return workstation_notes

    # 将工作站父目录添加到 Python 路径中，以便导入 workstation 和 sample 模块
    parent_dir = os.path.dirname(workstation_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
        print(f"[INFO] 添加到 Python 路径: {parent_dir}")

    # 遍历目录中的所有 Python 文件
    for filename in os.listdir(workstation_dir):
        if not filename.endswith('.py') or filename.startswith('__'):
            continue

        file_path = os.path.join(workstation_dir, filename)

        try:
            # 动态导入模块
            spec = importlib.util.spec_from_file_location(filename[:-3], file_path)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 调用 get_description() 函数
            if hasattr(module, 'get_description'):
                desc = module.get_description()
                name = desc.get('name', '')
                note_cn = desc.get('noteCn', '')

                if name and note_cn:
                    workstation_notes[name] = note_cn
                    print(f"[LOADED] {name}: {note_cn[:50]}...")

        except Exception as e:
            # 打印错误信息以便调试
            print(f"[ERROR] 加载失败 {filename}: {e}")
            continue

    return workstation_notes


# 读取 OpenAI API Key
API_KEY_FILE = "/opt/data/private/src/AIChemMCP/static/OPENAI_API_KEY"
if os.path.exists(API_KEY_FILE):
    with open(API_KEY_FILE, 'r') as f:
        api_key = f.read().strip()
    os.environ["OPENAI_API_KEY"] = api_key
else:
    raise ValueError(f"API Key 文件不存在: {API_KEY_FILE}")


# 可用的工作站列表
WORKSTATIONS = [
    "离心管架分液站",
    "液相色谱仪",
    "固体进样站",
    "高通量酶标仪工作站",
    "高通量XRD工作站",
    "物料站",
    "紫外光谱工作站",
    "多通道固体进样器",
    "气相色谱仪",
    "离心机",
    "光催化工作站",
    "双工位电化学工作站",
    "磁力搅拌工作站",
    "离心纯化工作站",
    "置物工作站",
    "烘干机",
    "超声清洗工作站",
    "高通量红外光谱工作站",
    "1ml液体进样站"
]


def discover_workstation_transformations_with_agent(workstation_dir: str = "/opt/data/private/src/AIChem-LaboratorySimulator-main/src/workstation_instances",
                                                   model: str = "gpt-4o") -> Dict[str, Dict]:
    """
    使用 AI Agent 分析工作站的转换功能（相态转换、容器转换等）

    通过调用 OpenAI API 让大模型理解每个工作站的 ability 函数代码

    Args:
        workstation_dir: 工作站实例目录路径
        model: 使用的模型（默认 gpt-4o）

    Returns:
        Dict[str, Dict]: 工作站名称到转换功能的映射
        {
            "工作站名": {
                "phase_transform": {"from": "...", "to": "..."},
                "container_transform": {"from": "...", "to": "..."},
                "volume_transform": {"min": ..., "max": ..., "operation": "..."},
                "lid_transform": {...},
                "description": "...",
                "constraints": "...",
                "input_requirements": "...",
                "output_state": "..."
            }
        }
    """
    # 初始化 OpenAI 客户端（使用连接池配置）
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 环境变量未设置！")

    # 使用带连接池配置的客户端，避免端口耗尽
    client = create_openai_client(api_key=api_key)

    transformations = {}

    # 将工作站父目录添加到 Python 路径中
    parent_dir = os.path.dirname(workstation_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # 遍历目录中的所有 Python 文件
    if not os.path.exists(workstation_dir):
        print(f"[WARNING] 工作站目录不存在: {workstation_dir}")
        return transformations

    workstation_files = []
    for filename in os.listdir(workstation_dir):
        if not filename.endswith('.py') or filename.startswith('__') or '#' in filename:
            continue
        workstation_files.append(filename)

    print(f"[AGENT] 找到 {len(workstation_files)} 个工作站文件待分析")

    for filename in sorted(workstation_files):
        file_path = os.path.join(workstation_dir, filename)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 动态导入获取工作站名称和描述
            spec = importlib.util.spec_from_file_location(filename[:-3], file_path)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if not hasattr(module, 'get_description'):
                continue

            desc = module.get_description()
            ws_name = desc.get('name', '')
            note_cn = desc.get('noteCn', '')

            if not ws_name:
                continue

            print(f"[AGENT] 正在分析: {ws_name}")

            # 提取 constraints 和 ability 函数代码
            constraints_match = re.search(r'def\s+(\w+_constraints)\(.*?\):\n(.*?)(?=\ndef|\nclass|\n[A-Z]|\Z)', content, re.DOTALL)
            ability_functions = re.findall(r'def\s+(\w+_ability(?:_\w+)?)\(.*?\):\n(.*?)(?=\ndef|\nclass|\Z)', content, re.DOTALL)

            if not ability_functions:
                print(f"  [WARNING] 未找到 ability 函数")
                continue

            # 构建分析提示
            code_snippets = []
            if constraints_match:
                code_snippets.append(f"# 约束函数:\n{constraints_match.group(0)}")

            for func_name, func_body in ability_functions:
                code_snippets.append(f"# {func_name}:\n{func_name}\n{func_body}")

            code_context = "\n\n".join(code_snippets)

            system_prompt = """你是一位实验室设备专家，专门分析化学实验室工作站的功能和转换能力。

你的任务是分析工作站代码，提取出该工作站对样品状态的所有转换信息。

请分析以下代码并返回 JSON 格式，包含以下字段：

1. **input_requirements**: 输入要求（相态、容器、体积、盖子状态等）
2. **phase_transform**: 相态转换信息
   - "from": 输入相态（如 "liquid", "solid", "suspension"）
   - "to": 输出相态
   - "conditional": 条件转换说明（如果有）
3. **container_transform**: 容器转换信息
   - "from": 输入容器
   - "to": 输出容器
4. **subcontainer_transform**: 子容器转换信息
5. **volume_transform**: 体积转换信息
   - "operation": 操作类型（如 "add", "reduce", "random"）
   - "range": 范围（如 [1, 3] 表示 1-3ml）
6. **lid_transform**: 盖子状态转换
   - "from": 输入盖子状态
   - "to": 输出盖子状态
7. **output_state**: 输出状态总结
8. **constraints_summary**: 约束条件总结

返回纯 JSON 格式，不要包含其他文本。"""

            user_prompt = f"""请分析以下工作站的功能转换代码：

工作站名称: {ws_name}
工作站描述: {note_cn}

代码：
```python
{code_context}
```

请提取该工作站的所有转换功能，返回 JSON 格式。"""

            # 调用 OpenAI API
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )

                result_text = response.choices[0].message.content
                result = json.loads(result_text)

                # 添加元数据
                result['description'] = note_cn[:100] if note_cn else ''
                result['source'] = 'ai_agent'
                result['file'] = filename

                transformations[ws_name] = result
                print(f"  ✓ 分析完成")

            except Exception as e:
                print(f"  [ERROR] API 调用失败: {e}")
                continue

        except Exception as e:
            print(f"[WARNING] 分析文件失败 {filename}: {e}")
            continue

    print(f"\n[AGENT] 共分析 {len(transformations)} 个工作站的转换功能")
    return transformations


def discover_workstation_transformations(workstation_dir: str = "/opt/data/private/src/AIChem-LaboratorySimulator-main/src/workstation_instances",
                                        test_script_path: str = "/opt/data/private/src/AIChem-LaboratorySimulator-main/src/playground_flow_test_all_workstations.py") -> Dict[str, Dict]:
    """
    发现工作站的转换功能（相态转换、容器转换等）

    通过两个渠道发现：
    1. 扫描 workstation_instances 目录中的 ability 函数
    2. 解析测试脚本中的 simulate_step 函数

    Args:
        workstation_dir: 工作站实例目录路径
        test_script_path: 测试脚本路径

    Returns:
        Dict[str, Dict]: 工作站名称到转换功能的映射
        {
            "工作站名": {
                "phase_transform": {"from": "...", "to": "..."},
                "container_transform": {"from": "...", "to": "..."},
                "volume_transform": {"min": ..., "max": ...},
                "lid_transform": {...},
                "description": "..."
            }
        }
    """
    transformations = {}

    # 1. 从测试脚本中解析转换逻辑
    if os.path.exists(test_script_path):
        with open(test_script_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 查找 simulate_step 函数中的转换逻辑
        # 匹配模式：elif step_name == 'XXX': 后面的赋值语句（使用更简单的模式）
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            # 匹配 elif step_name == 'XXX':
            if re.match(r"\s*elif step_name == '([^']+)':", line):
                step_match = re.search(r"'([^']+)'", line)
                if step_match:
                    step_name = step_match.group(1)
                    # 收集后续的代码行（直到下一个 elif 或 return）
                    body_lines = []
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j]
                        if re.match(r"\s*(elif |return |def )", next_line):
                            break
                        body_lines.append(next_line)
                        j += 1

                    body = '\n'.join(body_lines)
                    transforms = {}

                    # 检测相态转换 - 匹配 sample.data['container']['subcontainer']['subcontainer_phase'] = 'xxx'
                    phase_match = re.search(r"['\"]subcontainer_phase['\"]\]\s*=\s*['\"]([^'\"]+)['\"]", body)
                    if phase_match:
                        transforms['phase_transform'] = {'to': phase_match.group(1)}

                    # 检测容器转换 - 匹配 sample.data['container']['container_name'] = 'xxx'
                    container_match = re.search(r"['\"]container_name['\"]\]\s*=\s*['\"]([^'\"]+)['\"]", body)
                    if container_match:
                        transforms['container_transform'] = {'to': container_match.group(1)}

                    # 检测子容器转换 - 匹配 sample.data['container']['subcontainer']['subcontainer_name'] = 'xxx'
                    subcontainer_match = re.search(r"['\"]subcontainer_name['\"]\]\s*=\s*['\"]([^'\"]+)['\"]", body)
                    if subcontainer_match:
                        if 'container_transform' not in transforms:
                            transforms['container_transform'] = {}
                        transforms['container_transform']['subcontainer_to'] = subcontainer_match.group(1)

                    # 检测体积转换
                    volume_matches = re.findall(r"['\"]subcontainer_volume['\"]\]\s*=\s*(.+?)(?:\n|#)", body)
                    if volume_matches:
                        transforms['volume_transform'] = [v.strip() for v in volume_matches]

                    # 检测盖子转换
                    lid_match = re.search(r"['\"]covered['\"]\]\s*=\s*(True|False)", body)
                    if lid_match:
                        transforms['lid_transform'] = {'to': lid_match.group(1)}

                    # 检测条件性相态转换
                    conditional_phase = re.findall(r"if\s+.*subcontainer_phase\]\s*==\s*['\"]([^'\"]+)['\"]:.*?subcontainer_phase\]\s*=\s*['\"]([^'\"]+)['\"]", body, re.DOTALL)
                    if conditional_phase:
                        transforms['conditional_phase_transform'] = [{'from': p[0], 'to': p[1]} for p in conditional_phase]

                    if transforms:
                        # 添加描述（取第一个注释）
                        comment_match = re.search(r"# (.+)", body_lines[0] if body_lines else "")
                        desc = comment_match.group(1) if comment_match else "自动转换"
                        transforms['description'] = desc
                        transforms['source'] = 'test_script'

                        # 获取标准工作站名称
                        ws_name = None
                        for std_name in ["液相色谱仪", "高通量酶标仪工作站", "置物工作站", "烘干机", "气相色谱仪"]:
                            if std_name in step_name or step_name in std_name:
                                ws_name = std_name
                                break

                        if ws_name:
                            transformations[ws_name] = transforms

                i = j
            else:
                i += 1

    # 2. 扫描工作站实例文件中的 ability 函数
    if os.path.exists(workstation_dir):
        parent_dir = os.path.dirname(workstation_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        for filename in os.listdir(workstation_dir):
            if not filename.endswith('.py') or filename.startswith('__'):
                continue

            file_path = os.path.join(workstation_dir, filename)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 调用 get_description() 获取名称
                spec = importlib.util.spec_from_file_location(filename[:-3], file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    if hasattr(module, 'get_description'):
                        desc = module.get_description()
                        ws_name = desc.get('name', '')
                    else:
                        continue

                    if not ws_name:
                        continue

                    # 如果已经从测试脚本中发现，跳过
                    if ws_name in transformations:
                        continue

                    # 分析 ability 函数中的转换
                    transforms = {}

                    # 检测相态转换
                    phase_pattern = r"subcontainer_phase\]\s*=\s*['\"]([^'\"]+)['\"]"
                    phases = re.findall(phase_pattern, content)
                    if phases:
                        # 去重并获取最后一个（通常是输出）
                        unique_phases = list(dict.fromkeys(phases))
                        if len(unique_phases) > 0:
                            transforms['phase_transform'] = {'to': unique_phases[-1]}

                    # 检测体积转换
                    volume_pattern = r"subcontainer_volume\]\s*=\s*(.+?)(?:\n|$)"
                    volumes = re.findall(volume_pattern, content)
                    if volumes:
                        transforms['volume_transform'] = volumes

                    # 检测条件转换
                    conditional_pattern = r"if\s+.*covered.*?:(.*?covered\s*=\s*(True|False))"
                    conditional_matches = re.findall(conditional_pattern, content, re.DOTALL)
                    if conditional_matches:
                        transforms['conditional_transform'] = True

                    if transforms:
                        transforms['description'] = desc.get('noteCn', '')[:50]
                        transforms['source'] = 'workstation_code'
                        transformations[ws_name] = transforms

            except Exception as e:
                print(f"[WARNING] 分析文件失败 {filename}: {e}")
                continue

    return transformations


def print_workstation_transformations(transformations: Dict[str, Dict]):
    """
    打印工作站转换功能报告

    Args:
        transformations: discover_workstation_transformations 或 discover_workstation_transformations_with_agent 的返回结果
    """
    print("\n" + "="*80)
    print("工作站转换功能发现报告")
    print("="*80)

    if not transformations:
        print("未发现任何转换功能")
        return

    for ws_name, transforms in sorted(transformations.items()):
        print(f"\n【{ws_name}】")
        print(f"  描述: {transforms.get('description', 'N/A')[:80]}")
        print(f"  来源: {transforms.get('source', 'unknown')}")

        # AI Agent 分析的结果
        if transforms.get('source') == 'ai_agent':
            if transforms.get('input_requirements'):
                print(f"  ✓ 输入要求: {transforms['input_requirements']}")

            if 'phase_transform' in transforms:
                pt = transforms['phase_transform']
                if isinstance(pt, dict):
                    if pt.get('from') and pt.get('to'):
                        print(f"  ✓ 相态转换: {pt['from']} → {pt['to']}")
                    elif pt.get('to'):
                        print(f"  ✓ 相态转换: → {pt['to']}")
                    if pt.get('conditional'):
                        print(f"    条件: {pt['conditional']}")

            if 'container_transform' in transforms:
                ct = transforms['container_transform']
                if isinstance(ct, dict):
                    if ct.get('from') and ct.get('to'):
                        print(f"  ✓ 容器转换: {ct['from']} → {ct['to']}")
                    elif ct.get('to'):
                        print(f"  ✓ 容器转换: → {ct['to']}")

            if 'subcontainer_transform' in transforms:
                print(f"  ✓ 子容器转换: {transforms['subcontainer_transform']}")

            if 'volume_transform' in transforms:
                vt = transforms['volume_transform']
                if isinstance(vt, dict):
                    info = f"{vt.get('operation', 'N/A')}"
                    if vt.get('range'):
                        info += f" {vt['range']}"
                    print(f"  ✓ 体积转换: {info}")

            if 'lid_transform' in transforms:
                lt = transforms['lid_transform']
                if isinstance(lt, dict):
                    if lt.get('from') and lt.get('to'):
                        print(f"  ✓ 盖子转换: {lt['from']} → {lt['to']}")
                    elif lt.get('to'):
                        print(f"  ✓ 盖子转换: → {lt['to']}")

            if transforms.get('output_state'):
                print(f"  ✓ 输出状态: {transforms['output_state']}")

            if transforms.get('constraints_summary'):
                print(f"  ✓ 约束: {transforms['constraints_summary']}")

        # 正则表达式分析的结果（原格式）
        else:
            if 'phase_transform' in transforms:
                print(f"  ✓ 相态转换: → {transforms['phase_transform']['to']}")

            if 'conditional_phase_transform' in transforms:
                for cond in transforms['conditional_phase_transform']:
                    print(f"  ✓ 条件相态转换: {cond['from']} → {cond['to']}")

            if 'container_transform' in transforms:
                ct = transforms['container_transform']
                if 'to' in ct:
                    print(f"  ✓ 容器转换: → {ct['to']}")
                if 'subcontainer_to' in ct:
                    print(f"    子容器: → {ct['subcontainer_to']}")

            if 'volume_transform' in transforms:
                print(f"  ✓ 体积转换: {transforms['volume_transform']}")

            if 'lid_transform' in transforms:
                print(f"  ✓ 盖子转换: → {transforms['lid_transform']['to']}")

    print("\n" + "="*80)
    print(f"共发现 {len(transformations)} 个具有转换功能的工作站")
    print("="*80 + "\n")


def save_workstation_transformations(transformations: Dict[str, Dict], output_file: str):
    """
    保存工作站转换功能到 JSON 文件

    Args:
        transformations: discover_workstation_transformations 或 discover_workstation_transformations_with_agent 的返回结果
        output_file: 输出文件路径
    """
    import json
    from pathlib import Path

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(transformations, f, ensure_ascii=False, indent=2)

    print(f"[SAVE] 结果已保存到: {output_file}")


class PipelineToWorkstationAgent:
    """将实验流程 Markdown 文件转换为工作站流程的 Agent"""

    def __init__(self, model="gpt-4o", rag_db_path="/opt/data/private/src/AIChemMCP/rag_database.json",
                 workstation_dir="/opt/data/private/src/AIChem-LaboratorySimulator-main/src/workstation_instances",
                 transformations_path="/opt/data/private/src/AIChemMCP/workstation_transformations_agent.json"):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 环境变量未设置！")

        # 使用带连接池配置的客户端，避免端口耗尽
        self.client = create_openai_client(api_key=api_key)
        self.model = model
        self.workstations = WORKSTATIONS
        # 初始化 RAG 数据库
        self.rag_db = RAGDatabase(rag_db_path)
        # 加载工作站详细描述
        self.workstation_notes = load_workstation_notes(workstation_dir)
        # 加载工作站转换信息
        self.workstation_transformations = self._load_transformations(transformations_path)

        print(f"[AGENT] 初始化完成，模型: {self.model}")
        print(f"[AGENT] 可用工作站数量: {len(self.workstations)}")
        print(f"[AGENT] 已加载 {len(self.workstation_notes)} 个工作站的详细描述")
        print(f"[AGENT] 已加载 {len(self.workstation_transformations)} 个工作站的转换信息")
        print(f"[AGENT] RAG数据库初始化完成，当前包含 {self.rag_db.get_entry_count()} 条记录")

    def _load_transformations(self, transformations_path: str) -> Dict[str, Dict]:
        """
        加载工作站转换信息 JSON 文件

        Args:
            transformations_path: 转换信息文件路径

        Returns:
            Dict[str, Dict]: 工作站转换信息字典
        """
        if not os.path.exists(transformations_path):
            print(f"[WARNING] 转换信息文件不存在: {transformations_path}")
            return {}

        try:
            with open(transformations_path, 'r', encoding='utf-8') as f:
                transformations = json.load(f)
            print(f"[INFO] 成功加载转换信息: {len(transformations)} 个工作站")
            return transformations
        except Exception as e:
            print(f"[ERROR] 加载转换信息失败: {e}")
            return {}

    def build_system_prompt(self) -> str:
        """构建系统提示"""
        prompt = "# 角色与目标\n"
        prompt += "你是一位专家级的化学实验室工作流分析专家。你的任务是分析实验流程的 Markdown 文档，"
        prompt += "识别出实验步骤，并将每个步骤映射到最合适的实验室工作站。\n\n"

        prompt += "# 可用工作站列表及详细功能说明\n"
        prompt += "以下是你可以使用的工作站及其详细功能描述，你必须从中选择最合适的工作站：\n\n"

        # 使用动态加载的描述和转换信息
        for i, ws in enumerate(self.workstations, 1):
            prompt += f"{i}. **{ws}**\n"

            # 添加基本描述
            if ws in self.workstation_notes:
                note_cn = self.workstation_notes[ws]
                prompt += f"   - 功能: {note_cn}\n"

            # 添加转换信息
            if ws in self.workstation_transformations:
                trans = self.workstation_transformations[ws]

                # 输入要求
                if trans.get('input_requirements'):
                    prompt += f"   - 输入要求: {self._format_requirements(trans['input_requirements'])}\n"

                # 输出状态
                if trans.get('output_state'):
                    prompt += f"   - 输出状态: {self._format_requirements(trans['output_state'])}\n"

                # 关键转换
                key_transforms = []
                if trans.get('phase_transform'):
                    pt = trans['phase_transform']
                    if isinstance(pt, dict) and pt.get('from') and pt.get('to'):
                        # 单个转换（字典格式）
                        key_transforms.append(f"相态: {pt['from']} → {pt['to']}")
                    elif isinstance(pt, list) and len(pt) > 0:
                        # 多个条件转换（列表格式）
                        # 提取所有可能的转换
                        phase_changes = set()
                        for transform in pt:
                            if isinstance(transform, dict) and transform.get('from') and transform.get('to'):
                                phase_changes.add(f"{transform['from']}→{transform['to']}")
                        if phase_changes:
                            key_transforms.append(f"相态: {', '.join(sorted(phase_changes))}")

                if trans.get('container_transform'):
                    ct = trans['container_transform']
                    if isinstance(ct, dict) and ct.get('from') and ct.get('to'):
                        key_transforms.append(f"容器: {ct['from']} → {ct['to']}")

                if trans.get('volume_transform'):
                    vt = trans['volume_transform']
                    if isinstance(vt, dict) and vt.get('operation'):
                        range_str = f" {vt.get('range', '')}" if vt.get('range') else ''
                        key_transforms.append(f"体积: {vt['operation']}{range_str}")

                if key_transforms:
                    prompt += f"   - 关键转换: {', '.join(key_transforms)}\n"

                # 约束摘要
                if trans.get('constraints_summary'):
                    summary = trans['constraints_summary']
                    if len(summary) > 100:
                        summary = summary[:97] + "..."
                    prompt += f"   - 约束: {summary}\n"

            prompt += "\n"

        prompt += "# 工作流生成规则\n"
        prompt += "1. **顺序合理**: 确保工作流的顺序符合实验逻辑\n"
        prompt += "2. **以物料站开始**: 除非特殊说明，通常以物料站获取材料开始\n"
        prompt += "3. **兼容性检查（非常重要）**: 确保相邻工作站的输入输出兼容\n"
        prompt += "   - **相态匹配**: 前一个工作站的输出相态必须满足后一个工作站的输入要求\n"
        prompt += "   - **容器匹配（重要限制）**: 容器转换是单向的，不可逆！\n"
        prompt += "     - ✅ rack → plate/vial（通过高通量酶标仪工作站/液相色谱仪/气相色谱仪）\n"
        prompt += "     - ❌ plate/vial → rack（**不存在反向转换工作站**）\n"
        prompt += "     - ⚠️  一旦使用了孔板工作站（如高通量酶标仪工作站、高通量红外光谱工作站），\n"
        prompt += "         后续步骤必须能接受孔板容器，不能使用要求离心管架的工作站（如置物工作站、磁力搅拌工作站等）\n"
        prompt += "   - **体积匹配**: 前一个工作站的输出体积必须在后一个工作站的接受范围内\n"
        prompt += "   - **优先级**: 相态兼容 > 容器兼容 > 体积兼容\n"
        prompt += "4. **简化原则**: 只包含必要的工作站步骤，避免冗余\n\n"

        prompt += "# 输出要求\n"
        prompt += "你必须返回一个 JSON 格式，包含实验问题和对应的工作站列表，格式如下：\n"
        prompt += "```json\n"
        prompt += "{\n"
        prompt += "  \"question\": \"用一句话描述这个实验要解决的问题或目标\",\n"
        prompt += "  \"workstations\": [\"工作站1\", \"工作站2\", ...]\n"
        prompt += "}\n"
        prompt += "```\n\n"

        prompt += "重要：\n"
        prompt += "1. question 应该是一个简洁的问题描述，例如：'如何制备金纳米粒子与光谱表征？'\n"
        prompt += "2. 只能使用上述列出的工作站名称，不能添加新的工作站名称。\n"
        prompt += "3. **必须严格遵守每个工作站的输入输出约束**，特别是相态、容器和体积要求。\n"

        return prompt

    def _format_requirements(self, req: any) -> str:
        """格式化要求信息为字符串"""
        if isinstance(req, dict):
            # 简化字典显示
            items = []
            for k, v in req.items():
                if isinstance(v, (list, dict)):
                    v_str = str(v)
                    if len(v_str) > 50:
                        v_str = v_str[:47] + "..."
                else:
                    v_str = str(v)
                items.append(f"{k}={v_str}")
            return ", ".join(items)
        elif isinstance(req, list):
            return str(req)
        else:
            return str(req)

    def build_rag_enhanced_prompt(self, markdown_content: str, top_k=3, feedback_text: str = None) -> str:
        """
        构建包含RAG上下文的增强提示

        Args:
            markdown_content: Markdown 文档内容
            top_k: 从RAG数据库中获取的相似条目的数量
            feedback_text: 反馈文本（包含失败分析和建议）

        Returns:
            str: 增强的系统提示
        """
        # 获取基础系统提示
        base_prompt = self.build_system_prompt()

        # 从Markdown中提取简短描述作为查询
        # 取前500个字符作为查询
        query = markdown_content[:500]

        # 从RAG数据库获取相关上下文
        print(f"[AGENT] 正在从RAG数据库中查找相关的历史实验流程...")
        context = self.rag_db.get_relevant_context(query, top_k)

        # 添加RAG上下文到提示中
        rag_prompt = base_prompt + "\n# 相关历史实验流程参考 (RAG Context)\n"
        rag_prompt += "---\n"
        rag_prompt += context
        rag_prompt += "---\n\n"
        rag_prompt += "# 使用RAG上下文的指导原则\n"
        rag_prompt += "1. **优先使用RAG示例中的工作站名称**: 如果RAG示例中显示了带「[原名称: xxx]」的工作站，**必须优先使用完整名称**（如\"离心纯化工作站\"而不是\"离心机\"）\n"
        rag_prompt += "2. **参考历史经验**: 仔细分析上述相关的历史实验流程，学习其工作站选择和顺序安排\n"
        rag_prompt += "3. **避免重复错误**: 如果历史流程中有遇到兼容性问题，请参考其解决方案\n"
        rag_prompt += "4. **灵活应用**: 根据当前实验的具体需求，在参考历史的基础上进行调整，但优先考虑RAG中成功的工作站组合\n"
        rag_prompt += "5. **确保兼容性**: 参考历史流程中的兼容性处理方式（如相态转换、容器匹配等）\n"
        rag_prompt += "6. **特别提醒 - 离心操作的选择**:\n"
        rag_prompt += "   - 如果实验涉及纳米颗粒、催化剂、材料合成：使用 \"离心纯化工作站\"（输出纯固体或微量液体）\n"
        rag_prompt += "   - 如果实验涉及生物样品分离：使用 \"离心机\"（输出固液分离状态）\n\n"

        # 如果有反馈文本，添加到提示中
        if feedback_text:
            rag_prompt += "\n# 上次生成的失败反馈 (必须参考)\n"
            rag_prompt += "---\n"
            rag_prompt += feedback_text
            rag_prompt += "---\n\n"
            rag_prompt += "# 重要提示：基于反馈的改进要求\n"
            rag_prompt += "1. **必须解决上次失败的根本原因**: 仔细阅读上述失败反馈，确保新的流程解决所有提到的问题\n"
            rag_prompt += "2. **只能使用预定义的工作站**: 绝对不能创建新的工作站名称！如果反馈建议添加'相态转换'、'样品转移'等步骤，请用以下工作站组合实现：\n"
            rag_prompt += "   - 相态转换：使用 置物工作站(静置分层)、离心机(分离)、烘干机(干燥) 等组合\n"
            rag_prompt += "   - 样品转移/分装：使用 1ml液体进样站(精确移液)\n"
            rag_prompt += "3. **不要添加'盖子操作'**: 工作站系统会自动处理容器的盖子状态，不需要（也不能）添加独立的'盖子操作'、'盖子关闭'、'盖子打开'等步骤\n"
            rag_prompt += "4. **解决盖子问题的正确方法**: 如果反馈提到离心机需要盖子，这通常意味着流程设计有问题。正确的解决方法可能是：\n"
            rag_prompt += "   - 检查流程逻辑，确保步骤顺序合理\n"
            rag_prompt += "   - 使用不同的工作站组合\n"
            rag_prompt += "   - 避免使用无法满足离心机要求的工作站\n"
            rag_prompt += "5. **调整步骤顺序**: 如果反馈指出顺序问题，必须调整\n"
            rag_prompt += "6. **确保约束条件匹配**: 容器类型、相态、体积等必须符合工作站要求\n"
            rag_prompt += "7. **避免无效工作站**: 绝对不要使用'相态转换'、'样品转移到孔板'、'移液操作'、'盖子操作'等名称作为工作站！\n\n"

        return rag_prompt

    def extract_workflow_from_markdown(self, markdown_content: str, use_rag: bool = True, max_attempts: int = 3, feedback_text: str = None) -> Dict[str, any]:
        """
        使用 OpenAI API 从 Markdown 内容中提取工作流

        Args:
            markdown_content: Markdown 文件内容
            use_rag: 是否使用 RAG 增强提示（默认 True）
            max_attempts: 最大生成尝试次数（包括兼容性检查后的重新生成）
            feedback_text: 反馈文本（包含失败分析和建议）

        Returns:
            Dict[str, any]: 包含 question 和 workstations 的字典
        """
        # 初始系统提示（如果提供反馈文本，强制使用 RAG）
        if feedback_text:
            use_rag = True
        base_system_prompt = self.build_rag_enhanced_prompt(markdown_content, top_k=3, feedback_text=feedback_text) if use_rag else self.build_system_prompt()

        user_prompt = f"""请分析以下实验流程 Markdown 文档：
1. 提取实验要解决的问题或目标（用一个问题表述）
2. 识别实验步骤并将每个步骤映射到最合适的工作站

文档内容：
```
{markdown_content[:10000]}  # 限制长度避免 token 超限
```

要求：
1. 仔细阅读文档，理解实验要解决的问题或目标
2. 将每个步骤映射到最合适的工作站
3. 确保工作流的顺序合理
4. 只使用提供的工作站列表中的名称
5. 返回纯 JSON 格式，不要包含其他文本
"""

        # 兼容性检查后的重新生成循环
        for attempt in range(max_attempts):
            # 如果不是第一次尝试，在提示中添加兼容性问题信息
            current_system_prompt = base_system_prompt
            if attempt > 0:
                current_system_prompt += f"\n\n# 重要提醒：上次生成的计划存在兼容性问题，请参考上述问题描述重新生成。特别注意相态转换和约束条件匹配。"

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": current_system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )

                result_text = response.choices[0].message.content

                # 解析 JSON
                try:
                    # 提取 JSON 部分
                    if "```json" in result_text:
                        json_str = result_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in result_text:
                        json_str = result_text.split("```")[1].strip()
                    else:
                        json_str = result_text.strip()

                    result = json.loads(json_str)
                    question = result.get("question", "")
                    workstations = result.get("workstations", [])

                    # 验证工作站名称
                    valid_workstations = []
                    for ws in workstations:
                        if ws in self.workstations:
                            valid_workstations.append(ws)
                        else:
                            print(f"  警告: 跳过无效的工作站名称: {ws}")

                    # 如果没有提取到问题，使用默认描述
                    if not question:
                        question = "实验流程处理"

                    # 检查兼容性
                    compatibility_result = self.check_plan_compatibility(valid_workstations)

                    if compatibility_result['compatible']:
                        print(f"  ✓ 兼容性检查通过")
                        return {
                            "question": question,
                            "workstations": valid_workstations
                        }
                    else:
                        print(f"  ⚠ 兼容性问题 (尝试 {attempt + 1}/{max_attempts}):")
                        for issue in compatibility_result['issues']:
                            print(f"    - {issue}")

                        if attempt < max_attempts - 1:
                            print(f"  → 正在重新生成...")
                            # 将兼容性问题添加到用户提示中
                            user_prompt += f"\n\n上次生成的计划存在以下兼容性问题：\n"
                            for issue in compatibility_result['issues']:
                                user_prompt += f"- {issue}\n"
                            user_prompt += "\n请重新生成计划，确保解决这些兼容性问题。"
                            import time
                            time.sleep(1)
                        else:
                            print(f"  ⚠ 警告: 达到最大尝试次数，返回可能有兼容性问题的计划")
                            return {
                                "question": question,
                                "workstations": valid_workstations
                            }

                except json.JSONDecodeError as e:
                    print(f"  JSON 解析错误: {e}")
                    print(f"  原始响应: {result_text}")
                    if attempt < max_attempts - 1:
                        continue
                    else:
                        raise

            except Exception as e:
                print(f"  API 调用错误 (尝试 {attempt + 1}/{max_attempts}): {e}")
                if attempt < max_attempts - 1:
                    import time
                    time.sleep(2)
                    continue
                else:
                    raise

        return {"question": "实验流程处理", "workstations": []}

    def check_plan_compatibility(self, workstations: List[str]) -> dict:
        """
        检查工作流计划的兼容性（使用动态加载的转换数据）

        Args:
            workstations: 工作站名称列表

        Returns:
            dict: {'compatible': bool, 'issues': [str]}
        """
        if not workstations or len(workstations) <= 1:
            return {'compatible': True, 'issues': []}

        # 如果没有加载转换数据，回退到硬编码规则
        if not self.workstation_transformations:
            print("[WARNING] 未加载转换数据，使用硬编码兼容性规则")
            return self._check_compatibility_hardcoded(workstations)

        # 使用动态数据进行兼容性检查
        compatibility_issues = []

        for i in range(len(workstations) - 1):
            current = workstations[i]
            next_ws = workstations[i + 1]

            # 获取两个工作站的转换信息
            current_trans = self.workstation_transformations.get(current, {})
            next_trans = self.workstation_transformations.get(next_ws, {})

            # 如果缺少任一工作站的转换信息，跳过检查
            if not current_trans or not next_trans:
                continue

            # 检查输出-输入兼容性
            current_output = current_trans.get('output_state', {})
            next_input = next_trans.get('input_requirements', {})

            # 1. 检查相态兼容性
            current_phase = self._extract_phase_info(current_output)
            next_phase_requirement = self._extract_phase_requirement(next_input)

            if current_phase and next_phase_requirement:
                if not self._is_phase_compatible(current_phase, next_phase_requirement):
                    compatibility_issues.append(
                        f"步骤 {i+1}→{i+2}: {current} → {next_ws} 相态不兼容: "
                        f"{current} 输出相态为 {current_phase}，但 {next_ws} 要求 {next_phase_requirement}。"
                        f"建议: 在两者间添加能够转换相态的工作站"
                    )

            # 2. 检查容器兼容性
            current_container = self._extract_container_info(current_output)
            next_container_requirement = self._extract_container_requirement(next_input)

            if current_container and next_container_requirement:
                if not self._is_container_compatible(current_container, next_container_requirement):
                    # 判断是否是反向容器转换（plate/vial → rack）
                    is_reverse_conversion = (
                        current_container in ['24_hole_plate', '48_hole_plate', '96_hole_plate', 'vial'] and
                        next_container_requirement == 'rack'
                    )

                    if is_reverse_conversion:
                        suggestion = "⚠️ 反向容器转换不存在！系统无法将孔板/色谱瓶转换回离心管架。请重新设计流程，避免在孔板工作站后使用要求离心管架的工作站。"
                    else:
                        suggestion = "建议: 检查工作站的容器要求，或调整流程顺序"

                    compatibility_issues.append(
                        f"步骤 {i+1}→{i+2}: {current} → {next_ws} 容器不兼容: "
                        f"{current} 输出容器为 {current_container}，但 {next_ws} 要求 {next_container_requirement}。"
                        f"{suggestion}"
                    )

            # 3. 检查体积兼容性
            current_volume = self._extract_volume_info(current_output)
            next_volume_requirement = self._extract_volume_requirement(next_input)

            if current_volume and next_volume_requirement:
                if not self._is_volume_compatible(current_volume, next_volume_requirement):
                    compatibility_issues.append(
                        f"步骤 {i+1}→{i+2}: {current} → {next_ws} 体积不兼容: "
                        f"{current} 输出体积为 {current_volume}，但 {next_ws} 要求 {next_volume_requirement}。"
                        f"建议: 在两者间添加体积转换或分装工作站"
                    )

        return {
            'compatible': len(compatibility_issues) == 0,
            'issues': compatibility_issues
        }

    def _check_compatibility_hardcoded(self, workstations: List[str]) -> dict:
        """使用硬编码规则进行兼容性检查（备用方法）"""
        # 硬编码的关键不兼容规则（保持原有逻辑作为后备）
        incompatible_sequences = [
            {
                'from': ['烘干机'],
                'to': ['双工位电化学工作站', '超声清洗工作站'],
                'issue': '烘干机输出固体，目标工作站要求液体或悬浊液',
                'solution': '需要添加液体处理或磁力搅拌步骤'
            },
            {
                'from': ['固体进样站', '多通道固体进样器'],
                'to': ['双工位电化学工作站', '磁力搅拌工作站'],
                'issue': '固体进样站输出固体，目标工作站需要液体或悬浊液',
                'solution': '需要添加液体进样站，先加入液体形成悬浊液'
            },
            {
                'from': ['烘干机'],
                'to': ['高通量酶标仪工作站'],
                'issue': '烘干机输出固体，酶标仪要求液体；且容器不匹配',
                'solution': '需要添加液体分散步骤和容器转换'
            },
            {
                'from': ['离心纯化工作站'],
                'to': ['高通量红外光谱工作站'],
                'issue': '离心纯化输出悬浊液，红外光谱工作站要求固体或液体',
                'solution': '需要在两者间添加烘干或分离步骤'
            },
        ]

        compatibility_issues = []
        for i in range(len(workstations) - 1):
            current = workstations[i]
            next_workstation = workstations[i + 1]

            for rule in incompatible_sequences:
                if (any(keyword in current for keyword in rule['from']) and
                    any(keyword in next_workstation for keyword in rule['to'])):
                    compatibility_issues.append(
                        f"步骤 {i+1}→{i+2}: {current} → {next_workstation} 不兼容: {rule['issue']}. 建议: {rule['solution']}"
                    )

        return {
            'compatible': len(compatibility_issues) == 0,
            'issues': compatibility_issues
        }

    def _extract_phase_info(self, state: dict) -> str:
        """从状态中提取相态信息"""
        if isinstance(state, dict):
            phase = state.get('phase')
            if isinstance(phase, list):
                # 如果有多个可能的相态（条件转换），返回所有可能的相态
                return phase
            # 处理 "same as input" 这种特殊情况
            if isinstance(phase, str) and 'same as input' in phase.lower():
                return 'any'  # 表示保持原状态，可以适配任何要求
            return str(phase) if phase else ''
        return ''

    def _extract_phase_requirement(self, req: dict) -> str:
        """从要求中提取相态要求"""
        if isinstance(req, dict):
            phase = req.get('phase')
            if isinstance(phase, list):
                # 如果接受多个相态，返回第一个作为主要要求
                return phase[0] if phase else ''
            # 处理 "same as input" 这种特殊情况
            if isinstance(phase, str) and 'same as input' in phase.lower():
                return 'any'  # 表示接受任何输入相态
            return str(phase) if phase else ''
        return ''

    def _is_phase_compatible(self, output_phase: any, input_phase_req: str) -> bool:
        """检查相态是否兼容"""
        # 如果输入要求是 'any'，则兼容
        if input_phase_req.lower() == 'any':
            return True

        # 如果输出是 'any'（表示保持原状态），也认为兼容
        # 因为 "same as input" 意味着可以适配任何后续要求
        if output_phase == 'any' or (isinstance(output_phase, str) and output_phase.lower() == 'any'):
            return True

        # 如果输出是列表（条件转换），检查是否所有可能的输出都兼容
        if isinstance(output_phase, list):
            # 只要有任何一个输出相态兼容，就认为兼容（乐观策略）
            # 或者可以改为：只有所有输出都兼容才认为兼容（悲观策略）
            # 这里使用悲观策略，确保最坏情况下也兼容
            for op in output_phase:
                if self._check_single_phase_compatible(op, input_phase_req):
                    return True
            # 如果所有可能的输出都不兼容，返回 False
            # 但对于烘干机这样的设备，它可以根据条件产生不同输出
            # 所以应该检查是否有兼容的输出路径
            return False

        # 单一相态检查
        return self._check_single_phase_compatible(output_phase, input_phase_req)

    def _check_single_phase_compatible(self, output_phase: str, input_phase_req: str) -> bool:
        """检查单个相态是否兼容"""
        # 完全匹配
        if output_phase == input_phase_req:
            return True

        # 定义相态兼容性映射
        compatible_phases = {
            'liquid': ['liquid', 'suspension', 'slurry'],
            'suspension': ['suspension', 'liquid', 'solid_liquid_separated', 'solid_with_liquid_overlay', 'solid_with_tiny_liquid'],
            'slurry': ['slurry', 'suspension', 'liquid'],
            'solid': ['solid', 'solid_with_tiny_liquid'],
            'solid_liquid_separated': ['solid_liquid_separated', 'suspension', 'solid', 'liquid'],  # 固液分离可以视作悬浊液或固体
            'solid_with_liquid_overlay': ['solid_with_liquid_overlay', 'suspension', 'solid'],  # 固体带液体覆盖层
            'solid_with_tiny_liquid': ['solid_with_tiny_liquid', 'solid'],  # 固体带微量液体
            'empty': ['empty', 'solid', 'liquid']
        }

        # 检查是否在兼容列表中
        if output_phase in compatible_phases:
            return input_phase_req in compatible_phases[output_phase]

        return False

    def _extract_container_info(self, state: dict) -> str:
        """从状态中提取容器信息"""
        if isinstance(state, dict):
            container = state.get('container')
            if isinstance(container, list):
                return container[0] if container else ''
            # 处理 "same as input" 这种特殊情况
            if isinstance(container, str) and 'same as input' in container.lower():
                return 'any'  # 表示保持原容器
            return str(container) if container else ''
        return ''

    def _extract_container_requirement(self, req: dict) -> str:
        """从要求中提取容器要求"""
        if isinstance(req, dict):
            container = req.get('container')
            if isinstance(container, list):
                return container[0] if container else ''
            # 处理 "same as input" 这种特殊情况
            if isinstance(container, str) and 'same as input' in container.lower():
                return 'any'  # 表示接受任何容器
            return str(container) if container else ''
        return ''

    def _is_container_compatible(self, output_container: str, input_container_req: str) -> bool:
        """
        检查容器是否兼容

        注意：容器转换是单向的！只有特定工作站会进行容器转换。
        """
        # 如果输入要求是 'any'，则兼容
        if input_container_req.lower() == 'any':
            return True

        # 如果输出是 'any'（表示保持原容器），也认为兼容
        if output_container == 'any' or (isinstance(output_container, str) and output_container.lower() == 'any'):
            return True

        # 完全匹配
        if output_container == input_container_req:
            return True

        # 单向容器转换（基于实际的工作站能力）
        # 只有以下转换是允许的：
        # - rack → plate（通过高通量酶标仪工作站、高通量红外光谱工作站）
        # - rack → vial（通过液相色谱仪、气相色谱仪）
        # 注意：反向转换（plate/vial → rack）不存在！
        allowed_conversions = [
            ('rack', '24_hole_plate'),  # 高通量酶标仪工作站/红外光谱工作站
            ('rack', '48_hole_plate'),
            ('rack', '96_hole_plate'),
            ('rack', 'vial'),           # 液相色谱仪/气相色谱仪
        ]

        for from_container, to_container in allowed_conversions:
            # 只检查单向转换
            if output_container == from_container and input_container_req == to_container:
                return True

        # 其他情况不兼容（包括反向转换）
        return False

    def _extract_volume_info(self, state: dict) -> str:
        """从状态中提取体积信息"""
        if isinstance(state, dict):
            volume = state.get('volume')
            return str(volume) if volume is not None else ''
        return ''

    def _extract_volume_requirement(self, req: dict) -> str:
        """从要求中提取体积要求"""
        if isinstance(req, dict):
            volume = req.get('volume')
            if volume is None:
                volume = req.get('volume_max')
            return str(volume) if volume is not None else ''
        return ''

    def _is_volume_compatible(self, output_volume: str, input_volume_req: str) -> bool:
        """检查体积是否兼容（简化版本）"""
        # 如果输入要求是 'any'，则兼容
        if input_volume_req.lower() == 'any':
            return True

        # 这里可以添加更复杂的体积范围检查逻辑
        # 当前简化为总是返回 True，因为体积转换通常比较灵活
        return True

    def generate_plan_log(self, question: str, workflow: List[str], paper_name: str) -> str:
        """
        生成 plan_X.log 格式的输出

        Args:
            question: 实验问题描述
            workflow: 工作站列表
            paper_name: 论文名称

        Returns:
            str: 格式化的日志内容
        """
        output = []
        output.append(f"问题: {question}")
        output.append("")
        output.append("=== 第 1 次执行计划 ===")

        for i, workstation in enumerate(workflow, 1):
            output.append(f"  步骤 {i}: {{'method': '{workstation}', 'params': {{}}}}")

        output.append("")  # 空行

        return '\n'.join(output)

    def process_single_file(self, md_file: Path, output_file: Path, use_rag: bool = True, feedback_file: str = None) -> bool:
        """
        处理单个 Markdown 文件

        Args:
            md_file: 输入 Markdown 文件路径
            output_file: 输出 log 文件路径
            use_rag: 是否使用 RAG 增强提示（默认 True）
            feedback_file: 反馈文件路径（包含失败分析和建议）

        Returns:
            bool: 是否成功
        """
        print(f"处理: {md_file.name}")

        # 读取反馈文件（如果提供）
        feedback_text = None
        if feedback_file and os.path.exists(feedback_file):
            print(f"  [INFO] 使用反馈文件: {feedback_file}")
            with open(feedback_file, 'r', encoding='utf-8') as f:
                feedback_text = f.read()
        elif feedback_file:
            print(f"  [WARNING] 反馈文件不存在: {feedback_file}")

        try:
            # 读取 Markdown 文件
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 调用 Agent 提取工作流和问题
            result = self.extract_workflow_from_markdown(content, use_rag=use_rag, feedback_text=feedback_text)
            question = result.get("question", "实验流程处理")
            workflow = result.get("workstations", [])

            if not workflow:
                print(f"  警告: 未提取到工作流，使用默认流程")
                question = "实验流程处理"
                workflow = ["物料站", "1ml液体进样站", "磁力搅拌工作站"]

            # 生成输出
            plan_log = self.generate_plan_log(question, workflow, md_file.stem)

            # 写入输出文件
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                # 写入映射信息作为注释
                f.write(f"# Source: {md_file.name}\n")
                f.write(f"# Generated: {__import__('datetime').datetime.now().isoformat()}\n")
                f.write(plan_log)

            # 保存映射关系到单独的文件（用于重新生成）
            mapping_file = output_file.parent / f"{output_file.stem}_mapping.txt"
            with open(mapping_file, 'w', encoding='utf-8') as f:
                f.write(f"{md_file.name}")

            print(f"  -> {output_file.name} (问题: {question}, {len(workflow)} 个步骤)")
            return True

        except Exception as e:
            print(f"  错误: {e}")
            import traceback
            traceback.print_exc()
            return False

    def process_batch(self, input_dir: str, output_dir: str,
                     start_idx: int = 1, end_idx: int = None,
                     batch_size: int = None, use_rag: bool = True, feedback_file: str = None,
                     target_plan: int = None, input_file: str = None, skip_existing: bool = False):
        """
        批量处理 Pipeline 文件

        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            start_idx: 起始索引（从1开始）
            end_idx: 结束索引（None 表示处理到最后）
            batch_size: 批次大小（None 表示处理全部）
            use_rag: 是否使用 RAG 增强提示（默认 True）
            feedback_file: 反馈文件路径（包含失败分析和建议）
            target_plan: 目标 plan 编号（用于覆盖指定的 plan 文件）
            input_file: 直接指定要处理的 Paper 文件名（如 Paper_8.md）
            skip_existing: 是否跳过已存在的输出文件（默认 False）
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 如果直接指定了 input_file，使用它
        if input_file is not None:
            md_files = [input_path / input_file]
            if not md_files[0].exists():
                print(f"[ERROR] 文件不存在: {md_files[0]}")
                return
        else:
            # 获取所有 Markdown 文件并使用自然排序（按数字大小排序）
            import re
            def natural_key(path):
                # 从文件名中提取数字
                match = re.search(r'Paper_(\d+)', path.name)
                if match:
                    return int(match.group(1))
                return 0

            md_files = sorted(input_path.glob("Paper_*.md"), key=natural_key)

            # 应用索引范围
            if end_idx is None:
                end_idx = len(md_files)
            md_files = md_files[start_idx - 1:end_idx]

            # 应用批次大小
            if batch_size is not None:
                md_files = md_files[:batch_size]

        print(f"[AGENT] 找到 {len(md_files)} 个 Markdown 文件待处理")
        print(f"[AGENT] 输出目录: {output_dir}")
        print(f"[AGENT] 使用 RAG: {use_rag}")
        print()

        success_count = 0
        for i, md_file in enumerate(md_files, start=start_idx if input_file is None else 1):
            # 如果指定了 target_plan，使用它作为输出文件名
            if target_plan is not None:
                output_file = output_path / f"plan_{target_plan}.log"
            else:
                # 如果指定了 input_file，使用原始文件名提取的数字
                if input_file is not None:
                    match = re.search(r'Paper_(\d+)', md_file.name)
                    if match:
                        file_num = int(match.group(1))
                        output_file = output_path / f"plan_{file_num}.log"
                    else:
                        output_file = output_path / f"plan_{i}.log"
                else:
                    output_file = output_path / f"plan_{i}.log"

            if self.process_single_file(md_file, output_file, use_rag=use_rag, feedback_file=feedback_file):
                success_count += 1

            # 避免API速率限制和端口耗尽 - 增加延迟到5秒
            if i < (len(md_files) + (start_idx if input_file is None else 1) - 1):
                sleep_between_requests(seconds=5.0)

        print()
        print(f"[AGENT] 批量处理完成!")
        print(f"[AGENT] 成功: {success_count}/{len(md_files)}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="将 Pipelines 中的 Markdown 文件转换为工作站流程"
    )
    parser.add_argument(
        "--input", "-i",
        default="/opt/data/private/src/Pipelines",
        help="输入目录 (默认: /opt/data/private/src/Pipelines)"
    )
    parser.add_argument(
        "--output", "-o",
        default="/opt/data/private/src/pipeline_workstation_logs",
        help="输出目录 (默认: /opt/data/private/src/pipeline_workstation_logs)"
    )
    parser.add_argument(
        "--start", "-s",
        type=int,
        default=1,
        help="起始索引 (默认: 1)"
    )
    parser.add_argument(
        "--end", "-e",
        type=int,
        default=None,
        help="结束索引 (默认: 处理全部)"
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=None,
        help="批次大小 (默认: 处理全部)"
    )
    parser.add_argument(
        "--model", "-m",
        default="gpt-4o",
        help="OpenAI 模型 (默认: gpt-4o)"
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="禁用 RAG 增强提示（默认启用）"
    )
    parser.add_argument(
        "--feedback", "-f",
        type=str,
        default=None,
        help="反馈文件路径（包含失败分析和建议，用于重新生成）"
    )
    parser.add_argument(
        "--target-plan",
        type=int,
        default=None,
        help="目标 plan 编号（用于覆盖指定的 plan 文件，而不是按照 paper 编号命名）"
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default=None,
        help="直接指定要处理的 Paper 文件名（如 Paper_8.md），优先级高于 --start"
    )

    args = parser.parse_args()

    # 创建 Agent
    agent = PipelineToWorkstationAgent(model=args.model)

    # 批量处理
    agent.process_batch(
        input_dir=args.input,
        output_dir=args.output,
        start_idx=args.start,
        end_idx=args.end,
        batch_size=args.batch_size,
        use_rag=not args.no_rag,
        feedback_file=args.feedback,
        target_plan=args.target_plan,
        input_file=args.input_file
    )


if __name__ == "__main__":
    main()
