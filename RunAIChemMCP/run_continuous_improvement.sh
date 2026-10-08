#!/bin/bash
#
# 持续改进自动化脚本
# 功能：生成流程 → 测试 → 反思 → 重新生成 → 再测试，直到每个log都有通过的测试用例
# 成功标准：每个 plan log 至少有 1 次测试通过即可（如 5/5 次测试中有 2 次通过也行）
#

set -e  # 遇到错误立即退出

# 配置参数
PIPELINE_DIR="/opt/data/private/src/Pipelines"
OUTPUT_BASE_DIR="/opt/data/private/src/pipeline_workstation_logs"
WORKSTATION_SIMULATOR_DIR="/opt/data/private/src/AIChem-LaboratorySimulator-main/src"
AGENT_DIR="/opt/data/private/src/AIChemMCP"
TRANSFORMATIONS_PATH="/opt/data/private/src/AIChemMCP/workstation_transformations_agent.json"  # 工作站转换信息路径
MAX_ITERATIONS=3  # 最大迭代次数
BATCH_SIZE=3  # 每批处理的文件数（减少批量大小以避免端口耗尽）
NUM_TESTS=5  # 每个 plan 的测试次数
MAX_BATCHES=0  # 只处理第一批（用于测试）
USE_RAG=true  # 是否使用 RAG 增强提示
MODEL="gpt-4o"  # OpenAI 模型
CONTINUE_FROM=""  # 继续之前的运行（指定run目录）

# 显示使用说明
show_usage() {
    cat << EOF
用法: $0 [选项]

持续改进自动化脚本 - 自动生成、测试、反思和重新生成工作站流程

选项:
    -i, --input DIR          Pipeline Markdown 文件目录 (默认: $PIPELINE_DIR)
    -o, --output DIR         输出目录 (默认: $OUTPUT_BASE_DIR)
    -s, --simulator DIR      工作站模拟器目录 (默认: $WORKSTATION_SIMULATOR_DIR)
    -a, --agent DIR          Agent 目录 (默认: $AGENT_DIR)
    -t, --transformations PATH  工作站转换信息文件 (默认: $TRANSFORMATIONS_PATH)
    -m, --model MODEL        OpenAI 模型 (默认: $MODEL)
    --max-iterations N       最大迭代次数 (默认: $MAX_ITERATIONS)
    --batch-size N           每批处理的文件数 (默认: $BATCH_SIZE)
    --num-tests N            每个 plan 的测试次数 (默认: $NUM_TESTS)
    --max-batches N          最大批次数 (默认: $MAX_BATCHES, 0=无限制)
    --continue-from PATH     继续之前的运行 (指定之前的run目录路径)
    --no-rag                 禁用 RAG 增强提示
    -h, --help               显示此帮助信息

示例:
    # 使用默认配置运行
    $0

    # 处理 10 个文件，测试 10 次，使用 gpt-4o-mini
    $0 --batch-size 10 --num-tests 10 --model gpt-4o-mini

    # 禁用 RAG，处理所有批次
    $0 --no-rag --max-batches 0

    # 继续之前的运行（已生成50个plan，继续生成剩余的）
    $0 --continue-from /opt/data/private/src/continuous_improvement_runs/run_20260125_045020

EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -i|--input)
                PIPELINE_DIR="$2"
                shift 2
                ;;
            -o|--output)
                OUTPUT_BASE_DIR="$2"
                shift 2
                ;;
            -s|--simulator)
                WORKSTATION_SIMULATOR_DIR="$2"
                shift 2
                ;;
            -a|--agent)
                AGENT_DIR="$2"
                shift 2
                ;;
            -t|--transformations)
                TRANSFORMATIONS_PATH="$2"
                shift 2
                ;;
            -m|--model)
                MODEL="$2"
                shift 2
                ;;
            --max-iterations)
                MAX_ITERATIONS="$2"
                shift 2
                ;;
            --batch-size)
                BATCH_SIZE="$2"
                shift 2
                ;;
            --num-tests)
                NUM_TESTS="$2"
                shift 2
                ;;
            --max-batches)
                MAX_BATCHES="$2"
                shift 2
                ;;
            --no-rag)
                USE_RAG=false
                shift
                ;;
            --continue-from)
                CONTINUE_FROM="$2"
                shift 2
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                echo "未知选项: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# 创建带时间戳的运行目录
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RUN_DIR="/opt/data/private/src/continuous_improvement_runs/run_${TIMESTAMP}"

