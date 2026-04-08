import asyncio
import logging
import sys
from typing import Optional

from botbuilder.core import ActivityHandler, ConversationState, TurnContext
from botbuilder.schema import ChannelAccount

from azure.ai.agents import AgentsClient
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
        self._agents_client: Optional[AgentsClient] = None

    # ------------------------------------------------------------------
    # Azure AI Agents client (lazy, singleton)
    # ------------------------------------------------------------------

    def _get_agents_client(self) -> AgentsClient:
        if self._agents_client is not None:
            return self._agents_client

        if not self.config.AZURE_AI_PROJECT_ENDPOINT:
            raise ValueError(
                "AZURE_AI_PROJECT_ENDPOINT is not configured. "
                "Set it to your Foundry project endpoint, e.g. "
                "https://<aiservices-id>.services.ai.azure.com/api/projects/<project-name>."
            )

        self._agents_client = AgentsClient(
            endpoint=self.config.AZURE_AI_PROJECT_ENDPOINT,
            credential=DefaultAzureCredential(),
        )
        return self._agents_client

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

        # Offload the synchronous Agents SDK calls to a thread-pool executor
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
        client = self._get_agents_client()

        # Create a thread on the first turn of the conversation
        if not thread_id:
            thread = client.threads.create()
            thread_id = thread.id
            logger.info("Created new Foundry thread: %s", thread_id)

        # Add the user's message to the thread
        client.messages.create(
            thread_id=thread_id,
            role="user",
            content=message,
        )

        # Run the agent and block until it completes
        run = client.runs.create_and_process(
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
        messages = client.messages.list(thread_id=thread_id)
        for msg in messages:
            if msg.role == "assistant":
                for content_block in msg.content:
                    if hasattr(content_block, "text"):
                        return content_block.text.value, thread_id

        return "I couldn't generate a response at this time.", thread_id
