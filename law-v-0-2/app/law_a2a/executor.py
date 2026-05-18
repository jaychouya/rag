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
                from law_a2a.client_llm_util import (
                    client_llm_required,
                    make_client_sdk,
                    parse_client_llm_fields,
                )
                from law_finder.finder import auto_query
                from law_finder import llm as lf_llm

                token = None
                key, bu, md, err = parse_client_llm_fields(
                    m.get("llm_api_key"),
                    m.get("llm_base_url"),
                    m.get("llm_model"),
                )
                if err and (client_llm_required() or m.get("llm_api_key")):
                    result_container["error"] = err
                    finished_event.set()
                    return
                if key:
                    token = lf_llm.set_request_llm(make_client_sdk(key, bu, md))
                    result_container["client_llm"] = (key, bu, md)
                elif client_llm_required() or not (lf_llm.LLM_API_KEY or "").strip():
                    result_container["error"] = (
                        "A2A 请求须携带 metadata.llm_api_key / llm_base_url / llm_model，服务端不消耗所有者 Token。"
                    )
                    finished_event.set()
                    return

                try:
                    result = asyncio.run(
                        auto_query(
                            userquery,
                            category_scope=cat,
                            law_tags=tags,
                            progressCallback=callback,
                        )
                    )
                    result_container["result"] = result
                except Exception as e:
                    result_container["error"] = str(e)
                    result_container["traceback"] = traceback.format_exc()
                finally:
                    if token is not None:
                        lf_llm.reset_request_llm(token)
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

            from law_a2a.client_llm_util import make_client_sdk
            from law_finder.finder import get_summary_law_result_prompt
            from law_finder import llm as lf_llm
            from law_finder.llm import LLMSDK

            result, question_type = result_container["result"]
            prompt = get_summary_law_result_prompt(
                result=result, question=userquery, question_type=question_type
            )
            summary_token = None
            client_llm = result_container.get("client_llm")
            if client_llm:
                ck, cbu, cmd = client_llm
                summary_token = lf_llm.set_request_llm(make_client_sdk(ck, cbu, cmd))
            try:
                async for chunk in LLMSDK.chat_streaming(userquery, prompt):
                    await self._send_result(task, updater, chunk)
            finally:
                if summary_token is not None:
                    lf_llm.reset_request_llm(summary_token)

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
