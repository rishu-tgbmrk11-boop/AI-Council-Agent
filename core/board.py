# core/board.py
from typing import List, Callable, Optional
from core.message import Message


class MessageBoard:
    def __init__(self, on_message: Optional[Callable[[Message], None]] = None):
        self.messages: List[Message] = []
        self._speaker_counts: dict = {}
        self.on_message = on_message

    def post(self, message: Message):
        self.messages.append(message)
        self._speaker_counts[message.sender] = self._speaker_counts.get(message.sender, 0) + 1
        print(f"📢 [{message.sender}] posted a {message.message_type}.")
        if self.on_message:
            self.on_message(message)

    def get_all(self) -> List[Message]:
        return self.messages

    def get_recent(self, n: int = 10) -> List[Message]:
        return self.messages[-n:]

    def get_context_string(self, n: int = 10) -> str:
        recent = self.get_recent(n)
        return "\n".join(f"[{m.sender}] ({m.message_type}): {m.content}" for m in recent)

    def get_speaker_count(self, speaker: str) -> int:
        return self._speaker_counts.get(speaker, 0)

    def length(self) -> int:
        return len(self.messages)