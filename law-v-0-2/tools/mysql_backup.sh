#!/bin/bash

# MySQL数据库备份和恢复工具
# 使用方法:
#   备份: ./mysql_backup.sh backup -c 容器名 -u 用户名 -p 密码 [-d 数据库名] [-o 输出目录]
#   恢复: ./mysql_backup.sh restore -c 容器名 -u 用户名 -p 密码 -f 备份文件 [-d 数据库名]

set -e  # 遇到错误立即退出

# 默认值
DATABASE="law"
OUTPUT_DIR="./backups"
FULL_BACKUP=false

# 检测操作系统
OS_TYPE=""
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS_TYPE="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="macos"
elif [[ "$OSTYPE" == "cygwin" ]]; then
    OS_TYPE="windows"
elif [[ "$OSTYPE" == "msys" ]]; then
    OS_TYPE="windows"
else
    OS_TYPE="unknown"
fi

# 跨平台文件大小获取函数
get_file_size() {
    local file_path="$1"
    local file_size=0
    
    if [ ! -f "$file_path" ]; then
        echo "0"
        return
    fi
    
    case "$OS_TYPE" in
        "linux")
            file_size=$(stat -c%s "$file_path" 2>/dev/null || echo "0")
            ;;
        "macos")
            file_size=$(stat -f%z "$file_path" 2>/dev/null || echo "0")
            ;;
        *)
            # 备用方法，适用于大多数UNIX系统
            file_size=$(wc -c < "$file_path" 2>/dev/null | tr -d ' ' || echo "0")
            ;;
    esac
    
    echo "$file_size"
}

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示使用说明
show_usage() {
    echo "MySQL数据库备份和恢复工具"
    echo ""
    echo "使用方法:"
    echo "  备份数据库:"
    echo "    $0 backup -c <容器名> -u <用户名> -p <密码> [-d <数据库名>] [-o <输出目录>] [--full]"
    echo ""
    echo "  恢复数据库:"
    echo "    $0 restore -c <容器名> -u <用户名> -p <密码> -f <备份文件> [-d <数据库名>]"
    echo ""
    echo "参数说明:"
    echo "  -c, --container   MySQL Docker容器名称 (必需)"
    echo "  -u, --username    MySQL用户名 (必需)"
    echo "  -p, --password    MySQL密码 (必需)"
    echo "  -d, --database    数据库名称 (默认: law)"
    echo "  -o, --output      备份文件输出目录 (默认: ./backups)"
    echo "  -f, --file        备份文件路径 (恢复时必需)"
    echo "  --full            完整备份模式 (包含数据库创建语句)"
    echo "  -h, --help        显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  # 普通备份数据库"
    echo "  $0 backup -c mysql_container -u root -p mypassword"
    echo ""
    echo "  # 完整备份数据库 (包含数据库创建语句)"
    echo "  $0 backup -c mysql_container -u root -p mypassword --full"
    echo ""
    echo "  # 恢复数据库"
    echo "  $0 restore -c mysql_container -u root -p mypassword -f ./backups/law_backup_20231201_143022.sql"
    echo ""
    echo "  # 系统兼容性检查"
    echo "  $0 check"
}

# 备份数据库
backup_database() {
    print_info "开始备份数据库 ${DATABASE}..."
    
    # 确保输出目录存在
    mkdir -p "$OUTPUT_DIR"
    
    # 生成备份文件名（包含时间戳和备份类型）
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    if [ "$FULL_BACKUP" = true ]; then
        BACKUP_FILENAME="${DATABASE}_full_backup_${TIMESTAMP}.sql"
    else
        BACKUP_FILENAME="${DATABASE}_data_backup_${TIMESTAMP}.sql"
    fi
    BACKUP_PATH="${OUTPUT_DIR}/${BACKUP_FILENAME}"
    
    print_info "备份文件将保存到: ${BACKUP_PATH}"
    
    # 构建mysqldump命令
    if [ "$FULL_BACKUP" = true ]; then
        # 完整备份模式：包含数据库创建和选择语句
        MYSQLDUMP_CMD="mysqldump -u${USERNAME} -p${PASSWORD} --single-transaction --routines --triggers --databases ${DATABASE}"
        print_info "备份模式: 完整备份 (包含数据库创建语句)"
    else
        # 普通备份模式：仅备份数据库内容
        MYSQLDUMP_CMD="mysqldump -u${USERNAME} -p${PASSWORD} --single-transaction --routines --triggers ${DATABASE}"
        print_info "备份模式: 数据备份 (仅数据库内容)"
    fi
    
    # 在Docker容器中执行备份命令
    DOCKER_CMD="docker exec ${CONTAINER_NAME} ${MYSQLDUMP_CMD}"
    
    # 执行备份
    if $DOCKER_CMD > "$BACKUP_PATH" 2>./backup_error.log; then
        # 使用跨平台函数检查备份文件大小
        FILE_SIZE=$(get_file_size "$BACKUP_PATH")
        
        if [ "$FILE_SIZE" -gt 100 ]; then  # 至少要有100字节（SQL头部信息）
            print_success "备份成功完成! 文件大小: ${FILE_SIZE} 字节"
            print_success "备份文件路径: ${BACKUP_PATH}"
            
            # 显示一些额外的文件信息
            print_info "系统类型: ${OS_TYPE}"
            if command -v ls >/dev/null 2>&1; then
                print_info "文件详情: $(ls -lh "$BACKUP_PATH" | awk '{print $5, $9}')"
            fi
        else
            print_error "备份失败: 生成的备份文件过小或为空 (大小: ${FILE_SIZE} 字节)"
            if [ -f ./backup_error.log ]; then
                print_error "错误信息: $(cat ./backup_error.log)"
            fi
            rm -f "$BACKUP_PATH"
            exit 1
        fi
    else
        print_error "备份失败"
        if [ -f ./backup_error.log ]; then
            print_error "错误信息: $(cat ./backup_error.log)"
        fi
        rm -f "$BACKUP_PATH"
        exit 1
    fi
    
    # 清理错误日志
    rm -f ./backup_error.log
}

