# SmartDialer

A functional prototype of a smart dialing system that demonstrates both Progressive and Predictive dialing modes while enforcing strict safety constraints.

## Requirements
- Python 3.9+

## Setup Instructions

1. **Activate the Virtual Environment**
   Assuming you have already created a virtual environment (e.g. `python -m venv venv`), activate it:
   - On Windows:
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

2. **Install Dependencies**
   The core simulation only uses standard libraries (`asyncio`, `uuid`, etc).
   To run the tests, you will need to install `pytest` and `pytest-asyncio`:
   ```bash
   pip install pytest pytest-asyncio
   ```

## Running the Simulation

To run the main simulation which executes multiple scenarios (Predictive, Progressive, Chaos Provider, Agent Drops, Provider Outages, and a basic Load Test), run:

```bash
python main.py
```

## Running the Tests

To run the unit tests that verify Agent CAS concurrency, Pacing logic, Call state idempotency, and the Safety Controller:

```bash
pytest test_dialer.py -v
```
