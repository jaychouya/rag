#!/bin/bash

# 定义根目录（写死在代码中）
ROOT_DIR="/home/ps/dsx/runtime_envs/law-agent/test/unparse0625"

# 定义子目录数组（写死在代码中）
SUBDIRS=("审计")

# 获取脚本所在目录（当前目录）
script_dir=$(dirname "$(realpath "$0")")

# 构建目标Python脚本路径（当前目录下的summary_law_json.py）
python_script="${script_dir}/summary_law_json.py"

# 检查Python脚本是否存在
if [ ! -f "$python_script" ]; then
    echo "错误: 未找到Python脚本: $python_script"
    exit 1
fi

# 遍历数组并执行Python脚本
for subdir in "${SUBDIRS[@]}"; do
    full_path="${ROOT_DIR}/${subdir}"
    echo "正在执行: python $python_script $full_path"
    python "$python_script" "$full_path" || echo "警告: 执行 $full_path 时出错"
done