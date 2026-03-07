"""Communication module: message-passing, blackboard, and hybrid modes."""

from .message_passing import MessagePassingCommunication
from .blackboard_comm import BlackboardCommunication
from .hybrid_comm import HybridCommunication

__all__ = [
    "MessagePassingCommunication",
    "BlackboardCommunication",
    "HybridCommunication",
]
