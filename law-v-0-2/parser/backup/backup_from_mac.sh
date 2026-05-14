#!/bin/bash

# 从 Mac 本地备份 law 数据库的脚本
# 备份 LegalCategory 和 LegalDocuments 表

echo "开始从 Mac 本地备份 law 数据库..."

# 数据库名称
DATABASE_NAME="law"

# 检查数据库是否存在
DB_EXISTS=$(/Applications/Postgres.app/Contents/Versions/15/bin/psql -U postgres -p5432 -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DATABASE_NAME';" 2>/dev/null || echo "")

if [ -z "$DB_EXISTS" ]; then
    echo "错误：数据库 $DATABASE_NAME 不存在"
    exit 1
fi

echo "数据库 $DATABASE_NAME 存在"

# 检查LegalCategory表是否存在
CATEGORY_TABLE_EXISTS=$(/Applications/Postgres.app/Contents/Versions/15/bin/psql -U postgres -p5432 -d "$DATABASE_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='legalcategory';" 2>/dev/null || echo "")

if [ -z "$CATEGORY_TABLE_EXISTS" ]; then
    echo "错误：表 LegalCategory 不存在"
    exit 1
fi

# 检查LegalDocuments表是否存在
DOCUMENTS_TABLE_EXISTS=$(/Applications/Postgres.app/Contents/Versions/15/bin/psql -U postgres -p5432 -d "$DATABASE_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='legaldocuments';" 2>/dev/null || echo "")

if [ -z "$DOCUMENTS_TABLE_EXISTS" ]; then
    echo "错误：表 LegalDocuments 不存在"
    exit 1
fi

echo "在 $DATABASE_NAME 数据库中找到 LegalCategory 和 LegalDocuments 表"

# 生成带时间戳的备份文件名
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="./law_dump.sql"

echo "备份 law 数据库到文件: $BACKUP_FILE"

# 备份 LegalCategory 和 LegalDocuments 表（包含表结构和数据）
/Applications/Postgres.app/Contents/Versions/15/bin/pg_dump -U postgres -p5432 -d "$DATABASE_NAME" -t legalcategory -t legaldocuments --inserts > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✅ 备份成功！"
    
    # 备份文件信息
    BACKUP_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    echo "备份文件: $BACKUP_FILE"
    echo "文件大小: $BACKUP_SIZE"
    
    # 验证备份内容
    CATEGORY_COUNT=$(/Applications/Postgres.app/Contents/Versions/15/bin/psql -U postgres -p5432 -d "$DATABASE_NAME" -tAc "SELECT COUNT(*) FROM legalcategory;" 2>/dev/null || echo "0")
    DOCUMENTS_COUNT=$(/Applications/Postgres.app/Contents/Versions/15/bin/psql -U postgres -p5432 -d "$DATABASE_NAME" -tAc "SELECT COUNT(*) FROM legaldocuments;" 2>/dev/null || echo "0")
    echo "备份记录数:"
    echo "  LegalCategory: $CATEGORY_COUNT 条"
    echo "  LegalDocuments: $DOCUMENTS_COUNT 条"
    
else
    echo "❌ 备份失败！"
    exit 1
fi

echo "备份操作完成！"

