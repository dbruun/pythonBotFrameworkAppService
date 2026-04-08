# pythonBotFrameworkAppService

A Python App Service bot that bridges **Azure Bot Service** and an **Azure AI Foundry** agent.  
Users interact through any Bot Service channel (including the built-in test web chat), and every message is routed transparently to the Foundry agent and the reply is surfaced back to the user.

---

## Architecture

```
User  ──►  Azure Bot Service  ──►  /api/messages (aiohttp)
                                        │
                                        ▼
                              Azure AI Foundry Agent
                             (thread-per-conversation)
```

* **Bot Framework Adapter** (botbuilder-integration-aiohttp) authenticates inbound activities from Azure Bot Service.  
* **FoundryBot** maintains an Azure AI Foundry thread per conversation so multi-turn context is preserved within a session.  
* **Azure AI Projects SDK** (`azure-ai-projects`) wraps the Foundry Agents REST API.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.9+ | Tested with 3.11 |
| Azure subscription | North Central US recommended |
| Azure Bot Service resource | Any channel registration |
| Azure AI Foundry project | With a deployed agent |

---

## Local development

### 1. Clone and set up a virtual environment

```bash
git clone https://github.com/dbruun/pythonBotFrameworkAppService.git
cd pythonBotFrameworkAppService
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.template .env
# Open .env and fill in all values (see comments inside the file)
```

Required values:

| Variable | Where to find it |
|---|---|
| `MicrosoftAppId` | Azure Portal → Bot Service → Configuration |
| `MicrosoftAppPassword` | Azure Portal → Bot Service → Configuration |
| `AZURE_AI_PROJECT_CONNECTION_STRING` | Azure AI Foundry portal → project → Settings → Connection string |
| `AZURE_AI_AGENT_ID` | Azure AI Foundry portal → project → Agents → *your agent* → Agent ID |

### 3. Load env vars and start the bot

```bash
export $(grep -v '^#' .env | xargs)
python app.py
```

The bot listens on `http://localhost:3978/api/messages`.

### 4. Test with Bot Framework Emulator

1. Download [Bot Framework Emulator](https://github.com/microsoft/BotFramework-Emulator/releases).
2. Open the Emulator and click **Open Bot**.
3. Set **Bot URL** to `http://localhost:3978/api/messages`.
4. Enter your `MicrosoftAppId` and `MicrosoftAppPassword` (or leave blank if testing without auth).
5. Send a message – the reply should come from your Foundry agent.

---

## Azure deployment (North Central US)

### 1. Create Azure resources

```bash
# Resource group in North Central US
az group create --name rg-foundry-bot --location northcentralus

# App Service Plan (Linux, B1 or higher)
az appservice plan create \
  --name asp-foundry-bot \
  --resource-group rg-foundry-bot \
  --location northcentralus \
  --is-linux \
  --sku B1

# Web App (Python 3.11)
az webapp create \
  --name <your-unique-app-name> \
  --resource-group rg-foundry-bot \
  --plan asp-foundry-bot \
  --runtime "PYTHON:3.11"

# Set startup command
az webapp config set \
  --name <your-unique-app-name> \
  --resource-group rg-foundry-bot \
  --startup-file "bash startup.sh"
```

### 2. Configure App Settings

```bash
az webapp config appsettings set \
  --name <your-unique-app-name> \
  --resource-group rg-foundry-bot \
  --settings \
    MicrosoftAppId="<bot-app-id>" \
    MicrosoftAppPassword="<bot-app-password>" \
    AZURE_AI_PROJECT_CONNECTION_STRING="<foundry-connection-string>" \
    AZURE_AI_AGENT_ID="<agent-id>"
```

### 3. Enable Managed Identity (recommended)

```bash
# Enable system-assigned identity on the App Service
az webapp identity assign \
  --name <your-unique-app-name> \
  --resource-group rg-foundry-bot

# Grant the identity access to the Foundry project (Azure AI Developer role)
az role assignment create \
  --assignee <principal-id-from-above> \
  --role "Azure AI Developer" \
  --scope /subscriptions/<sub>/resourceGroups/rg-foundry-bot
```

### 4. Deploy code

```bash
az webapp deployment source config-local-git \
  --name <your-unique-app-name> \
  --resource-group rg-foundry-bot

git remote add azure <git-url-from-above>
git push azure main
```

### 5. Register the App Service as the Bot messaging endpoint

In the Azure Portal:

1. Open your **Bot Service** resource.
2. Go to **Configuration**.
3. Set **Messaging endpoint** to:  
   `https://<your-unique-app-name>.azurewebsites.net/api/messages`
4. Save.

### 6. Test via Bot Service test web chat

1. In the Azure Portal, open your Bot Service resource.
2. Click **Test in Web Chat** (left sidebar).
3. Send a message – it should route through the App Service to your Foundry agent and back.

---

## Health check

```
GET https://<your-app>.azurewebsites.net/health
```

Returns `{"status": "ok"}` when the service is running.

---

## Project structure

```
.
├── app.py              # aiohttp web server + Bot Framework adapter
├── bot.py              # FoundryBot – routes messages to/from Foundry agent
├── config.py           # Environment variable configuration
├── requirements.txt    # Python dependencies
├── startup.sh          # Azure App Service startup script
└── .env.template       # Environment variable template (copy to .env)
```

---

## Key dependencies

| Package | Purpose |
|---|---|
| `botbuilder-core` | Bot Framework SDK core |
| `botbuilder-integration-aiohttp` | aiohttp adapter for Bot Framework |
| `azure-ai-projects` | Azure AI Foundry Agents SDK |
| `azure-identity` | Azure authentication (Managed Identity / DefaultAzureCredential) |
| `aiohttp` | Async HTTP server |