# 子目录结构
PLAN_OUTPUT_DIR="$RUN_DIR/plans"           # 生成的 plan log
TEST_RESULTS_DIR="$RUN_DIR/test_results"   # 测试结果
REFLECTION_DIR="$RUN_DIR/reflection"        # 反思分析
RULES_DIR="$RUN_DIR/rules"                 # 学习规则
REPORTS_DIR="$RUN_DIR/reports"             # 报告
LOGS_DIR="$RUN_DIR/logs"                   # 详细日志

# 日志文件
LOG_FILE="$LOGS_DIR/run.log"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

print_section() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n" | tee -a "$LOG_FILE"
}

# 初始化
init() {
    # 如果指定了继续运行，使用之前的run目录
    if [ -n "$CONTINUE_FROM" ]; then
        if [ ! -d "$CONTINUE_FROM" ]; then
            echo "错误：指定的运行目录不存在: $CONTINUE_FROM"
            exit 1
        fi

        # 重新设置所有目录变量
        RUN_DIR="$CONTINUE_FROM"
        PLAN_OUTPUT_DIR="$RUN_DIR/plans"
        TEST_RESULTS_DIR="$RUN_DIR/test_results"
        REFLECTION_DIR="$RUN_DIR/reflection"
        RULES_DIR="$RUN_DIR/rules"
        REPORTS_DIR="$RUN_DIR/reports"
        LOGS_DIR="$RUN_DIR/logs"

        # 重新设置LOG_FILE（重要！）
        LOG_FILE="$LOGS_DIR/run.log"

        # 计算已生成的plan数量
        local existing_plans=$(ls -1 "$PLAN_OUTPUT_DIR"/plan_*.log 2>/dev/null | wc -l)

        print_section "继续之前的运行"
        print_info "使用运行目录: $RUN_DIR"
        print_info "已生成的plan数量: $existing_plans"
    fi

    # 创建所有必要的目录（必须在任何日志输出之前）
    mkdir -p "$PLAN_OUTPUT_DIR"
    mkdir -p "$TEST_RESULTS_DIR"
    mkdir -p "$REFLECTION_DIR"
    mkdir -p "$RULES_DIR"
    mkdir -p "$REPORTS_DIR"
    mkdir -p "$LOGS_DIR"

    print_section "初始化持续改进系统"

    # 创建日志文件
    echo "持续改进系统启动 - $(date)" > "$LOG_FILE"

    print_info "运行目录: $RUN_DIR"
    print_info "配置参数:"
    print_info "  Pipeline 目录: $PIPELINE_DIR"
    print_info "  Plan 输出目录: $PLAN_OUTPUT_DIR"
    print_info "  测试结果目录: $TEST_RESULTS_DIR"
    print_info "  反思分析目录: $REFLECTION_DIR"
    print_info "  工作站转换信息: $TRANSFORMATIONS_PATH"
    print_info "  OpenAI 模型: $MODEL"
    print_info "  使用 RAG: $USE_RAG"
    print_info "  最大迭代次数: $MAX_ITERATIONS"
    print_info "  批处理大小: $BATCH_SIZE"
    print_info "  每个 plan 测试次数: $NUM_TESTS"

    if [ -n "$CONTINUE_FROM" ]; then
        print_info "  继续模式: 是 (从 $CONTINUE_FROM)"
    fi

    # 检查必要的文件和目录
    if [ ! -d "$PIPELINE_DIR" ]; then
        print_error "Pipeline 目录不存在: $PIPELINE_DIR"
        exit 1
    fi

    if [ ! -d "$WORKSTATION_SIMULATOR_DIR" ]; then
        print_error "模拟器目录不存在: $WORKSTATION_SIMULATOR_DIR"
        exit 1
    fi

    # 保存运行信息
    cat > "$RUN_DIR/run_info.txt" << EOF
运行ID: run_${TIMESTAMP}
开始时间: $(date)
配置参数:
  - Pipeline目录: $PIPELINE_DIR
  - 最大迭代次数: $MAX_ITERATIONS
  - 批处理大小: $BATCH_SIZE
  - 测试次数: $NUM_TESTS
  - 工作站模拟器: $WORKSTATION_SIMULATOR_DIR
  - Agent目录: $AGENT_DIR
EOF

    print_success "初始化完成"
}

