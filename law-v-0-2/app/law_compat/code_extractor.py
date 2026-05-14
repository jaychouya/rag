# 通过案例查找目录及其中的法规
import asyncio
import json
import os
from typing import Callable, Literal, Optional
from dataclasses import dataclass

from law_compat.abs_llm import AbsLLM, LLMError
from law_compat.markdown_extract import (
    extract_all_json_from_markdown,
    extract_python_from_markdown,
    extract_sql_from_markdown,
)
from law_compat.tracer_noop import TracerManager

@dataclass
class CodeExtractDebugInfo:
    """大模型响应信息模型"""
    chat_response: Optional[str] = None
    message: Optional[str | list[dict[str, str]]] = None
    system_message: Optional[str] = None

### 专门负责提取json数据，不负责解析json数据
class CodeExtractor:
    """
    异步代码提取器类，用于调用大模型并返回结构化json或sql数据
    使用信号量控制并发数量，保护算力资源
    """

    def __init__(self, llm: AbsLLM, max_workers=5, title="agent", max_retry=3, enable_thinking: Optional[bool]=None) -> None:
        self.title = title
        self.llm = llm
        self.max_retry = max_retry
        self.max_workers = max_workers
        # 使用信号量控制并发数量，超过max_workers的请求会排队等待
        self._semaphore = asyncio.Semaphore(max_workers)
        self.enable_thinking = enable_thinking
        self.debug = os.getenv("DEBUG_MODE", "false").lower() == "true"

    def do_sync(
        self,
        message: str | list[dict[str, str]],
        system_message: Optional[str] = None,
        validation_method: Optional[Callable] = None,
        codeType: Literal["json", "sql", "python"] = "json",
        debug: bool = False,
        debug_out: Optional[CodeExtractDebugInfo] = None,
    ) -> dict | list | str:
        """
        同步执行代码提取任务
        该方法会自动运行事件循环，适用于同步调用场景

        Args:
            message: 输入消息，可以是字符串或消息列表
            system_message: 系统消息
            validation_method: 验证方法
            codeType: 代码类型，json、sql或python
            debug: 是否启用调试模式

        Returns:
            提取的结构化数据
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if loop.is_running():
            # 如果事件循环已在运行，需使用异步任务调度
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(
                self.do(
                    message=message,
                    system_message=system_message,
                    validation_method=validation_method,
                    codeType=codeType,
                    debug=debug,
                    debug_out=debug_out,
                )
            )
        else:
            return loop.run_until_complete(
                self.do(
                    message=message,
                    system_message=system_message,
                    validation_method=validation_method,
                    codeType=codeType,
                    debug=debug,
                    debug_out=debug_out,
                )
            )
    async def do(
        self,
        message: str | list[dict[str, str]],
        system_message: Optional[str] = None,
        validation_method: Optional[Callable] = None,
        codeType: Literal["json", "sql", "python"] = "json",
        debug: bool = False,
        debug_out: Optional[CodeExtractDebugInfo] = None,
    ) -> dict | list | str:
        """
        异步执行代码提取任务
        使用信号量控制并发数量，超过max_workers的请求会排队等待
        
        Args:
            message: 输入消息，可以是字符串或消息列表
            system_message: 系统消息
            validation_method: 验证方法
            codeType: 代码类型，json、sql或python
            debug: 是否启用调试模式
            out: 可选的输出模型，用于接收大模型的完整响应信息
            
        Returns:
            提取的结构化数据
        """
        # 使用信号量控制并发数量
        async with self._semaphore:
            return await self._do_with_llm(message, system_message, validation_method, codeType, debug, debug_out)


    @TracerManager.trace(span_name="extract_code", kind="chain")
    async def _do_with_llm(
        self,
        message: str | list[dict[str, str]],
        system_message: Optional[str] = None,
        validation_method: Optional[Callable] = None,
        codeType: Literal["json", "sql", "python"] = "json",
        debug: bool = False,
        _out: Optional[CodeExtractDebugInfo] = None,
    ) -> dict | str:
        """
        异步版本的LLM调用方法
        在线程池控制的线程中执行，确保并发控制
        """
        retry_count = 0
        is_debug = debug or self.debug

        # 根据输入类型调用不同的LLM方法
        if isinstance(message, str):
            message = [{"role": "user", "content": message}]
        if not isinstance(message, list):
            raise Exception(f"消息类型错误: {type(message)}")
        if not self.llm:
            raise Exception("未配置llm")
        
        chat_response = None
        await TracerManager.set_input({
            "message": message,
            "system_message": system_message,
            "codeType": codeType,
        })
        while retry_count < self.max_retry:
            try:
                # 异步调用LLM的chat方法
                print("======================================================================") if is_debug else None
                print(f"message: {message} \n system_message: {system_message}") if is_debug else None
                chat_response = await self.llm.chat(message, system_message=system_message, enable_thinking=self.enable_thinking)
                print(f"extractor_chat_response: \n{chat_response}") if is_debug else None
                print("======================================================================") if is_debug else None
                
                # 如果传入了out参数，将完整响应信息赋值给out
                if _out is not None:
                    _out.chat_response = chat_response
                    _out.message = message
                    _out.system_message = system_message
                result = None
                if codeType == "json":
                    result = self._extract_last_json(chat_response)
                elif codeType == "sql":
                    result = self._extract_last_sql(chat_response)
                elif codeType == "python":
                    result = self._extract_last_python(chat_response)
                
                if validation_method and not validation_method(result):
                    raise Exception(f"解析到的代码不符合验证规则：{result}")
                await TracerManager.set_output(chat_response)
                return result
            except LLMError as e:
                print("======================================================================")
                print(f"[Error] 结构化解析错误: {str(e)}")
                print("======================================================================")
                raise e
            except Exception as e:
                print("======================================================================")
                print(f"[Error] 结构化解析错误: {str(e)}")
                print(f"message: {message} \n system_message: {system_message}")
                print(f"chat_response: {chat_response}")
                print("======================================================================")
                await TracerManager.set_output(chat_response)
                await TracerManager.record_exception(e)
            
            retry_count += 1
            await TracerManager.add_event(f"失败重试{retry_count}/{self.max_retry}")
            if retry_count < self.max_retry:
                await asyncio.sleep(2)  # 异步等待重试
        
        raise Exception(f"无法从对话中解析到结构化信息 {chat_response}")

    def _extract_last_json(self, chatmessage: str) -> dict:
        jsonObjs = extract_all_json_from_markdown(chatmessage)

        if not jsonObjs or len(jsonObjs) == 0:
            raise Exception(f"无法从对话中解析到json字符串：{chatmessage}")
        data = jsonObjs[-1]  # 取最后一个解析到的json对象
        return data  # 返回第一个解析到的json对象

    def _extract_last_sql(self, chatmessage: str) -> str:
        sql = extract_sql_from_markdown(chatmessage)
        if not sql:
            raise Exception(f"无法从对话中解析到sql语句：{chatmessage}")
        return sql

    def _extract_last_python(self, chatmessage: str) -> str:
        python_code = extract_python_from_markdown(chatmessage)
        if not python_code:
            raise Exception(f"无法从对话中解析到python代码：{chatmessage}")
        return python_code


