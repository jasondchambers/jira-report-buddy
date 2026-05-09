import argparse
import os
import sys
from pathlib import Path
from typing import TypedDict, cast

import requests
import configure

CACHE_FILE = Path.home() / ".jira-report-buddy.orgs.cache"


class _Org(TypedDict):
    name: str


class _Issue(TypedDict):
    fields: dict[str, list[_Org] | None]


class _PageResult(TypedDict, total=False):
    issues: list[_Issue]
    isLast: bool
    nextPageToken: str


class _UserInfo(TypedDict):
    displayName: str
    emailAddress: str


def get_jira_config() -> tuple[str, str, str, str, str]:
    configure.load()

    url = os.getenv("JIRA_URL")
    email = os.getenv("JIRA_EMAIL")
    api_token = os.getenv("JIRA_API_TOKEN")
    jira_project = os.getenv("JIRA_PROJECT")
    org_field = os.getenv("JIRA_ISSUE_ORGANIZATION_FIELD_NAME")

    if url is None or email is None or api_token is None or jira_project is None or org_field is None:
        raise ValueError(
            "Missing required environment variables. "
            + "Please set JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT and "
            + "JIRA_ISSUE_ORGANIZATION_FIELD_NAME in ~/.jira-report-buddy.env"
        )

    return url.rstrip("/"), email, api_token, jira_project, org_field


def _extract_org_names(issue: _Issue, org_field: str) -> list[str]:
    orgs = issue["fields"].get(org_field)
    if not orgs:
        return []
    return [org["name"] for org in orgs if "name" in org]


def _fetch_issues_page(
    url: str,
    auth: tuple[str, str],
    jql: str,
    org_field: str,
    next_page_token: str | None,
) -> _PageResult:
    params: dict[str, str | int] = {
        "jql": jql,
        "maxResults": 100,
        "fields": org_field,
    }
    if next_page_token:
        params["nextPageToken"] = next_page_token

    response = requests.get(
        f"{url}/rest/api/3/search/jql",
        auth=auth,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return cast(_PageResult, response.json())


def _verify_connection(url: str, auth: tuple[str, str]) -> None:
    response = requests.get(f"{url}/rest/api/3/myself", auth=auth, timeout=30)
    response.raise_for_status()
    myself = cast(_UserInfo, response.json())
    print(
        f"Connected to Jira as: {myself['displayName']} ({myself['emailAddress']})",
        file=sys.stderr,
    )


def fetch_organizations_from_jira() -> list[str]:
    url, email, api_token, jira_project, org_field = get_jira_config()
    auth = (email, api_token)

    _verify_connection(url, auth)

    jql = f"project = {jira_project}"
    print(jql)
    organizations: set[str] = set()
    total_issues = 0
    next_page_token: str | None = None

    while True:
        data = _fetch_issues_page(url, auth, jql, org_field, next_page_token)
        issues = data.get("issues", [])

        if not issues:
            break

        total_issues += len(issues)
        for issue in issues:
            organizations.update(_extract_org_names(issue, org_field))

        if data.get("isLast", True):
            break
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    print(f"Scanned {total_issues} issues", file=sys.stderr)
    return sorted(organizations)


def read_cache() -> str | None:
    if CACHE_FILE.exists():
        return CACHE_FILE.read_text()
    return None


def write_cache(organizations: list[str]) -> None:
    content = "\n".join(organizations)
    if organizations:
        content += "\n"
    _ = CACHE_FILE.write_text(content)


class _Args(argparse.Namespace):
    refresh: bool = False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List all available organizations from Jira"
    )
    _ = parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh the cache with fresh data from Jira",
    )
    args = cast(_Args, parser.parse_args())

    if not args.refresh:
        cached = read_cache()
        if cached is not None:
            print(cached, end="")
            return

    organizations = fetch_organizations_from_jira()
    write_cache(organizations)

    for org in organizations:
        print(org)


if __name__ == "__main__":
    main()
