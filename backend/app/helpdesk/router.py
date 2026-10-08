from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.models.user import User
from backend.app.ai.helpdesk_service import answer_helpdesk_question
from backend.app.db.database import get_db
from backend.app.helpdesk.schemas import HelpdeskChatRequest, HelpdeskChatResponse


router = APIRouter(
    prefix="/helpdesk",
    tags=["Helpdesk"],
)

@router.post(
    "/chat",
    response_model=HelpdeskChatResponse,
)
def chat(
    request: HelpdeskChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
): 
    return answer_helpdesk_question(
        db,
        request.question,
    )