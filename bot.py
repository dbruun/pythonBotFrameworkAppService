import asyncio
import logging
import sys
from typing import Optional

from botbuilder.core import ActivityHandler, ConversationState, TurnContext
from botbuilder.schema import ChannelAccount

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


class FoundryBot(ActivityHandler):
    """
    Bot that forwards user messages to an Azure AI Foundry agent and returns
    the agent's response.  Each conversation gets its own Foundry thread so
    that multi-turn context is preserved within a session.
    """

    def __init__(self, config, conversation_state: ConversationState):
        self.config = config
        self.conversation_state = conversation_state
        # Accessor used to persist the Foundry thread ID across turns
        self._thread_id_accessor = conversation_state.create_property("FoundryThreadId")
        self._project_client: Optional[AIProjectClient] = None

    # ------------------------------------------------------------------
    # Azure AI Foundry client (lazy, singleton)
    # ------------------------------------------------------------------

    def _get_project_client(self) -> AIProjectClient:
        if self._project_client is not None:
            return self._project_client

        credential = DefaultAzureCredential()

        if self.config.AZURE_AI_PROJECT_CONNECTION_STRING:
            self._project_client = AIProjectClient.from_connection_string(
                conn_str=self.config.AZURE_AI_PROJECT_CONNECTION_STRING,
                credential=credential,
            )
        elif self.config.AZURE_AI_PROJECT_ENDPOINT:
            self._project_client = AIProjectClient(
                endpoint=self.config.AZURE_AI_PROJECT_ENDPOINT,
                credential=credential,
            )
        else:
            raise ValueError(
                "Neither AZURE_AI_PROJECT_CONNECTION_STRING nor "
                "AZURE_AI_PROJECT_ENDPOINT is configured."
            )

        return self._project_client

    # ------------------------------------------------------------------
    # Bot Framework activity handlers
    # ------------------------------------------------------------------

    async def on_message_activity(self, turn_context: TurnContext):
        user_message = turn_context.activity.text
        if not user_message:
            return

        # Retrieve the existing Foundry thread ID for this conversation (if any)
        thread_id: Optional[str] = await self._thread_id_accessor.get(
            turn_context, None
        )

        # Offload the synchronous Foundry SDK calls to a thread-pool executor
        # so that the asyncio event loop is not blocked.
        loop = asyncio.get_event_loop()
        response_text, thread_id = await loop.run_in_executor(
            None, self._query_foundry_agent, user_message, thread_id
        )

        # Persist the thread ID so the next turn continues in the same thread
        await self._thread_id_accessor.set(turn_context, thread_id)
        await self.conversation_state.save_changes(turn_context)

        await turn_context.send_activity(response_text)

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    "Hello! I'm powered by Azure AI Foundry. "
                    "How can I help you today?"
                )

    # ------------------------------------------------------------------
    # Synchronous helper – runs in thread-pool executor
    # ------------------------------------------------------------------

    def _query_foundry_agent(
        self, message: str, thread_id: Optional[str]
    ) -> tuple[str, str]:
        """
        Send *message* to the configured Foundry agent and return
        (response_text, thread_id).  If *thread_id* is None a new thread
        is created so this conversation starts fresh.
        """
        client = self._get_project_client()

        # Create a thread on the first turn of the conversation
        if not thread_id:
            thread = client.agents.create_thread()
            thread_id = thread.id
            logger.info("Created new Foundry thread: %s", thread_id)

        # Add the user's message to the thread
        client.agents.create_message(
            thread_id=thread_id,
            role="user",
            content=message,
        )

        # Run the agent and block until it completes
        run = client.agents.create_and_process_run(
            thread_id=thread_id,
            agent_id=self.config.AZURE_AI_AGENT_ID,
        )

        if run.status == "failed":
            logger.error(
                "Foundry agent run failed. Thread: %s  Last error: %s",
                thread_id,
                getattr(run, "last_error", "unknown"),
            )
            return (
                "I'm sorry, the AI agent encountered an error. Please try again.",
                thread_id,
            )

        # Retrieve messages and return the most recent assistant reply
        messages = client.agents.list_messages(thread_id=thread_id)
        for msg in messages:
            if msg.role == "assistant":
                for content_block in msg.content:
                    if hasattr(content_block, "text"):
                        return content_block.text.value, thread_id

        return "I couldn't generate a response at this time.", thread_id
