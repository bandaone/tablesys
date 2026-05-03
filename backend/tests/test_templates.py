"""
CHECKPOINT 2 – Template Profile API Tests
==========================================

Tests the FASTAPI endpoints defined in routers/templates.py:
  - POST /api/templates/upload-preview
  - POST /api/templates/save
  - GET  /api/templates/
  - GET  /api/templates/{id}
  - PUT  /api/templates/{id}/activate
  - DELETE /api/templates/{id}
"""

import io
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

def _make_excel_template_bytes() -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    data = [
        ["HOURS",        "2ND YEAR",  "",      "3RD YEAR", ""],
        ["",             "GEN-2",     "",      "AEN",      "EEE"],
        ["07:00-08:00",  "Lecture",   "",      "",         ""],
        ["08:00-09:00",  "",          "",      "Lab",      ""],
    ]
    for row in data:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

async def test_upload_preview_success(async_client: AsyncClient, auth_headers: dict):
    # Provide a valid excel dummy bytes
    file_bytes = _make_excel_template_bytes()
    files = {
        "file": (
            "template.xlsx",
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    }
    response = await async_client.post("/api/v1/templates/upload-preview", headers=auth_headers, files=files)
    assert response.status_code == 200, f"Error: {response.text}"
    
    data = response.json()
    assert data["file_type"] == "xlsx"
    assert "containers" in data
    assert len(data["containers"]) >= 2
    assert "shape" in data

async def test_save_profile_and_crud(async_client: AsyncClient, auth_headers: dict):
    # 1. Preview first to get parsed structural data
    file_bytes = _make_excel_template_bytes()
    files = {
        "file": (
            "template.xlsx",
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    }
    preview_res = await async_client.post("/api/v1/templates/upload-preview", headers=auth_headers, files=files)
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    
    # 2. Save profile
    save_req = {
        "name": "Engineering 2026 Layout",
        "school_name": "School of Engineering",
        "original_filename": "template.xlsx",
        "file_type": "xlsx",
        "shape": preview_data["shape"],
        "containers": preview_data["containers"]
    }
    save_res = await async_client.post("/api/v1/templates/save", headers=auth_headers, json=save_req)
    assert save_res.status_code == 201, f"Error: {save_res.text}"
    profile = save_res.json()
    
    assert profile["name"] == "Engineering 2026 Layout"
    assert profile["school_name"] == "School of Engineering"
    assert profile["is_active"] is False
    profile_id = profile["id"]
    
    # 3. List profiles
    list_res = await async_client.get("/api/v1/templates/", headers=auth_headers)
    assert list_res.status_code == 200
    all_profiles = list_res.json()
    assert any(p["id"] == profile_id for p in all_profiles)
    
    # 4. Get specific profile (detailed view)
    get_res = await async_client.get(f"/api/v1/templates/{profile_id}", headers=auth_headers)
    assert get_res.status_code == 200
    detailed = get_res.json()
    assert detailed["container_count"] == len(preview_data["containers"])
    assert "containers" in detailed
    
    # 5. Activate profile
    act_res = await async_client.put(f"/api/v1/templates/{profile_id}/activate", headers=auth_headers)
    assert act_res.status_code == 200
    activated = act_res.json()
    assert activated["is_active"] is True
    
    # 6. Delete profile
    del_res = await async_client.delete(f"/api/v1/templates/{profile_id}", headers=auth_headers)
    assert del_res.status_code == 204
    
    # 7. Verify deletion
    verify_del = await async_client.get(f"/api/v1/templates/{profile_id}", headers=auth_headers)
    assert verify_del.status_code == 404
