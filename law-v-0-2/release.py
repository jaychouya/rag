#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布脚本 - 自动化创建发布版本
功能：
1. 自动删除原有的release目录，并新建release目录
2. 创建.version文件，并且用日期+时间写入，代表release的时间
3. 将整个app目录拷贝到release目录中，并使用pyarmor混淆
4. pyarmor混淆会产生一个so的目录，也将其移动到app中
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_command(cmd, description):
    """执行命令并处理错误"""
    print(f"正在执行: {description}")
    print(f"命令: {cmd}")
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, 
                              capture_output=True, text=True)
        print(f"✓ {description} 成功")
        if result.stdout:
            print(f"输出: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} 失败")
        print(f"错误: {e.stderr}")
        return False


def check_dependencies():
    """检查必要的依赖"""
    print("=== 检查依赖 ===")
    import shutil

    # 检查 pyarmor 命令行工具
    if shutil.which("pyarmor") is None:
        print("✗ pyarmor 未安装或未加入PATH，请运行: pip install pyarmor")
        return False
    try:
        result = subprocess.run(["pyarmor", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ pyarmor 已安装，版本: {result.stdout.strip()}")
        else:
            print("✗ pyarmor 检查失败，请确认安装无误")
            return False
    except Exception as e:
        print(f"✗ pyarmor 检查异常: {e}")
        return False
    # 检查 Python 版本
    if sys.version_info < (3, 7):
        print("✗ Python 版本过低，需要 Python 3.7+")
        return False
    print("✓ Python 版本符合要求")
    return True


def create_release_directory():
    """创建发布目录"""
    print("\n=== 创建发布目录 ===")
    
    # 删除原有的 release 目录
    release_dir = Path("release")
    if release_dir.exists():
        print(f"删除原有目录: {release_dir}")
        shutil.rmtree(release_dir)
    
    # 创建新的 release 目录
    release_dir.mkdir(exist_ok=True)
    print(f"✓ 创建发布目录: {release_dir}")
    
    return release_dir


def create_version_file(release_dir):
    """创建版本文件"""
    print("\n=== 创建版本文件 ===")
    
    # 生成版本时间戳
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 创建 .version 文件
    version_file = release_dir / ".version"
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(timestamp)
    
    print(f"✓ 创建版本文件: {version_file}")
    print(f"版本时间: {timestamp}")


def copy_app_directory(release_dir):
    """拷贝 app 目录到 release 目录"""
    print("\n=== 拷贝 app 目录 ===")
    
    source_app = Path("app")
    target_app = release_dir / "app"
    
    if not source_app.exists():
        print(f"✗ 源目录不存在: {source_app}")
        return False
    
    # 拷贝 app 目录
    shutil.copytree(source_app, target_app)
    print(f"✓ 拷贝 app 目录: {source_app} -> {target_app}")
    
    return target_app


def obfuscate_with_pyarmor(app_dir):
    """使用 pyarmor 混淆代码"""
    print("\n=== 使用 pyarmor 混淆代码 ===")
    
    # 切换到 app 目录
    original_cwd = os.getcwd()
    os.chdir(app_dir)
    
    try:
        # 使用 pyarmor 混淆
        cmd = "pyarmor gen --recursive --output dist ."
        if not run_command(cmd, "pyarmor 混淆"):
            return False
        
        # 检查生成的 dist 目录
        dist_dir = Path("dist")
        if not dist_dir.exists():
            print("✗ pyarmor 未生成 dist 目录")
            return False
        
        # 将 dist 目录中的内容移动到当前目录（先删除当前目录下的所有内容，除了 dist）
        print("移动混淆后的文件...")
        for item in Path(".").iterdir():
            if item.name == "dist":
                continue
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        for item in dist_dir.iterdir():
            shutil.move(str(item), ".")
        # 删除空的 dist 目录
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
        
        print("✓ 混淆完成，文件已移动到 app 目录")
        return True
        
    finally:
        # 恢复原始工作目录
        os.chdir(original_cwd)


def copy_docker_compose(release_dir):
    """拷贝 docker-compose.yml 到发布目录"""
    print("\n=== 拷贝 Docker 配置 ===")
    
    docker_compose = Path("docker-compose.yml")
    if docker_compose.exists():
        shutil.copy2(docker_compose, release_dir)
        print(f"✓ 拷贝 docker-compose.yml 到发布目录")
    else:
        print("⚠ 未找到 docker-compose.yml 文件")


def main():
    """主函数"""
    print("=== 发布脚本启动 ===")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 创建发布目录
    release_dir = create_release_directory()
    
    # 创建版本文件
    create_version_file(release_dir)
    
    # 拷贝 app 目录
    app_dir = copy_app_directory(release_dir)
    if not app_dir:
        sys.exit(1)
    
    # 使用 pyarmor 混淆
    if not obfuscate_with_pyarmor(app_dir):
        print("✗ 混淆失败")
        sys.exit(1)
    
    # 拷贝 docker-compose.yml
    copy_docker_compose(release_dir)
    
    print("\n=== 发布完成 ===")
    print(f"发布目录: {release_dir.absolute()}")
    print("目录结构:")
    print(f"  {release_dir}/")
    print(f"  ├── .version          # 版本时间戳")
    print(f"  ├── app/              # 混淆后的应用代码")
    print(f"  │   ├── main.py       # 主程序")
    print(f"  │   ├── restful.py    # REST API")
    print(f"  │   ├── law_finder/   # 法律查找模块")
    print(f"  │   └── ...           # 其他文件")
    print(f"  └── docker-compose.yml # Docker 配置")
    print("\n要启动 Docker 容器，请执行：")
    print(f"cd {release_dir}")
    print("docker-compose up --build")


if __name__ == "__main__":
    main() 