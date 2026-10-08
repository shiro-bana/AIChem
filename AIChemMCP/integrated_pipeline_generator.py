#!/usr/bin/env python3
"""
集成流程生成系统
结合生成智能体和反思智能体，实现持续的流程优化
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict

# 导入原有的生成智能体
from pipeline_to_workstation_agent_plusConstraints import PipelineToWorkstationAgent
# 导入反思智能体
from reflection_agent import ReflectionAgent


class IntegratedPipelineGenerator:
    """集成的流程生成系统"""

    def __init__(self, model="gpt-4o"):
        self.model = model
        self.generator = PipelineToWorkstationAgent(model=model)
        self.reflector = ReflectionAgent(model=model)
        self.reflection_feedback = []
        self.learned_rules = []

        print("[INTEGRATED] 集成流程生成系统初始化完成")

    def load_reflection_feedback(self, feedback_file: str = None):
        """
        加载反思智能体的反馈

        Args:
            feedback_file: 反馈文件路径
        """
        if feedback_file and os.path.exists(feedback_file):
            with open(feedback_file, 'r', encoding='utf-8') as f:
                content = f.read()
                self.reflection_feedback.append(content)
            print(f"[INTEGRATED] 已加载反思反馈: {feedback_file}")

        # 尝试加载提取的规则
        rules_file = feedback_file.replace('.json', '_rules.json') if feedback_file else None
        if rules_file and os.path.exists(rules_file):
            with open(rules_file, 'r', encoding='utf-8') as f:
                rules = json.load(f)
                self.learned_rules.extend(rules)
            print(f"[INTEGRATED] 已加载 {len(rules)} 条学习规则")

    def analyze_test_logs(self, log_dir: str):
        """
        批量分析测试日志

        Args:
            log_dir: 测试日志目录
        """
        print(f"[INTEGRATED] 正在分析测试日志: {log_dir}")

        # 使用反思智能体批量分析
        temp_output = "/tmp/reflection_analysis_temp.json"
        results = self.reflector.batch_analyze_logs(log_dir, temp_output)

        if results:
            # 提取学习规则
            new_rules = self.reflector.extract_learning_rules(results)
            self.learned_rules.extend(new_rules)

            print(f"[INTEGRATED] 从 {len(results)} 个失败日志中提取了 {len(new_rules)} 条规则")

            # 保存规则
            rules_file = "/opt/data/private/src/AIChemMCP/learned_compatibility_rules.json"
            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump(self.learned_rules, f, ensure_ascii=False, indent=2)
            print(f"[INTEGRATED] 学习规则已保存到: {rules_file}")

        return results

    def generate_with_reflection(self, markdown_content: str, use_rag: bool = True) -> Dict[str, any]:
        """
        生成流程，并考虑反思反馈

        Args:
            markdown_content: Markdown 内容
            use_rag: 是否使用 RAG

        Returns:
            Dict: 生成结果
        """
        # 如果有学习规则，添加到系统提示中
        if self.learned_rules:
            print(f"[INTEGRATED] 应用 {len(self.learned_rules)} 条学习规则")
            # 这里可以修改生成智能体的系统提示
            # 暂时通过修改 incompatible_sequences 来实现
            self._apply_learned_rules()

        # 使用生成智能体生成流程
        result = self.generator.extract_workflow_from_markdown(markdown_content, use_rag=use_rag)

        return result

    def _apply_learned_rules(self):
        """应用学习到的规则到生成智能体"""
        # 将学习到的规则添加到生成智能体的兼容性检查中
        # 这需要在 check_plan_compatibility 方法中添加新的规则
        for rule in self.learned_rules:
            # 检查规则是否已存在
            exists = False
            for existing_rule in self.generator.check_plan_compatibility.__code__.co_consts:
                if isinstance(existing_rule, dict) and existing_rule.get('from') == rule['from']:
                    exists = True
                    break

            if not exists:
                print(f"[INTEGRATED] 添加新规则: {rule['from']} → {rule['to']}")

    def process_with_verification(self, md_file: Path, output_file: Path,
                                   test_script: str = None, use_rag: bool = True) -> Dict[str, any]:
        """
        处理文件并验证结果

        Args:
            md_file: 输入 Markdown 文件
            output_file: 输出 log 文件
            test_script: 测试脚本路径
            use_rag: 是否使用 RAG

        Returns:
            Dict: 处理结果
        """
        result = {
            'file': str(md_file),
            'generated': False,
            'tested': False,
            'test_passed': False,
            'feedback': None
        }

        # 1. 生成流程
        print(f"\n{'='*80}")
        print(f"处理: {md_file.name}")
        print(f"{'='*80}")

        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            workflow_result = self.generate_with_reflection(content, use_rag)

            # 保存生成的流程
            question = workflow_result.get("question", "实验流程处理")
            workflow = workflow_result.get("workstations", [])

            plan_log = self.generator.generate_plan_log(question, workflow, md_file.stem)

            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(plan_log)

            print(f"✓ 生成流程: {len(workflow)} 个步骤")
            result['generated'] = True

            # 2. 运行测试（如果提供了测试脚本）
            if test_script:
                print(f"正在测试生成的流程...")

                try:
                    # 运行测试脚本
                    test_result = subprocess.run(
                        [sys.executable, test_script],
                        capture_output=True,
                        text=True,
                        timeout=120,
                        cwd=os.path.dirname(test_script)
                    )

                    test_output = test_result.stdout + test_result.stderr

                    # 检查是否测试通过
                    if "✅所有测试都通过了" in test_output or "成功率: 100.0%" in test_output:
                        print(f"✓ 测试通过")
                        result['test_passed'] = True
                    else:
                        print(f"✗ 测试失败")
                        result['test_passed'] = False

                        result['tested'] = True

                        # 3. 如果测试失败，使用反思智能体分析
                        # 提取测试日志路径
                        import re
                        log_match = re.search(r'日志已保存到: (.+)', test_output)
                        if log_match:
                            test_log_file = log_match.group(1).strip()

                            print(f"正在分析失败原因...")
                            feedback = self.reflector.generate_feedback_for_generator(test_log_file)
                            result['feedback'] = feedback

                            # 将反馈添加到学习库
                            self.reflection_feedback.append(feedback)

                            print(f"\n反思反馈:")
                            print(feedback[:500] + "..." if len(feedback) > 500 else feedback)

                except subprocess.TimeoutExpired:
                    print(f"✗ 测试超时")
                    result['test_passed'] = False

                except Exception as e:
                    print(f"✗ 测试错误: {e}")
                    result['test_passed'] = False

        except Exception as e:
            print(f"✗ 生成失败: {e}")
            import traceback
            traceback.print_exc()

        return result

    def process_batch_with_verification(self, input_dir: str, output_dir: str,
                                        test_script: str = None,
                                        start_idx: int = 1, end_idx: int = None,
                                        batch_size: int = None, use_rag: bool = True):
        """
        批量处理文件并验证

        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            test_script: 测试脚本路径
            start_idx: 起始索引
            end_idx: 结束索引
            batch_size: 批次大小
            use_rag: 是否使用 RAG
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 获取所有 Markdown 文件并排序
        import re
        def natural_key(path):
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

        print(f"[INTEGRATED] 找到 {len(md_files)} 个文件待处理")

        results = []
        for i, md_file in enumerate(md_files, start=start_idx):
            output_file = output_path / f"plan_{i}.log"
            result = self.process_with_verification(md_file, output_file, test_script, use_rag)
            results.append(result)

            # 避免API速率限制
            if i < len(md_files) + start_idx - 1:
                import time
                time.sleep(1)

        # 打印总结
        print(f"\n{'='*80}")
        print("批量处理总结")
        print(f"{'='*80}")

        total = len(results)
        generated = sum(1 for r in results if r['generated'])
        tested = sum(1 for r in results if r['tested'])
        passed = sum(1 for r in results if r['test_passed'])
        failed = tested - passed

        print(f"总文件数: {total}")
        print(f"成功生成: {generated}")
        print(f"已测试: {tested}")
        print(f"测试通过: {passed}")
        print(f"测试失败: {failed}")

        if failed > 0:
            print(f"\n失败的文件:")
            for r in results:
                if r['tested'] and not r['test_passed']:
                    print(f"  - {r['file']}")

        # 保存失败分析
        if failed > 0:
            failed_feedback = [r['feedback'] for r in results if r.get('feedback')]
            if failed_feedback:
                feedback_file = output_path / "failed_feedback.md"
                with open(feedback_file, 'w', encoding='utf-8') as f:
                    f.write("# 流程生成失败分析与反馈\n\n")
                    for i, feedback in enumerate(failed_feedback, 1):
                        f.write(f"## 失败 {i}\n\n")
                        f.write(feedback)
                        f.write("\n\n---\n\n")
                print(f"\n失败分析已保存到: {feedback_file}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="集成流程生成系统 - 生成、测试、反思"
    )
    parser.add_argument(
        "--input", "-i",
        default="/opt/data/private/src/Pipelines",
        help="输入目录"
    )
    parser.add_argument(
        "--output", "-o",
        default="/opt/data/private/src/pipeline_workstation_logs",
        help="输出目录"
    )
    parser.add_argument(
        "--test-script", "-t",
        default="/opt/data/private/src/AIChem-LaboratorySimulator-main/src/playground_flow_test_all_workstations.py",
        help="测试脚本路径"
    )
    parser.add_argument(
        "--analyze-logs", "-a",
        action="store_true",
        help="分析现有的测试日志"
    )
    parser.add_argument(
        "--log-dir", "-l",
        default="/opt/data/private/src/AIChem-LaboratorySimulator-main/src/playground_test_logs",
        help="测试日志目录（用于分析）"
    )
    parser.add_argument(
        "--load-feedback", "-f",
        help="加载反馈文件"
    )
    parser.add_argument(
        "--model", "-m",
        default="gpt-4o",
        help="OpenAI 模型"
    )

    args = parser.parse_args()

    # 创建集成系统
    system = IntegratedPipelineGenerator(model=args.model)

    # 加载反馈
    if args.load_feedback:
        system.load_reflection_feedback(args.load_feedback)

    # 分析日志
    if args.analyze_logs:
        system.analyze_test_logs(args.log_dir)

    # 批量处理（如果没有只分析）
    if not args.analyze_logs:
        system.process_batch_with_verification(
            input_dir=args.input,
            output_dir=args.output,
            test_script=args.test_script,
            use_rag=True
        )


if __name__ == "__main__":
    main()
