import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from database import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feedback"])

class FeedbackCreate(BaseModel):
    message_id: str
    agent_id: str
    workspace_id: str
    vote_type: str
    category: Optional[str] = None
    comment_text: Optional[str] = None
    created_by: Optional[str] = None

class FeedbackResolve(BaseModel):
    resolved_by: str

@router.post("/api/feedback")
async def submit_feedback(payload: FeedbackCreate):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO message_feedback 
            (message_id, agent_id, workspace_id, vote_type, category, comment_text, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                payload.message_id, 
                payload.agent_id, 
                payload.workspace_id, 
                payload.vote_type, 
                payload.category, 
                payload.comment_text, 
                payload.created_by
            )
        )
        feedback_id = cursor.fetchone()[0]
        conn.commit()
        
        return {"id": feedback_id, "message": "Feedback submitted successfully"}
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.get("/api/feedback/open")
async def get_open_feedback(workspace_id: str = Query(...), user_id: str = Query(...)):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Auth Gate: Check if user is teammate or admin
        cursor.execute(
            "SELECT role FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
            (workspace_id, user_id)
        )
        user_role = cursor.fetchone()
        if not user_role or user_role[0] not in ['admin', 'teammate']:
            raise HTTPException(status_code=403, detail="Not authorized to view feedback dashboard")

        cursor.execute(
            """
            SELECT f.id, f.message_id, f.agent_id, f.vote_type, f.category, 
                   f.comment_text, f.created_at, f.created_by,
                   m.content as message_content, m.role,
                   a.name as agent_name
            FROM message_feedback f
            LEFT JOIN chat_messages m ON f.message_id = m.id
            LEFT JOIN agents a ON f.agent_id = a.id
            WHERE f.workspace_id = %s AND f.status = 'open'
            ORDER BY f.created_at DESC;
            """,
            (workspace_id,)
        )
        rows = cursor.fetchall()
        
        tickets = []
        for row in rows:
            tickets.append({
                "id": row[0],
                "message_id": row[1],
                "agent_id": row[2],
                "vote_type": row[3],
                "category": row[4],
                "comment_text": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "created_by": row[7],
                "message_content": row[8],
                "role": row[9],
                "agent_name": row[10]
            })
            
        return tickets
    except HTTPException:
        if conn: conn.rollback()
        raise
    except Exception as e:
        logger.error(f"Error fetching open feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch open feedback")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@router.post("/api/feedback/{feedback_id}/resolve")
async def resolve_feedback(feedback_id: str, payload: FeedbackResolve):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get workspace_id for the feedback to check permissions
        cursor.execute("SELECT workspace_id FROM message_feedback WHERE id = %s", (feedback_id,))
        feedback_row = cursor.fetchone()
        if not feedback_row:
            raise HTTPException(status_code=404, detail="Feedback ticket not found")
        workspace_id = feedback_row[0]

        # Auth Gate: Check if user is teammate or admin
        cursor.execute(
            "SELECT role FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
            (workspace_id, payload.resolved_by)
        )
        user_role = cursor.fetchone()
        if not user_role or user_role[0] not in ['admin', 'teammate']:
            raise HTTPException(status_code=403, detail="Not authorized to resolve feedback")

        cursor.execute(
            """
            UPDATE message_feedback
            SET status = 'resolved', resolved_at = now(), resolved_by = %s
            WHERE id = %s
            RETURNING id;
            """,
            (payload.resolved_by, feedback_id)
        )
        row = cursor.fetchone()
        conn.commit()
        
        return {"message": "Feedback resolved successfully"}
    except HTTPException:
        if conn: conn.rollback()
        raise
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error resolving feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve feedback")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
