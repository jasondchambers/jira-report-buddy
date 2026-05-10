"""Monthly YTD report for Jira support tickets and feature requests.

Generates a markdown report covering ticket flow (created/closed/net), open backlog
snapshots, detail tables for outstanding and closed tickets, and timing metrics (TTS/CT/LT).
"""

import os
from dataclasses import dataclass
from datetime import date
from jira import JIRA
from jira.resources import Issue
from datetime import datetime
from dotenv import load_dotenv

PROJECT = 'project = "Customer Success - Ticket Portal"'

# "Done" statuses per ticket type (must match Jira status names exactly)
SUPPORT_DONE_STATUSES = ["Closed", "Added to Product Backlog for consideration"]
FEATURE_DONE_STATUSES = ["Resolved", "Closed"]

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

def get_jira_client() -> JIRA:
    """Create and return an authenticated Jira client."""
    config_path = os.path.expanduser("~/.jira-report.env")
    load_dotenv(config_path)

    url = os.getenv("JIRA_URL")
    email = os.getenv("JIRA_EMAIL")
    api_token = os.getenv("JIRA_API_TOKEN")

    if url is None or email is None or api_token is None:
        raise ValueError(
            "Missing required environment variables. "
            "Please set JIRA_URL, JIRA_EMAIL, and JIRA_API_TOKEN in ~/.jira-report.env"
        )

    return JIRA(server=url, basic_auth=(email, api_token))

def calculate_metrics(
    created: str,
    started: str | None,
    closed: str | None,
) -> tuple[int | None, int | None, int | None]:
    """Calculate time metrics for a closed issue.

    Returns:
        Tuple of (time_to_start, cycle_time, lead_time) in days.
        - time_to_start: Days from created to first in-progress
        - cycle_time: Days from started to closed
        - lead_time: Days from created to closed
    """
    created_dt = datetime.strptime(created, "%Y-%m-%d")
    closed_dt = datetime.strptime(closed, "%Y-%m-%d") if closed else None
    started_dt = datetime.strptime(started, "%Y-%m-%d") if started else None

    # Time to Start (Started - Created)
    time_to_start = (started_dt - created_dt).days if started_dt else None

    # Cycle Time (Closed - Started)
    cycle_time = (closed_dt - started_dt).days if started_dt and closed_dt else None

    # Lead Time (Closed - Created)
    lead_time = (closed_dt - created_dt).days if closed_dt else None

    return time_to_start, cycle_time, lead_time


def get_first_in_progress_date(issue: Issue) -> str | None:
    """Get the date when an issue first moved to an 'In Progress' status."""
    if not hasattr(issue, "changelog"):
        return None
    # Get histories in chronological order (oldest first)
    histories = list(issue.changelog.histories)
    histories.reverse()

    # First try: look for statuses containing "In Progress"
    for history in histories:
        for item in history.items:
            if item.field == "status" and "In Progress" in item.toString:
                return history.created[:10]

    # Fallback for older workflow: look for "IN DEVELOPMENT"
    for history in histories:
        for item in history.items:
            if item.field == "status" and item.toString.upper() == "IN DEVELOPMENT":
                return history.created[:10]

    return None

def months_ytd(year: int) -> list[tuple[str, str, str]]:
    """Return (label, start, exclusive_end) for each month from Jan through last complete month."""
    today = date.today()
    result = []
    for m in range(1, 13):
        if date(year, m, 1) >= today.replace(day=1):
            break
        label = f"{year}-{m:02d}"
        start = f"{year}-{m:02d}-01"
        end_m, end_y = (m + 1, year) if m < 12 else (1, year + 1)
        end = f"{end_y}-{end_m:02d}-01"
        result.append((label, start, end))
    return result


def count(jira, jql: str) -> int:
    """Return the number of issues matching JQL without fetching issue bodies."""
    print(f"{jql}")
    return jira.search_issues(jql, maxResults=0).total


def changed_to_clause(statuses: list[str], start: str, end: str) -> str:
    """Build a JQL clause for issues whose status changed to any of the given values."""
    parts = [
        f'status CHANGED TO "{s}" DURING ("{start}", "{end}")'
        for s in statuses
    ]
    return "(" + " OR ".join(parts) + ")"


