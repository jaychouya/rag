#!/bin/bash

# Law数据库恢复脚本
# 通过 dsx_server_postgres 容器恢复数据库

set -e  # 遇到错误立即退出

echo "开始恢复Law数据库..."

# 检查 SQL 文件是否存在
DUMP_FILE="./law_dump.sql"
if [ ! -f "$DUMP_FILE" ]; then
    echo "错误：找不到数据库备份文件 $DUMP_FILE"
    exit 1
fi

# 容器名称
CONTAINER_NAME="dsx_server_postgres"

# 检查容器是否运行
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "错误：容器 $CONTAINER_NAME 没有运行"
    echo "请先启动 PostgreSQL 容器"
    exit 1
fi

echo "找到运行中的容器: $CONTAINER_NAME"

# 从容器中获取环境变量
echo "获取数据库连接信息..."
PGDB_USER=$(docker exec $CONTAINER_NAME printenv PGDB_USER || echo "postgres")
PGDB_NAME=$(docker exec $CONTAINER_NAME printenv PGDB_NAME || echo "law")
PGDB_HOST=$(docker exec $CONTAINER_NAME printenv PGDB_HOST || echo "localhost")
PGDB_PORT=$(docker exec $CONTAINER_NAME printenv PGDB_PORT || echo "5432")
PGDB_PASS=$(docker exec $CONTAINER_NAME printenv PGDB_PASS || echo "")

echo "数据库连接信息:"
echo "  用户: $PGDB_USER"
echo "  数据库: $PGDB_NAME"
echo "  主机: $PGDB_HOST"
echo "  端口: $PGDB_PORT"
echo "  密码: $([ -n "$PGDB_PASS" ] && echo "已设置" || echo "未设置")"

# 设置密码环境变量（如果有的话）
if [ -n "$PGDB_PASS" ]; then
    export PGPASSWORD="$PGDB_PASS"
fi

# 构建psql连接参数
PSQL_PARAMS="-U $PGDB_USER -h $PGDB_HOST -p $PGDB_PORT"
if [ -n "$PGDB_PASS" ]; then
    PSQL_ENV="PGPASSWORD=$PGDB_PASS"
else
    PSQL_ENV=""
fi

# 1. 检查目标数据库是否存在，如果不存在则创建
echo "检查数据库 $PGDB_NAME 是否存在..."
DB_EXISTS=$(docker exec $CONTAINER_NAME bash -c "$PSQL_ENV psql $PSQL_PARAMS -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='$PGDB_NAME';\"" 2>/dev/null || echo "")

if [ -z "$DB_EXISTS" ]; then
    echo "数据库 $PGDB_NAME 不存在，正在创建..."
    docker exec $CONTAINER_NAME bash -c "$PSQL_ENV psql $PSQL_PARAMS -d postgres -c \"CREATE DATABASE $PGDB_NAME;\""
    echo "数据库 $PGDB_NAME 创建成功"
else
    echo "数据库 $PGDB_NAME 已存在"
fi

# 2. 检查表是否存在，如果存在则询问是否覆盖
echo "检查表是否存在..."
CATEGORY_TABLE_EXISTS=$(docker exec $CONTAINER_NAME bash -c "$PSQL_ENV psql $PSQL_PARAMS -d $PGDB_NAME -tAc \"SELECT 1 FROM information_schema.tables WHERE table_name='legalcategory';\"" 2>/dev/null || echo "")
DOCUMENTS_TABLE_EXISTS=$(docker exec $CONTAINER_NAME bash -c "$PSQL_ENV psql $PSQL_PARAMS -d $PGDB_NAME -tAc \"SELECT 1 FROM information_schema.tables WHERE table_name='legaldocuments';\"" 2>/dev/null || echo "")

if [ ! -z "$CATEGORY_TABLE_EXISTS" ] || [ ! -z "$DOCUMENTS_TABLE_EXISTS" ]; then
    echo "警告：以下表已存在："
    [ ! -z "$CATEGORY_TABLE_EXISTS" ] && echo "  - LegalCategory"
    [ ! -z "$DOCUMENTS_TABLE_EXISTS" ] && echo "  - LegalDocuments"
    read -p "是否要删除现有表并重新创建？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "删除现有表..."
        docker exec $CONTAINER_NAME bash -c "$PSQL_ENV psql $PSQL_PARAMS -d $PGDB_NAME -c \"DROP TABLE IF EXISTS legaldocuments CASCADE;\""
        docker exec $CONTAINER_NAME bash -c "$PSQL_ENV psql $PSQL_PARAMS -d $PGDB_NAME -c \"DROP TABLE IF EXISTS legalcategory CASCADE;\""
        echo "现有表已删除"
    else
        echo "取消恢复操作"
        exit 1
    fi
fi

# 3. 恢复数据库
echo "开始恢复数据库..."
if [ -n "$PGDB_PASS" ]; then
    docker exec -i $CONTAINER_NAME bash -c "PGPASSWORD=$PGDB_PASS psql $PSQL_PARAMS -d $PGDB_NAME" < "$DUMP_FILE"
else
    docker exec -i $CONTAINER_NAME psql $PSQL_PARAMS -d "$PGDB_NAME" < "$DUMP_FILE"
fi

if [ $? -eq 0 ]; then
    echo "✅ 数据库恢复成功！"
    
    # 4. 验证恢复结果
    echo "验证恢复结果..."
    CATEGORY_COUNT=$(docker exec $CONTAINER_NAME bash -c "$PSQL_ENV psql $PSQL_PARAMS -d $PGDB_NAME -tAc \"SELECT COUNT(*) FROM legalcategory;\"" 2>/dev/null || echo "0")
    DOCUMENTS_COUNT=$(docker exec $CONTAINER_NAME bash -c "$PSQL_ENV psql $PSQL_PARAMS -d $PGDB_NAME -tAc \"SELECT COUNT(*) FROM legaldocuments;\"" 2>/dev/null || echo "0")
    echo "恢复后的数据统计:"
    echo "  LegalCategory: $CATEGORY_COUNT 条记录"
    echo "  LegalDocuments: $DOCUMENTS_COUNT 条记录"
    
    # 显示分类统计
    echo "各分类记录数统计:"
    docker exec $CONTAINER_NAME bash -c "$PSQL_ENV psql $PSQL_PARAMS -d $PGDB_NAME -c \"SELECT type, COUNT(*) as count FROM legalcategory GROUP BY type ORDER BY count DESC;\""
    
else
    echo "❌ 数据库恢复失败！"
    exit 1
fi

echo "恢复操作完成！"