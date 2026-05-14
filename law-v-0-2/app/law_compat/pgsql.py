"""
PostgreSQL数据库帮助类

提供PostgreSQL数据库的连接管理、增删改查以及直接执行SQL的功能。
支持异步操作，密码可为空，包含完整的错误处理机制。
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

try:
    import asyncpg
except ImportError:
    raise ImportError("需要安装asyncpg依赖: pip install asyncpg")


logger = logging.getLogger(__name__)


class PostgreSQLError(Exception):
    """PostgreSQL操作异常基类"""
    pass


class ConnectionError(PostgreSQLError):
    """数据库连接异常"""
    pass


class QueryError(PostgreSQLError):
    """查询执行异常"""
    pass




class PostgreSQLHelper:
    """
    PostgreSQL数据库帮助类
    
    支持异步操作的PostgreSQL数据库操作类，提供连接管理、
    增删改查以及直接执行SQL的功能。
    """
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        database: str = None,
        username: str = None,
        password: str = None,
        schema:str = "public",
        **kwargs
    ):
        """
        初始化PostgreSQL帮助类
        
        Args:
            host: 数据库主机地址，默认从环境变量PG_HOST获取，未设置则为localhost
            port: 数据库端口，默认从环境变量PG_PORT获取，未设置则为5432
            database: 数据库名，默认从环境变量PG_DATABASE获取
            username: 用户名，默认从环境变量PG_USER获取
            password: 密码，默认从环境变量PG_PASSWORD获取，可为空
            **kwargs: 其他连接参数，传递给asyncpg.connect()
        """
        self.host = host or os.getenv("PG_HOST", "localhost")
        self.port = port or int(os.getenv("PG_PORT", "5432"))
        self.database = database or os.getenv("PG_DATABASE")
        self.username = username or os.getenv("PG_USER")
        self.password = password or os.getenv("PG_PASSWORD", "")  # 密码可为空
        self.schema = schema or os.getenv("PGDB_SCHEMA", "public")
        self.kwargs = kwargs
        
        self._pool: Optional[asyncpg.Pool] = None
        
        if not self.database:
            raise ValueError("数据库名不能为空")
        if not self.username:
            raise ValueError("用户名不能为空")
    
    async def _get_connection_params(self) -> Dict[str, Any]:
        """获取数据库连接参数"""
        params = {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.username,
            **self.kwargs
        }
        
        # 只有密码不为空时才添加密码参数
        if self.password:
            params["password"] = self.password
            
        return params
    
    async def ensure_database_exists(self) -> None:
        """
        确保数据库存在，如果不存在则创建
        注意：需要连接到 postgres 数据库来创建新数据库
        """
        try:
            # 首先尝试连接到目标数据库
            params = await self._get_connection_params()
            test_conn = await asyncpg.connect(**params)
            await test_conn.close()
            logger.info(f"数据库 {self.database} 已存在")
            return
        except asyncpg.InvalidCatalogNameError:
            # 数据库不存在，需要创建
            logger.info(f"数据库 {self.database} 不存在，正在创建...")
        except Exception as e:
            logger.warning(f"检查数据库是否存在时出错: {e}")
            # 继续尝试创建数据库
        
        try:
            # 连接到 postgres 数据库来创建新数据库
            create_params = await self._get_connection_params()
            create_params["database"] = "postgres"  # 使用 postgres 数据库
            
            create_conn = await asyncpg.connect(**create_params)
            
            # 检查数据库是否已经存在
            check_sql = "SELECT 1 FROM pg_database WHERE datname = $1"
            exists = await create_conn.fetchval(check_sql, self.database)
            
            if not exists:
                # 创建数据库（需要使用单独的事务）
                create_sql = f'CREATE DATABASE "{self.database}"'
                await create_conn.execute(create_sql)
                logger.info(f"成功创建数据库: {self.database}")
            else:
                logger.info(f"数据库 {self.database} 已存在")
                
            await create_conn.close()
            
        except Exception as e:
            logger.error(f"创建数据库失败: {e}")
            raise ConnectionError(f"创建数据库失败: {e}")
    
    async def ensure_schema_exists(self) -> None:
        """
        确保 schema 存在，如果不存在则创建
        """
        if self.schema == "public":
            # public schema 总是存在的
            return
            
        try:
            params = await self._get_connection_params()
            conn = await asyncpg.connect(**params)
            
            # 检查 schema 是否存在
            check_sql = "SELECT 1 FROM information_schema.schemata WHERE schema_name = $1"
            exists = await conn.fetchval(check_sql, self.schema)
            
            if not exists:
                # 创建 schema
                create_sql = f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"'
                await conn.execute(create_sql)
                logger.info(f"成功创建 schema: {self.schema}")
            else:
                logger.info(f"Schema {self.schema} 已存在")
                
            await conn.close()
            
        except Exception as e:
            logger.error(f"创建 schema 失败: {e}")
            raise ConnectionError(f"创建 schema 失败: {e}")
    
    async def init_pool(self, min_size: int = 1, max_size: int = 10) -> None:
        """
        初始化连接池
        
        Args:
            min_size: 最小连接数
            max_size: 最大连接数
        """
        if self._pool is not None:
            return
            
        try:
            params = await self._get_connection_params()
            self._pool = await asyncpg.create_pool(
                min_size=min_size,
                max_size=max_size,
                **params
            )
            logger.info(f"PostgreSQL连接池初始化成功: {self.host}:{self.port}/{self.database}")
        except Exception as e:
            logger.error(f"PostgreSQL连接池初始化失败: {e}")
            raise ConnectionError(f"连接池初始化失败: {e}")
    
    async def close_pool(self) -> None:
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL连接池已关闭")
    
    @asynccontextmanager
    async def get_connection(self):
        """
        获取数据库连接的上下文管理器
        
        如果连接池未初始化，会自动初始化
        """
        if self._pool is None:
            await self.init_pool()
        
        async with self._pool.acquire() as connection:
            try:
                # 如果指定了schema，则设置search_path
                if self.schema:
                    await connection.execute(f"SET search_path TO {self.schema}, public")
                yield connection
            except Exception as e:
                logger.error(f"数据库操作异常: {e}")
                raise
    
    async def test_connection(self) -> bool:
        """
        测试数据库连接
        
        Returns:
            bool: 连接成功返回True，失败返回False
        """
        try:
            params = await self._get_connection_params()
            conn = await asyncpg.connect(**params)
            await conn.close()
            logger.info("PostgreSQL连接测试成功")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL连接测试失败: {e}")
            return False
    
    async def execute_query(
        self,
        query: str,
        params: List[Any] = None,
        fetch_mode: str = "all"
    ) -> Union[List[Dict[str, Any]], Dict[str, Any], None]:
        """
        执行查询SQL
        
        Args:
            query: SQL查询语句
            params: 查询参数列表
            fetch_mode: 获取模式，支持 'all', 'one', 'none'
            
        Returns:
            查询结果，根据fetch_mode返回不同格式
        """
        params = params or []
        
        try:
            async with self.get_connection() as conn:
                logger.debug(f"执行查询: {query}")
                
                if fetch_mode == "all":
                    result = await conn.fetch(query, *params)
                    return [dict(row) for row in result]
                elif fetch_mode == "one":
                    result = await conn.fetchrow(query, *params)
                    return dict(result) if result else None
                elif fetch_mode == "none":
                    await conn.execute(query, *params)
                    return None
                else:
                    raise ValueError(f"不支持的fetch_mode: {fetch_mode}")
                    
        except Exception as e:
            logger.error(f"查询执行失败: {e}, SQL: {query}")
            raise QueryError(f"查询执行失败: {e}")
    
    async def execute_script(self, script: str) -> None:
        """
        执行SQL脚本（多条语句）
        
        Args:
            script: SQL脚本内容
        """
        try:
            async with self.get_connection() as conn:
                logger.debug(f"执行SQL脚本: {script[:100]}...")
                await conn.execute(script)
                logger.info("SQL脚本执行成功")
        except Exception as e:
            logger.error(f"SQL脚本执行失败: {e}")
            raise QueryError(f"SQL脚本执行失败: {e}")
    
    async def batch_execute_sql(self, sql: str, params_list: List[List[Any]]) -> None:
        """
        批量执行同一条SQL语句
        
        Args:
            sql: SQL语句
            params_list: 参数列表的列表，每个子列表对应一次执行的参数
        """
        if not params_list:
            return
        
        try:
            async with self.get_connection() as conn:
                logger.debug(f"批量执行SQL: {sql}, 批次数量: {len(params_list)}")
                await conn.executemany(sql, params_list)
                logger.info(f"批量执行成功，处理了 {len(params_list)} 条记录")
        except Exception as e:
            logger.error(f"批量SQL执行失败: {e}, SQL: {sql}")
            raise QueryError(f"批量SQL执行失败: {e}")
    
    async def insert(
        self,
        table: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        returning: str = None
    ) -> Union[List[Dict[str, Any]], None]:
        """
        插入数据
        
        Args:
            table: 表名
            data: 要插入的数据，可以是单条记录的字典或多条记录的列表
            returning: RETURNING子句，如 "id" 或 "id, name"
            
        Returns:
            如果指定了returning，返回插入后的记录；否则返回None
        """
        if not data:
            return None
            
        # 标准化为列表格式
        if isinstance(data, dict):
            data = [data]
        
        if not data:
            return None
        
        try:
            async with self.get_connection() as conn:
                # 构建插入语句
                columns = list(data[0].keys())
                placeholders = [f"${i+1}" for i in range(len(columns))]
                
                sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                if returning:
                    sql += f" RETURNING {returning}"
                
                logger.debug(f"执行插入: {sql}")
                
                if len(data) == 1:
                    # 单条插入
                    values = [self._serialize_value(data[0][col]) for col in columns]
                    if returning:
                        result = await conn.fetchrow(sql, *values)
                        return [dict(result)] if result else None
                    else:
                        await conn.execute(sql, *values)
                        return None
                else:
                    # 批量插入
                    values_list = []
                    for record in data:
                        values = [self._serialize_value(record[col]) for col in columns]
                        values_list.append(values)
                    
                    if returning:
                        result = await conn.fetch(sql, *values_list[0])  # asyncpg的executemany不支持returning
                        return [dict(row) for row in result]
                    else:
                        await conn.executemany(sql, values_list)
                        return None
                        
        except Exception as e:
            logger.error(f"插入操作失败: {e}")
            raise QueryError(f"插入操作失败: {e}")
    
    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        where_clause: str,
        where_params: List[Any] = None,
        returning: str = None
    ) -> Union[List[Dict[str, Any]], int]:
        """
        更新数据
        
        Args:
            table: 表名
            data: 要更新的数据字典
            where_clause: WHERE条件，使用占位符 $1, $2 等
            where_params: WHERE条件的参数列表
            returning: RETURNING子句
            
        Returns:
            如果指定了returning，返回更新后的记录列表；否则返回影响的行数
        """
        if not data:
            return 0
            
        where_params = where_params or []
        
        try:
            async with self.get_connection() as conn:
                # 构建更新语句
                set_clauses = []
                values = []
                param_index = 1
                
                for column, value in data.items():
                    set_clauses.append(f"{column} = ${param_index}")
                    values.append(self._serialize_value(value))
                    param_index += 1
                
                # 添加WHERE参数
                for param in where_params:
                    values.append(param)
                
                sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE {where_clause}"
                if returning:
                    sql += f" RETURNING {returning}"
                
                logger.debug(f"执行更新: {sql}")
                
                if returning:
                    result = await conn.fetch(sql, *values)
                    return [dict(row) for row in result]
                else:
                    result = await conn.execute(sql, *values)
                    # 从执行结果中提取影响的行数
                    return int(result.split()[-1]) if result else 0
                    
        except Exception as e:
            logger.error(f"更新操作失败: {e}")
            raise QueryError(f"更新操作失败: {e}")
    
    async def delete(
        self,
        table: str,
        where_clause: str,
        where_params: List[Any] = None,
        returning: str = None
    ) -> Union[List[Dict[str, Any]], int]:
        """
        删除数据
        
        Args:
            table: 表名
            where_clause: WHERE条件，使用占位符 $1, $2 等
            where_params: WHERE条件的参数列表
            returning: RETURNING子句
            
        Returns:
            如果指定了returning，返回删除的记录列表；否则返回影响的行数
        """
        where_params = where_params or []
        
        try:
            async with self.get_connection() as conn:
                sql = f"DELETE FROM {table} WHERE {where_clause}"
                if returning:
                    sql += f" RETURNING {returning}"
                
                logger.debug(f"执行删除: {sql}")
                
                if returning:
                    result = await conn.fetch(sql, *where_params)
                    return [dict(row) for row in result]
                else:
                    result = await conn.execute(sql, *where_params)
                    # 从执行结果中提取影响的行数
                    return int(result.split()[-1]) if result else 0
                    
        except Exception as e:
            logger.error(f"删除操作失败: {e}")
            raise QueryError(f"删除操作失败: {e}")
    
    async def select(
        self,
        table: str,
        columns: str = "*",
        where_clause: str = None,
        where_params: List[Any] = None,
        order_by: str = None,
        limit: int = None,
        offset: int = None
    ) -> List[Dict[str, Any]]:
        """
        查询数据
        
        Args:
            table: 表名
            columns: 要查询的列，默认为 "*"
            where_clause: WHERE条件，使用占位符 $1, $2 等
            where_params: WHERE条件的参数列表
            order_by: ORDER BY子句
            limit: 限制返回行数
            offset: 偏移量
            
        Returns:
            查询结果列表
        """
        where_params = where_params or []
        
        try:
            sql = f"SELECT {columns} FROM {table}"
            
            if where_clause:
                sql += f" WHERE {where_clause}"
            
            if order_by:
                sql += f" ORDER BY {order_by}"
                
            if limit:
                sql += f" LIMIT {limit}"
                
            if offset:
                sql += f" OFFSET {offset}"
            
            return await self.execute_query(sql, where_params, "all")
            
        except Exception as e:
            logger.error(f"查询操作失败: {e}")
            raise QueryError(f"查询操作失败: {e}")
    
    async def count(
        self,
        table: str,
        where_clause: str = None,
        where_params: List[Any] = None
    ) -> int:
        """
        统计记录数
        
        Args:
            table: 表名
            where_clause: WHERE条件，使用占位符 $1, $2 等
            where_params: WHERE条件的参数列表
            
        Returns:
            记录总数
        """
        where_params = where_params or []
        
        try:
            sql = f"SELECT COUNT(*) as count FROM {table}"
            
            if where_clause:
                sql += f" WHERE {where_clause}"
            
            result = await self.execute_query(sql, where_params, "one")
            return result["count"] if result else 0
            
        except Exception as e:
            logger.error(f"统计操作失败: {e}")
            raise QueryError(f"统计操作失败: {e}")
    
    async def exists(
        self,
        table: str,
        where_clause: str,
        where_params: List[Any] = None
    ) -> bool:
        """
        检查记录是否存在
        
        Args:
            table: 表名
            where_clause: WHERE条件，使用占位符 $1, $2 等
            where_params: WHERE条件的参数列表
            
        Returns:
            存在返回True，不存在返回False
        """
        count = await self.count(table, where_clause, where_params)
        return count > 0
    
    @asynccontextmanager
    async def transaction(self):
        """事务上下文管理器实现"""
        async with self.get_connection() as conn:
            async with conn.transaction():
                # 临时替换连接池为当前事务连接
                original_pool = self._pool
                self._pool = _SingleConnectionPool(conn)
                try:
                    yield conn
                finally:
                    self._pool = original_pool
    
    def _serialize_value(self, value: Any) -> Any:
        """
        序列化值，将复杂对象转换为JSON字符串
        
        Args:
            value: 要序列化的值
            
        Returns:
            序列化后的值
        """
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False)
        return value


class _SingleConnectionPool:
    """单连接池，用于事务中临时替换连接池"""
    
    def __init__(self, connection):
        self.connection = connection
    
    def acquire(self):
        return _SingleConnectionContext(self.connection)


class _SingleConnectionContext:
    """单连接上下文，用于事务中"""
    
    def __init__(self, connection):
        self.connection = connection
    
    async def __aenter__(self):
        return self.connection
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# 便利函数：创建全局实例
_global_helper: Optional[PostgreSQLHelper] = None


def get_global_helper(**kwargs) -> PostgreSQLHelper:
    """
    获取全局PostgreSQL帮助类实例
    
    Args:
        **kwargs: 连接参数，仅在首次调用时有效
        
    Returns:
        PostgreSQL帮助类实例
    """
    global _global_helper
    if _global_helper is None:
        _global_helper = PostgreSQLHelper(**kwargs)
    return _global_helper


async def init_global_pool(**kwargs):
    """初始化全局连接池"""
    helper = get_global_helper(**kwargs)
    await helper.init_pool()


async def close_global_pool():
    """关闭全局连接池"""
    global _global_helper
    if _global_helper:
        await _global_helper.close_pool()
        _global_helper = None

