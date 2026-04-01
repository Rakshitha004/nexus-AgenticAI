from typing import Dict
from Intent_Agent3.base import BaseAgent, Message


class MessageDispatcher:

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent):
        self.agents[agent.name] = agent

    def get(self, name: str):
        return self.agents.get(name)

    async def dispatch(self, message: Message, target_agent: str):
        agent = self.get(target_agent)

        if not agent:
            raise ValueError(f"Agent {target_agent} not found")

        # Self-healing: Always enable the agent if it's currently disabled
        if not agent.enabled:
            print(f"Self-healing: Auto-enabling {target_agent}")
            agent.enabled = True

        return await agent.handle_message(message)


dispatcher = MessageDispatcher()