def not_done_clause(statuses: list[str]) -> str:
    parts = ", ".join(f'"{s}"' for s in statuses)
    return f"status NOT IN ({parts})"


@dataclass
class MonthRow:
    label: str
    st_created: int
    st_closed: int
    st_running: int
    fr_created: int
    fr_closed: int
    fr_running: int

    @property
    def st_net(self) -> int:
        return self.st_created - self.st_closed

    @property
    def fr_net(self) -> int:
        return self.fr_created - self.fr_closed


@dataclass
class FRDetail:
    key: str
    org: str
    created: str
    reporter: str
    status: str
    summary: str


@dataclass
class FRDoneDetail:
    key: str
    org: str
    started: str | None
    closed: str | None
    reporter: str
    status: str
    tts: int | None
    ct: int | None
    lt: int | None
    summary: str


def fetch_data(jira, months: list[tuple[str, str, str]]) -> tuple[list[MonthRow], int, int]:
    """Return (rows, st_open_now, fr_open_now)."""
    rows = []
    st_running = 0
    fr_running = 0
    for label, start, end in months:
        st_c = count(jira, f'{PROJECT} AND issuetype != "Feature Request" AND created >= "{start}" AND created < "{end}"')
        st_d = count(jira, f'{PROJECT} AND issuetype != "Feature Request" AND {changed_to_clause(SUPPORT_DONE_STATUSES, start, end)}')
        fr_c = count(jira, f'{PROJECT} AND issuetype = "Feature Request" AND created >= "{start}" AND created < "{end}"')
        fr_d = count(jira, f'{PROJECT} AND issuetype = "Feature Request" AND {changed_to_clause(FEATURE_DONE_STATUSES, start, end)}')
        st_running += st_c - st_d
        fr_running += fr_c - fr_d
        rows.append(MonthRow(label, st_c, st_d, st_running, fr_c, fr_d, fr_running))

    current_month_start = date.today().replace(day=1).strftime("%Y-%m-%d")
    st_open = count(jira, f'{PROJECT} AND issuetype != "Feature Request" AND created < "{current_month_start}" AND {not_done_clause(SUPPORT_DONE_STATUSES)}')
    fr_open = count(jira, f'{PROJECT} AND issuetype = "Feature Request" AND created < "{current_month_start}" AND {not_done_clause(FEATURE_DONE_STATUSES)}')
    return rows, st_open, fr_open


def get_fr_closed_date(issue) -> str | None:
    """Get the date an FR first moved to a done status (Resolved or Closed)."""
    if not hasattr(issue, "changelog"):
        return None
    for history in issue.changelog.histories:
        for item in history.items:
            if item.field == "status" and item.toString in FEATURE_DONE_STATUSES:
                return history.created[:10]
    return None


def get_st_closed_date(issue) -> str | None:
    """Get the date an ST first moved to a done status (Closed or Added to Product Backlog for consideration)."""
    if not hasattr(issue, "changelog"):
        return None
    for history in issue.changelog.histories:
        for item in history.items:
            if item.field == "status" and item.toString in SUPPORT_DONE_STATUSES:
                return history.created[:10]
    return None


def fetch_fr_done(jira, year: int) -> list[FRDoneDetail]:
    """Fetch Feature Requests closed YTD (excluding current month), sorted by closed date descending."""
    current_month_start = date.today().replace(day=1).strftime("%Y-%m-%d")
    ytd_start = f"{year}-01-01"
    jql = (
        f'{PROJECT} AND issuetype = "Feature Request" '
        f'AND {changed_to_clause(FEATURE_DONE_STATUSES, ytd_start, current_month_start)}'
    )
    issues = jira.search_issues(
        jql,
        maxResults=200,
        fields=["summary", "status", "created", "reporter", "customfield_10002"],
    )
    result = []
    for issue in issues:
        full = jira.issue(issue.key, expand="changelog")
        closed_date = get_fr_closed_date(full)
        started_date = get_first_in_progress_date(full)
        created = issue.fields.created[:10]
        tts, ct, lt = calculate_metrics(created, started_date, closed_date)
        orgs = getattr(issue.fields, "customfield_10002", None) or []
        org_name = orgs[0].name if orgs else "—"
        reporter = issue.fields.reporter
        reporter_name = reporter.displayName if reporter else "Unknown"
        result.append(FRDoneDetail(
            key=issue.key,
            org=org_name,
            started=started_date,
            closed=closed_date,
            reporter=reporter_name,
            status=str(issue.fields.status),
            tts=tts,
            ct=ct,
            lt=lt,
            summary=" ".join(issue.fields.summary.split()),
        ))
    result.sort(key=lambda r: r.closed or "", reverse=True)
    return result


