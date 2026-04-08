import asyncio
from dataclasses import dataclass
from fastapi.responses import JSONResponse

@dataclass
class ChaosState:
    slow_mode: bool = False
    slow_delay: float = 2.0
    error_mode: bool = False
    error_countdown: int = 0

chaos_state = ChaosState()

def enable_slow():
    chaos_state.slow_mode = True
    chaos_state.slow_delay = 2.0

def enable_errors(count: int = 10):
    chaos_state.error_mode = True
    chaos_state.error_countdown = count

def reset():
    chaos_state.slow_mode = False
    chaos_state.error_mode = False
    chaos_state.error_countdown = 0

def get_status() -> dict:
    return {
        "slow_mode": chaos_state.slow_mode,
        "slow_delay": chaos_state.slow_delay,
        "error_mode": chaos_state.error_mode,
        "error_countdown": chaos_state.error_countdown
    }

async def inject_chaos(request, call_next):
    path = request.url.path
    # Apply chaos specifically to application logic endpoints like /todos and /infer
    if path.startswith("/todos") or path.startswith("/infer"):
        if chaos_state.slow_mode:
            await asyncio.sleep(chaos_state.slow_delay)
        
        if chaos_state.error_mode and chaos_state.error_countdown > 0:
            chaos_state.error_countdown -= 1
            return JSONResponse(
                status_code=500,
                content={"detail": "Chaos Engineering: Simulated Internal Server Error"}
            )

    response = await call_next(request)
    return response
