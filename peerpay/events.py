"""A tiny publish/subscribe bus, and the notifier that sends push messages (DESIGN.md §11)."""

from .money import format_amount

TEMPLATES = {
    "sent": "You received {amount} (transfer #{id}). Accept it within 30 days.",
    "accepted": "Your transfer #{id} of {amount} was accepted.",
    "declined": "Your transfer #{id} of {amount} was declined. The money is back in your wallet.",
    "cancelled": "Transfer #{id} of {amount} was cancelled by the sender.",
    "expired": "Your transfer #{id} of {amount} expired. The money is back in your wallet."
}
NOTIFY_RECIPIENT = {"sent", "cancelled"}        # every other kind notifies the sender


class EventBus:
    def __init__(self):
        self._handlers = {}

    def subscribe(self, kind, handler):
        self._handlers.setdefault(kind, []).append(handler)

    def publish(self, kind, payload):
        for handler in self._handlers.get(kind, []):
            handler(payload)


class Notifier:
    """Stands in for a push-notification service: messages are kept in memory."""

    def __init__(self):
        self.outbox = []                         # (user_id, text)

    def push(self, kind, transfer):
        user_id = transfer.recipient_id if kind in NOTIFY_RECIPIENT else transfer.sender_id
        text = TEMPLATES[kind].format(id=transfer.id, amount=format_amount(transfer.amount))
        self.outbox.append((user_id, text))

    def messages_for(self, user_id):
        return [text for uid, text in self.outbox if uid == user_id]


def wire_notifications(bus, notifier):
    for kind in TEMPLATES:
        bus.subscribe(kind, lambda transfer: notifier.push(kind, transfer))
