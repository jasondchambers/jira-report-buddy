import os
from typing import NamedTuple

from jira import JIRA


class JiraProject(NamedTuple):
    key: str
    name: str


def _client() -> JIRA:
    return JIRA(
        server=os.environ["JIRA_URL"],
        basic_auth=(os.environ["JIRA_EMAIL"], os.environ["JIRA_API_TOKEN"]),
    )


def get_projects() -> list[JiraProject]:
    return sorted(
        (JiraProject(str(p.key), str(p.name)) for p in _client().projects()),  # pyright: ignore[reportAny]
        key=lambda p: p.name,
    )
