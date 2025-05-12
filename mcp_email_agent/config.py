import json
import os

from appdirs import user_config_dir, user_data_dir

APP_NAME = "MCP-EMAIL-AGENT"
APP_AUTHOR = "Jin Yang"

CONFIG_DIR = user_config_dir(APP_NAME, APP_AUTHOR)
DATA_DIR = user_data_dir(APP_NAME, APP_AUTHOR)

DEFAULT_CREDENTIALS_PATH = os.path.join(CONFIG_DIR, "credentials.json")
DEFAULT_TOKEN_PATH = os.path.join(DATA_DIR, "token.json")
DEFAULT_RULES_PATH = os.path.join(CONFIG_DIR, "rules.json")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]


def ensure_dir_exists(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def load_rules(rules_path=DEFAULT_RULES_PATH):
    ensure_dir_exists(rules_path)
    if not os.path.exists(rules_path):
        default_rules = {"categories": {}, "spam_deletion": {}, "auto_drafts": []}
        with open(rules_path, "w") as f:
            json.dump(default_rules, f, indent=2)
        print(f"Created a default rules file at: {rules_path}")
        return default_rules
    try:
        with open(rules_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {rules_path}. Please check its format.")
        return None
    except FileNotFoundError:
        print(f"Error: Rules file not found at {rules_path}")
        return None


ensure_dir_exists(DEFAULT_CREDENTIALS_PATH)
ensure_dir_exists(DEFAULT_TOKEN_PATH)
ensure_dir_exists(DEFAULT_RULES_PATH)