def fetch_st_done(jira, year: int) -> list[FRDoneDetail]:
    """Fetch Support Tickets closed YTD (excluding current month), sorted by closed date descending."""
    current_month_start = date.today().replace(day=1).strftime("%Y-%m-%d")
    ytd_start = f"{year}-01-01"
    jql = (
        f'{PROJECT} AND issuetype != "Feature Request" '
        f'AND {changed_to_clause(SUPPORT_DONE_STATUSES, ytd_start, current_month_start)}'
    )
    issues = jira.search_issues(
        jql,
        maxResults=500,
        fields=["summary", "status", "created", "reporter", "customfield_10002"],
    )
    result = []
    for issue in issues:
        full = jira.issue(issue.key, expand="changelog")
        closed_date = get_st_closed_date(full)
        started_date = get_first_in_progress_date(full)
        created = issue.fields.created[:10]
        tts, ct, lt = calculate_metrics(created, started_date, closed_date)
        orgs = getattr(issue.fields, "customfield_10002", None) or []
        org_name = orgs[0].name if orgs else "—"
        reporter = issue.fields.reporter
        reporter_name = reporter.displayName if reporter else "Unknown"
        result.append(FRDoneDetail(
            key=issue.key,
            org=org_name,
            started=started_date,
            closed=closed_date,
            reporter=reporter_name,
            status=str(issue.fields.status),
            tts=tts,
            ct=ct,
            lt=lt,
            summary=" ".join(issue.fields.summary.split()),
        ))
    result.sort(key=lambda r: r.closed or "", reverse=True)
    return result


def fetch_st_details(jira, year: int) -> list[FRDetail]:
    """Fetch all open Support Tickets created YTD (excluding current month), ordered by created date ascending."""
    current_month_start = date.today().replace(day=1).strftime("%Y-%m-%d")
    jql = (
        f'{PROJECT} AND issuetype != "Feature Request" '
        f'AND created >= "{year}-01-01" '
        f'AND created < "{current_month_start}" '
        f'AND {not_done_clause(SUPPORT_DONE_STATUSES)} '
        f'ORDER BY created DESC'
    )
    issues = jira.search_issues(
        jql,
        maxResults=500,
        fields=["summary", "status", "created", "reporter", "customfield_10002"],
    )
    result = []
    for issue in issues:
        orgs = getattr(issue.fields, "customfield_10002", None) or []
        org_name = orgs[0].name if orgs else "—"
        reporter = issue.fields.reporter
        reporter_name = reporter.displayName if reporter else "Unknown"
        result.append(FRDetail(
            key=issue.key,
            org=org_name,
            created=issue.fields.created[:10],
            reporter=reporter_name,
            status=str(issue.fields.status),
            summary=issue.fields.summary,
        ))
    return result


def fetch_fr_details(jira, year: int) -> list[FRDetail]:
    """Fetch all open Feature Requests created YTD (excluding current month), ordered by created date ascending."""
    current_month_start = date.today().replace(day=1).strftime("%Y-%m-%d")
    jql = (
        f'{PROJECT} AND issuetype = "Feature Request" '
        f'AND created >= "{year}-01-01" '
        f'AND created < "{current_month_start}" '
        f'AND {not_done_clause(FEATURE_DONE_STATUSES)} '
        f'ORDER BY created DESC'
    )
    issues = jira.search_issues(
        jql,
        maxResults=200,
        fields=["summary", "status", "created", "reporter", "customfield_10002"],
    )
    result = []
    for issue in issues:
        orgs = getattr(issue.fields, "customfield_10002", None) or []
        org_name = orgs[0].name if orgs else "—"
        reporter = issue.fields.reporter
        reporter_name = reporter.displayName if reporter else "Unknown"
        result.append(FRDetail(
            key=issue.key,
            org=org_name,
            created=issue.fields.created[:10],
            reporter=reporter_name,
            status=str(issue.fields.status),
            summary=issue.fields.summary,
        ))
    return result


