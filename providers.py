import asyncio
import random
import uuid
from models import CallState

class ProviderBase:
    async def place_call(self, call_id: str, phone: str, callback):
        pass

class ProviderA(ProviderBase):
    """Fast, reliable, standard behavior."""
    def __init__(self, answer_rate: float):
        self.answer_rate = answer_rate

    async def place_call(self, call_id: str, phone: str, callback):
        await asyncio.sleep(0.05)
        await callback(call_id, CallState.INITIATED, f"init_{uuid.uuid4().hex[:6]}")
        await asyncio.sleep(0.1)
        await callback(call_id, CallState.RINGING, f"ring_{uuid.uuid4().hex[:6]}")
        await asyncio.sleep(0.1)
        
        if random.random() < self.answer_rate:
            await callback(call_id, CallState.ANSWERED, f"ans_{uuid.uuid4().hex[:6]}")
        else:
            await callback(call_id, CallState.FAILED, f"fail_{uuid.uuid4().hex[:6]}")

class ProviderB(ProviderBase):
    """Models duplicates, out-of-order events, and jitter."""
    async def place_call(self, call_id: str, phone: str, callback):
        await asyncio.sleep(0.1)
        dup_id = f"init_{uuid.uuid4().hex[:6]}"
        await callback(call_id, CallState.INITIATED, dup_id)
        await callback(call_id, CallState.INITIATED, dup_id) # Duplicate event
        
        # Out of order execution (Answered fires before Ringing)
        ans_id = f"ans_{uuid.uuid4().hex[:6]}"
        ring_id = f"ring_{uuid.uuid4().hex[:6]}"
        
        if random.random() < 0.5:
            asyncio.create_task(self._delayed_cb(0.1, call_id, CallState.ANSWERED, ans_id, callback))
            asyncio.create_task(self._delayed_cb(0.2, call_id, CallState.RINGING, ring_id, callback))
        else:
            await callback(call_id, CallState.FAILED, f"fail_{uuid.uuid4().hex[:6]}")

    async def _delayed_cb(self, delay, cid, state, eid, cb):
        await asyncio.sleep(delay)
        await cb(cid, state, eid)

class OutageProvider(ProviderBase):
    """Models sudden provider failure."""
    async def place_call(self, call_id: str, phone: str, callback):
        await asyncio.sleep(0.1)
        await callback(call_id, CallState.FAILED, f"fail_outage_{uuid.uuid4().hex[:6]}")