import asyncio
import queue
import threading
import traceback
from typing import Union

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Task, TaskState, UnsupportedOperationError
from a2a.utils import new_agent_parts_message, new_task
from a2a.utils.errors import ServerError

from law_a2a.simple_types import (
    SimpleA2AMessageResult,
    SimpleA2APart,
    SimpleA2AStatusResult,
    SimpleA2ATaskStatus,
)


class LawA2AgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
        context.current_task = task
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        try:
            result_container: dict = {}
            finished_event = threading.Event()
            progress_queue: queue.Queue[str] = queue.Queue()
            userquery = context.get_user_input()
            m = context.metadata or {}
            cat = m.get("category_tags") or None
            tags = m.get("law_tags") or None
            if not cat:
                cat = None
            if not tags:
                tags = None

            def callback(message: str):
                progress_queue.put(message.rstrip("\n") + "\n")

            def find_task():
                from law_finder.finder import auto_query

                try:
                    result = asyncio.run(
                        auto_query(
                            userquery,
                            category_scope=cat,
                            law_tags=tags,
                            max_llm_threads=8,
                            progressCallback=callback,
                        )
                    )
                    result_container["result"] = result
                except Exception as e:
                    result_container["error"] = str(e)
                    result_container["traceback"] = traceback.format_exc()
                finished_event.set()

            law_thread = threading.Thread(target=find_task)
            law_thread.start()

            while not finished_event.is_set():
                message = ""
                while not progress_queue.empty():
                    message = message + progress_queue.get_nowait()
                    if not message.endswith("\n"):
                        message = message + "\n"
                if message:
                    for i in range(0, len(message), 10):
                        chunk = message[i : i + 10]
                        await self._send_result(
                            task,
                            updater,
                            SimpleA2AMessageResult(parts=[SimpleA2APart(data_type="text", content=chunk)]),
                        )
                await asyncio.sleep(0.1)

            law_thread.join()

            if "error" in result_container:
                raise RuntimeError(
                    f"{result_container['error']} {result_container.get('traceback', '')}"
                )

            from law_finder.finder import get_summary_law_result_prompt
            from law_finder.llm import LLMSDK

            result, question_type = result_container["result"]
            prompt = get_summary_law_result_prompt(
                result=result, question=userquery, question_type=question_type
            )
            async for chunk in LLMSDK.chat_streaming(userquery, prompt):
                await self._send_result(task, updater, chunk)

            await self._send_result(
                task,
                updater,
                SimpleA2AStatusResult(status=SimpleA2ATaskStatus.completed),
            )
        except Exception:
            await self._send_result(
                task,
                updater,
                SimpleA2AStatusResult(status=SimpleA2ATaskStatus.failed),
            )
            raise

    async def _send_result(
        self,
        task: Task,
        updater: TaskUpdater,
        result: Union[SimpleA2AMessageResult, SimpleA2AStatusResult, str],
    ) -> None:
        if isinstance(result, str):
            result = SimpleA2AMessageResult(parts=[SimpleA2APart(data_type="text", content=result)])
        parts = [item.to_part() for item in result.parts] if result.parts else []
        if isinstance(result, SimpleA2AStatusResult):
            await updater.update_status(
                TaskState(result.status.value),
                new_agent_parts_message(parts, task.context_id, task.id) if parts else None,
            )
        elif isinstance(result, SimpleA2AMessageResult):
            await updater.update_status(
                TaskState.working,
                new_agent_parts_message(parts, task.context_id, task.id),
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