# 步骤1：生成流程
generate_workflows() {
    local start_idx=$1
    local batch_size=$2
    local iteration=$3

    print_section "步骤1：生成流程 (迭代 $iteration, 文件 $start_idx-$((start_idx + batch_size - 1)))"

    cd "$AGENT_DIR"

    # 等待之前的连接完全关闭
    print_info "等待5秒以确保之前的网络连接完全关闭..."
    sleep 5

    # 构建命令参数
    local cmd_args="--input \"$PIPELINE_DIR\" --output \"$PLAN_OUTPUT_DIR\" --start \"$start_idx\" --batch-size \"$batch_size\" --model \"$MODEL\""

    # 添加 RAG 参数
    if [ "$USE_RAG" = false ]; then
        cmd_args="$cmd_args --no-rag"
    fi

    # 执行命令
    eval "python pipeline_to_workstation_agent_plusConstraints.py $cmd_args" 2>&1 | tee -a "$LOG_FILE"

    print_success "流程生成完成"
}

# 步骤2：测试流程
test_workflows() {
    local start_idx=$1
    local batch_size=$2
    local iteration=$3
    local batch_idx=$4  # 添加batch索引

    print_section "步骤2：测试流程 (批次 $((batch_idx + 1)), 迭代 $iteration, 每个 plan 测试 $NUM_TESTS 次)"

    cd "$WORKSTATION_SIMULATOR_DIR"

    # 找到新生成的 plan 文件
    local end_idx=$((start_idx + batch_size - 1))
    declare -A test_results

    for i in $(seq $start_idx $end_idx); do
        local plan_file="$PLAN_OUTPUT_DIR/plan_${i}.log"

        if [ ! -f "$plan_file" ]; then
            print_warning "plan_${i}.log 不存在，跳过"
            test_results["plan_${i}"]="SKIP"
            continue
        fi

        print_info "测试 plan_${i}.log ($NUM_TESTS 次)"

        # 为这个 plan 创建专门的测试日志目录（包含batch和iteration信息）
        local plan_test_log_dir="$TEST_RESULTS_DIR/plan_${i}"
        mkdir -p "$plan_test_log_dir"

        # 创建临时测试脚本，指定 LOG_FILE 和测试次数
        local test_script="playground_flow_test_all_workstations.py"
        local temp_script="playground_flow_test_temp_${i}.py"

        # 复制并修改测试脚本
        cp "$test_script" "$temp_script"

        # 修改 NUM_TESTS 和 LOG_FILE
        sed -i "s/num_tests = 5/num_tests = $NUM_TESTS/" "$temp_script"
        sed -i "s|LOG_FILE = \".*\"|LOG_FILE = \"$plan_file\"|" "$temp_script"

        # 运行测试
        local test_output
        test_output=$(python "$temp_script" 2>&1)

        # 保存测试输出到文件（包含batch和iteration信息，避免覆盖）
        echo "$test_output" > "$plan_test_log_dir/batch_${batch_idx}_iteration_${iteration}_test.log"

        # 从输出中提取成功率
        local success_count=$(echo "$test_output" | grep -oP "成功次数: \K\d+" || echo "0")
        local total_count=$NUM_TESTS

        # 检查是否至少有1次通过
        if [ "$success_count" -ge 1 ]; then
            print_success "plan_${i}.log 测试通过 ($success_count/$total_count)"
            test_results["plan_${i}"]="PASS:$success_count/$total_count"
        else
            print_warning "plan_${i}.log 测试失败 ($success_count/$total_count)"
            test_results["plan_${i}"]="FAIL:$success_count/$total_count"
        fi

        # 清理临时文件
        rm -f "$temp_script"
    done

    # 保存测试结果（包含batch信息，避免覆盖）
    local results_file="$TEST_RESULTS_DIR/batch_${batch_idx}_iteration_${iteration}_results.txt"
    > "$results_file"  # 清空文件
    for key in "${!test_results[@]}"; do
        echo "$key:${test_results[$key]}" >> "$results_file"
    done

    print_success "测试完成，结果已保存到 $results_file"
}

