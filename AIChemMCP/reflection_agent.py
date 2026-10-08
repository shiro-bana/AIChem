#!/usr/bin/env python3
"""
反思智能体 (Reflection Agent)
读取失败的测试日志，分析兼容性问题，反馈给生成智能体
"""

import os
import sys
import re
import json
from pathlib import Path
from typing import List, Dict, Optional
from openai import OpenAI

# 导入 OpenAI 客户端配置工具
from openai_client_config import create_openai_client, sleep_between_requests


class ReflectionAgent:
    """反思智能体 - 分析失败的测试日志并提供反馈"""

    def __init__(self, model="gpt-4o", transformations_path="/opt/data/private/src/AIChemMCP/workstation_transformations_agent.json"):
        # 读取 OpenAI API Key
        api_key_file = "/opt/data/private/src/AIChemMCP/static/OPENAI_API_KEY"
        if os.path.exists(api_key_file):
            with open(api_key_file, 'r') as f:
                api_key = f.read().strip()
            os.environ["OPENAI_API_KEY"] = api_key
        else:
            raise ValueError(f"API Key 文件不存在: {api_key_file}")

        # 使用带连接池配置的客户端，避免端口耗尽
        self.client = create_openai_client(api_key=api_key)
        self.model = model
        self.transformations_path = transformations_path

        # 加载工作站转换信息
        self.transformations = self._load_transformations(transformations_path)
        print(f"[REFLECTION_AGENT] 初始化完成，模型: {self.model}")
        print(f"[REFLECTION_AGENT] 已加载 {len(self.transformations)} 个工作站的转换信息")

    def _load_transformations(self, transformations_path: str) -> Dict[str, Dict]:
        """加载工作站转换信息 JSON 文件"""
        if not os.path.exists(transformations_path):
            print(f"[WARNING] 转换信息文件不存在: {transformations_path}")
            return {}

        try:
            with open(transformations_path, 'r', encoding='utf-8') as f:
                transformations = json.load(f)
            return transformations
        except Exception as e:
            print(f"[ERROR] 加载转换信息失败: {e}")
            return {}

    def _get_workstation_transform(self, workstation_name: str) -> Optional[Dict]:
        """根据工作站名称获取转换信息"""
        # 支持多种名称匹配方式
        for key, transform in self.transformations.items():
            if workstation_name == key or workstation_name in transform.get('aliases', []):
                return transform
        return None

    def _find_compatible_workstations(self, current_phase: str, target_phase: str) -> List[str]:
        """
        查找能够实现相态转换的工作站

        Args:
            current_phase: 当前相态
            target_phase: 目标相态

        Returns:
            List[str]: 能够实现转换的工作站列表
        """
        compatible_workstations = []

        for ws_name, ws_data in self.transformations.items():
            # 检查输入要求
            input_requirements = ws_data.get('input_requirements', {})
            required_phase = input_requirements.get('phase')

            # 检查输出
            output_state = ws_data.get('output_state', {})
            output_phase = output_state.get('phase')

            # 检查相态转换
            phase_transforms = ws_data.get('phase_transform', [])
            if isinstance(phase_transforms, list):
                for transform in phase_transforms:
                    if isinstance(transform, dict):
                        from_phase = transform.get('from')
                        to_phase = transform.get('to')
                        # 检查是否能实现所需转换
                        if (from_phase == current_phase or from_phase == 'any') and \
                           (to_phase == target_phase or to_phase == 'same as input'):
                            compatible_workstations.append(ws_name)
                            break
            elif isinstance(phase_transforms, dict):
                from_phase = phase_transforms.get('from')
                to_phase = phase_transforms.get('to')
                if (from_phase == current_phase or from_phase == 'any') and \
                   (to_phase == target_phase or to_phase == 'same as input'):
                    compatible_workstations.append(ws_name)

        return compatible_workstations

    def parse_test_log(self, log_file: str) -> Dict[str, any]:
        """
        解析测试日志文件，提取关键信息

        Args:
            log_file: 测试日志文件路径

        Returns:
            Dict: 包含解析结果的字典
        """
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()

        result = {
            'log_file': log_file,
            'question': None,
            'workflow': [],
            'failed_step': None,
            'failed_step_name': None,
            'failed_constraints': [],
            'state_before_failure': {}
        }

        # 提取问题
        question_match = re.search(r'问题: (.+)', content)
        if question_match:
            result['question'] = question_match.group(1).strip()

        # 提取工作流步骤 - 尝试两种格式
        # 格式1: 从 plan log 中提取 (method 格式)
        step_matches = re.findall(r"'method': '([^']+)'", content)
        if not step_matches:
            # 格式2: 从测试日志中提取 (编号列表格式)
            step_matches = re.findall(r"  \d+\. (.+)", content)
        result['workflow'] = step_matches

        # 提取失败的步骤
        failed_pattern = r"正在执行步骤 (\d+): ([^\n]+)\n.*?❌步骤 \1 约束条件不满足\n.*?以下约束条件冲突:\n((?:[ \t]*- .+\n)*)"
        failed_match = re.search(failed_pattern, content, re.DOTALL)

        if failed_match:
            result['failed_step'] = int(failed_match.group(1))
            result['failed_step_name'] = failed_match.group(2).strip()

            # 提取冲突的约束条件
            constraints_text = failed_match.group(3)
            constraint_matches = re.findall(r'- (.+)', constraints_text)
            result['failed_constraints'] = constraint_matches

        # 提取失败前的状态
        state_pattern = r"=== 步骤 \d+ 失败前状态 ===\n" + \
                        r"容器类型: (.+)\n" + \
                        r"子容器: (.+)\n" + \
                        r"子容器数量: (.+)\n" + \
                        r"子容器体积: (.+) ml\n" + \
                        r"相态: (.+)\n" + \
                        r"是否覆盖: (.+)\n" + \
                        r"温度: (.+)°C"

        state_match = re.search(state_pattern, content)
        if state_match:
            result['state_before_failure'] = {
                'container_type': state_match.group(1).strip(),
                'subcontainer': state_match.group(2).strip(),
                'subcontainer_number': state_match.group(3).strip(),
                'volume': state_match.group(4).strip(),
                'phase': state_match.group(5).strip(),
                'covered': state_match.group(6).strip(),
                'temperature': state_match.group(7).strip()
            }

        return result

    def analyze_failure(self, log_data: Dict[str, any]) -> Dict[str, any]:
        """
        分析失败原因并提供解决方案

        Args:
            log_data: 解析后的日志数据

        Returns:
            Dict: 包含分析和建议的字典
        """
        workflow = log_data['workflow']
        failed_step = log_data['failed_step']
        failed_step_name = log_data['failed_step_name']
        failed_constraints = log_data['failed_constraints']
        state = log_data['state_before_failure']

        # 检查 workflow 是否为空
        if not workflow:
            return self._basic_analysis(log_data)

        # 获取失败的步骤及其前驱步骤
        prev_step_name = workflow[failed_step - 2] if failed_step > 1 and failed_step <= len(workflow) else None

        # 查找能够实现所需转换的工作站
        current_phase = state.get('phase', '')
        compatible_workstations = []
        if current_phase:
            # 尝试查找可能的转换工作站
            for ws_name, ws_data in self.transformations.items():
                phase_transforms = ws_data.get('phase_transform', [])
                if isinstance(phase_transforms, list):
                    for transform in phase_transforms:
                        if isinstance(transform, dict):
                            from_phase = transform.get('from', '')
                            to_phase = transform.get('to', '')
                            if from_phase == current_phase or from_phase == 'any':
                                compatible_workstations.append({
                                    'name': ws_name,
                                    'transform': f"{from_phase} → {to_phase}"
                                })
                                break

        # 构建可用工作站信息
        available_workstations_info = ""
        if compatible_workstations:
            available_workstations_info = "\n### 可用的相态转换工作站\n"
            for ws in compatible_workstations[:10]:  # 只显示前10个
                available_workstations_info += f"- {ws['name']}: {ws['transform']}\n"

        # 构建 LLM 提示
        system_prompt = f"""你是一位化学实验室流程分析专家。你的任务是分析实验流程测试失败的日志，
找出兼容性问题的根本原因，并提供具体的改进建议。

## 重要限制和成功模式

### 容器转换规则（单向，不可逆！）
- ✅ **允许的单向转换**:
  - rack → plate（通过高通量酶标仪工作站、高通量红外光谱工作站）
  - rack → vial（通过液相色谱仪、气相色谱仪）
- ❌ **反向转换不存在**:
  - plate/vial → rack（系统中没有这样的工作站！）
  - 一旦使用了孔板工作站，后续步骤必须能接受孔板，不能转回要求离心管架的工作站

### 成功的相态转换模式（参考案例）
1. **离心纯化 → 烘干机 → 固体分析**
   - 离心纯化：suspension → suspension
   - 烘干机：suspension → solid（相态转换）
   - 高通量红外光谱/高通量XRD：solid → solid（兼容）

2. **液体处理 → 固体转换**
   - 1ml液体进样站：solid → suspension
   - 离心纯化：suspension → suspension
   - 烘干机：suspension → solid
   - 固体分析：solid → solid

3. **相态兼容性**
   - suspension 可以转换为 solid（通过烘干机）
   - solid 可以被 solid_with_tiny_liquid 接受
   - solid_liquid_separated 可以被 suspension 或 solid 接受
{available_workstations_info}

### 常见的兼容性问题类型
1. **容器类型不匹配**:
   - ❌ 错误建议：添加"样品转移到孔板"工作站（不存在）
   - ✅ 正确做法：删除孔板工作站或重新设计流程

2. **相态不匹配**:
   - 例如：悬浊液需要转换为固体（可通过烘干机）

3. **盖子状态不匹配**:
   - 有些步骤需要开盖，有些需要闭盖

4. **体积限制**:
   - 酶标仪要求≤2ml
   - 离心机要求≤30ml

5. **容器数量限制**:
   - 离心机要求偶数数量的容器

请提供：
1. **根本原因**: 为什么这个流程会失败？
2. **可行性分析**: 这个问题能否通过添加中间步骤解决？还是需要重新设计流程？
3. **改进建议**: 具体应该如何修改流程？（基于实际存在的工作站）"""

        user_prompt = f"""请分析以下测试失败的实验流程：

**实验问题**: {log_data['question']}

**完整流程**:
"""

        for i, step in enumerate(workflow, 1):
            if i == failed_step:
                user_prompt += f"  {i}. {step} ❌ (在此失败)\n"
            else:
                user_prompt += f"  {i}. {step}\n"

        user_prompt += f"""

**失败的步骤**: 步骤 {failed_step} - {failed_step_name}

**冲突的约束条件**:
"""
        for constraint in failed_constraints:
            user_prompt += f"  - {constraint}\n"

        user_prompt += f"""

**失败前的样品状态**:
  - 容器类型: {state.get('container_type', 'N/A')}
  - 子容器: {state.get('subcontainer', 'N/A')}
  - 子容器数量: {state.get('subcontainer_number', 'N/A')}
  - 体积: {state.get('volume', 'N/A')} ml
  - 相态: {state.get('phase', 'N/A')}
  - 是否覆盖: {state.get('covered', 'N/A')}
  - 温度: {state.get('temperature', 'N/A')}°C

**前驱步骤**: {prev_step_name if prev_step_name else '无（这是第一步）'}

**前驱步骤输出的状态**: {workflow[failed_step-3] if failed_step > 2 else '初始状态'}

请分析：
1. 为什么在 {prev_step_name if prev_step_name else '初始状态'} 之后不能直接执行 {failed_step_name}？
2. 中间缺少了什么转换步骤？
3. 应该如何修改流程？

请以 JSON 格式返回：
{{
  "root_cause": "根本原因描述",
  "missing_step_type": "缺失的步骤类型（如：样品转移、相态转换、盖子操作等）",
  "insert_position": "应该在哪个步骤之前插入（步骤编号或步骤名称）",
  "suggested_workflow": ["修正后的流程步骤列表"],
  "explanation": "详细解释为什么需要这个修改"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result_text = response.choices[0].message.content
            analysis = json.loads(result_text)

            return analysis

        except Exception as e:
            print(f"[ERROR] LLM 分析失败: {e}")
            # 返回基础分析
            return self._basic_analysis(log_data)

    def _basic_analysis(self, log_data: Dict[str, any]) -> Dict[str, any]:
        """
        基础分析（当 LLM 调用失败时使用）

        Args:
            log_data: 日志数据

        Returns:
            Dict: 基础分析结果
        """
        workflow = log_data['workflow']
        failed_step = log_data['failed_step']
        failed_step_name = log_data['failed_step_name']
        failed_constraints = log_data['failed_constraints']
        state = log_data['state_before_failure']

        # 简单的规则匹配
        root_cause = "状态不兼容"
        missing_step_type = "转换步骤"
        insert_position = failed_step
        explanation = ""
        is_feasible = True  # 默认认为可以通过添加步骤解决

        # 检查反向容器转换（plate/vial → rack）- 不可行！
        if ('容器类型为离心管架' in str(failed_constraints) or '容器必须是离心管架' in str(failed_constraints)) and \
           state.get('container_type') in ['24_hole_plate', '48_hole_plate', '96_hole_plate', 'vial']:
            root_cause = f"容器类型不匹配：当前使用{state.get('container_type')}，但{failed_step_name}要求离心管架(rack)"
            missing_step_type = "无法添加：反向容器转换不存在"
            explanation = f"⚠️ 系统中没有将孔板/色谱瓶转换回离心管架的工作站！建议：删除步骤 {failed_step-1} 的孔板工作站，或删除 {failed_step_name}，重新设计流程避免使用孔板工作站"
            is_feasible = False

        # 检查相态不匹配 - 提供基于成功案例的建议
        elif '相态' in str(failed_constraints):
            current_phase = state.get('phase', '')
            root_cause = f"相态不匹配：当前相态为{current_phase}，但{failed_step_name}要求不同的相态"

            # 根据当前相态和目标相态，给出具体的转换建议
            if current_phase == 'suspension' and '固体' in str(failed_constraints):
                missing_step_type = "烘干机（相态转换）"
                explanation = f"参考成功案例：可以在步骤 {failed_step-1} 和 {failed_step} 之间添加烘干机，将悬浊液(suspension)转换为固体(solid)"
            elif current_phase == 'liquid' and '固体' in str(failed_constraints):
                missing_step_type = "烘干机或离心纯化"
                explanation = f"需要在步骤 {failed_step-1} 和 {failed_step} 之间添加转换步骤：如离心纯化（liquid→suspension）+ 烘干机（suspension→solid）"
            elif current_phase == 'solid' and '液体' in str(failed_constraints):
                missing_step_type = "液体进样站"
                explanation = f"需要在步骤 {failed_step-1} 和 {failed_step} 之间添加液体进样站，将固体转换为液体或悬浊液"
            else:
                missing_step_type = "相态转换步骤"
                explanation = f"需要在步骤 {failed_step-1} 和 {failed_step} 之间添加相态转换步骤"

        # 检查盖子状态不匹配
        elif '盖子' in str(failed_constraints):
            root_cause = f"盖子状态不匹配：当前为{state.get('covered')}，但{failed_step_name}要求不同的盖子状态"
            missing_step_type = "盖子操作步骤"
            explanation = f"需要在步骤 {failed_step-1} 和 {failed_step} 之间添加{'盖上盖子' if state.get('covered') == 'False' else '打开盖子'}的步骤"

        # 检查体积限制
        elif '体积' in str(failed_constraints):
            root_cause = f"体积超限：当前体积{state.get('volume')}ml，但{failed_step_name}有体积限制"
            missing_step_type = "取样或稀释步骤"
            explanation = f"需要在步骤 {failed_step-1} 和 {failed_step} 之间添加取样或稀释步骤"

        # 检查容器类型不匹配（其他情况）
        elif '容器' in str(failed_constraints):
            root_cause = f"容器类型不匹配：当前使用{state.get('container_type')}，但{failed_step_name}要求不同的容器"
            missing_step_type = "检查兼容性"
            explanation = f"需要检查步骤 {failed_step-1} 输出的容器类型与 {failed_step_name} 要求的容器类型是否兼容"

        # 生成建议的工作流
        if is_feasible:
            suggested_workflow = workflow[:failed_step-1] + [f"建议添加: {missing_step_type}"] + workflow[failed_step-1:]
        else:
            # 不可行的建议：删除问题步骤
            suggested_workflow = workflow[:failed_step-1] + [f"⚠️ 删除或重新设计"] + workflow[failed_step-1:]

        # 添加可行性标记到返回结果
        result = {
            'root_cause': root_cause,
            'missing_step_type': missing_step_type,
            'insert_position': f"步骤{failed_step}之前",
            'suggested_workflow': suggested_workflow,
            'explanation': explanation,
            'is_feasible': is_feasible
        }

        return result

    def generate_feedback_for_generator(self, log_file: str) -> str:
        """
        生成反馈信息，用于提供给生成智能体

        Args:
            log_file: 失败的测试日志文件

        Returns:
            str: 反馈信息
        """
        # 解析日志
        log_data = self.parse_test_log(log_file)

        # 分析失败
        analysis = self.analyze_failure(log_data)

        # 生成反馈
        is_feasible = analysis.get('is_feasible', True)

        feasibility_section = ""
        if not is_feasible:
            feasibility_section = """
