---
name: scaffold-fastapi
description: Use when the task asks to create a new FastAPI service or HTTP API in Python.
---

Scaffold a minimal, test-backed FastAPI service.

1. Create `app/main.py` with a FastAPI app and a `GET /health` route returning
   `{"status": "ok"}`.
2. Add `requirements.txt` pinning `fastapi` and `uvicorn[standard]`.
3. Create `tests/test_health.py` using `fastapi.testclient.TestClient` that
   asserts `GET /health` returns 200 and the expected JSON.
4. Run `pip install -r requirements.txt` then `pytest -q`. Report the output.
5. Do not add auth, databases, or extra routes unless the task asks. Keep it
   minimal and correct.
