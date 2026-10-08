# agent.py
import subprocess
import json
import sys
import time
from threading import Thread
from llm_client import OpenAI_LLM
import os

from rag_database import RAGDatabase


class Agent:
    def __init__(self, rag_db_path="rag_database.json"):
        self.servers = {}
        self.tools = {}
        self.history = []
        self.llm_client = OpenAI_LLM()
        # 初始化RAG数据库
        self.rag_db = RAGDatabase(rag_db_path)
        print(f"[AGENT] RAG数据库初始化完成，当前包含 {self.rag_db.get_entry_count()} 条记录")

    def start_server(self, name: str, command: list):
        """启动一个服务器子进程并管理其IO管道"""
        print(f"[AGENT] Starting server: {name}...")
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            text=True,
            bufsize=1,  # Line-buffered
            universal_newlines=True
        )
        self.servers[name] = {
            "process": process,
            "stdin": process.stdin,
            "stdout": process.stdout,
        }
        # 启动一个线程来打印服务器的stderr日志，以免阻塞
        Thread(target=self._log_stderr, args=(name, process.stderr), daemon=True).start()
        print(f"[AGENT] Server '{name}' started.")

    def _log_stderr(self, name, stderr_pipe):
        """在后台打印服务器的日志"""
        for line in iter(stderr_pipe.readline, ''):
            print(f"[{name} LOG] {line.strip()}", file=sys.stderr)

    def discover_tools(self):
        """从所有启动的服务器接收advertise消息，并构建工具列表"""
        print("\n[AGENT] Discovering tools from all servers...")
        
        for name, server in self.servers.items():
            print(f"[AGENT] Reading from server: {name}")
            
            # 读取服务器的第一条消息（应该是advertise）
            adv_line = server['stdout'].readline()
            print(f"[AGENT] Raw output from {name}: {repr(adv_line)}")
            
            if not adv_line:
                print(f"[AGENT] No output from server {name}")
                continue
                
            try:
                adv_data = json.loads(adv_line)
                print(f"[AGENT] Successfully parsed JSON from {name}")
                
                # 提取工具列表 - 注意路径可能有变化
                server_tools = []
                
                # 尝试不同的路径
                if "params" in adv_data and "server" in adv_data["params"]:
                    server_tools = adv_data["params"]["server"].get("capabilities", {}).get("tools", [])
                elif "result" in adv_data and "server" in adv_data["result"]:
                    server_tools = adv_data["result"]["server"].get("capabilities", {}).get("tools", [])
                else:
                    print(f"[AGENT] Unexpected message format from {name}: {adv_data}")
                    continue
                    
                print(f"[AGENT] Found {len(server_tools)} tools from '{name}'")
                
                for tool in server_tools:
                    tool_name = tool['name']
                    self.tools[tool_name] = tool
                    self.tools[tool_name]['server_name'] = name
                    print(f"[AGENT] Added tool: {tool_name}")
                    
            except json.JSONDecodeError as e:
                print(f"[AGENT] JSON decode error from {name}: {e}")
                print(f"[AGENT] Raw line that failed: {repr(adv_line)}")
            except Exception as e:
                print(f"[AGENT] Error processing {name}: {e}")

        print(f"[AGENT] Tool discovery complete. Total tools available: {len(self.tools)}")
        
        # 打印所有发现的工具
        if self.tools:
            print("[AGENT] Available tools:")
            for tool_name in self.tools.keys():
                print(f"  - {tool_name}")

    def build_system_prompt(self) -> str:
        """构建包含角色、工具列表和"脚手架"的系统提示"""
        prompt = "# 角色与总目标\n"
        prompt += "你是一位顶级的AI研究化学家。你的任务是利用实验室的自动化工具，高效、安全地完成科研目标。\n\n"

        prompt += "# 可用工具\n---\n"
        for name, tool in self.tools.items():
            prompt += f"- 工具: {name}\n"
            prompt += f"  - 描述: {tool['description']}\n"
            prompt += f"  - 参数: {json.dumps(tool['parameters'])}\n"
        prompt += "---\n\n"

        prompt += "# 核心工作流提示 (SOPs & Best Practices)\n"
        prompt += "当你需要执行一个**优化任务**时，一个高效、标准的流程是贝叶斯优化循环。强烈建议你遵循以下步骤：\n"
        prompt += "1.  **初始化 (Initialize)**: (如果需要) 调用 `initialize` 来开始一个新的优化会话。\n"
        prompt += "2.  **建议 (Suggest)**: 调用 `suggest` 工具，获取下一步的实验参数。\n"
        prompt += "3.  **执行 (Execute)**: 使用 `robotic_reaction` 和 `robotic_measurement` 工具来运行实验并测量结果。\n"
        prompt += "4.  **观察 (Observe)**: 调用 `observe` 工具，将新的实验参数和结果反馈给优化器。\n"
        prompt += "5.  **重复 (Repeat)**: 持续这个循环，直到达成优化目标。\n\n"

        prompt += "# 工作站约束条件与兼容性检查 (Workstation Constraints & Compatibility)\n"
        prompt += "每个工作站都有特定的约束条件，确保实验顺利进行和设备安全。在规划实验流程时必须进行兼容性检查：\n\n"

        prompt += "## 约束条件验证\n"
        prompt += "1.  **单个工作站约束**: 包括容器类型、样品体积、样品相态、容器数量、盖子状态等\n"
        prompt += "2.  **自动验证**: 工作站会自动验证样品是否满足约束条件\n"
        prompt += "3.  **失败处理**: 如果验证失败，工具会返回 'constraints_validation_failed' 错误\n\n"

        prompt += "## 兼容性检查 (关键步骤)\n"
        prompt += "在生成实验流程时，必须检查工作站之间的输入输出兼容性：\n\n"

        prompt += "### 常见的不兼容情况：\n"
        prompt += "1.  **相态不匹配**:\n"
        prompt += "   - 烘干机输出固体(solid) → 电化学工作站要求悬浊液(suspension) \n"
        prompt += "   - 解决方案：烘干后需要加液体重新分散成悬浊液\n\n"
        prompt += "2.  **容器类型不匹配**:\n"
        prompt += "   - 某些工作站要求特定容器类型(如50ml试管、微孔板等)\n\n"
        prompt += "3.  **盖子状态不匹配**:\n"
        prompt += "   - 电化学工作站要求无盖容器\n"
        prompt += "   - 离心纯化要求有盖容器\n\n"
        prompt += "4.  **体积限制**:\n"
        prompt += "   - 不同工作站有不同的最小/最大体积要求\n\n"

        prompt += "### 兼容性检查流程：\n"
        prompt += "1.  **规划阶段检查**: 在提交工作流计划前，验证每个工作站步骤的兼容性\n"
        prompt += "2.  **状态追踪**: 追踪样品在每个步骤后的状态变化(相态、体积、容器等)\n"
        prompt += "3.  **冲突解决**: 如果发现不兼容，插入中间步骤(如液体处理、磁力搅拌等)\n"
        prompt += "4.  **重新验证**: 修改后的流程需要重新检查兼容性\n\n"

        prompt += "### 示例检查：\n"
        prompt += "- 烘干机 → 电化学工作站:  不兼容(固体→悬浊液)\n"
        prompt += "- 烘干机 → 液体进样站 → 磁力搅拌 → 电化学工作站:  兼容\n"
        prompt += "- 固体进样 → 磁力搅拌 → 离心纯化 → 烘干 → XRD分析:  兼容\n\n"

        prompt += "## 指导原则\n"
        prompt += "1.  **先检查再执行**: 在生成计划时就必须考虑兼容性\n"
        prompt += "2.  **插入中间步骤**: 当发现不兼容时，主动插入合适的中间工作站\n"
        prompt += "3.  **状态转换**: 理解每个工作站的输入输出状态变化\n"
        prompt += "4.  **优化流程**: 选择最短且兼容的工作站序列\n\n"

        return prompt

    def build_rag_enhanced_prompt(self, user_goal: str, top_k=4) -> str:
        """
        构建包含RAG上下文的增强提示

        Args:
            user_goal: 用户的目标
            top_k: 从RAG数据库中获取的相似条目的数量

        Returns:
            str: 增强的系统提示
        """
        # 获取基础系统提示
        base_prompt = self.build_planner_system_prompt()

        # 从RAG数据库获取相关上下文
        print(f"[AGENT] 正在从RAG数据库中查找与 '{user_goal}' 相关的记录...")
        context = self.rag_db.get_relevant_context(user_goal, top_k)

        # 添加RAG上下文到提示中
        rag_prompt = base_prompt + "\n# 相关历史经验 (RAG Context)\n"
        rag_prompt += "---\n"
        rag_prompt += context
        rag_prompt += "---\n\n"
        rag_prompt += "# 使用RAG上下文的指导原则\n"
        rag_prompt += "1. **参考历史经验**: 仔细分析上述相关的历史问题和解决方案\n"
        rag_prompt += "2. **避免重复工作**: 如果有相似的问题已经解决，参考其方法\n"
        rag_prompt += "3. **创新优化**: 在参考历史的基础上，根据当前问题的特殊性进行优化\n"
        rag_prompt += "4. **完整性**: 确保你的解决方案覆盖所有必要的步骤\n\n"

        return rag_prompt


    def dispatch_tool_call(self, tool_call: dict) -> dict:
        """将工具调用请求分发给正确的服务器并返回结果"""
        method = tool_call.get("method")
        if not method or method not in self.tools:
            return {"error": f"Tool '{method}' not found."}

        # 根据工具名找到对应的服务器
        server_name = self.tools[method]['server_name']
        server = self.servers[server_name]

        # 构建并发送JSON-RPC请求
        request_id = int(time.time() * 1000)
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": tool_call.get("params", {}),
            "id": request_id
        }

        print(f"[AGENT] -> [{server_name}] {json.dumps(request)}")
        server['stdin'].write(json.dumps(request) + '\n')
        server['stdin'].flush()

        # 等待并读取响应
        while True:
            response_line = server['stdout'].readline()
            if not response_line:
                return {"error": "Server connection closed."}
            response = json.loads(response_line)
            if response.get("id") == request_id:
                print(f"[AGENT] <- [{server_name}] {json.dumps(response)}")

                # 检查是否是 constraints 验证失败的错误
                if (response.get("result") and
                    isinstance(response["result"], dict) and
                    response["result"].get("error") == "constraints_validation_failed"):

                    # 添加专门的 constraints 验证失败处理
                    error_msg = response["result"].get("message", "样品约束条件验证失败")
                    workstation_name = response["result"].get("workstation", "工作站")

                    enhanced_response = {
                        "result": {
                            "status": "constraints_failed",
                            "workstation": workstation_name,
                            "message": error_msg,
                            "error": "constraints_validation_failed",
                            "suggestion": f"请检查样品参数（容器类型、体积、相态等）是否满足{workstation_name}的约束条件，或选择其他合适的工作站。",
                            "original_response": response["result"]
                        }
                    }

                    print(f"[AGENT] Constraints validation failed for {workstation_name}: {error_msg}")
                    return enhanced_response

                return response

    def build_planner_system_prompt(self) -> str:
        """为规划阶段构建专用的系统提示"""
        prompt = "# 角色与目标\n"
        prompt += "你是一个专家级的实验室工作流规划师。你的任务是根据用户的目标，将一系列可用的基础工具，组合成一个逻辑正确的、有序的步骤列表来完成任务。\n\n"

        prompt += "# 可用工具\n---\n"
        for name, tool in self.tools.items():
            # 只提供名称和描述，让LLM专注于逻辑，而非实现细节
            prompt += f"- {name}: {tool['description']}\n"
        prompt += "---\n\n"

        prompt += "# 关键要求：兼容性检查\n"
        prompt += "在生成工作流计划时，必须进行严格的兼容性检查。每个工作站的输出必须满足下一个工作站的输入要求：\n\n"

        prompt += "## 必须检查的兼容性：\n"
        prompt += "1. **相态转换**: 烘干机(solid) → 电化学工作站(suspension) 不兼容 ❌\n"
        prompt += "2. **容器类型**: 确保容器类型匹配(如50ml试管、微孔板等)\n"
        prompt += "3. **盖子状态**: 电化学工作站需要无盖，离心纯化需要有盖\n"
        prompt += "4. **体积要求**: 检查最小/最大体积限制\n\n"

        prompt += "## 解决方案：\n"
        prompt += "如果发现不兼容，必须插入中间步骤：\n"
        prompt += "- 固体→悬浊液：插入液体处理或磁力搅拌工作站\n"
        prompt += "- 盖子状态不匹配：插入开盖/关盖步骤\n"
        prompt += "- 容器转换：插入样品转移步骤\n\n"

        prompt += "## 任务\n"
        prompt += "请分析用户的目标，并生成一个包含所有必要步骤的完整计划。在生成计划时必须：\n"
        prompt += "1. 检查每一步的兼容性\n"
        prompt += "2. 如果发现不兼容，插入必要的中间步骤\n"
        prompt += "3. 确保最终的技术可行性\n"
        prompt += "4. 你的最终输出必须是一个调用`submit_workflow_plan`工具的请求，其中包含所有步骤。\n"
        return prompt

    def plan_workflow(self, user_goal: str) -> list:
        """【规划阶段】调用LLM生成一个多步计划"""
        print("\n[AGENT] Entering PLANNING stage...")
        rag_enhanced_prompt = self.build_rag_enhanced_prompt(user_goal)
        system_prompt = rag_enhanced_prompt
        plan = self.llm_client.generate_plan(system_prompt, user_goal, self.tools)

        print("[AGENT] Plan generated successfully.")
        # for i, step in enumerate(plan, 1):
        #     print(f"  Step {i}: {step['method']}({json.dumps(step['params'])})")
        return plan

    def run(self):
        """启动主交互循环"""
        system_prompt = self.build_system_prompt()
        self.history.append({"role": "system", "content": system_prompt})

        print("\n--- Agent is Ready ---")
        print("System Prompt has been constructed. You can now interact with the agent.")
        print("Try typing: 'Please optimize the reaction yield.'")

        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ["exit", "quit"]:
                for server in self.servers.values():
                    server['process'].terminate()
                print("[AGENT] All servers terminated. Exiting.")
                break

            self.history.append({"role": "user", "content": user_input})

            print("[AGENT] Thinking with OpenAI...")
            # 将system_prompt, history, 和 self.tools 全部传给决策函数
            llm_response = self.llm_client.get_decision(
                system_prompt,
                self.history,
                self.tools
            )
            print(f"[LLM] Thought: {llm_response.get('thought')}")
            self.history.append({"role": "assistant", "content": llm_response})

            # 2. 如果LLM决定调用工具，则分发
            if "tool_call" in llm_response:
                tool_call = llm_response['tool_call']
                print(f"[AGENT] Dispatching tool call: {tool_call.get('method')}")

                result = self.dispatch_tool_call(tool_call)
                self.history.append({"role": "tool_result", "content": result})
                print(f"[AGENT] Tool execution result: {result}")

                # 模拟工具执行后的再次思考
                print("[AGENT] Thinking about the result...")
                next_llm_response = self.llm_client.get_decision(system_prompt, self.history, self.tools)
                print(f"[LLM] Next Thought: {next_llm_response.get('thought')}")
                if "speak" in next_llm_response:
                    print(f"\nAgent: {next_llm_response['speak']}")
            elif "speak" in llm_response:
                print(f"\nAgent: {llm_response['speak']}")


