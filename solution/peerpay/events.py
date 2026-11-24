"""Publish/subscribe, and the notifier that turns events into push messages (DESIGN.md §11)."""

import functools
from collections.abc import Callable
from typing import Literal

from .models import Transfer

type EventKind = Literal["sent", "accepted", "declined", "cancelled", "expired"]
type Handler = Callable[[Transfer], None]

TEMPLATES: dict[EventKind, str] = {
    "sent": "You received {amount} (transfer #{id}). Accept it within 30 days.",
    "accepted": "Your transfer #{id} of {amount} was accepted.",
    "declined": "Your transfer #{id} of {amount} was declined. The money is back in your wallet.",
    "cancelled": "Transfer #{id} of {amount} was cancelled by the sender.",
    "expired": "Your transfer #{id} of {amount} expired. The money is back in your wallet."
}
NOTIFY_RECIPIENT: frozenset[EventKind] = frozenset(("sent", "cancelled"))   # others: the sender


class EventBus:
    """Delivers every published transfer event to the handlers subscribed to its kind."""

    def __init__(self) -> None:
        self._handlers: dict[EventKind, list[Handler]] = {}

    def subscribe(self, kind: EventKind, handler: Handler) -> None:
        self._handlers.setdefault(kind, []).append(handler)

    def publish(self, kind: EventKind, transfer: Transfer) -> None:
        for handler in self._handlers.get(kind, []):
            handler(transfer)


class Notifier:
    """Stands in for a push-notification service: the messages it sends are kept in memory."""

    def __init__(self) -> None:
        self.outbox: list[tuple[int, str]] = []         # (user id, text), in the order sent

    def push(self, kind: EventKind, transfer: Transfer) -> None:
        user_id = transfer.recipient_id if kind in NOTIFY_RECIPIENT else transfer.sender_id
        text = TEMPLATES[kind].format(id=transfer.id, amount=transfer.amount)
        self.outbox.append((user_id, text))

    def messages_for(self, user_id: int) -> list[str]:
        return [text for recipient, text in self.outbox if recipient == user_id]


def wire_notifications(bus: EventBus, notifier: Notifier) -> None:
    """Subscribes the notifier to every kind of event, each with its own template (bug S1)."""

    for kind in TEMPLATES:
        # partial binds the current value of kind; a lambda would see only its last value
        bus.subscribe(kind, functools.partial(notifier.push, kind))
