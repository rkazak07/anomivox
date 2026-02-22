from fastapi import Body
from configs import logger, log_verbose
from server.utils import BaseResponse
from server.db.repository import feedback_message_to_db

def chat_feedback(message_id: str = Body("", max_length=32, description="Chat record ID"),
            score: int = Body(0, max=100, description="User rating, max 100, higher means better evaluation"),
            reason: str = Body("", description="User rating reason, e.g. not factual")
            ):
    try:
        feedback_message_to_db(message_id, score, reason)
    except Exception as e:
        msg = f"Error submitting chat record feedback: {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)

    return BaseResponse(code=200, msg=f"Chat record {message_id} feedback submitted")
