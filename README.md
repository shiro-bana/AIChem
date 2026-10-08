# AIChem

面向化学实验自动化的研究项目：将实验描述或 Markdown 文档转换为工作站流程，通过样品约束和实验室模拟器验证流程，并利用失败反馈迭代改进规划。

## 项目组成

| 目录 | 用途 |
| --- | --- |
| [AIChemMCP](AIChemMCP/) | 大模型规划、工具服务、约束映射、RAG 检索与反思分析 |
| [AIChem-LaboratorySimulator-main](AIChem-LaboratorySimulator-main/) | 样品模型、工作站能力与实验流程模拟验证 |
| [RunAIChemMCP](RunAIChemMCP/) | 生成、测试、反思和重新生成的 Bash 自动化脚本 |

## 主要功能

- 将自然语言目标或实验 Markdown 转换为工作站步骤。
- 检查容器类型、数量、体积、相态和盖子状态等约束，识别流程兼容性问题。
- 使用 Sentence Transformers 和 JSON 经验库进行 RAG 检索增强。
- 模拟样品状态转换，记录步骤执行结果与约束冲突。
- 根据失败日志进行反思和重新规划，提供 OpenAI 与 Qwen 相关实现。

流程：实验描述 → 工作站规划 → 模拟验证 → 失败分析 → 重新生成。

## 关键文件

| 文件或目录 | 说明 |
| --- | --- |
| AIChemMCP/agent.py | 工具发现与实验目标规划入口 |
| AIChemMCP/pipeline_to_workstation_agent_plusConstraints.py | Markdown 批量流程生成 |
| AIChemMCP/pipeline_to_workstation_agent_qwen.py | Qwen 流程生成实现 |
| AIChemMCP/reflection_agent.py | 失败反思与反馈 |
| AIChemMCP/rag_database.py | 检索与经验库维护 |
| AIChemMCP/constraints_mapping.py | 工具与模拟工作站映射 |
| AIChemMCP/workstation_transformations_agent.json | 工作站转换信息 |
| AIChemMCP/servers_and_tools/ | Agent 使用的服务与工具实现 |
| AIChemMCP/servers/、tools/、workstation_data/ | 服务、工具与工作站数据 |
| AIChem-LaboratorySimulator-main/src/sample.py | 样品模型 |
| AIChem-LaboratorySimulator-main/src/sample_schema.yaml | 样品结构 |
| AIChem-LaboratorySimulator-main/src/workstation.py | 工作站能力抽象 |
| AIChem-LaboratorySimulator-main/src/workstation_instances/ | 工作站约束与状态转换 |
| AIChem-LaboratorySimulator-main/src/playground_flow_test_all_workstations.py | 工作站流程模拟验证 |

## 运行配置

当前代码仍使用原部署目录 `/opt/data/private/src` 下的绝对路径。运行前按实际部署位置核对：

- 流程生成器中的模块搜索路径、工作站目录、RAG 数据库、转换信息与 API Key 文件路径。
- `AIChemMCP/llm_client.py` 的 `API_KEY_FILE`：该模块直接读取文件，单独设置环境变量不足以替代文件配置。
- 模拟器脚本顶部的 `LOG_FILE`：需指向待验证的计划日志。
- 持续改进脚本的输入、输出、Agent、模拟器目录及脚本内其他绝对路径。

流程生成器支持读取 `OPENAI_API_KEY` 环境变量；若配置的密钥文件存在，会用文件内容设置该变量：

```bash
export OPENAI_API_KEY="<你的 API Key>"
```

RAG 默认使用 `all-MiniLM-L6-v2`，AIChemMCP 中已有同名模型目录，请检查文件完整性并从正确的工作目录启动。实验 Markdown 输入目录需自行准备，当前根目录没有默认的 `Pipelines/` 目录。

以下示例均以完成运行配置为前提。`gpt-4o` 来自代码默认值，实际模型按账户配置选择。

## 使用方法

### 1. 生成工作站流程

从仓库根目录执行：

```bash
cd AIChemMCP
python pipeline_to_workstation_agent_plusConstraints.py --help
python pipeline_to_workstation_agent_plusConstraints.py --input ../Pipelines --output ../pipeline_workstation_logs --batch-size 1 --model gpt-4o
```

| 参数 | 说明 |
| --- | --- |
| --input / --output | Markdown 输入目录与计划日志输出目录 |
| --start / --end | 起止索引 |
| --batch-size | 本次处理数量 |
| --model | 模型名称 |
| --no-rag | 禁用检索增强提示 |
| --feedback | 失败分析与建议文件 |
| --input-file | 指定输入文件名，例如 Paper_8.md |
| --target-plan | 覆盖指定编号的计划日志 |

### 2. 模拟验证

先修改模拟器脚本的 `LOG_FILE`，再从仓库根目录执行：

```bash
cd AIChem-LaboratorySimulator-main/src
python playground_flow_test_all_workstations.py
```

脚本解析工作站步骤、检查约束并模拟样品状态转换，日志写入当前目录的 `playground_test_logs/`。测试次数和随机初始化开关在 `main()` 中配置，当前为 5 次且启用随机初始化。

### 3. 持续改进

从仓库根目录执行以下命令。脚本内部的 Python 路径仍需提前调整：

```bash
bash RunAIChemMCP/run_continuous_improvement.sh --help
bash RunAIChemMCP/run_continuous_improvement.sh --input "$PWD/Pipelines" --output "$PWD/pipeline_workstation_logs" --agent "$PWD/AIChemMCP" --simulator "$PWD/AIChem-LaboratorySimulator-main/src" --transformations "$PWD/AIChemMCP/workstation_transformations_agent.json" --batch-size 1 --num-tests 5 --max-iterations 3 --max-batches 1
```

当前脚本默认每批 3 个文件、每个计划测试 5 次、最多迭代 3 次，最大批次数为 0（无限制）。成功标准是每个计划至少一次模拟通过，并不要求所有随机测试均通过。历史帮助文档的部分默认值与脚本不同，以脚本为准。

运行结果包括计划、测试结果、反思、规则、报告和详细日志。使用 `--continue-from` 可指定既有运行目录继续处理，使用 `--no-rag` 可进行对比。

### 4. 目标规划 Agent

配置好 `llm_client.py` 的密钥文件路径后，从仓库根目录执行：

```bash
cd AIChemMCP
python agent.py
```

入口会启动 `servers_and_tools/` 中的服务、发现工具，并规划代码中预设的实验目标。更换目标需修改入口中的 `user_goal`。

## 扩展与调试

- 新增工作站时，同步维护模拟器能力与约束、服务工具、约束映射和转换信息。
- 容器或相态冲突可通过模拟日志和对应工作站实例定位，再调整流程或反馈规则。
- 文件找不到时，检查残留的 `/opt/data/private/src` 路径和运行工作目录。
- 项目保留了测试脚本、Notebook、历史日志和备份实现，使用时以实际入口引用的文件为准。

模拟器检验的是代码建模的约束与状态转换，模拟通过不能替代实际实验和设备验证。本文依据当前代码整理，尚未验证完整模型调用与端到端运行。

## 相关文档与许可证

- [AIChemMCP 功能说明](AIChemMCP/README.md)
- [持续改进脚本说明](RunAIChemMCP/run_continuous_help.md)
- [模拟器 MIT 许可证](AIChem-LaboratorySimulator-main/LICENSE)

模拟器子项目带有 MIT 许可证；当前仓库根目录没有统一许可证文件，其他部分的授权范围需分别确认。
