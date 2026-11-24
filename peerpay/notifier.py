"""Stands in for a push-notification service (DESIGN.md §8): messages are kept in memory."""


class Notifier:
    def __init__(self):
        self.outbox = []                # (user_id, text), in the order sent

    def push(self, user_id, text):
        self.outbox.append((user_id, text))

    def messages_for(self, user_id):
        return [text for uid, text in self.outbox if uid == user_id]