def start_all_servers(servers_dir="servers_and_tools"):
    """遍历servers目录下的所有Python文件并启动对应的服务器"""
    # 检查servers目录是否存在
    if not os.path.exists(servers_dir):
        print(f"错误: 目录 '{servers_dir}' 不存在")
        return

    if not os.path.isdir(servers_dir):
        print(f"错误: '{servers_dir}' 不是一个目录")
        return

    # 遍历目录中的所有文件
    for filename in os.listdir(servers_dir):
        # 构建完整文件路径
        file_path = os.path.join(servers_dir, filename)

        # 只处理Python文件且是普通文件
        if os.path.isfile(file_path) and filename.endswith(".py"):
            # 提取服务器名称（不带.py扩展名）
            server_name = os.path.splitext(filename)[0]

            print(f"启动服务器: {server_name}")
            try:
                # 启动服务器
                agent.start_server(
                    server_name,
                    ["python", file_path]
                )
                print(f"服务器 {server_name} 启动成功")
            except Exception as e:
                print(f"启动服务器 {server_name} 失败: {str(e)}")


if __name__ == "__main__":
    agent = Agent()

    # 启动所有服务器
    start_all_servers("servers_and_tools")

    # 增加等待时间，确保服务器完全启动
    print("[AGENT] Waiting for servers to initialize...")
    time.sleep(3)  # 增加到3秒
    
    agent.discover_tools()

    # 生成计划
    if agent.tools:
        user_goal = "如何制备高熵氢氧化物并进行电催化性能测试？"
        plan = agent.plan_workflow(user_goal)
        print("生成的计划:")
        for i, step in enumerate(plan, 1):
            print(f"  步骤 {i}: {step}")
    else:
        print("错误: 没有发现任何工具")