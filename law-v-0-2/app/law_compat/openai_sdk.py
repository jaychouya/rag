import json
import time
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional
import asyncio

import aiohttp

from law_compat.abs_llm import AbsLLM, LLMError
import os

"""
OpenAI 响应格式
非流式响应示例：
{
  "choices": [
    {
      "finish_reason": "stop",
      "index": 0,
      "logprobs": null,
      "message": {
        "content": "我是豆包呀，能陪你畅聊各种话题，像日常趣事、知识问答、观点探讨等。你只需在对话框输入文字，清晰表达你想聊的内容，比如分享你的经历，或是询问特定信息，我就会给出回应，咱们就能愉快交流啦。 ",
        "role": "assistant"
      }
    }
  ]
}
流式响应示例:
data: {"choices":[{"delta":{"content":"我","role":"assistant"},"index":0}],"created":1750329345,"id":"0217503293447507cc37f667a86cb86ae91e87193dfe09d626575","model":"doubao-1-5-pro-256k-250115","service_tier":"default","object":"chat.completion.chunk","usage":null}

data: {"choices":[{"delta":{"content":"是","role"
:"assistant"},"index":0}],"created":1750329345,"id":"0217503293447507cc37f667a86cb86ae91e87193dfe09d626575","model":"doubao-1-5-pro-256k-250115","service_tier":"default","object":"chat.completion.chunk","usage":null}

data: {"choices":[{"delta":{"content":"豆","role":"assistant"},"index":0}],"created":1750329345,"id":"0217503293447507cc37f667a86cb86ae91e87193dfe09d626575","model":"doubao-1-5-pro-256k-250115","service_tier":"default","object":"chat.completion.chunk","usage":null}

data: {"choices":[{"delta":{"content":"包","role":"assistant"},"index":0}],"created":1750329345,"id":"0217503293447507cc37f667a86cb86ae91e87193dfe09d626575","model":"doubao-1-5-pro-256k-250115","service_tier":"default","object":"chat.completion.chunk","usage":null}

data: {"choices":[{"delta":{"content":"呀","role":"assistant"},"index":0}],"created":1750329345,"id":"0217503293447507cc37f667a86cb86ae91e87193dfe09d626575","model":"doubao-1-5-pro-256k-250115","service_tier":"default","object":"chat.completion.chunk","usage":null}
....
data: [DONE]
"""

