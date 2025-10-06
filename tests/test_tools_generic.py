import os
import importlib

def test_list_and_read(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "a.txt").write_text("hello world", encoding="utf-8")
    os.environ["STATIC_MCP_DATA_DIR"] = str(data_dir)
    server = importlib.reload(importlib.import_module("draupnir_mcp_server.server"))
    files = server.list_files("**/*.txt")
    assert "a.txt" in files
    text = server.read_text("a.txt")
    assert "hello world" in text
