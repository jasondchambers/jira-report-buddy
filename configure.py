import getpass
from pathlib import Path
from dotenv import load_dotenv, set_key

from jira import JIRA
from jira.exceptions import JIRAError

import jira_buddy
from fuzzy_find import fuzzy_find

ENV_FILE = Path.home() / ".jira-report-buddy.env"


def load() -> None:
    _ = load_dotenv(ENV_FILE)

def init() -> bool:
    print("Jira Report Buddy — Configuration")
    print("=" * 34)

    url = input("JIRA URL (e.g. https://yourcompany.atlassian.net): ").strip()
    email = input("JIRA Email: ").strip()
    token = getpass.getpass("JIRA API Token: ")

    print("\nTesting connection...")
    try:
        client = JIRA(server=url, basic_auth=(email, token))
        me = client.myself()
        print(f"Connected as {me['displayName']} ({me['emailAddress']})")
    except JIRAError as e:
        print(f"Connection failed: {e.text}")
        return False
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

    lines = [
        f'JIRA_URL="{url}"',
        f'JIRA_EMAIL="{email}"',
        f'JIRA_API_TOKEN="{token}"',
    ]
    _ = ENV_FILE.write_text("\n".join(lines) + "\n")

    print(f"\nSettings saved to {ENV_FILE}")
    return True


def set_project() -> None:
    if not ENV_FILE.exists():
        if not init():
            return
    load()
    projects = jira_buddy.get_projects()
    _, idx = fuzzy_find([p.name for p in projects], title="Select a Jira project: ")
    key = projects[idx].key
    _ = set_key(ENV_FILE, "JIRA_PROJECT", key)
    print(f"\nJIRA_PROJECT set to {key}")
