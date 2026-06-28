"""Databricks Genie endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import GenieAnswerResponse, GenieAskRequest
from app.core.serialization import records_from_df
from app.services import genie

router = APIRouter(prefix="/api/genie", tags=["genie"])


@router.get("/status")
def genie_status() -> dict[str, bool | str]:
    return {"configured": genie.is_configured(), "space_id": genie.space_id()}


@router.post("/ask", response_model=GenieAnswerResponse)
def ask_genie(payload: GenieAskRequest) -> GenieAnswerResponse:
    answer = genie.ask(payload.question, payload.conversation_id)
    if answer is None:
        raise HTTPException(status_code=503, detail="Genie is not configured")
    rows = genie.fetch_rows(answer)
    return GenieAnswerResponse(
        text=answer.text,
        sql=answer.sql,
        sql_description=answer.sql_description,
        statement_id=answer.statement_id,
        rows=records_from_df(rows),
        follow_ups=answer.follow_ups,
        conversation_id=answer.conversation_id,
        message_id=answer.message_id,
    )
