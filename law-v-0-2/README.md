# 法规查询 MCP 服务

## 项目概述

这是一个基于 MCP (Model Context Protocol) 的法规查询服务，提供智能化的法规检索和匹配功能。服务支持两种主要的查询模式：直接法规查询和基于案例的法规匹配。

## 核心功能

### 1. 直接法规查询 (`query_law_by_lawpath`)
- **功能描述**: 用户直接指定法规名称、章节、条款等信息进行精确查询
- **适用场景**: 已知具体法规名称和条款编号的查询
- **输入**: 法规名称、章节名字、条款编号等文字信息
- **输出**: 相关法规内容的详细信息和匹配结果

### 2. 案例匹配法规 (`query_law_by_case_info`)
- **功能描述**: 基于用户提供的案例信息，智能匹配相关法规
- **适用场景**: 通过具体案例查找适用的法规条款
- **输入**: 案例描述、咨询问题等文字信息
- **输出**: 匹配的法规条款和适用性分析

### 3. 法规库列表查询 (`list_all_laws`)
- **功能描述**: 查询法规库中支持的所有法规、条例等规章制度
- **输出**: 完整的法规库列表

## 技术架构

### 服务架构
- **MCP 服务**: 基于 FastMCP 框架，提供标准化的工具接口
- **REST API**: 提供 HTTP 接口，支持流式响应
- **多线程处理**: 支持并发查询，提高响应速度
- **进度通知**: 实时反馈查询进度

### 核心组件

#### 1. 主服务 (`app/main.py`)
```python
# 主要功能
- MCP 服务启动和配置
- 工具函数注册和路由
- 依赖服务检查 (LLM, 数据库)
- 进度通知处理
```

#### 2. 法规查找引擎 (`app/law_finder/`)
```
law_finder/
├── finder.py              # 核心查找逻辑
├── find_law_bypath.py     # 直接法规查询实现
├── find_law_bycase.py     # 案例匹配查询实现
├── find_article_exactly.py # 精确条款查找
├── find_article_bycase.py  # 案例条款匹配
├── parse_law_path.py      # 法规路径解析
├── parse_case.py          # 案例信息解析
├── llm.py                 # LLM 服务接口
├── models.py              # 数据模型定义
├── utils.py               # 工具函数
└── templates/             # 模板文件
```

#### 3. REST API 服务 (`app/restful.py`)
```python
# 主要接口
- POST /api/analyze_case    # 案例分析接口
- 支持流式响应和同步响应
- 支持自定义 LLM 线程数
```

## 代码结构

```
law-agent/
├── app/                    # 主应用目录
│   ├── main.py            # MCP 服务入口
│   ├── restful.py         # REST API 服务
│   ├── init.sql           # 数据库初始化脚本
│   └── law_finder/        # 法规查找核心模块
│       ├── finder.py      # 查找引擎主逻辑
│       ├── find_law_bypath.py    # 直接查询实现
│       ├── find_law_bycase.py    # 案例查询实现
│       ├── find_article_exactly.py # 精确条款查找
│       ├── find_article_bycase.py  # 案例条款匹配
│       ├── parse_law_path.py      # 法规路径解析
│       ├── parse_case.py          # 案例解析
│       ├── llm.py                 # LLM 接口
│       ├── models.py              # 数据模型
│       ├── utils.py               # 工具函数
│       └── templates/             # 模板文件
├── release.py             # 发布脚本
├── docker-compose.yml     # Docker 部署配置
├── laws/                  # 法规数据目录
├── test/                  # 测试目录
├── tools/                 # 工具脚本
└── logs/                  # 日志目录
```

## 部署方式

### 1. Docker 部署 (推荐)

```bash
# 使用发布脚本创建发布版本
python3 release.py

# 进入发布目录
cd release

# 启动服务
docker-compose up --build
```

### 2. 环境变量配置

```bash
# 必需的环境变量
TZ=Asia/Shanghai
LLM_BASE_URL=http://your-llm-server:port
LLM_API_KEY=your-api-key
LLM_MODEL=your-model-name
DB_HOST=your-database-host
DB_PORT=your-database-port
DB_USER=your-database-user
DB_PASS=your-database-password
```

### 3. 服务端口

- **MCP 服务**: 80 端口 (可通过 MCP_SERVER_PORT 环境变量修改)
- **REST API**: 50001 端口

## 使用示例

### MCP 客户端调用

```python
# 直接法规查询
result = await client.call_tool(
    "query_law_by_lawpath",
    {"userquery": "《中华人民共和国刑法》第一百三十四条"}
)

# 案例匹配查询
result = await client.call_tool(
    "query_law_by_case_info", 
    {"userquery": "张三在工地施工时未戴安全帽，从高处坠落受伤"}
)
```

### REST API 调用

```bash
# 案例分析 (流式响应)
curl -X POST http://localhost:50001/api/analyze_case \
  -H "Content-Type: application/json" \
  -d '{
    "query": "张三在工地施工时未戴安全帽，从高处坠落受伤",
    "streaming": true,
    "chat_id": "12345"
  }'

# 案例分析 (同步响应)
curl -X POST http://localhost:50001/api/analyze_case \
  -H "Content-Type: application/json" \
  -d '{
    "query": "张三在工地施工时未戴安全帽，从高处坠落受伤",
    "max_llm_threads": 4
  }'
```

## 开发指南

### 1. 本地开发环境

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 MCP 服务
python3 app/main.py

# 启动 REST API 服务
python3 app/restful.py
```

### 2. 发布流程

```bash
# 运行发布脚本
python3 release.py

# 脚本会自动执行以下步骤：
# 1. 删除原有 release 目录
# 2. 创建新的 release 目录
# 3. 创建 .version 文件记录发布时间
# 4. 拷贝 app 目录到 release
# 5. 使用 pyarmor 混淆代码
# 6. 拷贝 docker-compose.yml
```

### 3. 测试

```bash
# 运行测试
python3 -m pytest test/

# 或运行特定测试文件
python3 test/test_law_finder.py
```

## 技术特性

### 1. 智能匹配算法
- 基于语义相似度的法规匹配
- 多线程并发查询提高效率
- 支持模糊匹配和精确匹配

### 2. 实时进度反馈
- MCP 协议支持进度通知
- REST API 支持流式响应
- 详细的查询状态反馈

### 3. 高可用性
- 自动重试机制
- 服务健康检查
- 错误处理和恢复

### 4. 安全性
- 代码混淆保护
- 环境变量配置
- Docker 容器化部署

## 依赖服务

### 1. LLM 服务
- 提供智能文本理解和生成能力
- 支持法规内容分析和匹配

### 2. 法规数据库
- 存储法规条文和结构信息
- 支持快速检索和查询

### 3. 网络服务
- 外部网络连接用于 LLM 调用
- 内部网络用于服务间通信

## 监控和日志

- 服务启动时会检查 LLM 和数据库连接
- 详细的查询日志记录
- 错误日志和异常处理
- 性能监控和统计

## 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

## 贡献指南

欢迎提交 Issue 和 Pull Request 来改进项目。

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 GitHub Issue
- 发送邮件至项目维护者 