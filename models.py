import asyncio
import enum
import time
from dataclasses import dataclass, field
from typing import Optional, Set

class AgentState(enum.Enum):
    OFFLINE = 0
    AVAILABLE = 1
    RESERVED = 2
    DIALING = 3
    CONNECTED = 4
    WRAP_UP = 5
    PAUSED = 6

class CallState(enum.Enum):
    QUEUED = 1
    RESERVED = 2
    INITIATED = 3
    RINGING = 4
    ANSWERED = 5
    CONNECTED = 6
    COMPLETED = 7
    FAILED = 8
    CANCELLED = 9

@dataclass
class Agent:
    id: str
    state: AgentState = AgentState.AVAILABLE
    version: int = 0
    assigned_call: Optional[str] = None
    last_updated: float = field(default_factory=time.time)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

@dataclass
class Call:
    id: str
    borrower_phone: str
    state: CallState = CallState.QUEUED
    events_seen: Set[str] = field(default_factory=set)
    agent_id: Optional[str] = None
    abandoned: bool = False
    timestamp: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)