# 步骤3：反思分析失败的流程
analyze_failures() {
    local iteration=$1
    local batch_idx=$2  # 添加batch索引
    local results_file="$TEST_RESULTS_DIR/batch_${batch_idx}_iteration_${iteration}_results.txt"

    print_section "步骤3：反思分析失败的流程 (批次 $((batch_idx + 1)), 迭代 $iteration)"

    if [ ! -f "$results_file" ]; then
        print_warning "测试结果文件不存在: $results_file"
        return
    fi

    # 找出失败的 plan
    local failed_plans=()
    while IFS= read -r line; do
        if [[ "$line" == *":FAIL"* ]]; then
            local plan_name=$(echo "$line" | cut -d':' -f1)
            failed_plans+=("$plan_name")
        fi
    done < "$results_file"

    if [ ${#failed_plans[@]} -eq 0 ]; then
        print_success "没有失败的流程，跳过反思分析"
        return
    fi

    print_info "发现 ${#failed_plans[@]} 个失败的流程: ${failed_plans[*]}"

    cd "$AGENT_DIR"

    # 创建本次迭代的反思目录（包含batch信息）
    local iteration_reflection_dir="$REFLECTION_DIR/batch_${batch_idx}_iteration_${iteration}"
    mkdir -p "$iteration_reflection_dir"

    # 对每个失败的 plan 进行反思分析
    for plan in "${failed_plans[@]}"; do
        # 提取 plan 编号
        local plan_num=$(echo "$plan" | grep -oP '\d+')

        # 找到对应的测试日志（包含batch和iteration信息）
        local plan_test_log_dir="$TEST_RESULTS_DIR/plan_${plan_num}"
        local test_log=$(find "$plan_test_log_dir" -name "batch_${batch_idx}_iteration_${iteration}_test.log" -type f 2>/dev/null | head -1)

        if [ -z "$test_log" ]; then
            print_warning "未找到 $plan 的测试日志"
            continue
        fi

        print_info "分析 $plan 的失败原因..."

        # 使用反思智能体分析
        python reflection_agent.py \
            --log-file "$test_log" \
            --output "$iteration_reflection_dir/${plan}_feedback.json" \
            2>&1 | tee -a "$LOG_FILE"
    done

    # 批量分析测试日志以提取兼容性规则
    if [ -d "$TEST_RESULTS_DIR" ]; then
        print_info "批量分析测试日志以提取兼容性规则..."

        python reflection_agent.py \
            --log-dir "$TEST_RESULTS_DIR" \
            --output "$iteration_reflection_dir/reflection_summary.json" \
            --extract-rules \
            2>&1 | tee -a "$LOG_FILE"

        # 复制学习规则到规则目录（包含batch信息）
        if [ -f "$AGENT_DIR/learned_compatibility_rules.json" ]; then
            cp "$AGENT_DIR/learned_compatibility_rules.json" \
               "$RULES_DIR/learned_rules_batch_${batch_idx}_iteration_${iteration}.json"
        fi
    fi

    print_success "反思分析完成"
}

# 步骤4：检查是否所有流程都至少有1次通过
check_all_passed() {
    local batch_idx=$1  # 添加batch索引
    local iteration=$2  # 添加iteration索引

    print_info "检查是否所有流程都至少有1次测试通过..."

    local results_file="$TEST_RESULTS_DIR/batch_${batch_idx}_iteration_${iteration}_results.txt"

    if [ ! -f "$results_file" ]; then
        print_warning "没有找到测试结果文件: $results_file"
        return 1
    fi

    local total_files=0
    local passed_files=0
    local failed_plans=()

    while IFS= read -r line; do
        local plan_name=$(echo "$line" | cut -d':' -f1)
        local result=$(echo "$line" | cut -d':' -f2)

        total_files=$((total_files + 1))

        if [[ "$result" == "PASS"* ]]; then
            passed_files=$((passed_files + 1))
        elif [[ "$result" == "FAIL"* ]]; then
            failed_plans+=("$plan_name")
        fi
    done < "$results_file"

    print_info "通过率: $passed_files/$total_files"

    if [ "$passed_files" -eq "$total_files" ]; then
        print_success "所有流程都至少有1次测试通过！"
        return 0
    else
        print_warning "还有 ${#failed_plans[@]} 个流程未通过: ${failed_plans[*]}"
        return 1
    fi
}

# 获取失败的流程列表
get_failed_plans() {
    local batch_idx=$1  # 添加batch索引
    local iteration=$2  # 添加iteration索引

    local results_file="$TEST_RESULTS_DIR/batch_${batch_idx}_iteration_${iteration}_results.txt"
    local failed_plans=()

    if [ ! -f "$results_file" ]; then
        echo ""
        return
    fi

    while IFS= read -r line; do
        if [[ "$line" == *":FAIL"* ]]; then
            # 提取 plan_ 后面的数字
            local plan_name=$(echo "$line" | cut -d':' -f1)
            local plan_num=$(echo "$plan_name" | sed 's/plan_\([0-9]*\)/\1/')
            # 确保是有效数字
            if [[ "$plan_num" =~ ^[0-9]+$ ]] && [ "$plan_num" -gt 0 ]; then
                failed_plans+=("$plan_num")
            fi
        fi
    done < "$results_file"

    # 返回空格分隔的plan编号列表
    echo "${failed_plans[@]}"
}

# 重新生成失败的流程
regenerate_failed_workflows() {
    local failed_plans=$1
    local iteration=$2
    local batch_idx=$3  # 添加 batch_idx 参数

    if [ -z "$failed_plans" ]; then
        return
    fi

    print_section "重新生成失败的流程 (批次 $((batch_idx + 1)), 迭代 $iteration)"

    cd "$AGENT_DIR"

    for plan_num in $failed_plans; do
        # 尝试从映射文件读取原始 Paper 文件名
        local mapping_file="$PLAN_OUTPUT_DIR/plan_${plan_num}_mapping.txt"
        local md_file=""

        if [ -f "$mapping_file" ]; then
            local paper_name=$(cat "$mapping_file")
            md_file="$PIPELINE_DIR/$paper_name"
            print_info "从映射文件读取: plan_${plan_num} → $paper_name"
        else
            # 回退到旧的命名方式（Paper_X.md）
            md_file="$PIPELINE_DIR/Paper_${plan_num}.md"
            print_warning "映射文件不存在，使用默认命名: Paper_${plan_num}.md"
        fi

        if [ ! -f "$md_file" ]; then
            print_warning "文件不存在: $md_file，跳过 plan_${plan_num}"
            continue
        fi

        # 查找反馈文件（使用上一轮迭代的反馈，包含 batch 信息）
        local prev_iteration=$((iteration - 1))
        local feedback_file="$REFLECTION_DIR/batch_${batch_idx}_iteration_${prev_iteration}/plan_${plan_num}_feedback.json"

        print_info "重新生成 plan_${plan_num}.log..."

        # 构建基础命令参数
        local cmd_args="--input \"$PIPELINE_DIR\" --output \"$PLAN_OUTPUT_DIR\" --input-file \"$paper_name\" --target-plan \"$plan_num\" --model \"$MODEL\""

        # 添加 RAG 参数
        if [ "$USE_RAG" = false ]; then
            cmd_args="$cmd_args --no-rag"
        fi

        if [ -f "$feedback_file" ]; then
            print_info "  使用反馈文件: $feedback_file"
            cmd_args="$cmd_args --feedback \"$feedback_file\""
        else
            print_warning "  反馈文件不存在: $feedback_file，不使用反馈重新生成"
        fi

        # 执行命令
        eval "python pipeline_to_workstation_agent_plusConstraints.py $cmd_args" 2>&1 | tee -a "$LOG_FILE"
    done

    print_success "重新生成完成"
}

# 生成最终报告
generate_final_report() {
    print_section "生成最终报告"

    local report_file="$REPORTS_DIR/final_report.md"

    cat > "$report_file" << EOF
# 持续改进系统 - 最终报告

生成时间: $(date)

运行目录: \`$RUN_DIR\`

## 执行摘要

EOF

    # 汇总所有batch的结果
    local total_files=0
    local passed_files=0
    local total_success_tests=0
    local total_tests=0
    declare -A all_results  # 存储所有结果

    # 读取所有batch的最后迭代结果
    for results_file in "$TEST_RESULTS_DIR"/batch_*_iteration_*_results.txt; do
        if [ -f "$results_file" ]; then
            # 提取batch和iteration编号
            local filename=$(basename "$results_file" .txt)
            local batch_num=$(echo "$filename" | grep -oP 'batch_\K\d+')
            local iter_num=$(echo "$filename" | grep -oP 'iteration_\K\d+')

            # 只统计每个batch的最后一次迭代
            local is_last_iteration=true
            for other_file in "$TEST_RESULTS_DIR"/batch_${batch_num}_iteration_*_results.txt; do
                if [ -f "$other_file" ]; then
                    local other_iter=$(echo "$other_file" | grep -oP 'iteration_\K\d+')
                    if [ "$other_iter" -gt "$iter_num" ]; then
                        is_last_iteration=false
                        break
                    fi
                fi
            done

            if [ "$is_last_iteration" = true ]; then
                while IFS= read -r line; do
                    local plan_name=$(echo "$line" | cut -d':' -f1)
                    local result=$(echo "$line" | cut -d':' -f2)
                    total_files=$((total_files + 1))

                    # 存储结果
                    all_results["$plan_name"]="Batch $((batch_num + 1)): $result"

                    if [[ "$result" == "PASS"* ]]; then
                        passed_files=$((passed_files + 1))
                        # 提取测试通过次数
                        local success_count=$(echo "$result" | grep -oP 'PASS:\K\d+')
                        total_success_tests=$((total_success_tests + success_count))
                    fi
                    total_tests=$((total_tests + NUM_TESTS))
                done < "$results_file"
            fi
        fi
    done

    local pass_rate=0
    if [ "$total_files" -gt 0 ]; then
        pass_rate=$(echo "scale=1; $passed_files * 100 / $total_files" | bc)
    fi

    cat >> "$report_file" << EOF
- 总文件数: $total_files
- 至少1次通过的: $passed_files
- 完全失败的: $((total_files - passed_files))
- 计划通过率: ${pass_rate}%
- 总测试次数: $total_tests
- 成功测试次数: $total_success_tests

## 成功标准说明
每个 plan log 运行 $NUM_TESTS 次测试，只要有至少 1 次通过即视为成功。

## 各批次最终测试结果

EOF

    # 按plan排序输出结果
    for plan_name in $(echo "${!all_results[@]}" | sort); do
        echo "- **${plan_name}**: ${all_results[$plan_name]}" >> "$report_file"
    done

    # 添加所有批次的迭代历史
    cat >> "$report_file" << EOF

## 所有批次迭代历史

EOF

    # 按batch和iteration排序
    for results_file in $(ls "$TEST_RESULTS_DIR"/batch_*_iteration_*_results.txt 2>/dev/null | sort); do
        if [ -f "$results_file" ]; then
            local filename=$(basename "$results_file" .txt)
            local batch_num=$(echo "$filename" | grep -oP 'batch_\K\d+')
            local iter_num=$(echo "$filename" | grep -oP 'iteration_\K\d+')

            echo "### Batch $((batch_num + 1)), 迭代 $iter_num" >> "$report_file"
            cat "$results_file" >> "$report_file"
            echo "" >> "$report_file"
        fi
    done

    # 添加学习到的规则
    cat >> "$report_file" << EOF

## 学习到的兼容性规则

EOF

    # 合并所有batch和迭代的学习规则
    local rules_found=false
    for rule_file in "$RULES_DIR"/learned_rules_batch_*.json; do
        if [ -f "$rule_file" ]; then
            local rule_name=$(basename "$rule_file" .json | sed 's/learned_rules_//' | sed 's/_/ /g')
            echo "### $rule_name" >> "$report_file"
            echo "\`\`\`json" >> "$report_file"
            cat "$rule_file" >> "$report_file"
            echo "\`\`\`" >> "$report_file"
            echo "" >> "$report_file"
            rules_found=true
        fi
    done

    if [ "$rules_found" = false ]; then
        echo "（未提取到兼容性规则）" >> "$report_file"
    fi

    # 添加目录结构说明
    cat >> "$report_file" << EOF

## 输出文件结构

\`\`\`
$RUN_DIR/
├── plans/                    # 生成的 plan log 文件
├── test_results/             # 测试结果
│   ├── batch_0_iteration_1_results.txt  # 批次0迭代1的结果
│   ├── batch_0_iteration_2_results.txt  # 批次0迭代2的结果
│   ├── plan_1/
│   │   └── batch_0_iteration_1_test.log
│   │   └── batch_0_iteration_2_test.log
│   └── ...
├── reflection/               # 反思分析
│   ├── batch_0_iteration_1/
│   │   ├── plan_1_feedback.json
│   │   └── reflection_summary.json
│   └── ...
├── rules/                    # 学习规则
│   └── learned_rules_batch_*_iteration_*.json
├── reports/                  # 报告
│   └── final_report.md
├── logs/                     # 详细日志
│   └── run.log
└── run_info.txt             # 运行信息
\`\`\`

EOF

    print_success "最终报告已生成: $report_file"

    # 保存运行完成时间
    echo "完成时间: $(date)" >> "$RUN_DIR/run_info.txt"

    # 打印摘要到控制台
    echo ""
    echo "========================================="
    echo "          最终报告摘要"
    echo "========================================="
    echo "总文件数: $total_files"
    echo "成功: $passed_files"
    echo "失败: $((total_files - passed_files))"
    echo "通过率: ${pass_rate}%"
    echo "========================================="
    echo "运行目录: $RUN_DIR"
    echo "最终报告: $report_file"
    echo "详细日志: $LOG_FILE"
    echo "========================================="
}

# 主循环
main_loop() {
    local total_papers=$(ls -1 "$PIPELINE_DIR"/Paper_*.md 2>/dev/null | wc -l)
    local batch_count=$((total_papers / BATCH_SIZE))
    if [ $((total_papers % BATCH_SIZE)) -ne 0 ]; then
        batch_count=$((batch_count + 1))
    fi

    # 限制批次数
    if [ $MAX_BATCHES -lt $batch_count ] && [ $MAX_BATCHES -ne 0 ]; then
        batch_count=$MAX_BATCHES
    fi

    # 如果是继续运行模式，计算从哪个plan开始
    local start_plan_idx=1
    if [ -n "$CONTINUE_FROM" ]; then
        # 计算已生成的plan数量
        local existing_plans=$(ls -1 "$PLAN_OUTPUT_DIR"/plan_*.log 2>/dev/null | wc -l)

        if [ "$existing_plans" -gt 0 ]; then
            start_plan_idx=$((existing_plans + 1))

            print_info "继续运行模式："
            print_info "  已生成 $existing_plans 个 plan"
            print_info "  从 plan $start_plan_idx 开始"

            # 如果已经全部生成完
            if [ "$existing_plans" -ge "$total_papers" ]; then
                print_warning "所有 $total_papers 个 plan 都已生成！"
                print_info "如需重新生成，请不使用 --continue-from 参数"
                return
            fi
        fi
    fi

    # 计算起始batch索引
    local start_batch_idx=$(((start_plan_idx - 1) / BATCH_SIZE))

    print_info "总共 $total_papers 个文件，将处理 $batch_count 批（每批 $BATCH_SIZE 个）"

    # 对每批文件进行处理（从start_batch_idx开始）
    for batch_idx in $(seq $start_batch_idx $((batch_count - 1))); do
        local batch_start_idx=$((batch_idx * BATCH_SIZE + 1))
        local batch_end_idx=$((batch_start_idx + BATCH_SIZE - 1))
        local remaining=$((total_papers - batch_idx * BATCH_SIZE))
        local current_batch_size=$((remaining < BATCH_SIZE ? remaining : BATCH_SIZE))

        # 计算实际的start_idx（第一个batch可能是从中间开始）
        local actual_start_idx=$batch_start_idx
        if [ "$batch_idx" -eq "$start_batch_idx" ] && [ "$start_plan_idx" -gt "$batch_start_idx" ]; then
            actual_start_idx=$start_plan_idx
            current_batch_size=$((batch_end_idx - actual_start_idx + 1))
        fi

        print_section "批次 $((batch_idx + 1))/$batch_count (文件 $actual_start_idx-$((actual_start_idx + current_batch_size - 1)))"

        # 迭代循环
        for iteration in $(seq 1 $MAX_ITERATIONS); do
            print_section "=== 迭代 $iteration/$MAX_ITERATIONS (批次 $((batch_idx + 1))) ==="

            # 如果不是第一次迭代，只重新生成失败的流程
            if [ "$iteration" -gt 1 ]; then
                local prev_iteration=$((iteration - 1))
                local failed_plans=$(get_failed_plans "$batch_idx" "$prev_iteration")

                if [ -z "$failed_plans" ]; then
                    print_info "没有需要重新生成的流程"
                    break
                fi

                regenerate_failed_workflows "$failed_plans" "$iteration" "$batch_idx"

                # 重新生成后短暂等待，让API连接池有时间恢复
                print_info "等待API连接池恢复..."
                sleep 5
            else
                # 第一次迭代，生成所有流程
                generate_workflows "$actual_start_idx" "$current_batch_size" "$iteration"
            fi

            # 生成后短暂等待，让API连接池有时间恢复
            print_info "等待API连接池恢复..."
            sleep 5

            # 测试流程（传递batch_idx）
            test_workflows "$actual_start_idx" "$current_batch_size" "$iteration" "$batch_idx"

            # 检查是否全部通过（传递batch_idx和iteration）
            if check_all_passed "$batch_idx" "$iteration"; then
                print_success "批次 $((batch_idx + 1)) 在迭代 $iteration 完成所有流程！"
                break
            fi

            # 如果不是最后一次迭代，进行反思分析（传递batch_idx）
            if [ "$iteration" -lt "$MAX_ITERATIONS" ]; then
                analyze_failures "$iteration" "$batch_idx"
                print_warning "批次 $((batch_idx + 1)) 未完全通过，准备重新生成失败的流程..."
                sleep 5  # 等待更长时间，让API连接池和TIME_WAIT连接恢复
            fi
        done

        # 批次之间等待，让连接池完全恢复
        if [ "$batch_idx" -lt "$((batch_count - 1))" ]; then
            print_section "批次 $((batch_idx + 1)) 完成，等待5秒后继续下一批次..."
            sleep 5
        fi
    done

    # 生成最终报告
    generate_final_report

    print_section "持续改进系统完成"
    print_info "详细日志: $LOG_FILE"
    print_info "最终报告: $REPORTS_DIR/final_report.md"
}

# 信号处理
cleanup() {
    print_info "收到中断信号，正在清理..."
    # 清理临时文件
    find "$WORKSTATION_SIMULATOR_DIR" -name "playground_flow_test_temp_*.py" -delete 2>/dev/null || true
    exit 1
}

trap cleanup SIGINT SIGTERM

# 主函数
main() {
    # 解析命令行参数
    parse_args "$@"
    init
    main_loop
}

# 如果直接运行此脚本
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
