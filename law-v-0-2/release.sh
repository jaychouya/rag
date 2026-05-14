#!/bin/bash

# 代码发布脚本 - 一键执行混淆和编译

echo "=== 代码发布脚本 ==="
echo "此脚本将执行以下步骤："
echo "1. 使用 pyarmor 混淆 app 目录下的代码"
echo "2. 使用 Cython 编译混淆后的代码"
echo "3. 创建 Docker 部署文件"
echo ""

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

# 检查必要的包
echo "检查必要的 Python 包..."
python3 -c "import pyarmor" 2>/dev/null || {
    echo "错误: 未安装 pyarmor，请运行: pip install pyarmor"
    exit 1
}

python3 -c "import Cython" 2>/dev/null || {
    echo "错误: 未安装 Cython，请运行: pip install Cython"
    exit 1
}

# 第一步：混淆代码
echo ""
echo "=== 第一步：代码混淆 ==="
python3 release_obfuscate.py
if [ $? -ne 0 ]; then
    echo "代码混淆失败!"
    exit 1
fi

echo ""
echo "=== 第二步：Cython 编译 ==="
python3 release_cython.py
if [ $? -ne 0 ]; then
    echo "Cython 编译失败!"
    exit 1
fi

echo ""
echo "=== 发布完成! ==="
echo "发布目录结构："
echo "release_$(date +%Y%m%d)/"
echo "  ├── obfuscated/     # 混淆后的代码"
echo "  ├── cython/         # 编译后的代码"
echo "  └── templates/      # 模板文件"
echo ""
echo "要启动 Docker 容器，请执行："
echo "cd release_$(date +%Y%m%d)/cython"
echo "docker-compose up --build" 