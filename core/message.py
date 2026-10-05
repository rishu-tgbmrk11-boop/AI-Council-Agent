# core/message.py
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class Message:
    sender: str
    content: str
    role: str = "agent"              # agent | user | system
    message_type: str = "thought"    # goal | thought | proposal | critique | final
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __repr__(self):
        return f"[{self.sender}] ({self.message_type}): {self.content}"