# 恢复数据库
restore_database() {
    print_info "开始恢复数据库 ${DATABASE}..."
    
    # 检查备份文件是否存在
    if [ ! -f "$BACKUP_FILE" ]; then
        print_error "备份文件不存在: ${BACKUP_FILE}"
        exit 1
    fi
    
    # 获取备份文件的绝对路径 (跨平台兼容)
    if command -v realpath >/dev/null 2>&1; then
        BACKUP_FILE=$(realpath "$BACKUP_FILE")
    elif command -v greadlink >/dev/null 2>&1; then
        # macOS上可能安装了GNU coreutils
        BACKUP_FILE=$(greadlink -f "$BACKUP_FILE")
    elif [[ "$BACKUP_FILE" != /* ]]; then
        # 如果不是绝对路径，手动转换
        BACKUP_FILE="$(pwd)/$BACKUP_FILE"
    fi
    
    print_info "从备份文件恢复: ${BACKUP_FILE}"
    
    # 检测备份文件类型（是否包含数据库创建语句）
    if grep -q "CREATE DATABASE" "$BACKUP_FILE" 2>/dev/null; then
        print_info "检测到完整备份文件 (包含数据库创建语句)"
        SKIP_DB_CREATE=true
    else
        print_info "检测到数据备份文件 (需要预先创建数据库)"
        SKIP_DB_CREATE=false
    fi
    
    # 如果不是完整备份，需要先检查数据库是否存在，如果不存在则创建
    if [ "$SKIP_DB_CREATE" = false ]; then
        CREATE_DB_SQL="CREATE DATABASE IF NOT EXISTS ${DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        DOCKER_CREATE_CMD="docker exec ${CONTAINER_NAME} mysql -u${USERNAME} -p${PASSWORD} -e \"${CREATE_DB_SQL}\""
        
        print_info "确保目标数据库存在..."
        if eval "$DOCKER_CREATE_CMD" 2>./create_error.log; then
            print_success "数据库 ${DATABASE} 已准备就绪"
        else
            print_error "创建数据库失败"
            if [ -f ./create_error.log ]; then
                print_error "错误信息: $(cat ./create_error.log)"
            fi
            exit 1
        fi
    else
        print_info "跳过数据库创建 (备份文件已包含数据库创建语句)"
    fi
    
    # 将备份文件复制到容器中
    CONTAINER_BACKUP_PATH="/tmp/$(basename "$BACKUP_FILE")"
    COPY_CMD="docker cp ${BACKUP_FILE} ${CONTAINER_NAME}:${CONTAINER_BACKUP_PATH}"
    
    print_info "将备份文件复制到容器中..."
    if $COPY_CMD 2>./copy_error.log; then
        print_success "备份文件已复制到容器"
    else
        print_error "复制备份文件到容器失败"
        if [ -f ./copy_error.log ]; then
            print_error "错误信息: $(cat ./copy_error.log)"
        fi
        exit 1
    fi
    
    # 构建mysql恢复命令
    if [ "$SKIP_DB_CREATE" = true ]; then
        # 完整备份：不需要指定数据库名，让SQL文件自己处理
        MYSQL_CMD="mysql -u${USERNAME} -p${PASSWORD} < ${CONTAINER_BACKUP_PATH}"
        print_info "恢复模式: 完整恢复 (包含数据库创建)"
    else
        # 数据备份：需要指定目标数据库
        MYSQL_CMD="mysql -u${USERNAME} -p${PASSWORD} ${DATABASE} < ${CONTAINER_BACKUP_PATH}"
        print_info "恢复模式: 数据恢复 (到指定数据库: ${DATABASE})"
    fi
    DOCKER_RESTORE_CMD="docker exec ${CONTAINER_NAME} sh -c '${MYSQL_CMD}'"
    
    print_info "开始恢复数据..."
    if eval "$DOCKER_RESTORE_CMD" 2>./restore_error.log; then
        print_success "数据库恢复成功!"
        
        # 清理容器中的临时备份文件
        CLEANUP_CMD="docker exec ${CONTAINER_NAME} rm -f ${CONTAINER_BACKUP_PATH}"
        $CLEANUP_CMD 2>/dev/null || true
        
    else
        print_error "恢复数据库失败"
        if [ -f ./restore_error.log ]; then
            print_error "错误信息: $(cat ./restore_error.log)"
        fi
        
        # 清理容器中的临时备份文件
        CLEANUP_CMD="docker exec ${CONTAINER_NAME} rm -f ${CONTAINER_BACKUP_PATH}"
        $CLEANUP_CMD 2>/dev/null || true
        exit 1
    fi
    
    # 清理错误日志
    rm -f ./create_error.log ./copy_error.log ./restore_error.log
}

# 检查Docker是否运行
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker命令未找到，请确保Docker已安装"
        exit 1
    fi
    
    if ! docker ps &> /dev/null; then
        print_error "无法连接到Docker守护进程，请确保Docker正在运行"
        exit 1
    fi
}

# 检查容器是否存在并运行
check_container() {
    if ! docker ps --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        print_error "容器 '${CONTAINER_NAME}' 未运行或不存在"
        print_info "当前运行的容器:"
        docker ps --format "table {{.Names}}\t{{.Status}}"
        exit 1
    fi
}

# 系统兼容性检查
check_system_compatibility() {
    print_info "=== 系统兼容性检查 ==="
    
    # 检测操作系统
    print_info "操作系统类型: ${OS_TYPE}"
    print_info "OSTYPE: ${OSTYPE}"
    
    # 检查必要的命令
    local required_commands=("docker" "stat" "wc" "ls" "awk" "tr")
    local missing_commands=()
    
    for cmd in "${required_commands[@]}"; do
        if command -v "$cmd" >/dev/null 2>&1; then
            print_success "✓ $cmd 命令可用"
        else
            print_warning "✗ $cmd 命令未找到"
            missing_commands+=("$cmd")
        fi
    done
    
    # 测试文件大小检测函数
    print_info "测试文件大小检测函数..."
    echo "test content" > ./test_file_size.tmp
    local test_size=$(get_file_size "./test_file_size.tmp")
    if [ "$test_size" -gt 0 ]; then
        print_success "✓ 文件大小检测正常 (测试文件: ${test_size} 字节)"
    else
        print_error "✗ 文件大小检测失败"
    fi
    rm -f ./test_file_size.tmp
    
    # 检查Docker
    if command -v docker >/dev/null 2>&1; then
        if docker ps >/dev/null 2>&1; then
            print_success "✓ Docker 守护进程运行正常"
            print_info "Docker 版本: $(docker --version)"
        else
            print_warning "✗ Docker 守护进程未运行"
        fi
    fi
    
    # 总结
    if [ ${#missing_commands[@]} -eq 0 ]; then
        print_success "=== 系统兼容性检查通过! ==="
        print_info "脚本可以在当前系统 (${OS_TYPE}) 上正常运行"
    else
        print_warning "=== 系统兼容性检查发现问题 ==="
        print_warning "缺少命令: ${missing_commands[*]}"
        print_info "请安装缺少的命令后重试"
    fi
}

# 主函数
main() {
    # 检查参数数量
    if [ $# -eq 0 ]; then
        show_usage
        exit 0
    fi
    
    # 检查第一个参数（命令）
    COMMAND=$1
    shift
    
    case "$COMMAND" in
        "backup"|"restore")
            ;;
        "check")
            check_system_compatibility
            exit 0
            ;;
        "-h"|"--help"|"help")
            show_usage
            exit 0
            ;;
        *)
            print_error "未知命令: $COMMAND"
            show_usage
            exit 1
            ;;
    esac
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -c|--container)
                CONTAINER_NAME="$2"
                shift 2
                ;;
            -u|--username)
                USERNAME="$2"
                shift 2
                ;;
            -p|--password)
                PASSWORD="$2"
                shift 2
                ;;
            -d|--database)
                DATABASE="$2"
                shift 2
                ;;
            -o|--output)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            -f|--file)
                BACKUP_FILE="$2"
                shift 2
                ;;
            --full)
                FULL_BACKUP=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "未知参数: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # 检查必需参数
    if [ -z "$CONTAINER_NAME" ] || [ -z "$USERNAME" ] || [ -z "$PASSWORD" ]; then
        print_error "缺少必需参数: 容器名(-c), 用户名(-u), 密码(-p)"
        show_usage
        exit 1
    fi
    
    if [ "$COMMAND" = "restore" ] && [ -z "$BACKUP_FILE" ]; then
        print_error "恢复命令需要指定备份文件(-f)"
        show_usage
        exit 1
    fi
    
    # 检查Docker和容器
    check_docker
    check_container
    
    # 执行相应命令
    case "$COMMAND" in
        "backup")
            backup_database
            ;;
        "restore")
            restore_database
            ;;
    esac
}

# 运行主函数
main "$@" 