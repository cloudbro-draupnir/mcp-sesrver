import os
import importlib

def test_k8s_context_mock(tmp_path, monkeypatch):
    os.environ["STATIC_MCP_DATA_DIR"] = str(tmp_path / "data")
    server = importlib.reload(importlib.import_module("draupnir_mcp_server.server"))

    def fake_run(cmd, timeout=60):
        if cmd[:3] == ["kubectl", "config", "current-context"]:
            return {"code": 0, "stdout": "gke_reflecting-surf-ctx", "stderr": ""}
        return {"code": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(server, "_run_cmd", fake_run)
    res = server.k8s_context()
    assert res["context"] == "gke_reflecting-surf-ctx"
