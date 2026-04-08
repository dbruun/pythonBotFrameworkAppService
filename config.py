import os


class DefaultConfig:
    """Bot and Azure AI Foundry configuration loaded from environment variables."""

    # Azure Bot Service credentials
    APP_ID: str = os.environ.get("MicrosoftAppId", "")
    APP_PASSWORD: str = os.environ.get("MicrosoftAppPassword", "")

    # Port the app listens on (Azure App Service injects PORT; fall back to 3978)
    PORT: int = int(os.environ.get("PORT", 3978))

    # Azure AI Foundry – connection string from the Foundry portal
    # Format: "<endpoint>;<subscription_id>;<resource_group>;<project_name>"
    AZURE_AI_PROJECT_CONNECTION_STRING: str = os.environ.get(
        "AZURE_AI_PROJECT_CONNECTION_STRING", ""
    )

    # Azure AI Foundry – project endpoint (alternative to connection string)
    AZURE_AI_PROJECT_ENDPOINT: str = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "")

    # Azure AI Foundry – ID of the agent to query (created in the Foundry portal)
    AZURE_AI_AGENT_ID: str = os.environ.get("AZURE_AI_AGENT_ID", "")
