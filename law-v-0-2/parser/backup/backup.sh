#!/bin/bash

# Law数据库备份脚本
# 通过 dsx_server_postgres 容器备份数据库

set -e  # 遇到错误立即退出

echo "开始备份Law数据库..."

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
PGDB_USER=$(docker exec $CONTAINER_NAME printenv PGDB_USER || echo "")
PGDB_NAME=$(docker exec $CONTAINER_NAME printenv PGDB_NAME || echo "")
PGDB_HOST=$(docker exec $CONTAINER_NAME printenv PGDB_HOST || echo "")
PGDB_PORT=$(docker exec $CONTAINER_NAME printenv PGDB_PORT || echo "")

echo "数据库连接信息:"
echo "  用户: $PGDB_USER"
echo "  数据库: $PGDB_NAME"
echo "  主机: $PGDB_HOST"
echo "  端口: $PGDB_PORT"

# 检查数据库和表是否存在
echo "检查数据库和表是否存在..."
DB_EXISTS=$(docker exec $CONTAINER_NAME psql -U "$PGDB_USER" -h "$PGDB_HOST" -p "$PGDB_PORT" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$PGDB_NAME';" 2>/dev/null || echo "")

if [ -z "$DB_EXISTS" ]; then
    echo "错误：数据库 $PGDB_NAME 不存在"
    exit 1
fi

# 检查LegalCategory表是否存在
CATEGORY_TABLE_EXISTS=$(docker exec $CONTAINER_NAME psql -U "$PGDB_USER" -h "$PGDB_HOST" -p "$PGDB_PORT" -d "$PGDB_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='legalcategory';" 2>/dev/null || echo "")

if [ -z "$CATEGORY_TABLE_EXISTS" ]; then
    echo "错误：表 LegalCategory 不存在"
    exit 1
fi

# 检查LegalDocuments表是否存在
DOCUMENTS_TABLE_EXISTS=$(docker exec $CONTAINER_NAME psql -U "$PGDB_USER" -h "$PGDB_HOST" -p "$PGDB_PORT" -d "$PGDB_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='legaldocuments';" 2>/dev/null || echo "")

if [ -z "$DOCUMENTS_TABLE_EXISTS" ]; then
    echo "错误：表 LegalDocuments 不存在"
    exit 1
fi

# 生成带时间戳的备份文件名
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="./law_dump_$TIMESTAMP.sql"

echo "开始备份到文件: $BACKUP_FILE"

# 执行备份 - 备份表结构和数据
docker exec $CONTAINER_NAME pg_dump -U "$PGDB_USER" -h "$PGDB_HOST" -p "$PGDB_PORT" -d "$PGDB_NAME" -t legalcategory -t legaldocuments --inserts > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✅ 数据库备份成功！"
    
    # 备份文件信息
    BACKUP_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    echo "备份文件: $BACKUP_FILE"
    echo "文件大小: $BACKUP_SIZE"
    
    # 验证备份内容
    CATEGORY_COUNT=$(docker exec $CONTAINER_NAME psql -U "$PGDB_USER" -h "$PGDB_HOST" -p "$PGDB_PORT" -d "$PGDB_NAME" -tAc "SELECT COUNT(*) FROM legalcategory;" 2>/dev/null || echo "0")
    DOCUMENTS_COUNT=$(docker exec $CONTAINER_NAME psql -U "$PGDB_USER" -h "$PGDB_HOST" -p "$PGDB_PORT" -d "$PGDB_NAME" -tAc "SELECT COUNT(*) FROM legaldocuments;" 2>/dev/null || echo "0")
    echo "备份记录数:"
    echo "  LegalCategory: $CATEGORY_COUNT 条"
    echo "  LegalDocuments: $DOCUMENTS_COUNT 条"
    
else
    echo "❌ 数据库备份失败！"
    exit 1
fi

echo "备份操作完成！"

