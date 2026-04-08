#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# startup.sh – Azure App Service startup script for the Python bot.
#
# Set this as the "Startup Command" in:
#   App Service → Configuration → General settings → Startup Command
#   Value: bash startup.sh
# ---------------------------------------------------------------------------
set -e

# Install/update dependencies from requirements.txt
pip install --quiet -r requirements.txt

# Start the bot (aiohttp uses the PORT env-var injected by App Service)
python app.py
