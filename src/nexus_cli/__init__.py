"""Nexus CLI package init file."""
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path.home() / ".config/nexus/.env"

# Loaded before any console import, the default parameter path is evaluated at import time.
# Variables already set in the shell take precedence over the file.
load_dotenv(ENV_FILE)
