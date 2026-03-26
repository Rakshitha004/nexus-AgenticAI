from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from API_Integrations.db.setup import get_db
from Intent_Agent3.registry import MessageDispatcher
from Intent_Agent3.base import Message

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/stream")
async def stream_response(session_id: int, text: str):
    """Stream LLM response token by token."""
    agent = dispatcher.get("llm_agent")

    async def event_generator():
        async for token in agent.stream(text):
            yield token

    return StreamingResponse(event_generator(), media_type="text/plain")


@router.post("/session")
def create_session(conn=Depends(get_db)):
    """Create a new chat session and return its ID."""
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO ChatSessions (user_id, title)
    OUTPUT INSERTED.id
    VALUES (?, ?)
    """, 1, "New Chat Session")

    session_id = cursor.fetchone()[0]

    conn.commit()

    return {"session_id": session_id}


@router.post("/send")
async def send_message(session_id: int, text: str, conn=Depends(get_db)):
    """Process user message through the agent pipeline and save to DB."""
    cursor = conn.cursor()

    # store user message
    cursor.execute("""
    INSERT INTO ChatMessages (session_id, role, text)
    VALUES (?, ?, ?)
    """, session_id, "user", text)

    conn.commit()

    # get conversation history for context
    cursor.execute("""
    SELECT role, text
    FROM ChatMessages
    WHERE session_id = ?
    ORDER BY timestamp
    """, session_id)

    rows = cursor.fetchall()

    # send to router agent (intent → domain agent / LLM)
    response = await dispatcher.dispatch(
        Message(sender="user", text=text),
        "router_agent"
    )

    # save agent response
    cursor.execute("""
    INSERT INTO ChatMessages (session_id, role, sender_agent, text)
    VALUES (?, ?, ?, ?)
    """, session_id, "agent", response.sender, response.text)

    conn.commit()

    return {"response": response.text, "sender": response.sender}


@router.get("/history/{session_id}")
def get_history(session_id: int, conn=Depends(get_db)):
    """Retrieve full chat history for a given session."""
    cursor = conn.cursor()

    cursor.execute("""
    SELECT role, sender_agent, text, timestamp
    FROM ChatMessages
    WHERE session_id = ?
    ORDER BY timestamp
    """, session_id)

    rows = cursor.fetchall()

    messages = []

    for r in rows:
        messages.append({
            "role": r[0],
            "sender_agent": r[1],
            "text": r[2],
            "timestamp": str(r[3])
        })

    return messages


@router.get("/sessions")
def list_sessions(conn=Depends(get_db)):
    """List all chat sessions."""
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, user_id, title, created_at
    FROM ChatSessions
    ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()

    sessions = []

    for r in rows:
        sessions.append({
            "id": r[0],
            "user_id": r[1],
            "title": r[2],
            "created_at": str(r[3])
        })

    return sessions
