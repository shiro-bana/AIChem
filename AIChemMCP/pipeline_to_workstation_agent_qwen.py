#!/usr/bin/env python3
"""
使用 Agent 形式调用 Qwen API 将 Pipelines 中的 Markdown 文件转换为工作站流程
模仿 pipeline_to_workstation_agent_plusConstraints.py 的结构，使用 Qwen API
支持思考过程输出和选择理由说明
"""

import os
import sys
import json
import re
import importlib.util
import time
from pathlib import Path
from typing import List, Dict, Optional
from openai import OpenAI

# 导入 RAGDatabase
sys.path.append('/opt/data/private/src/AIChemMCP')
from rag_database import RAGDatabase


# Qwen API 配置
QWEN_API_KEY_FILE = "/opt/data/private/src/AIChemMCP/static/QWEN_API_KEY"
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_MODEL = "qwen-max"  # 可选: qwen-max, qwen-plus, qwen-turbo


def load_qwen_api_key():
    """加载 Qwen API Key"""
    if os.path.exists(QWEN_API_KEY_FILE):
        with open(QWEN_API_KEY_FILE, 'r') as f:
            return f.read().strip()
    else:
        raise ValueError(f"Qwen API Key 文件不存在: {QWEN_API_KEY_FILE}")


def create_qwen_client():
    """创建 Qwen 客户端"""
    api_key = load_qwen_api_key()
    return OpenAI(
        api_key=api_key,
        base_url=QWEN_BASE_URL,
    )


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

    # 将工作站父目录添加到 Python 路径中
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
            print(f"[ERROR] 加载失败 {filename}: {e}")
            continue

    return workstation_notes


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


