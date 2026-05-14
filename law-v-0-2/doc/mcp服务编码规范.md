# MCP 服务器代码规范

## 1. 项目结构

### 1.1 目录组织
```
project/
├── app/
│   ├── main.py              # MCP 服务器入口文件
│   ├── models.py            # 数据模型定义
│   └── services/            # 业务逻辑模块
│       ├── __init__.py
│       └── core/            # 核心业务逻辑
├── doc/                     # 文档目录
├── templates/               # 模板文件
├── requirements.txt         # 依赖管理
└── README.md               # 项目说明
```

### 1.2 文件命名规范
- 使用小写字母和下划线：`user_service.py`
- 类名使用大驼峰命名：`UserService`
- 函数和变量使用小写字母和下划线：`get_user_info`
- 常量使用大写字母和下划线：`MAX_RETRY_COUNT`

## 2. 依赖库规范

### 2.1 核心依赖
```python
# MCP 服务器框架
from mcp.server.fastmcp import FastMCP, Context

# 数据验证和序列化
from pydantic import BaseModel, Field

# 类型注解
from typing import Optional, List, Dict, Union, Literal

# 异步支持
import asyncio
import aiohttp  # 如果需要 HTTP 客户端

# 日志记录
import logging
```

### 2.2 依赖管理
- 使用 `requirements.txt` 管理依赖
- 指定版本号：`mcp[cli]==1.10.1`
- 定期更新依赖版本
- 使用虚拟环境隔离依赖

## 3. 数据类型定义规范

### 3.1 使用 Pydantic 模型
```python
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class RequestModel(BaseModel):
    """请求数据模型"""
    user_id: int = Field(..., description="用户ID", ge=1)
    query: str = Field(..., description="查询内容", min_length=1, max_length=1000)
    options: Optional[Dict[str, any]] = Field(default=None, description="可选参数")

class ResponseModel(BaseModel):
    """响应数据模型"""
    code: int = Field(200, description="状态码")
    message: str = Field("", description="状态信息")
    data: Optional[List[Dict]] = Field(default=None, description="响应数据")
    summary_type: Optional[Literal["prompt", "text", "llm", "none"]] = Field(
        None, description="摘要类型"
    )
```

### 3.2 类型注解规范
```python
# 基本类型
user_id: int
name: str
is_active: bool
price: float

# 可选类型
description: Optional[str] = None
tags: Optional[List[str]] = None

# 联合类型
result: Union[str, int, None]
status: Literal["success", "error", "pending"]

# 复杂类型
users: List[Dict[str, any]]
config: Dict[str, Union[str, int, bool]]
```

## 4. MCP 工具定义规范

### 4.1 工具装饰器
```python
@mcp.tool(
    description="工具的功能描述，清晰说明用途和适用场景",
    name="tool_name",
    title="工具显示名称",
    structured_output=True,  # 使用结构化输出
)
async def tool_function(
    param1: str = Field(description="参数1的描述", title="参数1标题"),
    param2: int = Field(description="参数2的描述", ge=1, le=100),
    context: Context = Context(),
) -> ResponseModel:
    """函数文档字符串，详细说明功能、参数和返回值"""
    pass
```

### 4.2 参数定义规范
```python
# 必需参数
user_query: str = Field(
    description="用户的查询内容，支持自然语言描述",
    title="用户查询",
    min_length=1,
    max_length=2000
)

# 可选参数
max_results: int = Field(
    default=10,
    description="最大返回结果数量",
    ge=1,
    le=100
)

# 枚举参数
sort_by: Literal["relevance", "date", "popularity"] = Field(
    default="relevance",
    description="排序方式"
)

# 复杂参数
filters: Optional[Dict[str, any]] = Field(
    default=None,
    description="过滤条件，支持多维度筛选"
)
```

## 5. 异步编程规范

