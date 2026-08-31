import asyncio
import random
import uuid
from typing import List

from models import Agent, Call, AgentState, CallState
from providers import ProviderBase, ProviderA, ProviderB, OutageProvider
from engine import DataStore, PredictivePacing, SafetyController, StaleSweeper

class SmartDialer:
    def __init__(self, store: DataStore, provider: ProviderBase, predictive: bool = True):
        self.store = store
        self.provider = provider
        self.predictive = predictive
        self.pacing = PredictivePacing()
        self.safety = SafetyController()
        self.sweeper = StaleSweeper(self.store, timeout_sec=1.0) # short timeout for testing
        self.ringing_count = 0
        self.stats = {"initiated": 0, "connected": 0, "abandoned": 0, "failed": 0, "recovered": 0}

    async def handle_telecom_event(self, call_id: str, state: CallState, event_id: str):
        if not self.store.update_call_state(call_id, state, event_id):
            return

        call = self.store.calls[call_id]

        if state == CallState.RINGING:
            self.ringing_count += 1
            
        elif state == CallState.ANSWERED:
            self.ringing_count = max(0, self.ringing_count - 1)
            
            agents = await self.store.get_available_agents()
            allocated = False
            for agent in agents:
                if await self.store.try_reserve_agent(agent.id, agent.version):
                    call.agent_id = agent.id
                    await self.store.transition_agent(agent.id, AgentState.CONNECTED, call.id)
                    self.store.update_call_state(call_id, CallState.CONNECTED, f"conn_{uuid.uuid4().hex[:6]}")
                    
                    self.stats["connected"] += 1
                    self.safety.connected += 1
                    allocated = True
                    asyncio.create_task(self._sim_conversation(agent.id, call_id))
                    break

            if not allocated:
                call.abandoned = True
                self.stats["abandoned"] += 1
                self.safety.abandoned += 1
                self.store.update_call_state(call_id, CallState.COMPLETED, f"comp_{uuid.uuid4().hex[:6]}")

        elif state == CallState.FAILED:
            self.ringing_count = max(0, self.ringing_count - 1)
            self.stats["failed"] += 1
            self.safety.provider_failures += 1

    async def _sim_conversation(self, agent_id: str, call_id: str):
        await asyncio.sleep(random.uniform(0.2, 0.5))
        self.store.update_call_state(call_id, CallState.COMPLETED, f"comp_{uuid.uuid4().hex[:6]}")
        await self.store.transition_agent(agent_id, AgentState.WRAP_UP)
        await asyncio.sleep(0.1)
        await self.store.transition_agent(agent_id, AgentState.AVAILABLE)

    async def tick(self, leads: List[str]):
        recovered = await self.sweeper.sweep()
        if recovered > 0:
            self.stats["recovered"] += recovered
            
        avail_agents = len(await self.store.get_available_agents())
        
        req_dials = avail_agents
        if self.predictive:
            req_dials = self.pacing.get_dials(avail_agents, self.ringing_count)

        safe_dials = self.safety.evaluate(req_dials, avail_agents, self.predictive)

        for _ in range(safe_dials):
            if not leads: break
            phone = leads.pop(0)
            call_id = f"CALL_{uuid.uuid4().hex[:8]}"
            self.store.calls[call_id] = Call(id=call_id, borrower_phone=phone)
            self.stats["initiated"] += 1
            
            asyncio.create_task(
                self.provider.place_call(call_id, phone, self.handle_telecom_event)
            )

async def run_scenario(name: str, provider: ProviderBase, mode: bool, agents=10, leads=50):
    store = DataStore()
    for i in range(agents):
        store.agents[f"A{i}"] = Agent(id=f"A{i}")
        
    lead_list = [f"555-{i:04d}" for i in range(leads)]
    dialer = SmartDialer(store, provider, predictive=mode)

    print(f"\n--- Running: {name} ---")
    for step in range(10):
        await dialer.tick(lead_list)
        
        if name == "Agent Drop Test" and step == 3:
            print("   [!] Testing sudden loss of 8 agents...")
            for i in range(8):
                await store.transition_agent(f"A{i}", AgentState.OFFLINE)

        await asyncio.sleep(0.3)

    await asyncio.sleep(1.0) # Drain
    
    print(f"Initiated: {dialer.stats['initiated']}")
    print(f"Connected: {dialer.stats['connected']}")
    print(f"Abandoned: {dialer.stats['abandoned']}")
    print(f"Failed   : {dialer.stats['failed']}")
    if dialer.stats.get('recovered', 0) > 0:
        print(f"Recovered: {dialer.stats['recovered']}")
    if dialer.stats['connected'] > 0:
        print(f"Abandon Rate: {(dialer.stats['abandoned'] / (dialer.stats['abandoned'] + dialer.stats['connected']))*100:.1f}%")

async def run_worker_crash_scenario():
    print("\n--- Running: Worker Crash & Recovery ---")
    store = DataStore()
    store.agents["A0"] = Agent(id="A0")
    
    dialer = SmartDialer(store, ProviderA(1.0), predictive=False)
    
    # 1. Start a call and reserve agent
    await dialer.tick(["555-CRASH"])
    await asyncio.sleep(0.3) # Wait for Answered (0.05 + 0.1 + 0.1)
    
    # Check that agent is CONNECTED
    assert store.agents["A0"].state == AgentState.CONNECTED
    print("   [!] Testing worker crash right after call answered...")
    
    # The worker processing the call "crashed", meaning it won't ever finish the call and reset the agent.
    # We will let time pass and tick the dialer to model a new/recovered worker sweeping.
    await asyncio.sleep(1.2) # Longer than sweeper timeout (1.0s)
    print("   [!] System comes back. New worker ticks...")
    
    await dialer.tick([]) # Sweeper runs
    
    # Check that agent was recovered
    assert store.agents["A0"].state == AgentState.AVAILABLE
    print("   [*] Agent recovered back to AVAILABLE by sweeper.")

async def run_load_test():
    import time
    print("\n--- Running: Basic Load Test (1,000 Agents) ---")
    store = DataStore()
    for i in range(1000):
        store.agents[f"A{i}"] = Agent(id=f"A{i}")
        
    lead_list = [f"555-{i:04d}" for i in range(5000)]
    dialer = SmartDialer(store, ProviderA(0.6), predictive=True)

    start_time = time.time()
    for _ in range(10): # 10 ticks
        tick_start = time.time()
        await dialer.tick(lead_list)
        tick_time = time.time() - tick_start
        print(f"Tick processed in {tick_time:.4f}s")
        await asyncio.sleep(0.3)
        
    await asyncio.sleep(1.0)
    total_time = time.time() - start_time
    print(f"\nLoad Test Completed in {total_time:.2f}s")
    print(f"Initiated: {dialer.stats['initiated']}")

async def run_all():
    print("STARTING SMARTDIALER EXECUTIONS")
    await run_scenario("A - Predictive Optimal (70% Answer)", ProviderA(0.7), True)
    await run_scenario("B - Progressive Strict (70% Answer)", ProviderA(0.7), False)
    await run_scenario("C - Chaos Provider B (Duplicates/Out-of-Order)", ProviderB(), True)
    await run_scenario("Agent Drop Test", ProviderA(0.5), True)
    await run_scenario("Provider Outage Protection", OutageProvider(), True)
    await run_worker_crash_scenario()
    await run_load_test()

if __name__ == "__main__":
    asyncio.run(run_all())