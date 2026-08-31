from typing import Dict, List, Optional
import time
import os
from models import Agent, Call, AgentState, CallState

class DataStore:
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.calls: Dict[str, Call] = {}

    async def get_available_agents(self) -> List[Agent]:
        return [a for a in self.agents.values() if a.state == AgentState.AVAILABLE]

    async def try_reserve_agent(self, agent_id: str, expected_version: int) -> bool:
        """Atomic Compare-And-Swap (CAS) execution."""
        agent = self.agents.get(agent_id)
        if not agent: return False
        
        async with agent.lock:
            if agent.state == AgentState.AVAILABLE and agent.version == expected_version:
                agent.state = AgentState.RESERVED
                agent.version += 1
                agent.last_updated = time.time()
                return True
            return False

    async def transition_agent(self, agent_id: str, state: AgentState, call_id: Optional[str] = None):
        agent = self.agents.get(agent_id)
        if not agent: return
        async with agent.lock:
            agent.state = state
            agent.assigned_call = call_id
            agent.version += 1
            agent.last_updated = time.time()

    def update_call_state(self, call_id: str, state: CallState, event_id: str) -> bool:
        """Idempotent and Monotonic call state updates."""
        call = self.calls.get(call_id)
        if not call: return False

        if event_id in call.events_seen:
            return False 
        
        terminal_states = {CallState.COMPLETED, CallState.FAILED, CallState.CANCELLED}
        if call.state in terminal_states:
            return False 
            
        if state.value <= call.state.value and state not in terminal_states:
            return False 

        call.state = state
        call.events_seen.add(event_id)
        call.last_updated = time.time()
        return True

class StaleSweeper:
    def __init__(self, store: DataStore, timeout_sec: float = None):
        self.store = store
        self.timeout_sec = timeout_sec if timeout_sec is not None else float(os.getenv("SWEEPER_TIMEOUT_SEC", "10.0"))

    async def sweep(self) -> int:
        recovered = 0
        now = time.time()
        for agent_id, agent in list(self.store.agents.items()):
            if agent.state in {AgentState.RESERVED, AgentState.CONNECTED}:
                if now - agent.last_updated > self.timeout_sec:
                    # Force reset agent
                    if agent.assigned_call:
                        call = self.store.calls.get(agent.assigned_call)
                        if call and call.state not in {CallState.COMPLETED, CallState.FAILED, CallState.CANCELLED}:
                            call.state = CallState.FAILED
                            call.last_updated = now
                    
                    await self.store.transition_agent(agent.id, AgentState.AVAILABLE, None)
                    recovered += 1
        return recovered

class PredictivePacing:
    def get_dials(self, available_agents: int, active_ringing: int, hit_rate: float = None) -> int:
        if hit_rate is None:
            hit_rate = float(os.getenv("PREDICTIVE_HIT_RATE", "0.5"))
        if available_agents == 0: return 0
        target = int(available_agents / max(0.1, hit_rate))
        return max(0, target - active_ringing)

class SafetyController:
    def __init__(self, max_abandon_rate: float = None):
        self.max_abandon_rate = max_abandon_rate if max_abandon_rate is not None else float(os.getenv("MAX_ABANDON_RATE", "0.05"))
        self.abandoned = 0
        self.connected = 0
        self.provider_failures = 0

    def evaluate(self, requested_dials: int, available_agents: int, is_predictive: bool) -> int:
        total = self.abandoned + self.connected
        abandon_rate = (self.abandoned / total) if total > 0 else 0.0

        if self.provider_failures > 10:
            return 0 

        if is_predictive and abandon_rate > self.max_abandon_rate:
            return min(requested_dials, available_agents)

        if not is_predictive:
            return min(requested_dials, available_agents)

        return min(requested_dials, available_agents * 3)