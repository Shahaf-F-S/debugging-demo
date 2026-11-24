"""Stands in for a push-notification service (DESIGN.md §8): messages are kept in memory."""


class Notifier:
    def __init__(self) -> None:
        self.outbox: list[tuple[int, str]] = []         # (user id, text), in the order sent

    def push(self, user_id: int, text: str) -> None:
        self.outbox.append((user_id, text))

    def messages_for(self, user_id: int) -> list[str]:
        return [text for recipient, text in self.outbox if recipient == user_id]
