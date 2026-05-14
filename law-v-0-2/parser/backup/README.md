# Law数据库备份和恢复脚本

这些脚本用于备份和恢复law数据库，通过 `dsx_server_postgres` Docker 容器操作。

## 📁 文件说明

- `backup.sh` - 数据库备份脚本（备份 LegalCategory 和 LegalDocuments 表）
- `backup_from_mac.sh` - 从Mac本地备份脚本
- `restore.sh` - 数据库恢复脚本
- `law_dump.sql` - 最新的数据库备份文件
- `law_dump_YYYYMMDD_HHMMSS.sql` - 带时间戳的备份文件

## 🔧 前置要求

1. **Docker 容器运行中**：确保 `dsx_server_postgres` 容器正在运行
2. **环境变量**：容器中应包含以下环境变量：
   - `PGDB_USER` - 数据库用户名（默认：postgres）
   - `PGDB_NAME` - 数据库名称（默认：law）
   - `PGDB_HOST` - 数据库主机（默认：localhost）
   - `PGDB_PORT` - 数据库端口（默认：5432）
   - `PGDB_PASS` - 数据库密码（可选）

## 📊 备份操作

### 使用方法
```bash
cd parser/backup
./backup.sh
```

### 功能特点
- ✅ 自动检测容器是否运行
- ✅ 从容器获取数据库连接信息
- ✅ 生成带时间戳的备份文件
- ✅ 备份表结构和数据，使用 INSERT 语句格式
- ✅ 验证备份结果
- ✅ 创建最新备份的软链接

### 输出示例
```
开始备份Law数据库...
找到运行中的容器: dsx_server_postgres
获取数据库连接信息...
数据库连接信息:
  用户: postgres
  数据库: law
  主机: localhost
  端口: 5432
检查数据库和表是否存在...
开始备份到文件: ./law_dump_20241202_143022.sql
✅ 数据库备份成功！
备份文件: ./law_dump_20241202_143022.sql
文件大小: 2.1M
备份记录数:
  LegalCategory: 26 条
  LegalDocuments: 114 条
已创建最新备份链接: law_dump.sql -> ./law_dump_20241202_143022.sql
备份操作完成！
```

## 🔄 恢复操作

### 使用方法
```bash
cd parser/backup
./restore.sh
```

### 功能特点
- ✅ 自动检测容器是否运行
- ✅ 从容器获取数据库连接信息
- ✅ 自动创建不存在的数据库
- ✅ 安全检查：询问是否覆盖现有表
- ✅ 验证恢复结果
- ✅ 显示恢复后的数据统计

### 交互式确认
如果表已存在，脚本会询问：
```
警告：以下表已存在：
  - LegalCategory
  - LegalDocuments
是否要删除现有表并重新创建？(y/N):
```

### 输出示例
```
开始恢复Law数据库...
找到运行中的容器: dsx_server_postgres
获取数据库连接信息...
数据库连接信息:
  用户: postgres
  数据库: law
  主机: localhost
  端口: 5432
检查数据库 law 是否存在...
数据库 law 已存在
检查表是否存在...
开始恢复数据库...
✅ 数据库恢复成功！
验证恢复结果...
恢复后的数据统计:
  LegalCategory: 26 条记录
  LegalDocuments: 114 条记录
各分类记录数统计:
           type            | count 
---------------------------+-------
 其他公共法规              |    18
 公安内部纪律规范          |     4
 信访                     |     2
 督查                     |     2
恢复操作完成！
```

## 🖥️ Mac本地备份

### 使用方法
```bash
cd parser/backup
./backup_from_mac.sh
```

### 功能特点
- ✅ 从Mac本地PostgreSQL备份
- ✅ 自动检测数据库和表是否存在
- ✅ 生成带时间戳的备份文件
- ✅ 验证备份内容

## ⚠️ 注意事项

1. **权限要求**：确保脚本有执行权限（`chmod +x *.sh`）
2. **容器名称**：脚本假设容器名为 `dsx_server_postgres`
3. **备份文件**：恢复脚本会查找 `./law_dump.sql` 文件
4. **数据覆盖**：恢复操作会完全替换现有数据
5. **网络连接**：确保容器网络配置正确
6. **表依赖关系**：LegalDocuments表依赖于LegalCategory表，恢复时会按正确顺序处理

## 🛠️ 故障排除

### 常见错误

**容器未运行**
```
错误：容器 dsx_server_postgres 没有运行
请先启动 PostgreSQL 容器
```
解决方案：启动 PostgreSQL 容器

**备份文件不存在**
```
错误：找不到数据库备份文件 ./law_dump.sql
```
解决方案：先运行备份脚本或确保备份文件存在

**数据库不存在**
```
错误：数据库 law 不存在
```
解决方案：恢复脚本会自动创建数据库

**表不存在**
```
错误：表 LegalCategory 不存在
错误：表 LegalDocuments 不存在
```
解决方案：确保数据库中有正确的表结构

### 手动操作

如果脚本无法正常工作，可以手动执行：

```bash
# 手动备份
docker exec dsx_server_postgres pg_dump -U postgres -d law -t legalcategory -t legaldocuments > backup.sql

# 手动恢复
docker exec -i dsx_server_postgres psql -U postgres -d law < backup.sql
```

## 📋 维护建议

1. **定期备份**：建议每日执行备份操作
2. **备份清理**：定期清理旧的备份文件
3. **测试恢复**：定期测试恢复流程
4. **监控容器**：确保 PostgreSQL 容器稳定运行
5. **数据验证**：备份后验证数据完整性