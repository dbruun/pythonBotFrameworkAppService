import sys
import traceback
from datetime import datetime, timezone
from http import HTTPStatus

from aiohttp import web
from aiohttp.web import Request, Response, json_response

from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    ConversationState,
    MemoryStorage,
    TurnContext,
)
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity, ActivityTypes

from bot import FoundryBot
from config import DefaultConfig

# ---------------------------------------------------------------------------
# Configuration & adapter
# ---------------------------------------------------------------------------

CONFIG = DefaultConfig()

SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)


async def on_error(context: TurnContext, error: Exception):
    """Global error handler for unhandled exceptions during a turn."""
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()

    await context.send_activity("The bot encountered an error or bug.")
    await context.send_activity(
        "To continue to run this bot, please fix the bot source code."
    )

    # Send a trace activity when talking to the Bot Framework Emulator
    if context.activity.channel_id == "emulator":
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.now(timezone.utc),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        await context.send_activity(trace_activity)


ADAPTER.on_turn_error = on_error

# ---------------------------------------------------------------------------
# State & bot
# ---------------------------------------------------------------------------

# MemoryStorage is used here for simplicity.  For production deployments
# replace it with CosmosDbPartitionedStorage or BlobStorage so that state
# survives App Service restarts.
MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)

BOT = FoundryBot(CONFIG, CONVERSATION_STATE)

# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------


async def messages(req: Request) -> Response:
    """Main bot message endpoint – Azure Bot Service POSTs activities here."""
    if "application/json" not in req.headers.get("Content-Type", ""):
        return Response(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
    if response:
        return json_response(data=response.body, status=response.status)
    return Response(status=HTTPStatus.OK)


async def health(req: Request) -> Response:
    """Simple health-check endpoint for Azure App Service."""
    return json_response({"status": "ok"})


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/messages", messages)
APP.router.add_get("/health", health)

if __name__ == "__main__":
    try:
        web.run_app(APP, host="0.0.0.0", port=CONFIG.PORT)
    except Exception as error:
        raise error
