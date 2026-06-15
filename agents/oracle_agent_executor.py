from __future__ import annotations

import logging

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import TaskArtifactUpdateEvent
from a2a.types import TaskState
from a2a.types import TaskStatus
from a2a.types import TaskStatusUpdateEvent
from a2a.utils import new_agent_text_message
from a2a.utils import new_task
from a2a.utils import new_text_artifact

from agents.oracle_worker_agent import OracleWorkerAgent


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class OracleLangGraphAgentExecutor(AgentExecutor):
    """A2A executor that exposes the Oracle LangGraph worker agent."""

    def __init__(self):
        self.agent = OracleWorkerAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = None

        try:
            query = context.get_user_input()
            if not query:
                raise ValueError("No user input provided")

            task = context.current_task
            if not task:
                task = new_task(context.message)
                await event_queue.enqueue_event(task)

            logger.info(
                "[OracleLangGraphAgentExecutor] Starting execution for query: %s",
                query,
            )

            async for event in self.agent.stream(query, task.context_id):
                logger.info("[OracleLangGraphAgentExecutor] Event: %s", event)

                is_complete = event.get("is_task_complete", False)
                requires_input = event.get("require_user_input", False)
                content = event.get("content", "")

                if is_complete:
                    await event_queue.enqueue_event(
                        TaskArtifactUpdateEvent(
                            taskId=task.id,
                            contextId=task.context_id,
                            artifact=new_text_artifact(
                                name="oracle_result",
                                description="Result of Oracle worker request.",
                                text=content,
                            ),
                            append=False,
                            lastChunk=True,
                        )
                    )
                    await event_queue.enqueue_event(
                        TaskStatusUpdateEvent(
                            taskId=task.id,
                            contextId=task.context_id,
                            status=TaskStatus(state=TaskState.completed),
                            final=True,
                        )
                    )

                elif requires_input:
                    await event_queue.enqueue_event(
                        TaskStatusUpdateEvent(
                            taskId=task.id,
                            contextId=task.context_id,
                            status=TaskStatus(
                                state=TaskState.input_required,
                                message=new_agent_text_message(
                                    content,
                                    task.context_id,
                                    task.id,
                                ),
                            ),
                            final=True,
                        )
                    )

                else:
                    await event_queue.enqueue_event(
                        TaskStatusUpdateEvent(
                            taskId=task.id,
                            contextId=task.context_id,
                            status=TaskStatus(
                                state=TaskState.working,
                                message=new_agent_text_message(
                                    content,
                                    task.context_id,
                                    task.id,
                                ),
                            ),
                            final=False,
                        )
                    )

        except Exception as exc:
            logger.error(
                "[OracleLangGraphAgentExecutor] Error in execute: %s",
                exc,
                exc_info=True,
            )

            if task:
                await event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        taskId=task.id,
                        contextId=task.context_id,
                        status=TaskStatus(
                            state=TaskState.error,
                            message=new_agent_text_message(
                                f"Error processing Oracle request: {exc}",
                                task.context_id,
                                task.id,
                            ),
                        ),
                        final=True,
                    )
                )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancel not supported")
