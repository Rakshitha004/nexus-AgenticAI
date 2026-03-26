import json


def log_agent_event(conn, agent_name, action, details):
    """Log agent events to the AgentEvents table for auditing."""
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO AgentEvents (agent_name, action, details_json)
    VALUES (?, ?, ?)
    """,
    agent_name,
    action,
    json.dumps(details)
    )

    conn.commit()