class PipelineToWorkstationAgentQwen:
    """将实验流程 Markdown 文件转换为工作站流程的 Agent (使用 Qwen API)"""

    def __init__(self, model=QWEN_MODEL, rag_db_path="/opt/data/private/src/AIChemMCP/rag_database.json",
                 workstation_dir="/opt/data/private/src/AIChem-LaboratorySimulator-main/src/workstation_instances",
                 transformations_path="/opt/data/private/src/AIChemMCP/workstation_transformations_agent.json"):
        # 创建 Qwen 客户端
        self.client = create_qwen_client()
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
        """加载工作站转换信息 JSON 文件"""
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
                        key_transforms.append(f"相态: {pt['from']} → {pt['to']}")
                    elif isinstance(pt, list) and len(pt) > 0:
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
        prompt += "你需要先进行思考分析，然后返回结果。\n\n"
        prompt += "## 思考过程（Thinking）\n"
        prompt += "在返回结果之前，请先进行以下思考：\n"
        prompt += "1. **实验步骤识别**: 识别实验文档中的所有关键步骤\n"
        prompt += "2. **工作站匹配分析**: 对每个步骤，分析为什么选择特定的工作站\n"
        prompt += "   - 该步骤需要什么操作？（如加热、搅拌、测量、分离等）\n"
        prompt += "   - 哪些工作站能够执行这个操作？\n"
        prompt += "   - 为什么选择这个工作站而不是其他类似的工作站？\n"
        prompt += "3. **兼容性验证**: 检查相邻工作站的输入输出是否兼容\n"
        prompt += "   - 相态是否匹配？（如液体→液体，固体→固体）\n"
        prompt += "   - 容器是否匹配？（如 rack→plate 是单向转换）\n"
        prompt += "   - 如果不兼容，需要添加什么中间工作站？\n"
        prompt += "4. **流程优化**: 是否有冗余步骤？是否可以简化？\n\n"
        prompt += "## 输出格式\n"
        prompt += "你必须返回一个 JSON 格式，包含以下字段：\n"
        prompt += "```json\n"
        prompt += "{\n"
        prompt += "  \"question\": \"用一句话描述这个实验要解决的问题或目标\",\n"
        prompt += "  \"thinking\": \"你的详细思考过程，包括步骤识别、工作站选择理由、兼容性分析等\",\n"
        prompt += "  \"workstations\": [\n"
        prompt += "    {\n"
        prompt += "      \"name\": \"工作站名称\",\n"
        prompt += "      \"reason\": \"选择该工作站的详细理由，包括：1) 该步骤需要什么操作 2) 为什么这个工作站合适 3) 与前一步骤的兼容性考虑\"\n"
        prompt += "    },\n"
        prompt += "    ...\n"
        prompt += "  ]\n"
        prompt += "}\n"
        prompt += "```\n\n"

        prompt += "重要提示：\n"
        prompt += "1. **question 应该是一个简洁的问题描述**，例如：'如何制备金纳米粒子与光谱表征？'\n"
        prompt += "2. **thinking 字段必须包含详细的思考过程**，展示你的分析逻辑\n"
        prompt += "3. **每个工作站的 reason 必须详细说明**：\n"
        prompt += "   - 该步骤对应的实验操作是什么\n"
        prompt += "   - 为什么选择这个工作站（引用该工作站的功能特点）\n"
        prompt += "   - 兼容性考虑（与前一步骤的输入输出匹配）\n"
        prompt += "4. 只能使用上述列出的工作站名称，不能添加新的工作站名称\n"
        prompt += "5. **必须严格遵守每个工作站的输入输出约束**，特别是相态、容器和体积要求\n"

        return prompt

    def _format_requirements(self, req: any) -> str:
        """格式化要求信息为字符串"""
        if isinstance(req, dict):
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
        """构建包含RAG上下文的增强提示"""
        base_prompt = self.build_system_prompt()
        query = markdown_content[:500]

        print(f"[AGENT] 正在从RAG数据库中查找相关的历史实验流程...")
        context = self.rag_db.get_relevant_context(query, top_k)

        rag_prompt = base_prompt + "\n# 相关历史实验流程参考 (RAG Context)\n"
        rag_prompt += "---\n"
        rag_prompt += context
        rag_prompt += "---\n\n"
        rag_prompt += "# 使用RAG上下文的指导原则\n"
        rag_prompt += "1. **优先使用RAG示例中的工作站名称**: 如果RAG示例中显示了带「[原名称: xxx]」的工作站，**必须优先使用完整名称**\n"
        rag_prompt += "2. **参考历史经验**: 仔细分析上述相关的历史实验流程，学习其工作站选择和顺序安排\n"
        rag_prompt += "3. **避免重复错误**: 如果历史流程中有遇到兼容性问题，请参考其解决方案\n"
        rag_prompt += "4. **灵活应用**: 根据当前实验的具体需求，在参考历史的基础上进行调整\n"
        rag_prompt += "5. **确保兼容性**: 参考历史流程中的兼容性处理方式（如相态转换、容器匹配等）\n"
        rag_prompt += "6. **特别提醒 - 离心操作的选择**:\n"
        rag_prompt += "   - 如果实验涉及纳米颗粒、催化剂、材料合成：使用 \"离心纯化工作站\"\n"
        rag_prompt += "   - 如果实验涉及生物样品分离：使用 \"离心机\"\n\n"

        if feedback_text:
            rag_prompt += "\n# 上次生成的失败反馈 (必须参考)\n"
            rag_prompt += "---\n"
            rag_prompt += feedback_text
            rag_prompt += "---\n\n"
            rag_prompt += "# 重要提示：基于反馈的改进要求\n"
            rag_prompt += "1. **必须解决上次失败的根本原因**\n"
            rag_prompt += "2. **只能使用预定义的工作站**\n"
            rag_prompt += "3. **不要添加'盖子操作'**\n"
            rag_prompt += "4. **解决兼容性问题**\n\n"

        return rag_prompt

    def extract_workflow_from_markdown(self, markdown_content: str, use_rag: bool = True, max_attempts: int = 3, feedback_text: str = None) -> Dict[str, any]:
        """
        使用 Qwen API 从 Markdown 内容中提取工作流

        Args:
            markdown_content: Markdown 文件内容
            use_rag: 是否使用 RAG 增强提示（默认 True）
            max_attempts: 最大生成尝试次数
            feedback_text: 反馈文本（包含失败分析和建议）

        Returns:
            Dict[str, any]: 包含 question, thinking, 和 workstations 的字典
        """
        if feedback_text:
            use_rag = True
        base_system_prompt = self.build_rag_enhanced_prompt(markdown_content, top_k=3, feedback_text=feedback_text) if use_rag else self.build_system_prompt()

        user_prompt = f"""请分析以下实验流程 Markdown 文档：
1. 提取实验要解决的问题或目标（用一个问题表述）
2. 识别实验步骤并将每个步骤映射到最合适的工作站
3. 在 thinking 字段中详细说明你的分析过程
4. 为每个工作站提供选择理由

文档内容：
```
{markdown_content[:10000]}
```

要求：
1. 仔细阅读文档，理解实验要解决的问题或目标
2. 将每个步骤映射到最合适的工作站
3. 确保工作流的顺序合理，检查兼容性
4. 只使用提供的工作站列表中的名称
5. 返回纯 JSON 格式，不要包含其他文本
6. **thinking 字段必须详细**，包括步骤识别、工作站选择理由、兼容性分析等
7. **每个工作站必须有详细的 reason**，说明为什么选择该工作站
"""

        for attempt in range(max_attempts):
            current_system_prompt = base_system_prompt
            if attempt > 0:
                current_system_prompt += f"\n\n# 重要提醒：上次生成的计划存在兼容性问题，请参考上述问题描述重新生成。"

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": current_system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1
                )

                result_text = response.choices[0].message.content

                # 解析 JSON
                try:
                    if "```json" in result_text:
                        json_str = result_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in result_text:
                        json_str = result_text.split("```")[1].strip()
                    else:
                        json_str = result_text.strip()

                    result = json.loads(json_str)
                    question = result.get("question", "")
                    thinking = result.get("thinking", "")
                    workstations_data = result.get("workstations", [])

                    # 提取工作站名称列表
                    workstations = []
                    for ws_item in workstations_data:
                        if isinstance(ws_item, dict):
                            ws_name = ws_item.get("name", "")
                            if ws_name in self.workstations:
                                workstations.append(ws_name)
                        elif isinstance(ws_item, str) and ws_item in self.workstations:
                            workstations.append(ws_item)

                    if not question:
                        question = "实验流程处理"

                    # 检查兼容性
                    compatibility_result = self.check_plan_compatibility(workstations)

                    if compatibility_result['compatible']:
                        print(f"  ✓ 兼容性检查通过")
                        return {
                            "question": question,
                            "thinking": thinking,
                            "workstations": workstations,
                            "workstations_with_reasons": workstations_data
                        }
                    else:
                        print(f"  ⚠ 兼容性问题 (尝试 {attempt + 1}/{max_attempts}):")
                        for issue in compatibility_result['issues']:
                            print(f"    - {issue}")

                        if attempt < max_attempts - 1:
                            print(f"  → 正在重新生成...")
                            user_prompt += f"\n\n上次生成的计划存在以下兼容性问题：\n"
                            for issue in compatibility_result['issues']:
                                user_prompt += f"- {issue}\n"
                            user_prompt += "\n请重新生成计划，确保解决这些兼容性问题。"
                            time.sleep(1)
                        else:
                            print(f"  ⚠ 警告: 达到最大尝试次数，返回可能有兼容性问题的计划")
                            return {
                                "question": question,
                                "thinking": thinking,
                                "workstations": workstations,
                                "workstations_with_reasons": workstations_data
                            }

                except json.JSONDecodeError as e:
                    print(f"  JSON 解析错误: {e}")
                    if attempt < max_attempts - 1:
                        continue
                    else:
                        raise

            except Exception as e:
                print(f"  API 调用错误 (尝试 {attempt + 1}/{max_attempts}): {e}")
                if attempt < max_attempts - 1:
                    time.sleep(2)
                    continue
                else:
                    raise

        return {"question": "实验流程处理", "thinking": "", "workstations": [], "workstations_with_reasons": []}

    def check_plan_compatibility(self, workstations: List[str]) -> dict:
        """检查工作流计划的兼容性"""
        if not workstations or len(workstations) <= 1:
            return {'compatible': True, 'issues': []}

        if not self.workstation_transformations:
            print("[WARNING] 未加载转换数据，使用硬编码兼容性规则")
            return self._check_compatibility_hardcoded(workstations)

        compatibility_issues = []

        for i in range(len(workstations) - 1):
            current = workstations[i]
            next_ws = workstations[i + 1]

            current_trans = self.workstation_transformations.get(current, {})
            next_trans = self.workstation_transformations.get(next_ws, {})

            if not current_trans or not next_trans:
                continue

            current_output = current_trans.get('output_state', {})
            next_input = next_trans.get('input_requirements', {})

            # 检查相态兼容性
            current_phase = self._extract_phase_info(current_output)
            next_phase_requirement = self._extract_phase_requirement(next_input)

            if current_phase and next_phase_requirement:
                if not self._is_phase_compatible(current_phase, next_phase_requirement):
                    compatibility_issues.append(
                        f"步骤 {i+1}→{i+2}: {current} → {next_ws} 相态不兼容: "
                        f"{current} 输出相态为 {current_phase}，但 {next_ws} 要求 {next_phase_requirement}"
                    )

            # 检查容器兼容性
            current_container = self._extract_container_info(current_output)
            next_container_requirement = self._extract_container_requirement(next_input)

            if current_container and next_container_requirement:
                if not self._is_container_compatible(current_container, next_container_requirement):
                    is_reverse_conversion = (
                        current_container in ['24_hole_plate', '48_hole_plate', '96_hole_plate', 'vial'] and
                        next_container_requirement == 'rack'
                    )

                    if is_reverse_conversion:
                        suggestion = "⚠️ 反向容器转换不存在！请重新设计流程"
                    else:
                        suggestion = "建议: 检查工作站的容器要求"

                    compatibility_issues.append(
                        f"步骤 {i+1}→{i+2}: {current} → {next_ws} 容器不兼容: "
                        f"{current} 输出容器为 {current_container}，但 {next_ws} 要求 {next_container_requirement}。{suggestion}"
                    )

        return {
            'compatible': len(compatibility_issues) == 0,
            'issues': compatibility_issues
        }

    def _check_compatibility_hardcoded(self, workstations: List[str]) -> dict:
        """使用硬编码规则进行兼容性检查"""
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
                'solution': '需要添加液体进样站'
            },
            {
                'from': ['烘干机'],
                'to': ['高通量酶标仪工作站'],
                'issue': '烘干机输出固体，酶标仪要求液体；且容器不匹配',
                'solution': '需要添加液体分散步骤和容器转换'
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
                return phase
            if isinstance(phase, str) and 'same as input' in phase.lower():
                return 'any'
            return str(phase) if phase else ''
        return ''

    def _extract_phase_requirement(self, req: dict) -> str:
        """从要求中提取相态要求"""
        if isinstance(req, dict):
            phase = req.get('phase')
            if isinstance(phase, list):
                return phase[0] if phase else ''
            if isinstance(phase, str) and 'same as input' in phase.lower():
                return 'any'
            return str(phase) if phase else ''
        return ''

    def _is_phase_compatible(self, output_phase: any, input_phase_req: str) -> bool:
        """检查相态是否兼容"""
        if input_phase_req.lower() == 'any':
            return True
        if output_phase == 'any' or (isinstance(output_phase, str) and output_phase.lower() == 'any'):
            return True
        if isinstance(output_phase, list):
            for op in output_phase:
                if self._check_single_phase_compatible(op, input_phase_req):
                    return True
            return False
        return self._check_single_phase_compatible(output_phase, input_phase_req)

    def _check_single_phase_compatible(self, output_phase: str, input_phase_req: str) -> bool:
        """检查单个相态是否兼容"""
        if output_phase == input_phase_req:
            return True

        compatible_phases = {
            'liquid': ['liquid', 'suspension', 'slurry'],
            'suspension': ['suspension', 'liquid', 'solid_liquid_separated', 'solid_with_liquid_overlay'],
            'slurry': ['slurry', 'suspension', 'liquid'],
            'solid': ['solid', 'solid_with_tiny_liquid'],
            'solid_liquid_separated': ['solid_liquid_separated', 'suspension', 'solid', 'liquid'],
        }

        if output_phase in compatible_phases:
            return input_phase_req in compatible_phases[output_phase]
        return False

    def _extract_container_info(self, state: dict) -> str:
        """从状态中提取容器信息"""
        if isinstance(state, dict):
            container = state.get('container')
            if isinstance(container, list):
                return container[0] if container else ''
            if isinstance(container, str) and 'same as input' in container.lower():
                return 'any'
            return str(container) if container else ''
        return ''

    def _extract_container_requirement(self, req: dict) -> str:
        """从要求中提取容器要求"""
        if isinstance(req, dict):
            container = req.get('container')
            if isinstance(container, list):
                return container[0] if container else ''
            if isinstance(container, str) and 'same as input' in container.lower():
                return 'any'
            return str(container) if container else ''
        return ''

    def _is_container_compatible(self, output_container: str, input_container_req: str) -> bool:
        """检查容器是否兼容"""
        if input_container_req.lower() == 'any':
            return True
        if output_container == 'any' or (isinstance(output_container, str) and output_container.lower() == 'any'):
            return True
        if output_container == input_container_req:
            return True

        allowed_conversions = [
            ('rack', '24_hole_plate'),
            ('rack', '48_hole_plate'),
            ('rack', '96_hole_plate'),
            ('rack', 'vial'),
        ]

        for from_container, to_container in allowed_conversions:
            if output_container == from_container and input_container_req == to_container:
                return True
        return False

    def generate_plan_log(self, question: str, thinking: str, workflow: List[str], workstations_with_reasons: List[Dict], paper_name: str) -> str:
        """生成 plan_X.log 格式的输出"""
        output = []
        output.append(f"问题: {question}")
        output.append("")
        output.append("=== 思考过程 ===")
        output.append(thinking)
        output.append("")
        output.append("=== 第 1 次执行计划 ===")

        for i, ws_data in enumerate(workstations_with_reasons, 1):
            if isinstance(ws_data, dict):
                ws_name = ws_data.get("name", "")
                ws_reason = ws_data.get("reason", "")
                output.append(f"  步骤 {i}: {{'method': '{ws_name}', 'params': {{}}}}")
                if ws_reason:
                    output.append(f"    理由: {ws_reason}")
            else:
                output.append(f"  步骤 {i}: {{'method': '{ws_data}', 'params': {{}}}}")

        output.append("")
        return '\n'.join(output)

    def process_single_file(self, md_file: Path, output_file: Path, use_rag: bool = True, feedback_file: str = None) -> bool:
        """处理单个 Markdown 文件"""
        print(f"处理: {md_file.name}")

        feedback_text = None
        if feedback_file and os.path.exists(feedback_file):
            print(f"  [INFO] 使用反馈文件: {feedback_file}")
            with open(feedback_file, 'r', encoding='utf-8') as f:
                feedback_text = f.read()
        elif feedback_file:
            print(f"  [WARNING] 反馈文件不存在: {feedback_file}")

        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            result = self.extract_workflow_from_markdown(content, use_rag=use_rag, feedback_text=feedback_text)
            question = result.get("question", "实验流程处理")
            thinking = result.get("thinking", "")
            workflow = result.get("workstations", [])
            workstations_with_reasons = result.get("workstations_with_reasons", [])

            if not workflow:
                print(f"  警告: 未提取到工作流，使用默认流程")
                question = "实验流程处理"
                thinking = "未提取到有效工作流，使用默认流程"
                workflow = ["物料站", "1ml液体进样站", "磁力搅拌工作站"]
                workstations_with_reasons = [
                    {"name": "物料站", "reason": "默认：获取实验材料"},
                    {"name": "1ml液体进样站", "reason": "默认：精确移液"},
                    {"name": "磁力搅拌工作站", "reason": "默认：搅拌混合"}
                ]

            plan_log = self.generate_plan_log(question, thinking, workflow, workstations_with_reasons, md_file.stem)

            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# Source: {md_file.name}\n")
                f.write(f"# Generated: {__import__('datetime').datetime.now().isoformat()}\n")
                f.write(f"# Model: {self.model}\n")
                f.write(plan_log)

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
                     target_plan: int = None, input_file: str = None):
        """批量处理 Pipeline 文件"""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if input_file is not None:
            md_files = [input_path / input_file]
            if not md_files[0].exists():
                print(f"[ERROR] 文件不存在: {md_files[0]}")
                return
        else:
            def natural_key(path):
                match = re.search(r'Paper_(\d+)', path.name)
                if match:
                    return int(match.group(1))
                return 0

            md_files = sorted(input_path.glob("Paper_*.md"), key=natural_key)

            if end_idx is None:
                end_idx = len(md_files)
            md_files = md_files[start_idx - 1:end_idx]

            if batch_size is not None:
                md_files = md_files[:batch_size]

        print(f"[AGENT] 找到 {len(md_files)} 个 Markdown 文件待处理")
        print(f"[AGENT] 输出目录: {output_dir}")
        print(f"[AGENT] 使用 RAG: {use_rag}")
        print()

        success_count = 0
        for i, md_file in enumerate(md_files, start=start_idx if input_file is None else 1):
            if target_plan is not None:
                output_file = output_path / f"plan_{target_plan}.log"
            else:
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

            if i < (len(md_files) + (start_idx if input_file is None else 1) - 1):
                time.sleep(5.0)

        print()
        print(f"[AGENT] 批量处理完成!")
        print(f"[AGENT] 成功: {success_count}/{len(md_files)}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="将 Pipelines 中的 Markdown 文件转换为工作站流程 (使用 Qwen API，支持思考过程和理由说明)"
    )
    parser.add_argument(
        "--input", "-i",
        default="/opt/data/private/src/Pipelines",
        help="输入目录"
    )
    parser.add_argument(
        "--output", "-o",
        default="/opt/data/private/src/pipeline_workstation_logs_qwen",
        help="输出目录"
    )
    parser.add_argument("--start", "-s", type=int, default=1, help="起始索引")
    parser.add_argument("--end", "-e", type=int, default=None, help="结束索引")
    parser.add_argument("--batch-size", "-b", type=int, default=None, help="批次大小")
    parser.add_argument(
        "--model", "-m",
        default=QWEN_MODEL,
        help=f"Qwen 模型 (默认: {QWEN_MODEL})"
    )
    parser.add_argument("--no-rag", action="store_true", help="禁用 RAG")
    parser.add_argument("--feedback", "-f", type=str, default=None, help="反馈文件路径")
    parser.add_argument("--target-plan", type=int, default=None, help="目标 plan 编号")
    parser.add_argument("--input-file", type=str, default=None, help="指定 Paper 文件名")

    args = parser.parse_args()

    agent = PipelineToWorkstationAgentQwen(model=args.model)

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