def fmt_net(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


def write_report(out, rows: list[MonthRow], st_open: int, fr_open: int, fr_details: list[FRDetail], fr_done: list[FRDoneDetail], st_details: list[FRDetail], st_done: list[FRDoneDetail], jira_url: str) -> None:
    n = len(rows)
    st_total_c = sum(r.st_created for r in rows)
    st_total_d = sum(r.st_closed for r in rows)
    fr_total_c = sum(r.fr_created for r in rows)
    fr_total_d = sum(r.fr_closed for r in rows)
    st_final = rows[-1].st_running if rows else 0
    fr_final = rows[-1].fr_running if rows else 0

    # --- Feature Requests ---
    out.write("### Feature Requests\n\n")
    out.write("| Month | Created | Closed | Net | Running |\n")
    out.write("|-------|--------:|-------:|----:|--------:|\n")
    for r in reversed(rows):
        out.write(f"| {r.label} | {r.fr_created} | {r.fr_closed} | {fmt_net(r.fr_net)} | {fmt_net(r.fr_running)} |\n")
    out.write(
        f"| **YTD** | **{fr_total_c}** | **{fr_total_d}** | **{fmt_net(fr_total_c - fr_total_d)}** | **{fmt_net(fr_final)}** |\n\n"
    )

    # FR narrative
    out.write(f"At the time of writing, we have **{fr_open}** outstanding feature request{'s' if fr_open != 1 else ''} in the backlog.\n\n")

    fr_close_rate = round(fr_total_d / fr_total_c * 100) if fr_total_c else 0
    out.write(
        f"{fr_total_c} feature request{'s were' if fr_total_c != 1 else ' was'} created and {fr_total_d} "
        f"{'were' if fr_total_d != 1 else 'was'} closed over {n} month{'s' if n != 1 else ''}, "
        f"a close rate of {fr_close_rate}% of incoming volume.\n\n"
    )

    if fr_final > 0:
        out.write(
            f"The running total is **+{fr_final}**, meaning the open feature request backlog has grown "
            f"by {fr_final} item{'s' if fr_final != 1 else ''} since January 1.\n\n"
        )
    elif fr_final < 0:
        out.write(
            f"The running total is **{fr_final}**, meaning {abs(fr_final)} more feature request{'s' if abs(fr_final) != 1 else ''} "
            f"{'have' if abs(fr_final) != 1 else 'has'} been closed than arrived since January 1.\n\n"
        )
    else:
        out.write("The running total is **0** — feature requests closed exactly matched arrivals.\n\n")

    # Recommendation: dynamic based on trend when backlog is still growing
    if fr_final > 0:
        improving_trend = (
            n >= 2
            and rows[-1].fr_net <= rows[-2].fr_net  # didn't get worse vs last month
            and rows[-1].fr_net < rows[0].fr_net    # overall direction is improving
        )
        if improving_trend:
            out.write(
                "**Recommendation:** Good progress — the monthly net is trending in the right direction. "
                "The backlog is still growing, but the rate is slowing. Keep this momentum going.\n\n"
            )
        else:
            out.write(
                "**Recommendation:** We are not keeping on top of feature requests. We do not necessarily need to implement "
                "every feature request, but we do as an organization need to improve our process for managing feature requests.\n\n"
            )

    # FR detail sub-section
    last_month_num = int(rows[-1].label.split("-")[1]) if rows else 0
    last_month_name = MONTH_NAMES[last_month_num] if last_month_num else ""
    added_last_month = rows[-1].fr_created if rows else 0
    total_open_ytd = len(fr_details)
    fr_closed_from_ytd = fr_total_c - total_open_ytd
    fr_closed_clause = f" ({fr_closed_from_ytd} {'have' if fr_closed_from_ytd != 1 else 'has'} been closed)" if fr_closed_from_ytd > 0 else ""

    out.write(f"#### Added to the Backlog ({added_last_month})\n\n")
    out.write(
        f"{added_last_month} new feature request{'s were' if added_last_month != 1 else ' was'} added during {last_month_name}. "
        f"The following table shows the {total_open_ytd} accumulated new feature request{'s' if total_open_ytd != 1 else ''} YTD "
        f"that are still outstanding{fr_closed_clause} and their current status.\n\n"
    )
    out.write("| Key | Org | Created | Reporter | Status | Summary |\n")
    out.write("|-----|-----|---------|----------|--------|---------|\n")
    for fr in fr_details:
        key_link = f"[{fr.key}]({jira_url}/servicedesk/customer/portal/1/{fr.key})"
        out.write(f"| {key_link} | {fr.org} | {fr.created} | {fr.reporter} | {fr.status} | {fr.summary} |\n")
    out.write("\n")

    # FR Done sub-section
    closed_last_month = rows[-1].fr_closed if rows else 0
    out.write(f"#### Done ({closed_last_month})\n\n")
    out.write(
        f"{closed_last_month} feature request{'s were' if closed_last_month != 1 else ' was'} closed during {last_month_name}. "
        f"The following table shows the {len(fr_done)} feature request{'s' if len(fr_done) != 1 else ''} "
        f"that {'have' if len(fr_done) != 1 else 'has'} been closed YTD.\n\n"
    )
    out.write("*TTS = Time to Start: Created to first In Progress (days)*  \n")
    out.write("*CT = Cycle Time: Started to Closed (days)*  \n")
    out.write("*LT = Lead Time: Created to Closed (days)*\n\n")
    out.write("| Key | Org | Started | Closed | Status | Reporter | TTS | CT | LT | Summary |\n")
    out.write("|-----|-----|---------|--------|--------|----------|----:|---:|---:|---------|\n")
    for fr in fr_done:
        key_link = f"[{fr.key}]({jira_url}/servicedesk/customer/portal/1/{fr.key})"
        started = fr.started or "N/A"
        closed = fr.closed or "N/A"
        tts = str(fr.tts) if fr.tts is not None else "N/A"
        ct = str(fr.ct) if fr.ct is not None else "N/A"
        lt = str(fr.lt) if fr.lt is not None else "N/A"
        out.write(f"| {key_link} | {fr.org} | {started} | {closed} | {fr.status} | {fr.reporter} | {tts} | {ct} | {lt} | {fr.summary} |\n")
    out.write("\n")

    # --- Support Tickets ---
    out.write("### Support Tickets\n\n")
    out.write("| Month | Created | Closed | Net | Running |\n")
    out.write("|-------|--------:|-------:|----:|--------:|\n")
    for r in reversed(rows):
        out.write(f"| {r.label} | {r.st_created} | {r.st_closed} | {fmt_net(r.st_net)} | {fmt_net(r.st_running)} |\n")
    out.write(
        f"| **YTD** | **{st_total_c}** | **{st_total_d}** | **{fmt_net(st_total_c - st_total_d)}** | **{fmt_net(st_final)}** |\n\n"
    )

    # ST narrative
    out.write(f"At the time of writing, we have **{st_open}** outstanding support ticket{'s' if st_open != 1 else ''} in the backlog.\n\n")

    close_rate = round(st_total_d / st_total_c * 100) if st_total_c else 0
    out.write(
        f"{st_total_c} support ticket{'s were' if st_total_c != 1 else ' was'} created and {st_total_d} "
        f"{'were' if st_total_d != 1 else 'was'} closed over {n} month{'s' if n != 1 else ''}, "
        f"a close rate of {close_rate}% of incoming volume.\n\n"
    )

    if st_final > 0:
        out.write(
            f"The running total is **+{st_final}**, meaning the open support backlog has grown "
            f"by {st_final} ticket{'s' if st_final != 1 else ''} since January 1. "
            "The team is not yet keeping pace with incoming volume.\n\n"
        )
    elif st_final < 0:
        out.write(
            f"The running total is **{st_final}**, meaning the team has closed {abs(st_final)} more "
            f"support ticket{'s' if abs(st_final) != 1 else ''} than arrived since January 1. "
            "The team is making progress against the backlog.\n\n"
        )
    else:
        out.write(
            "The running total is **0** — the team has closed exactly as many support tickets as arrived. "
            "The backlog is holding steady.\n\n"
        )

    # ST detail sub-section
    added_last_month = rows[-1].st_created if rows else 0
    total_open_ytd = len(st_details)
    st_closed_from_ytd = st_total_c - total_open_ytd
    closed_clause = f" ({st_closed_from_ytd} {'have' if st_closed_from_ytd != 1 else 'has'} been closed)" if st_closed_from_ytd > 0 else ""

    out.write(f"#### Added to the Backlog ({added_last_month})\n\n")
    out.write(
        f"{added_last_month} new support ticket{'s were' if added_last_month != 1 else ' was'} added during {last_month_name}. "
        f"The following table shows the {total_open_ytd} accumulated new support ticket{'s' if total_open_ytd != 1 else ''} YTD "
        f"that are still outstanding{closed_clause} and their current status.\n\n"
    )
    out.write("| Key | Org | Created | Reporter | Status | Summary |\n")
    out.write("|-----|-----|---------|----------|--------|---------|\n")
    for st in st_details:
        key_link = f"[{st.key}]({jira_url}/servicedesk/customer/portal/1/{st.key})"
        out.write(f"| {key_link} | {st.org} | {st.created} | {st.reporter} | {st.status} | {st.summary} |\n")
    out.write("\n")

    # ST Done sub-section
    closed_last_month = rows[-1].st_closed if rows else 0
    out.write(f"#### Done ({closed_last_month})\n\n")
    out.write(
        f"{closed_last_month} support ticket{'s were' if closed_last_month != 1 else ' was'} closed during {last_month_name}. "
        f"The following table shows the {len(st_done)} support ticket{'s' if len(st_done) != 1 else ''} "
        f"that {'have' if len(st_done) != 1 else 'has'} been closed YTD.\n\n"
    )
    out.write("*TTS = Time to Start: Created to first In Progress (days)*  \n")
    out.write("*CT = Cycle Time: Started to Closed (days)*  \n")
    out.write("*LT = Lead Time: Created to Closed (days)*\n\n")
    out.write("| Key | Org | Started | Closed | Status | Reporter | TTS | CT | LT | Summary |\n")
    out.write("|-----|-----|---------|--------|--------|----------|----:|---:|---:|---------|\n")
    for st in st_done:
        key_link = f"[{st.key}]({jira_url}/servicedesk/customer/portal/1/{st.key})"
        started = st.started or "N/A"
        closed = st.closed or "N/A"
        tts = str(st.tts) if st.tts is not None else "N/A"
        ct = str(st.ct) if st.ct is not None else "N/A"
        lt = str(st.lt) if st.lt is not None else "N/A"
        out.write(f"| {key_link} | {st.org} | {started} | {closed} | {st.status} | {st.reporter} | {tts} | {ct} | {lt} | {st.summary} |\n")


def main() -> None:
    jira = get_jira_client()

    today = date.today()
    year = today.year
    months = months_ytd(year)

    print(f"Fetching data for {len(months)} month(s)...", flush=True)
    rows, st_open, fr_open = fetch_data(jira, months)

    print("Fetching feature request details...", flush=True)
    fr_details = fetch_fr_details(jira, year)

    print("Fetching closed feature request details...", flush=True)
    fr_done = fetch_fr_done(jira, year)

    print("Fetching support ticket details...", flush=True)
    st_details = fetch_st_details(jira, year)

    print("Fetching closed support ticket details...", flush=True)
    st_done = fetch_st_done(jira, year)

    jira_url = os.getenv("JIRA_URL", "").rstrip("/")

    last_month = rows[-1].label if rows else f"{year}-??"
    filename = f"monthly_report_{last_month}.md"

    with open(filename, "w") as f:
        write_report(f, rows, st_open, fr_open, fr_details, fr_done, st_details, st_done, jira_url)

    print(f"Report saved to: {filename}")


if __name__ == "__main__":
    main()
