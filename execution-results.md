# SmartDialer Test & Execution Results

This file contains the raw output logs from executing the automated test suite and running the core execution scenarios.

## 1. Unit Test Results (`pytest`)
These tests specifically validate the atomic CAS (Compare-And-Swap) locking mechanism, ensuring two workers can never reserve the same agent simultaneously.

```text
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0
rootdir: E:\Coding\Projects\Cred
plugins: anyio-4.14.2, asyncio-1.4.0
asyncio: mode=Mode.STRICT, debug=False
collected 4 items

test_dialer.py ....                                                      [100%]

============================== 4 passed in 0.08s ==============================
```

## 2. Load & Scenario Execution (`python main.py`)
This execution executes the engine against 6 distinct stress-test scenarios, including predictive dialing, out-of-order events, worker crashes, provider outages, and a 1,000-agent load test.

```text
STARTING SMARTDIALER EXECUTIONS

--- Running: A - Predictive Optimal (70% Answer) ---
Initiated: 42
Connected: 24
Abandoned: 5
Failed   : 13
Abandon Rate: 17.2%

--- Running: B - Progressive Strict (70% Answer) ---
Initiated: 35
Connected: 24
Abandoned: 0
Failed   : 11
Abandon Rate: 0.0%

--- Running: C - Chaos Provider B (Duplicates/Out-of-Order) ---
Initiated: 31
Connected: 15
Abandoned: 2
Failed   : 14
Abandon Rate: 11.8%

--- Running: Agent Drop Test ---
   [!] Testing sudden loss of 8 agents...
Initiated: 30
Connected: 12
Abandoned: 6
Failed   : 12
Abandon Rate: 33.3%

--- Running: Provider Outage Protection ---
Initiated: 20
Connected: 0
Abandoned: 0
Failed   : 20

--- Running: Worker Crash & Recovery ---
   [!] Testing worker crash right after call answered...
   [!] System comes back. New worker ticks...
   [*] Agent recovered back to AVAILABLE by sweeper.

--- Running: Basic Load Test (1,000 Agents) ---
Tick processed in 0.0447s
Tick processed in 0.0016s
Tick processed in 0.0016s
Tick processed in 0.0026s
Tick processed in 0.0020s
Tick processed in 0.0030s
Tick processed in 0.0038s
Tick processed in 0.0033s
Tick processed in 0.0058s
Tick processed in 0.0031s

Load Test Completed in 4.17s
Initiated: 2000
```
