# MCP服务器协议规范

## 概述

本文档详细说明了MCP服务器在返回数据时应遵循的协议规范，包括列表数据、图表数据以及结果总结的处理方式。遵循此协议可确保与AI智能体平台的无缝集成。

## 1. 基础响应格式

所有MCP工具调用都应返回标准化的响应格式。这是MCP服务器原始返回的数据结构，SDK会自动包装为完整的响应格式。

### 1.1 响应结构

```json
{
  "code": 200,
  "message": "success",
  "data": {
    // 具体数据内容
  },
  "meta": {
    // 元数据信息
  },
  "summary_type": "none",
  "summary": ""
}
```

### 1.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | int | 是 | 响应状态码，200表示成功 |
| `message` | string | 否 | 响应消息 |
| `data` | object | 否 | 实际数据内容 |
| `meta` | object | 否 | 元数据信息 |
| `summary_type` | string | 否 | 总结类型 |
| `summary` | string | 否 | 总结内容或提示词 |

## 2. 列表数据格式

当工具返回列表数据时，需要遵循特定的格式规范。

### 2.1 列表数据响应格式

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 1000,
    "list": [
      {
        "id": 1,
        "name": "示例项目1",
        "status": "active",
        "created_at": "2024-01-01T00:00:00Z"
      },
      {
        "id": 2,
        "name": "示例项目2",
        "status": "inactive",
        "created_at": "2024-01-02T00:00:00Z"
      }
    ]
  },
  "meta": {
    "data_type": "list",
    "page_size_param": "pagination.pageSize",
    "page_param": "pagination.page"
  },
  "summary_type": "llm",
  "summary": ""
}
```

### 2.2 列表数据字段说明

#### data字段（建议返回格式）
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `total` | int | 是 | 总记录数 |
| `list` | array | 是 | 当前页数据列表 |

#### meta字段
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `data_type` | string | 是 | 固定值："list" |
| `page_size_param` | string | 是 | 页大小参数路径，如"pagination.pageSize"，也可以使用lambda函数字符串 |
| `page_param` | string | 是 | 页码参数路径，如"pagination.page"，也可以使用lambda函数字符串 |

### 2.3 分页参数路径说明

分页参数路径支持两种格式：

#### 点分隔路径格式
```json
{
  "meta": {
    "page_size_param": "pagination.pageSize",
    "page_param": "pagination.page"
  }
}
```

对应的查询参数格式：
```json
{
  "pagination": {
    "page": 1,
    "pageSize": 20
  }
}
```

#### Lambda函数格式
```json
{
  "meta": {
    "page_size_param": "lambda param, pagesize: param['mypath']['mypagesize'] = pagesize",
    "page_param": "lambda param, page: param['mypath']['mypage'] = page"
  }
}
```

## 3. 图表数据格式

当工具返回图表数据时，需要遵循特定的格式规范。

### 3.1 图表数据响应格式

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "result": [
      {
        "category": "产品A",
        "value": 120,
        "percentage": 30
      },
      {
        "category": "产品B",
        "value": 80,
        "percentage": 20
      },
      {
        "category": "产品C",
        "value": 200,
        "percentage": 50
      }
    ]
  },
  "meta": {
    "data_type": "chart",
    "chart_type": "bar"
  },
  "summary_type": "text",
  "summary": "销售数据显示，产品C的销售额最高，占总销售额的50%。"
}
```

### 3.2 图表数据字段说明

#### data字段
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `result` | array | 是 | 图表数据数组 |

#### meta字段
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `data_type` | string | 是 | 固定值："chart" |
| `chart_type` | string | 是 | 图表类型：bar/line/pie |

### 3.3 支持的图表类型

| 图表类型 | 说明 | 适用场景 |
|----------|------|----------|
| `bar` | 柱状图 | 分类数据对比 |
| `line` | 折线图 | 趋势数据展示 |
| `pie` | 饼图 | 占比数据展示 |

