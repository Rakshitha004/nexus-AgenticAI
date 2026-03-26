from abc import ABC, abstractmethod


class Message:
    def __init__(self, sender: str, text: str, metadata: dict = None):
        self.sender = sender
        self.text = text
        self.metadata = metadata or {}


class BaseAgent(ABC):

    def __init__(self, name: str):
        self.name = name
        self.enabled = True

    @abstractmethod
    async def handle_message(self, message: Message) -> Message:
        pass