**⚠️ 可行性分析**: 这个问题**无法通过添加中间步骤解决**，需要重新设计流程，避免使用不可逆的容器转换。"""

        feedback = f"""# 反馈：流程兼容性问题分析

## 测试失败的流程
- 问题: {log_data['question']}
- 原始流程: {' → '.join(log_data['workflow'])}
- 失败步骤: 步骤 {log_data['failed_step']} - {log_data['failed_step_name']}

## 问题分析
**根本原因**: {analysis['root_cause']}

**缺失的步骤类型**: {analysis['missing_step_type']}

**插入位置**: {analysis['insert_position']}{feasibility_section}

**详细解释**: {analysis['explanation']}

## 建议的修正流程
{(' → '.join(analysis['suggested_workflow']))}

## 对生成智能体的建议

### 容器转换规则（严格遵守）
- ✅ **允许的单向转换**: rack → plate/vial（通过高通量酶标仪、红外光谱、液相色谱、气相色谱等）
- ❌ **反向转换不存在**: plate/vial → rack（系统中没有这样的工作站！）
- ⚠️  一旦使用了孔板工作站，后续步骤必须能接受孔板容器，不能使用要求离心管架的工作站

### 成功的相态转换模式（参考案例）
1. **离心纯化 → 烘干机 → 固体分析**
   - 离心纯化：suspension → suspension
   - 烘干机：suspension → solid（相态转换）
   - 高通量红外光谱/高通量XRD：solid → solid（兼容）

