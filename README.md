# SmartDialer Implementation

This repository contains my solution for the SmartDialer technical assignment. It's a fully functioning prototype built to handle the complexities of both Predictive and Progressive dialing strategies, prioritizing strict safety limits and concurrency control above all else.

## Tech Stack & Requirements
The application is written purely in **Python (3.9+)**, leveraging the built-in `asyncio` framework to handle thousands of concurrent operations without relying on heavy external message brokers.

## Getting Started

Follow these steps to get the engine running on your local machine.

### 1. Environment Setup
First, establish an isolated Python environment so dependencies don't conflict with your global setup:

```bash
# On Windows
python -m venv env
.\env\Scripts\activate

# On Mac or Linux
python3 -m venv env
source env/bin/activate
```

### 2. Install Packages
The dialer itself is built entirely with standard libraries. However, to execute the unit tests and run the real-world Plivo webhook server, install the following packages:

```bash
pip install pytest pytest-asyncio fastapi uvicorn httpx python-dotenv
```

### 3. Configuration
Copy the sample environment file to create your own configuration. The `.env` file controls all the pacing limits, timeouts, and telecom credentials.
```bash
cp .env.example .env
```

## Running the Engine

You can test the dialer in two different ways depending on what you want to evaluate.

### Option A: The Local Executor
If you want to observe how the dialer handles extreme scenarios (like suddenly losing 8 agents, or the telecom provider sending out-of-order events), run the standalone executor. This models everything purely in-memory:

```bash
python main.py
```
*This will execute 6 distinct stress-test scenarios, concluding with a 1,000-agent load test.*

### Option B: The Live Plivo Server
To run the dialer against the real world, launch the FastAPI application. This boots up a background thread that calculates pacing, while simultaneously exposing an HTTP listener for Plivo webhooks:

```bash
uvicorn server:app --reload
```
*(Note: You will need to expose port 8000 via `ngrok` and update your `.env` file with the public URL for Plivo callbacks to work).*

## Executing the Test Suite

I've included a comprehensive suite of unit tests verifying the core logic constraints (like the atomic Compare-And-Swap lock on agents). Run them via pytest:

```bash
pytest test_dialer.py -v
```
