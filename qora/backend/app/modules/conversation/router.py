"""Conversation router — API_CONTRACT §4."""
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.conversation.schemas import ConversationOut, MessageIn, MessageOut, RecoveryIn
from app.modules.conversation.service import ConversationService
from app.modules.analytics.tasks import aggregate_service_day
from app.shared.deps import get_current_user

router = APIRouter(prefix="/conversations", tags=["conversation"])


@router.get("", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return ConversationService.list_for(db, user.id)


@router.post("", response_model=ConversationOut, status_code=201)
def create_conversation(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return ConversationService.create(db, user.id)


@router.get("/{conversation_id}")
def get_conversation(conversation_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    conv = ConversationService.get(db, user.id, conversation_id)
    return {
        "conversation": ConversationOut.model_validate(conv).model_dump(),
        "messages": [MessageOut.model_validate(m).model_dump() for m in ConversationService.messages(db, conv.id)],
    }


@router.post("/{conversation_id}/messages")
def send_message(
    conversation_id: int,
    data: MessageIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    result = ConversationService.send_message(db, user.id, conversation_id, data.content)
    service_id = (result.get("service_match") or {}).get("chosen_service_id")
    if service_id and (result.get("service_response") or {}).get("session_id"):
        background_tasks.add_task(aggregate_service_day, service_id)
    return result


@router.post("/{conversation_id}/recovery")
def recover(conversation_id: int, data: RecoveryIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return ConversationService.recover(db, user.id, conversation_id, data.option)


@router.get("/{conversation_id}/trace/{trace_id}")
def get_trace(conversation_id: int, trace_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.shared.errors import NOT_FOUND, AppError

    ConversationService.get(db, user.id, conversation_id)
    for t in ConversationService.traces(db, conversation_id):
        if t.id == trace_id:
            return {
                "trace_id": t.id,
                "intent": {"slug": t.intent_slug, "confidence": t.intent_confidence, "entities": t.entities},
                "candidate_services": t.candidate_services,
                "chosen_service_id": t.chosen_service_id,
                "chosen_service_version_id": t.chosen_service_version_id,
                "context_shared": t.context_shared,
                "permission_needed": t.permission_needed,
                "session_id": t.session_id,
                "outcome_status": t.outcome_status,
                "started_at": t.started_at,
                "finished_at": t.finished_at,
            }
    raise AppError(NOT_FOUND, "Trace not found", 404)
