import getpass
from pathlib import Path
from dotenv import load_dotenv

from jira import JIRA
from jira.exceptions import JIRAError

ENV_FILE = Path.home() / ".jira-report-buddy.env"


def load() -> None:
    _ = load_dotenv(ENV_FILE)

def init() -> None:
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
        return
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    lines = [
        f'JIRA_URL="{url}"',
        f'JIRA_EMAIL="{email}"',
        f'JIRA_API_TOKEN="{token}"',
    ]
    _ = ENV_FILE.write_text("\n".join(lines) + "\n")

    print(f"\nSettings saved to {ENV_FILE}")
