from fastapi import APIRouter
from Intent_Agent3.registry import MessageDispatcher

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/")
def list_agents():
    """List all registered agents with their enabled status."""
    agents = []

    for name, agent in MessageDispatcher.agents.items():
        agents.append({
            "name": name,
            "enabled": agent.enabled
        })

    return agents


@router.post("/disable/{agent_name}")
def disable_agent(agent_name: str):
    """Disable a specific agent by name."""
    agent = MessageDispatcher.get(agent_name)

    if not agent:
        return {"error": "Agent not found"}

    agent.enabled = False

    return {"status": f"{agent_name} disabled"}


@router.post("/enable/{agent_name}")
def enable_agent(agent_name: str):
    """Enable a specific agent by name."""
    agent = MessageDispatcher.get(agent_name)

    if not agent:
        return {"error": "Agent not found"}

    agent.enabled = True

    return {"status": f"{agent_name} enabled"}
