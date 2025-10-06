import importlib

def test_import_version():
    mod = importlib.import_module("draupnir_mcp_server")
    assert hasattr(mod, "__version__")
    assert isinstance(mod.__version__, str)