### 3.4 图表数据示例

#### 柱状图数据
```json
{
  "data": {
    "result": [
      {"category": "一月", "value": 100},
      {"category": "二月", "value": 150},
      {"category": "三月", "value": 200}
    ]
  },
  "meta": {
    "data_type": "chart",
    "chart_type": "bar"
  }
}
```

#### 饼图数据
```json
{
  "data": {
    "result": [
      {"category": "技术", "value": 40},
      {"category": "销售", "value": 30},
      {"category": "市场", "value": 30}
    ]
  },
  "meta": {
    "data_type": "chart",
    "chart_type": "pie"
  }
}
```

## 4. 总结处理方式

MCP服务器可以通过`summary_type`字段控制AI智能体如何处理返回的数据。

### 4.1 总结类型说明

| 总结类型 | 说明 | 使用场景 |
|----------|------|----------|
| `none` | 不生成总结，工具的返回结果转换为字符串直接返回用户 | 数据本身已经很清晰，无需额外处理 |
| `text` | 直接使用summary字段内容返回用户 | 服务器已生成总结，直接展示 |
| `prompt` | 使用summary作为提示词，调用llm生成回复 | 需要AI根据特定提示词处理数据 |
| `llm` | 使用AI生成总结，自动对data进行总结 | 需要AI智能分析数据并生成总结 |

### 4.2 总结类型示例

#### none类型
```json
{
  "code": 200,
  "data": {
    "total": 100,
    "list": [...]
  },
  "meta": {
    "data_type": "list"
  },
  "summary_type": "none"
}
```

#### text类型
```json
{
  "code": 200,
  "data": {
    "result": [...]
  },
  "meta": {
    "data_type": "chart",
    "chart_type": "bar"
  },
  "summary_type": "text",
  "summary": "根据销售数据显示，本月销售额较上月增长了15%，主要增长来自新产品线的贡献。"
}
```

#### prompt类型
```json
{
  "code": 200,
  "data": {
    "total": 1000,
    "list": [...]
  },
  "meta": {
    "data_type": "list"
  },
  "summary_type": "prompt",
  "summary": "请分析以下用户数据，重点关注用户活跃度、地域分布和用户行为模式，生成一份用户画像分析报告。"
}
```

#### llm类型
```json
{
  "code": 200,
  "data": {
    "result": [...]
  },
  "meta": {
    "data_type": "chart",
    "chart_type": "pie"
  },
  "summary_type": "llm"
}
```

**注意**
+ 当data_type不为 list 或者 chart的时候，data中的数据可以没有。data的数据需要放到summary中，并设置合适的summary方式，此时智能体会根据summary的类型来处理回复。
+ 当summary_type是none的时候，data如果也没有内容，则无任何回复

## 5. 错误处理

### 5.1 错误响应格式

```json
{
  "code": 500,
  "message": "查询失败：数据库连接异常",
  "data": null,
  "meta": {},
  "summary_type": "none"
}
```

### 5.2 常见错误码

| 错误码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 认证失败 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 6. 输入参数解析提示词