2. **液体处理 → 固体转换**
   - 1ml液体进样站：solid → suspension
   - 离心纯化：suspension → suspension
   - 烘干机：suspension → solid
   - 固体分析：solid → solid

### 具体建议
在生成类似的实验流程时，请注意：
1. 当流程中包含 {log_data['workflow'][log_data['failed_step']-2] if log_data['failed_step'] > 1 else '初始状态'} 时，如果后续需要 {log_data['failed_step_name']}，必须先添加 {analysis['missing_step_type']}
2. 确保流程中的状态转换是连续的，不要跳过必要的中间步骤
3. 如果遇到反向容器转换问题，删除孔板工作站或重新设计流程，不要尝试添加不存在的转换步骤
4. 在生成流程后，进行兼容性检查，验证相邻步骤之间的输入输出是否匹配
"""

        return feedback

    def batch_analyze_logs(self, log_dir: str, output_file: str = None) -> List[Dict[str, any]]:
        """
        批量分析失败的测试日志

        Args:
            log_dir: 日志目录
            output_file: 输出文件路径（可选）

        Returns:
            List[Dict]: 所有分析结果
        """
        log_path = Path(log_dir)
        results = []

        # 找到所有测试日志文件
        log_files = sorted(log_path.glob("test_log_*.txt"))

        print(f"[REFLECTION_AGENT] 找到 {len(log_files)} 个测试日志文件")

        for log_file in log_files:
            print(f"\n[REFLECTION_AGENT] 分析: {log_file.name}")

            try:
                # 解析日志
                log_data = self.parse_test_log(str(log_file))

                # 只分析失败的日志
                if log_data['failed_step']:
                    # 分析失败
                    analysis = self.analyze_failure(log_data)

                    results.append({
                        'log_file': str(log_file),
                        'log_data': log_data,
                        'analysis': analysis
                    })

                    print(f"  失败步骤: {log_data['failed_step']} - {log_data['failed_step_name']}")
                    print(f"  根本原因: {analysis['root_cause']}")

            except Exception as e:
                print(f"  错误: {e}")
                continue

        # 保存结果
        if output_file and results:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n[REFLECTION_AGENT] 分析结果已保存到: {output_file}")

        return results

    def extract_learning_rules(self, analysis_results: List[Dict[str, any]]) -> List[Dict[str, str]]:
        """
        从分析结果中提取学习规则

        Args:
            analysis_results: 分析结果列表

        Returns:
            List[Dict]: 学习规则列表
        """
        rules = []

        for result in analysis_results:
            log_data = result['log_data']
            analysis = result['analysis']

            workflow = log_data['workflow']
            failed_step = log_data['failed_step']

            # 获取前驱步骤
            prev_step = workflow[failed_step - 2] if failed_step > 1 else "初始状态"
            failed_step_name = log_data['failed_step_name']

            rule = {
                'from': prev_step,
                'to': failed_step_name,
                'issue': analysis['root_cause'],
                'solution': analysis['explanation']
            }

            rules.append(rule)

        return rules


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="反思智能体 - 分析失败的测试日志")
    parser.add_argument(
        "--log-file", "-l",
        help="单个测试日志文件路径"
    )
    parser.add_argument(
        "--log-dir", "-d",
        default="./playground_test_logs",
        help="测试日志目录（批量分析）"
    )
    parser.add_argument(
        "--output", "-o",
        default="/opt/data/private/src/AIChemMCP/reflection_feedback.json",
        help="输出文件路径"
    )
    parser.add_argument(
        "--model", "-m",
        default="gpt-4o",
        help="OpenAI 模型"
    )
    parser.add_argument(
        "--transformations-path", "-t",
        default="/opt/data/private/src/AIChemMCP/workstation_transformations_agent.json",
        help="工作站转换信息 JSON 文件路径"
    )
    parser.add_argument(
        "--extract-rules",
        action="store_true",
        help="提取学习规则并保存"
    )

    args = parser.parse_args()

    # 创建反思智能体
    agent = ReflectionAgent(model=args.model, transformations_path=args.transformations_path)

    if args.log_file:
        # 分析单个日志文件
        print("=" * 80)
        print("反思智能体 - 单个日志分析")
        print("=" * 80)

        feedback = agent.generate_feedback_for_generator(args.log_file)
        print(feedback)

        # 保存反馈
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(feedback)
        print(f"\n[REFLECTION_AGENT] 反馈已保存到: {args.output}")

    elif args.log_dir:
        # 批量分析日志文件
        print("=" * 80)
        print("反思智能体 - 批量日志分析")
        print("=" * 80)

        results = agent.batch_analyze_logs(args.log_dir, args.output)

        # 提取学习规则
        if args.extract_rules and results:
            rules = agent.extract_learning_rules(results)

            rules_file = args.output.replace('.json', '_rules.json')
            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)

            print(f"\n[REFLECTION_AGENT] 提取了 {len(rules)} 条学习规则")
            print(f"[REFLECTION_AGENT] 规则已保存到: {rules_file}")

            # 打印规则
            print("\n" + "=" * 80)
            print("提取的学习规则")
            print("=" * 80)
            for i, rule in enumerate(rules, 1):
                print(f"\n规则 {i}:")
                print(f"  从: {rule['from']}")
                print(f"  到: {rule['to']}")
                print(f"  问题: {rule['issue']}")
                print(f"  解决方案: {rule['solution']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
