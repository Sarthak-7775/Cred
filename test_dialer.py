import pytest
import asyncio
from models import Agent, Call, AgentState, CallState
from engine import DataStore, PredictivePacing, SafetyController

@pytest.fixture
def store():
    return DataStore()

@pytest.mark.asyncio
async def test_agent_cas_reservation(store):
    agent = Agent(id="A1", state=AgentState.AVAILABLE, version=0)
    store.agents["A1"] = agent

    # Two concurrent workers try to reserve the same agent
    # The first one that runs should succeed (returns True)
    # The second one should fail (returns False) because the version bumped
    
    task1 = store.try_reserve_agent("A1", 0)
    task2 = store.try_reserve_agent("A1", 0)
    
    results = await asyncio.gather(task1, task2)
    
    # Exactly one should be True, one should be False
    assert results.count(True) == 1
    assert results.count(False) == 1
    assert store.agents["A1"].state == AgentState.RESERVED
    assert store.agents["A1"].version == 1

def test_predictive_pacing():
    pacing = PredictivePacing()
    
    # 10 available agents, 0 ringing, hit rate 50%
    # target = 10 / 0.5 = 20 dials
    dials = pacing.get_dials(10, 0, hit_rate=0.5)
    assert dials == 20
    
    # 10 available agents, 15 ringing, hit rate 50%
    # target = 20, minus 15 ringing = 5 dials
    dials = pacing.get_dials(10, 15, hit_rate=0.5)
    assert dials == 5
    
    # Negative dials should hit floor of 0
    dials = pacing.get_dials(10, 25, hit_rate=0.5)
    assert dials == 0

def test_call_state_idempotency_and_monotonicity(store):
    call = Call(id="C1", borrower_phone="555-1234")
    store.calls["C1"] = call

    # 1. Normal transition
    success = store.update_call_state("C1", CallState.INITIATED, "event_1")
    assert success is True
    assert store.calls["C1"].state == CallState.INITIATED

    # 2. Duplicate event (idempotency)
    success = store.update_call_state("C1", CallState.INITIATED, "event_1")
    assert success is False

    # 3. Monotonicity: Try to go backwards (INITIATED to QUEUED)
    # The state enum has QUEUED=1, INITIATED=2
    # The state check should block moving back to a lower value state.
    success = store.update_call_state("C1", CallState.QUEUED, "event_2")
    assert success is False
    assert store.calls["C1"].state == CallState.INITIATED

def test_safety_controller_limits():
    safety = SafetyController(max_abandon_rate=0.05)
    
    # Normal operation
    dials = safety.evaluate(requested_dials=20, available_agents=10, is_predictive=True)
    assert dials == 20
    
    # High abandon rate -> limits to available agents (fallback to progressive)
    safety.abandoned = 6
    safety.connected = 94
    # Abandon rate is 6 / 100 = 0.06 (6%) > 5%
    dials = safety.evaluate(requested_dials=20, available_agents=10, is_predictive=True)
    assert dials == 10
    
    # Progressive mode always limits to available agents
    dials = safety.evaluate(requested_dials=20, available_agents=5, is_predictive=False)
    assert dials == 5

    # Provider failures kill dialing completely
    safety.provider_failures = 15
    dials = safety.evaluate(requested_dials=20, available_agents=10, is_predictive=True)
    assert dials == 0
