# AIChemMCP 实验自动化系统

## 概述

AIChemMCP 是一个智能化学实验自动化系统，通过 Agent 生成可执行的实验流程。系统具备两大核心功能：**工作站约束条件验证**和**工作流兼容性检查**，确保生成的实验流程在技术上可行且安全。

---

## 一、工作站约束条件验证

### 功能说明

每个工作站都有特定的约束条件（容器类型、相态、体积、数量等），系统在调用工具前会自动验证样品是否满足这些约束，避免执行无效或危险的操作。

### 覆盖范围

已完成 **17个服务器工具文件** 的约束条件集成：

| 服务器工具 | 工作站实例 | 主要约束条件 |
|-----------|-----------|-------------|
| magnetic_stirring_server_tools | magnetic_stirring_workstation | 离心管架/50ml试管/聚四氟瓶/西林瓶 |
| electrochemical_workstation_dual_server_tools | dual_station_electrochemical_workstation | 离心管架，无盖，1-10个容器，悬浊液，>4ml |
| ultrasonic_cleaning_server_tools | ultrasonic_cleaning_workstation | 离心管架，液体或悬浊液 |
| dryer_server_tools | drying_station | 任意容器 |
| new_centrifugation_server_tools | centrifuge | 离心管架，双数容器 |
| ustc_photocatalysis_server_tools | photocatalytic_workstation | 西林瓶，体积≤15ml |
| microplate_reader_server_tools | high_throughput_microplate_reader_workstation | 微孔板 |
| high_flux_ir_workstation_server_tools | high_throughput_ftir_workstation | 固体或液体（非悬浊液） |
| high_flux_xrd_workstation_server_tools | high_throughput_xrd_workstation | 固体 |
| ustc_mul_solid_server_tools | multi_channel_solid_sampler | 离心管架 |
| starting_station_server_tools | material_station_get_tube | 初始状态 |
| pure_server_tools | centrifugal_purification_with_wash_liquid | 离心管架，有盖 |
| liquid_dispensing_server_tools | liquid_sampling_station | 离心管架，体积≤30ml |
| toLC_server_tools | liquid_chromatograph | 液体 |
| solid_dispensing_server_tools | solid_injection | 50ml离心管，无盖，空或固体 |
| liquid_handling_workstation_server_tools | decentralization | 离心管架，50ml试管，1-10个，液体 |
| transfer_workstation_server_tools | storage_workstation | 离心管架，1-10个容器 |

### 技术实现

**核心文件：**
- `constraints_mapping.py` - 服务器工具与工作站实例的映射
- `agent.py` - 智能错误处理和约束验证集成

**验证流程：**
```
用户请求 → Agent规划 → 调用工具 → 服务器验证约束条件
                                        ↓
                                验证通过 → 执行操作
                                验证失败 → 返回详细错误信息
```

**约束验证代码示例：**
```python
if 'sample' in params:
    if not validate_sample_constraints(server_name, params['sample']):
        return {
            "status": "failed",
            "error": "constraints_validation_failed",
            "message": "样品不满足工作站的约束条件"
        }
```

---

## 二、工作流兼容性检查

### 功能说明

检测工作站之间的输入输出兼容性问题（如相态不匹配、容器类型不符），自动插入必要的中间步骤确保流程可行。

### 兼容性规则

| 不兼容序列 | 问题描述 | 解决方案 |
|-----------|---------|---------|
| 烘干机 → 电化学工作站 | 输出固体，要求悬浊液 | 添加液体进样站 + 磁力搅拌 |
| 烘干机 → 超声清洗工作站 | 输出固体，要求液体/悬浊液 | 添加液体进样站 |
| 离心纯化 → 红外光谱工作站 | 输出悬浊液，要求固体/液体 | 添加烘干或分离步骤 |
| 任意工作站 → 光催化工作站 | 容器/体积不符 | 添加样品转移至西林瓶 |
| 固体进样 → 电化学工作站 | 需要悬浊液 | 添加液体进样站 + 磁力搅拌 |

### 检查维度

- **相态转换**：solid ↔ liquid ↔ suspension
- **容器类型**：50ml试管 ↔ 西林瓶 ↔ 微孔板
- **体积限制**：不同工作站的最大/最小体积要求
- **盖子状态**：有盖/无盖要求

### 技术实现

**兼容性检查函数：**
```python
def check_plan_compatibility(plan):
    """检查工作流计划的兼容性，返回问题和解决方案"""
    issues = []
    for i in range(len(plan) - 1):
        from_step = plan[i]
        to_step = plan[i + 1]
        # 检查预定义的兼容性规则
        ...
    return issues
```

**重新规划机制：**
- 最多3次重新规划尝试
- 每次基于具体错误信息调整提示
- 明确的解决方案指导

---

## 三、使用指南

### 运行 Agent
```bash
cd /opt/data/private/src/AIChemMCP
python agent.py
```

### 测试兼容性检查
```python
from test_compatibility import check_plan_compatibility

plan = [
    {"workstation": "烘干机"},
    {"workstation": "电化学工作站"}
]

issues = check_plan_compatibility(plan)
if issues:
    print(f"发现兼容性问题: {issues}")
```

### 验证约束条件
```python
from constraints_mapping import validate_sample_constraints

sample = {
    "container": {...},
    "phase": "suspension"
}

is_valid = validate_sample_constraints('electrochemical_workstation_dual_server_tools', sample)
```

---

## 四、系统优势

1. **提高实验成功率** - 通过约束验证和兼容性检查，确保流程可行
2. **保护设备安全** - 避免不合适的样品损坏工作站
3. **减少无效实验** - 提前发现问题，减少浪费
4. **智能自适应** - Agent 从错误中学习，优化后续规划
5. **易于扩展** - 新增工作站只需添加映射和约束条件

---

## 五、文件结构

```
AIChemMCP/
├── agent.py                          # 主Agent，包含约束和兼容性逻辑
├── constraints_mapping.py            # 服务器-工作站映射
├── add_constraints_to_all_tools.py   # 自动化集成脚本
├── test_compatibility.py             # 兼容性检查测试
├── test_agent_workflow.py            # Agent工作流测试
├── servers_and_tools/                # 服务器工具文件
└── workstation_data/                 # 工作站实例数据
```

---

## 六、后续扩展方向

1. **RAG集成** - 将约束和兼容性经验添加到知识库
2. **可视化工具** - 开发约束条件可视化界面
3. **智能推荐** - 基于约束和兼容性推荐最优工作站序列
4. **约束优化** - 基于实际使用数据持续优化约束条件
