from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any, Dict, List, Optional


class LLMError(Exception):
    pass


class AbsLLM(ABC):
    @abstractmethod
    async def chat(
        self, messages: str | List[Dict[str, Any]], system_message: Optional[str] = None
    ) -> str:
        pass

    @abstractmethod
    async def chat_streaming(
        self, messages: str | List[Dict[str, Any]], system_message: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        pass

    def context_window_len(self) -> Optional[int]:
        return None