### 5.1 异步函数定义
```python
async def process_request(
    user_input: str,
    context: Context,
    progress_callback: Optional[Callable[[str], None]] = None
) -> ResponseModel:
    """异步处理请求"""
    try:
        # 异步操作
        result = await some_async_operation(user_input)
        
        # 进度通知
        if progress_callback:
            progress_callback("处理完成")
            
        return ResponseModel(
            code=200,
            message="处理成功",
            data=result
        )
    except Exception as e:
        logging.error(f"处理失败: {e}")
        return ResponseModel(
            code=500,
            message=f"处理失败: {str(e)}"
        )
```

### 5.2 并发处理
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def concurrent_processing(items: List[str]) -> List[Dict]:
    """并发处理多个项目"""
    async def process_item(item: str) -> Dict:
        # 异步处理单个项目
        return {"item": item, "result": "processed"}
    
    # 并发执行
    tasks = [process_item(item) for item in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return [r for r in results if not isinstance(r, Exception)]
```

## 6. 错误处理规范

### 6.1 异常处理
```python
async def safe_operation():
    """安全的异步操作"""
    try:
        result = await risky_operation()
        return ResponseModel(code=200, message="成功", data=result)
    except ValueError as e:
        logging.warning(f"参数错误: {e}")
        return ResponseModel(code=400, message=f"参数错误: {e}")
    except ConnectionError as e:
        logging.error(f"连接错误: {e}")
        return ResponseModel(code=503, message="服务暂时不可用")
    except Exception as e:
        logging.error(f"未知错误: {e}")
        return ResponseModel(code=500, message="内部服务器错误")
```

### 6.2 输入验证
```python
from pydantic import ValidationError

async def validate_and_process(data: Dict) -> ResponseModel:
    """验证输入并处理"""
    try:
        validated_data = RequestModel(**data)
        result = await process_data(validated_data)
        return ResponseModel(code=200, message="成功", data=result)
    except ValidationError as e:
        return ResponseModel(code=400, message=f"数据验证失败: {e}")
```

## 7. 长任务进度反馈规范

### 7.1 进度反馈要求
- 对于执行时间超过10秒的长任务，必须提供进度反馈
- 进度反馈间隔不应超过10秒
- 使用 MCP 框架的进度通知机制

### 7.2 进度反馈实现模式
```python
import queue
import threading
from typing import Optional, Callable

async def long_running_tool(
    user_query: str = Field(description="用户查询内容"),
    context: Context = Context(),
) -> ResponseModel:
    """
    长任务工具函数示例
    
    注意：context 参数由 MCP 框架自动注入，无需在工具描述中说明
    """
    # 创建进度队列和结果容器
    progress_queue = queue.Queue()
    result_container = {}
    finished_event = threading.Event()

    def progress_callback(message: str):
        """进度回调函数，将消息放入队列"""
        progress_queue.put(message)

    def actual_work():
        """实际工作函数，在独立线程中执行"""
        try:
            # 模拟长时间处理
            for i in range(10):
                # 执行实际工作
                time.sleep(2)  # 模拟耗时操作
                
                # 发送进度消息
                progress_callback(f"处理进度: {i+1}/10")
            
            result = {"status": "completed", "data": "处理结果"}
            result_container["result"] = result
        except Exception as e:
            result_container["error"] = str(e)
        finally:
            finished_event.set()

    # 启动工作线程
    work_thread = threading.Thread(target=actual_work)
    work_thread.start()

    # 在主线程中处理进度通知
    while not finished_event.is_set() or not progress_queue.empty():
        try:
            message = progress_queue.get(timeout=0.1)
            if message and context:
                await context.session.send_progress_notification(
                    progress_token=int(context.request_id),
                    message=message,
                    progress=0,  # 可以根据实际进度计算百分比
                    related_request_id=context.request_id
                )
        except queue.Empty:
            continue

    # 等待工作线程完成
    work_thread.join()

    # 返回结果
    if "error" in result_container:
        return ResponseModel(code=500, message=f"处理失败: {result_container['error']}")
    else:
        return ResponseModel(code=200, message="处理成功", data=result_container["result"])
```

### 7.3 进度反馈最佳实践

#### 7.3.1 线程安全设计
```python
def safe_progress_callback(progress_queue: queue.Queue):
    """线程安全的进度回调函数"""
    def callback(message: str):
        try:
            progress_queue.put_nowait(message)
        except queue.Full:
            # 队列满时，可以选择丢弃消息或记录日志
            pass
    return callback
```

#### 7.3.2 进度计算
```python
def calculate_progress(current: int, total: int) -> int:
    """计算进度百分比"""
    if total == 0:
        return 0
    return min(100, int((current / total) * 100))

# 在进度通知中使用
progress = calculate_progress(i + 1, 10)
await context.session.send_progress_notification(
    progress_token=int(context.request_id),
    message=f"处理进度: {i+1}/10",
    progress=progress,
    related_request_id=context.request_id
)
```

#### 7.3.3 错误处理
```python
def robust_work_function(progress_callback: Callable[[str], None]):
    """健壮的工作函数"""
    try:
        # 执行工作
        for i in range(10):
            progress_callback(f"步骤 {i+1}: 开始处理")
            
            # 执行实际工作
            result = perform_work_step(i)
            
            progress_callback(f"步骤 {i+1}: 完成")
            
    except Exception as e:
        progress_callback(f"错误: {str(e)}")
        raise
```

### 7.4 进度反馈模板
```python
async def template_long_task(
    param1: str = Field(description="参数1"),
    param2: int = Field(description="参数2", ge=1),
    context: Context = Context(),
) -> ResponseModel:
    """
    长任务模板函数
    """
    progress_queue = queue.Queue()
    result_container = {}
    finished_event = threading.Event()

    def callback(message: str):
        progress_queue.put(message)

    def work():
        try:
            # 1. 初始化阶段
            callback("正在初始化...")
            
            # 2. 数据准备阶段
            callback("正在准备数据...")
            
            # 3. 处理阶段
            total_steps = 5
            for step in range(total_steps):
                callback(f"正在处理第 {step+1}/{total_steps} 步...")
                # 执行具体工作
                time.sleep(2)
            
            # 4. 完成阶段
            callback("正在完成处理...")
            
            result_container["result"] = {"status": "success"}
        except Exception as e:
            result_container["error"] = str(e)
        finally:
            finished_event.set()

    # 启动工作线程
    work_thread = threading.Thread(target=work)
    work_thread.start()

    # 处理进度通知
    while not finished_event.is_set() or not progress_queue.empty():
        try:
            message = progress_queue.get(timeout=0.1)
            if message and context:
                await context.session.send_progress_notification(
                    progress_token=int(context.request_id),
                    message=message,
                    progress=0,
                    related_request_id=context.request_id
                )
        except queue.Empty:
            continue

    work_thread.join()

    if "error" in result_container:
        return ResponseModel(code=500, message=result_container["error"])
    else:
        return ResponseModel(code=200, message="成功", data=result_container["result"])
```

### 7.5 注意事项
- **context 参数**：由 MCP 框架自动注入，无需在工具描述中说明
- **线程安全**：确保进度队列的线程安全操作
- **超时处理**：设置合理的超时时间，避免无限等待
- **资源清理**：确保线程正确结束，避免资源泄漏
- **错误传播**：确保工作线程中的错误能够正确传播到主线程

## 8. Docker Compose 撰写规范

### 8.1 容器命名规范
- 所有 MCP 服务的容器名称必须以 `dsx_mcp` 开头
- 命名格式：`dsx_mcp_服务名称`
- 示例：`dsx_mcp_law_query`、`dsx_mcp_document_analysis`

### 8.2 基础镜像规范
```yaml
services:
  mcp_service:
    image: ${LATEST_PYTHON_ENV_IMAGE}  # 使用公司统一的基础镜像
    # 联系帆叔获取最新的镜像版本和所需库信息
```

### 8.3 网络配置规范
```yaml
services:
  mcp_service:
    networks:
      - dsx-service-network  # 使用外部网络

networks:
  dsx-service-network:
    external: true  # 外部网络，由运维团队管理
```

### 8.4 源码挂载规范
```yaml
services:
  mcp_service:
    volumes:
      - ./app:/app  # 应用源码挂载到容器内的 /app 目录
      - $TADK_PATH:/tadk  # AI SDK 挂载到容器内的 /sdk 目录
```
  
### 8.5 完整示例
```yaml
version: '3'
services:
  mcp_law_query:
    environment:
      TZ: ${TZ}
      MCP_SERVER_PORT: 3000
    image: ${LATEST_PYTHON_ENV_IMAGE}
    container_name: dsx_mcp_law_query
    networks:
      - dsx-service-network
    volumes:
      - ./app:/app
      - $TADK_PATH:/tadk
    restart: always
    command: python3 /app/main.py
    ports:
      - "3000:3000"

networks:
  dsx-service-network:
    external: true
```

### 8.6 MCP服务docker-compose配置说明
- AI SDK 是公司自研的帮助库，已挂载到容器的 `/sdk` 目录
- 在 Python 代码中可以直接导入使用
- SDK 包含常用的 AI 相关功能，如 LLM 调用、数据处理等
- 示例：
```python
# 在应用代码中使用 AI SDK
from sdk.llm import LLMClient
from sdk.utils import data_processor

# 直接调用 SDK 功能
client = LLMClient()
result = client.query("你的问题")
```

### 8.7 注意事项
- **镜像版本**：定期更新 `tmindtech.com/python_dev_env` 镜像版本
- **网络配置**：确保外部网络 `dsx-service-network` 已创建
- **权限管理**：确保容器有足够的权限访问挂载的目录
- **环境变量**：根据需要在 `environment` 中配置必要的环境变量
- **端口映射**：根据服务需要配置端口映射
- **资源限制**：根据服务特点配置 CPU 和内存限制

### 8.8 开发环境配置
```yaml
# docker-compose.dev.yml
version: '3'
services:
  mcp_service_dev:
    environment:
      TZ: ${TZ}
      DEBUG: "true"
      LOG_LEVEL: "DEBUG"
    image: ${LATEST_PYTHON_ENV_IMAGE}
    container_name: dsx_mcp_service_dev
    networks:
      - dsx-service-network
    volumes:
      - ./app:/app
      - $TADK_PATH:/tadk
      - ./logs:/app/logs  # 开发环境日志挂载
    restart: "no"
    command: python3 -m debugpy --listen 0.0.0.0:5678 /app/main.py
    ports:
      - "3000:3000"
      - "5678:5678"  # 调试端口

networks:
  dsx-service-network:
    external: true
```

## 9. Git 规范
+ mcp服务的均放到 [各种MCP服务](https://git.int.tmindtech.com/dahua-dc/AI/mcp-server) 这个group下
+ 示例工程-[法规查询](ssh://git@git.int.tmindtech.com:8022/dahua-dc/AI/law-agent.git), 该工程因为含有其他智能体代码和法规清洗代码，因此没有放到mcp组中。

## 10. 文档规范

### 10.1 函数文档
```python
async def complex_tool_function(
    query: str,
    filters: Optional[Dict[str, any]] = None,
    context: Context = Context()
) -> ResponseModel:
    """
    复杂工具函数
    
    Args:
        query: 查询字符串，支持自然语言描述
        filters: 可选的过滤条件，支持多维度筛选
        context: MCP 上下文对象
        
    Returns:
        ResponseModel: 包含处理结果的响应模型
        
    Raises:
        ValueError: 当查询参数无效时
        ConnectionError: 当外部服务不可用时
        
    Example:
        >>> result = await complex_tool_function("查询用户信息", {"status": "active"})
        >>> print(result.code)  # 200
    """
    pass
```

## 11. 代码质量规范

### 11.1 代码格式化
- 使用 `black` 进行代码格式化
- 使用 `isort` 排序导入语句
- 使用 `flake8` 检查代码风格
- 使用 `mypy` 进行类型检查


遵循这些规范可以确保 MCP 服务器代码的质量、可维护性和可扩展性。 