  新增参数

  | 参数                       | 说明                   | 默认值                                                                 |
  |----------------------------|------------------------|------------------------------------------------------------------------|
  | -t, --transformations PATH | 工作站转换信息文件路径 | /opt/data/private/src/AIChemMCP/workstation_transformations_agent.json |
  | -m, --model MODEL          | OpenAI 模型选择        | gpt-4o                                                                 |
  | --no-rag                   | 禁用 RAG 增强提示      | 启用                                                                   |
  | --max-iterations N         | 最大迭代次数           | 5                                                                      |
  | --batch-size N             | 每批处理文件数         | 5                                                                      |
  | --num-tests N              | 每个 plan 测试次数     | 5                                                                      |
  | --max-batches N            | 最大批次数（0=无限制） | 1                                                                      |

  使用方法

  # 查看帮助
  bash run_continuous_improvement.sh --help

  # 使用默认配置运行（处理 5 个文件，每个测试 5 次，最多迭代 5 次）
  bash run_continuous_improvement.sh

  # 处理 10 个文件，每个测试 10 次，使用 gpt-4o-mini
  bash run_continuous_improvement.sh --batch-size 10 --num-tests 10 --model gpt-4o-mini

  # 禁用 RAG，处理所有批次
  bash run_continuous_improvement.sh --no-rag --max-batches 0

  # 使用自定义转换信息文件
  bash run_continuous_improvement.sh --transformations /path/to/custom_transformations.json

  脚本工作流程

  1. 生成流程：使用 pipeline_to_workstation_agent_plusConstraints.py 将 Markdown 转换为工作站流程
  2. 测试流程：在模拟器中测试生成的流程
  3. 反思分析：使用 reflection_agent.py 分析失败原因
  4. 重新生成：使用反馈重新生成失败的流程
  5. 迭代：重复步骤 2-4，直到全部通过或达到最大迭代次数

  输出目录结构

  /opt/data/private/src/continuous_improvement_runs/run_YYYYMMDD_HHMMSS/
  ├── plans/                    # 生成的 plan log
  ├── test_results/             # 测试结果
  ├── reflection/               # 反思分析
  ├── rules/                    # 学习的兼容性规则
  ├── reports/                  # 最终报告
  └── logs/                     # 详细日志

  与改进功能的集成

  脚本现在会：
  - 自动使用 workstation_transformations_agent.json（由 AI Agent 分析生成）
  - 支持选择不同的 OpenAI 模型
  - 可以禁用 RAG 进行对比测试
  - 所有参数都可以通过命令行覆盖