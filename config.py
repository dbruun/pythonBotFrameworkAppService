import os


class DefaultConfig:
    """Bot and Azure AI Foundry configuration loaded from environment variables."""

    # Azure Bot Service credentials
    APP_ID: str = os.environ.get("MicrosoftAppId", "")
    APP_PASSWORD: str = os.environ.get("MicrosoftAppPassword", "")

    # Port the app listens on (Azure App Service injects PORT; fall back to 3978)
    PORT: int = int(os.environ.get("PORT", 3978))

    # Azure AI Foundry – project endpoint
    # Format: https://<aiservices-id>.services.ai.azure.com/api/projects/<project-name>
    # Found in: Azure AI Foundry portal → your project → Overview → Project endpoint
    AZURE_AI_PROJECT_ENDPOINT: str = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "")

    # Azure AI Foundry – ID of the agent to query (created in the Foundry portal)
    AZURE_AI_AGENT_ID: str = os.environ.get("AZURE_AI_AGENT_ID", "")
