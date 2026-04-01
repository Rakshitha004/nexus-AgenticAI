from Intent_Agent3.registry import dispatcher
from Intent_Agent3.llm_agent import LLMAgent
from Intent_Agent3.student_agent import StudentAgent
from Intent_Agent3.router_agent import RouterAgent
from Intent_Agent3.intent_agent import HierarchicalIntentAgent
from table_agent.agent import TableAgent
from column_pruning_agent.agent import ColumnPruningAgent


def init_agents():
    """Register all agents with the dispatcher and ensure they are enabled."""
    agents = [
        LLMAgent(),
        StudentAgent(),
        TableAgent(),
        HierarchicalIntentAgent(),
        RouterAgent(),
        ColumnPruningAgent()
    ]
    for agent in agents:
        agent.enabled = True
        dispatcher.register(agent)