class OpenAICompatibleSDK(AbsLLM):
    
    @classmethod
    async def test_service(cls, base_url: str, model: str, api_key: Optional[str] = None) -> bool:
        """
        Test the service by making a simple request to the chat endpoint.
        Returns True if the service is reachable and responds correctly, otherwise False.
        """
        sdk = cls(base_url, model, api_key)
        return await sdk.test()
    
    def __init__(self, base_url: str, model: str, api_key: Optional[str] = None, temperature: float = 0.7,
                 max_tokens: Optional[int] = None, context_window_len: Optional[int] = 100000, top_p: Optional[float] = None, 
                 top_k: Optional[int] = None, frequency_penalty: Optional[float] = None,
                 presence_penalty: Optional[float] = None, stop: Optional[List[str]] = None, enable_thinking: bool = False,
                 stream_flush_interval: float = 0.1, stream_flush_max_char: Optional[int] = os.getenv("STREAM_FLUSH_MAX_CHAR", 30),
                 timeout: Optional[float] = None):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.top_k = top_k
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        self.stop = stop
        self._context_window_len = context_window_len
        # 流式响应合并配置
        self.stream_flush_interval = stream_flush_interval  # 最大缓存时间间隔（秒）
        self.stream_flush_max_char = stream_flush_max_char  # 单个chunk最大字符数
        self.enable_thinking = enable_thinking
        # 请求超时配置，优先使用传入参数，其次读取环境变量，默认300秒
        self.timeout = timeout if timeout is not None else float(os.getenv("LLM_REQUEST_TIMEOUT", 300))
    
    def context_window_len(self) -> Optional[int]:
        return self._context_window_len

    
    async def test(self)->bool:
        try:
            response = await self.chat(messages=[{'role': 'user', 'content': 'please output "1"'}])
            return True
        except Exception as e:
            print(f"Service test failed: {e}")
            return False
        

    async def chat(self, messages:str | List[Dict[str, Any]], system_message: Optional[str] = None, enable_thinking=None) -> str:
        """
        聊天接口，向OpenAI兼容模型发送消息并获取回复。

        参数说明：
            messages (str | List[Dict[str, Any]]): 聊天消息列表，支持字符串或OpenAI格式的消息字典列表。
            system_message (Optional[str]): 可选，系统提示词，作为对话的系统上下文。
            enable_thinking (Optional[bool]): 可选，是否启用思维链（思考过程）功能，若传入非None则覆盖实例配置。
        返回值:
            str: 模型回复的内容。
        """
        endpoint = f'{self.base_url.rstrip("/")}/chat/completions'
        payload = self.get_llm_payload(messages, system_message, stream=False, enable_thinking=enable_thinking)
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(endpoint, headers=self.get_llm_headers(), json=payload) as response:
                    response.raise_for_status()
                    res = await response.json()
                    return res['choices'][0]['message']['content']
        except Exception as e:
            raise LLMError(f"LLM聊天请求异常: {str(e)}")
    

    async def chat_streaming(self, messages:str | List[Dict[str, Any]], system_message: Optional[str] = None, enable_thinking=None) -> AsyncGenerator[str, None]:
        """
        聊天接口，向OpenAI兼容模型发送消息并获取回复。

        参数说明：
            messages (str | List[Dict[str, Any]]): 聊天消息列表，支持字符串或OpenAI格式的消息字典列表。
            system_message (Optional[str]): 可选，系统提示词，作为对话的系统上下文。
            enable_thinking (Optional[bool]): 可选，是否启用思维链（思考过程）功能，若传入非None则覆盖实例配置。
        返回值:
            str: 模型回复的内容。
        """
        endpoint = f'{self.base_url.rstrip("/")}/chat/completions'
        payload = self.get_llm_payload(messages, system_message, stream=True, enable_thinking=enable_thinking)
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(endpoint, headers=self.get_llm_headers(), json=payload) as response:
                    if response.status // 100 != 2:
                        error_text = await response.text()
                        raise Exception(f"Error: {response.status} - {error_text}")

                    async for chunk in self._cached_stream_response(response):
                        yield chunk
        except Exception as e:
            raise LLMError(f"LLM流式聊天请求异常: {str(e)}")
    
    def _extract_streaming_delta_content(self, response: str) -> tuple[List[tuple[Literal["think","content"], str]], bool]:
        results = []
        if response.startswith("data:"):
            chunk_data = response[5:]  # 去掉 "data: " 前缀
            if chunk_data.strip().upper() == "[DONE]":
                return None, True
            data = json.loads(chunk_data)
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                delta = choice.get("delta", {}) if isinstance(choice, dict) else {}
                # 优先解析think/reasoning相关
                reasoning_text = (
                    delta.get("reasoning")
                    or delta.get("reasoning_content")
                    or delta.get("thinking")
                    or delta.get("thoughts")
                )
                if isinstance(reasoning_text, dict):
                    reasoning_text = reasoning_text.get("content")
                if reasoning_text:
                    results.append(("think", reasoning_text))
                content_text = delta.get("content")
                if content_text:
                    results.append(("content", content_text))
            return results, False
        else:
            return results, False
    
    async def _yield_content_buffer(self, content_buffer: List[str]) -> AsyncGenerator[str, None]:
        """
        按字符数量限制输出content_buffer内容，避免单次输出超过设置的字符限制
        """
        if not content_buffer:
            return
            
        merged_content = ''.join(content_buffer)
        if not self.stream_flush_max_char or self.stream_flush_max_char <= 0:
            # 没有字符限制，直接输出
            yield merged_content
            return
            
        # 按字符数量分块输出
        max_chars = self.stream_flush_max_char
        
        start = 0
        while start < len(merged_content):
            end = min(start + max_chars, len(merged_content))
            chunk = merged_content[start:end]
            
            if chunk:
                yield chunk
            start = end
        
    async def _cached_stream_response(self, response: aiohttp.ClientResponse) -> AsyncGenerator[str, None]:
        """
        优化的异步流式响应处理，解析并缓存content内容，按时间或字符阈值进行flush
        """
        content_buffer = []  # 缓存实际的content内容
        is_thinking = False
        last_flush_time = time.time()
        
        async for line in response.content:
            if line:
                line_str = line.decode('utf-8').strip()
                if line_str:
                    # 解析流式响应，提取content内容
                    contents, is_done = self._extract_streaming_delta_content(line_str)
                    if is_done:
                        # 遇到DONE消息，输出剩余缓存的内容
                        if content_buffer:
                            async for chunk in self._yield_content_buffer(content_buffer):
                                yield chunk
                            content_buffer.clear()
                        break
                    
                    if contents:  # 如果有实际content内容
                        for item in contents:
                            (c_type, c_content) = item
                            if c_type == 'think' and not is_thinking:
                                strip_content = c_content.strip(" \t\r\n")
                                if strip_content:
                                    content_buffer.append("<think>")
                                    is_thinking = True
                            if c_type == 'content' and is_thinking:
                                content_buffer.append("</think>")
                                is_thinking = False
                            content_buffer.append(c_content)
                        
                        current_time = time.time()
                        # 检查是否需要flush：达到时间间隔
                        if (current_time - last_flush_time) >= self.stream_flush_interval:
                            if content_buffer:
                                async for chunk in self._yield_content_buffer(content_buffer):
                                    yield chunk
                                content_buffer.clear()
                                last_flush_time = current_time
        
        # 处理剩余的缓存内容（如果没有遇到DONE消息）
        if content_buffer:
            async for chunk in self._yield_content_buffer(content_buffer):
                yield chunk

    def get_llm_headers(self) -> dict:
        headers = {
            'Content-Type': 'application/json'
        }
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers
    
    def get_llm_payload(self, messages: str | List[dict], system_message: Optional[str] = None, stream: bool = False, enable_thinking=None) -> dict:
        full_messages = []
        if isinstance(messages, str):
            messages = [{'role': 'user', 'content': messages}]
        if system_message:
            full_messages.append({'role': 'system', 'content': system_message})
        
        full_messages.extend(messages)

        payload = {
            'model': self.model,
            'messages': full_messages,
            'stream': stream,
            'extra_body': {
                # 尽可能请求服务端返回 reasoning/think 数据（若服务端支持会生效）
                'include_reasoning': enable_thinking
            }
        }
        if self.temperature is not None:
            payload['temperature'] = self.temperature
        if self.max_tokens is not None:
            payload['max_tokens'] = self.max_tokens
        if self.top_p is not None:
            payload['top_p'] = self.top_p
        if self.top_k is not None:    
            payload['top_k'] = self.top_k
        if self.frequency_penalty is not None:
            payload['frequency_penalty'] = self.frequency_penalty
        if self.presence_penalty is not None:
            payload['presence_penalty'] = self.presence_penalty
        if self.stop:
            payload['stop'] = self.stop
        self._set_thinking_payload(payload, enable_thinking)
        return payload
    
    def _set_thinking_payload(self, payload: dict, enable_thinking) -> dict:
        enable_thinking = enable_thinking if enable_thinking is not None else self.enable_thinking
        if not enable_thinking:
            payload['extra_body']['include_reasoning'] = False
            if 'qwen3' in self.model.lower():
                messages = payload['messages']
                messages[-1]['content'] = messages[-1]['content'] + " /no_think"
        return payload

OpenAICompatibleLLM = OpenAICompatibleSDK