### 6.1 工具参数解析提示词规则
+ 正常情况下，智能体自动使用mcp server的inputschema来根据用户问题生成输入参数。
+ mcpserver可以按照命名规则提供对应工具的提示词方法，名字规则为 `{tool_name}_input_prompt(query: str)`
+ 当mcp服务提供了tool对应的提示词方法，那么智能体将尝试使用提供的提示词进行参数解析
+ 如果提供了提示词，那么提示词的效果最后应该输出使用```json包裹的对象数据，里面每个key为tool的入参的名字，value为入参的值

### 6.2 提示词输出示例
+ 工具定义： `def query(page, pageSize, condition1)` 
+ 提示词最后的输出中应该包含以下的json
```json
{
  "page": 1,
  "pageSize": 10,
  "condition1": true
}
```

### 6.3 提示词实现示例

```python
def query_users_input_prompt(query: str) -> str:
    """用户查询工具的输入参数解析提示词"""
    return f"""
请根据用户的问题，解析出查询参数。

用户问题：{query}

请分析用户意图，提取以下参数：
- page: 页码（默认为1）
- pageSize: 每页大小（默认为20）
- condition1: 查询条件1（布尔值）

请返回JSON格式的参数：
```json
{{
  "page": 1,
  "pageSize": 20,
  "condition1": true
}}
```
"""
```

## 7. 完整示例

### 7.1 列表查询示例

**请求参数：**
```json
{
  "pagination": {
    "page": 1,
    "pageSize": 20
  },
  "filters": {
    "status": "active",
    "category": "technology"
  }
}
```

**响应数据：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 156,
    "list": [
      {
        "id": 1,
        "title": "AI技术发展趋势",
        "author": "张三",
        "publish_date": "2024-01-15",
        "status": "active",
        "views": 1250
      }
    ]
  },
  "meta": {
    "data_type": "list",
    "page_size_param": "pagination.pageSize",
    "page_param": "pagination.page"
  },
  "summary_type": "llm",
  "summary": ""
}
```

### 7.2 图表查询示例

**请求参数：**
```json
{
  "date_range": {
    "start": "2024-01-01",
    "end": "2024-01-31"
  },
  "chart_type": "bar"
}
```

**响应数据：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "result": [
      {
        "category": "周一",
        "value": 120,
        "percentage": 20
      },
      {
        "category": "周二",
        "value": 150,
        "percentage": 25
      }
    ]
  },
  "meta": {
    "data_type": "chart",
    "chart_type": "bar"
  },
  "summary_type": "text",
  "summary": "本周销售数据显示，周二销售额最高，达到150万元，占总销售额的25%。"
}
```

### 7.3 普通工具调用示例

**响应数据：**
```json
{
  "code": 200,
  "message": "success",
  "data": null,
  "meta": {},
  "summary_type": "text",
  "summary": "文件上传成功，文件ID为：file_12345，大小：2.5MB，上传时间：2024-01-15 10:30:00"
}
```

## 8. 开发建议

### 8.1 数据格式建议

1. **保持一致性**：所有工具都应遵循相同的响应格式
2. **字段命名**：使用驼峰命名法，保持与前端约定一致
3. **数据类型**：确保数据类型正确，避免类型转换错误
4. **空值处理**：使用null而不是空字符串表示空值

### 8.2 性能建议

1. **分页查询**：对于大量数据，必须支持分页查询
2. **数据压缩**：考虑对大数据量进行压缩传输
3. **缓存策略**：对频繁查询的数据实施缓存
4. **异步处理**：对于耗时操作，考虑异步处理

### 8.3 错误处理建议

1. **详细错误信息**：提供具体的错误描述，便于调试
2. **错误分类**：区分业务错误和系统错误
3. **错误日志**：记录详细的错误日志信息
4. **降级处理**：提供降级方案，确保服务可用性

## 9. 测试验证

### 9.1 格式验证

开发完成后，请使用以下工具验证响应格式：

1. **JSON Schema验证**：确保响应符合JSON Schema规范
2. **类型检查**：验证所有字段的数据类型正确
3. **必填字段检查**：确保所有必填字段都存在
4. **枚举值验证**：验证枚举字段的值在允许范围内

### 9.2 功能测试

1. **列表分页测试**：验证分页功能正常工作
2. **图表渲染测试**：验证图表数据能正确渲染
3. **总结生成测试**：验证不同总结类型的效果
4. **错误处理测试**：验证错误情况的处理

## 10. 版本兼容性

### 10.1 向后兼容

- 新增字段应为可选字段
- 删除字段前应提供迁移方案
- 字段类型变更应提供转换逻辑

### 10.2 版本管理

- 使用语义化版本号
- 记录版本变更日志
- 提供版本升级指南

---

**注意**：本文档会随着平台功能的更新而更新，请定期查看最新版本。
