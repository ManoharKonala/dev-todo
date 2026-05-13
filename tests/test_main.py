import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app, todos_store, update_gauges
from app.chaos import reset as chaos_reset

@pytest.fixture(autouse=True)
def reset_state():
    # Clear in-memory store and reset chaos configuration before every test ensures pristine isolation
    todos_store.clear()
    chaos_reset()
    update_gauges()

@pytest.mark.asyncio
async def test_health_returns_ok_with_all_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        expected_keys = {"status", "total_todos", "completed_todos", "completion_rate", "uptime_seconds", "environment", "version"}
        assert expected_keys.issubset(data.keys())
        assert data["status"] == "healthy"

@pytest.mark.asyncio
async def test_version_endpoint_returns_metadata():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/version")
        assert response.status_code == 200
        data = response.json()
        expected_keys = {"version", "color", "namespace", "build_number"}
        assert expected_keys.issubset(data.keys())

@pytest.mark.asyncio
async def test_create_todo_with_priority():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"title": "High priority task", "priority": "high"}
        response = await client.post("/todos", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "High priority task"
        assert data["priority"] == "high"
        assert data["completed"] is False
        assert "id" in data

@pytest.mark.asyncio
async def test_get_todos_returns_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/todos", json={"title": "Task 1", "priority": "low"})
        await client.post("/todos", json={"title": "Task 2", "priority": "medium"})
        
        response = await client.get("/todos")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

@pytest.mark.asyncio
async def test_toggle_todo_completion_updates_metrics():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create
        create_res = await client.post("/todos", json={"title": "Metric Update Task", "priority": "medium"})
        todo_id = create_res.json()["id"]
        
        # Toggle completion
        update_res = await client.put(f"/todos/{todo_id}", json={"completed": True})
        assert update_res.status_code == 200
        assert update_res.json()["completed"] is True
        
        # Validate health reflects 100% completion rate
        health_res = await client.get("/health")
        assert health_res.json()["completion_rate"] == 1.0

@pytest.mark.asyncio
async def test_delete_todo():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_res = await client.post("/todos", json={"title": "To be deleted", "priority": "low"})
        todo_id = create_res.json()["id"]
        
        del_res = await client.delete(f"/todos/{todo_id}")
        assert del_res.status_code == 200
        
        # Ensure collection is empty
        list_res = await client.get("/todos")
        assert len(list_res.json()) == 0

@pytest.mark.asyncio
async def test_delete_nonexistent_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/todos/invalid-uuid-string")
        assert response.status_code == 404

@pytest.mark.asyncio
async def test_chaos_slow_mode_enable_and_reset():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        slow_res = await client.get("/chaos/slow")
        assert slow_res.status_code == 200
        assert slow_res.json()["status"] == "slow_mode_enabled"
        
        status_res = await client.get("/chaos/status")
        assert status_res.json()["slow_mode"] is True
        
        reset_res = await client.get("/chaos/reset")
        assert reset_res.status_code == 200
        
        final_status = await client.get("/chaos/status")
        assert final_status.json()["slow_mode"] is False

@pytest.mark.asyncio
async def test_chaos_error_mode_triggers_500():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Enable errors
        err_res = await client.get("/chaos/errors")
        assert err_res.status_code == 200
        
        # Trigger an API logic endpoint covered by chaos injection middleware
        todo_res = await client.get("/todos")
        assert todo_res.status_code == 500
        
        # Ensure graceful restoration
        await client.get("/chaos/reset")
        clean_res = await client.get("/todos")
        assert clean_res.status_code == 200

@pytest.mark.asyncio
async def test_completion_rate_updates_correctly():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/todos", json={"title": "Task A", "priority": "low"})
        res2 = await client.post("/todos", json={"title": "Task B", "priority": "high"})
        id1 = res1.json()["id"]
        
        # Initially 0%
        h1 = await client.get("/health")
        assert h1.json()["completion_rate"] == 0.0
        
        # Complete Task A
        await client.put(f"/todos/{id1}", json={"completed": True})
        
        # Now 50%
        h2 = await client.get("/health")
        assert h2.json()["completion_rate"] == 0.5
