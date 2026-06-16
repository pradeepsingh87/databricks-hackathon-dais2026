"""Inline Genie chat — send a question, get an answer, render in the app.

Wraps the Databricks Genie API:
  - POST /api/2.0/genie/spaces/{space_id}/start-conversation
  - POST /api/2.0/genie/spaces/{space_id}/conversations/{conv_id}/messages
  - GET  /api/2.0/genie/spaces/{space_id}/.../attachments/{attachment_id}/query-result

A Genie response carries up to three useful artefacts per message:
  - text       — natural-language answer
  - query      — generated SQL + statement_id to re-execute it
  - suggestions — follow-up questions Genie thinks the user will ask next

We surface text + the result of executing the SQL (as a DataFrame) so the
app can render the answer alongside an actual chart/table without sending
the user out to a separate Genie tab.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import pandas as pd
import requests

_API_VERSION = "2.0"
_TIMEOUT = 30           # per HTTP request
_POLL_DEADLINE = 120    # seconds we'll wait for a message to COMPLETE
_POLL_INTERVAL = 2.0    # how often to re-check status


def _host() -> str:
    return os.environ.get("DATABRICKS_HOST", "").rstrip("/")


def _token() -> str:
    return os.environ.get("DATABRICKS_TOKEN", "")


def is_configured() -> bool:
    return bool(_host() and _token() and os.environ.get("GENIE_SPACE_ID"))


def space_id() -> str:
    return os.environ.get("GENIE_SPACE_ID", "")


def _headers() -> dict:
    return {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}


@dataclass
class GenieAnswer:
    text: str
    sql: str | None
    sql_description: str | None
    statement_id: str | None
    rows: pd.DataFrame
    follow_ups: list[str]
    conversation_id: str
    message_id: str


def _extract(message: dict, conversation_id: str) -> GenieAnswer:
    text_parts: list[str] = []
    sql, sql_desc, statement_id = None, None, None
    follow_ups: list[str] = []
    for att in message.get("attachments") or []:
        if att.get("text", {}).get("content"):
            text_parts.append(att["text"]["content"])
        if att.get("query"):
            q = att["query"]
            sql = q.get("query")
            sql_desc = q.get("description")
            statement_id = q.get("statement_id")
        if att.get("suggested_questions"):
            follow_ups.extend(att["suggested_questions"].get("questions", []) or [])
    return GenieAnswer(
        text="\n\n".join(text_parts).strip(),
        sql=sql, sql_description=sql_desc, statement_id=statement_id,
        rows=pd.DataFrame(),     # filled in by the caller after fetch_rows()
        follow_ups=follow_ups,
        conversation_id=conversation_id,
        message_id=message.get("message_id") or message.get("id") or "",
    )


def _post(path: str, body: dict) -> dict:
    r = requests.post(
        f"{_host()}/api/{_API_VERSION}{path}",
        headers=_headers(), json=body, timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def _get(path: str) -> dict:
    r = requests.get(
        f"{_host()}/api/{_API_VERSION}{path}",
        headers=_headers(), timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def _poll_until_complete(sid: str, conversation_id: str, message_id: str) -> dict:
    """Poll the message until it reaches a terminal state.

    Genie's REST API returns immediately with status=SUBMITTED; the answer
    (text + SQL + suggestions) lands on the message resource asynchronously.
    The CLI's --no-wait=false hides this polling under the covers, but for an
    inline UX we need to do it ourselves so the page can render the answer
    when it's actually ready.
    """
    deadline = time.monotonic() + _POLL_DEADLINE
    last: dict = {}
    while time.monotonic() < deadline:
        last = _get(f"/genie/spaces/{sid}/conversations/{conversation_id}"
                    f"/messages/{message_id}")
        status = (last.get("status") or "").upper()
        if status in {"COMPLETED", "FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"}:
            return last
        time.sleep(_POLL_INTERVAL)
    return last  # timeout — return whatever we last saw


def ask(question: str, conversation_id: str | None = None) -> GenieAnswer | None:
    """Send a question and wait for the answer.

    If conversation_id is None, a new conversation is started; otherwise the
    question is appended to the existing one (Genie carries context across
    messages within a conversation).
    """
    if not is_configured():
        return None
    sid = space_id()
    if conversation_id:
        resp = _post(
            f"/genie/spaces/{sid}/conversations/{conversation_id}/messages",
            {"content": question},
        )
    else:
        resp = _post(f"/genie/spaces/{sid}/start-conversation",
                     {"content": question})
        conversation_id = resp.get("conversation_id", "")

    # The POST returns a stub message with status=SUBMITTED. Poll the message
    # resource until the LLM finishes and attachments arrive.
    message_id = (
        resp.get("message_id")
        or (resp.get("message") or {}).get("id")
        or (resp.get("message") or {}).get("message_id")
    )
    if not message_id:
        return _extract(resp, conversation_id)

    completed = _poll_until_complete(sid, conversation_id, message_id)
    return _extract(completed, conversation_id)


def fetch_rows(answer: GenieAnswer, limit: int = 1000) -> pd.DataFrame:
    """Run the SQL Genie generated and return rows as a DataFrame.

    We could re-fetch via the statement_id, but cheaper + portable is to
    re-run the SQL via the SQL Statements API on our existing warehouse —
    that means we don't depend on Genie keeping the result hot.
    """
    from .sql_client import query_df

    if not answer.sql:
        return pd.DataFrame()
    return query_df(f"SELECT * FROM ({answer.sql}) LIMIT {int(limit)}")
