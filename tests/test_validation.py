import os
import importlib
from pathlib import Path
import yaml

def write_file(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

def test_validate_cilium_policy_with_rules(tmp_path, monkeypatch):
    # point server to temp data dir
    data_dir = tmp_path / "data"
    os.environ["STATIC_MCP_DATA_DIR"] = str(data_dir)

    # (re)import server after setting env
    server = importlib.reload(importlib.import_module("draupnir_mcp_server.server"))

    # org rules require DNS + L7
    rules = {
        "require_dns_egress": True,
        "require_l7_ports": True,
        "forbid_wildcard_fqdns": True,
    }
    write_file(data_dir / "policy_rules.yaml", yaml.safe_dump(rules))

    # policy missing DNS egress, and with broad allow (no toPorts)
    policy = {
        "apiVersion": "cilium.io/v2",
        "kind": "CiliumNetworkPolicy",
        "metadata": {"name": "web-ztp", "namespace": "default"},
        "spec": {
            "endpointSelector": {"matchLabels": {"app": "web"}},
            "ingress": [{}],
            "egress": [{}],
        },
    }
    write_file(data_dir / "web.yaml", yaml.safe_dump(policy))

    res = server.validate_cilium_policy("web.yaml")
    assert res["kind"] == "CiliumNetworkPolicy"
    # should warn for DNS egress missing and L7 ports missing
    warn_text = "\n".join(res["warnings"])
    assert "DNS egress" in warn_text or "DNS" in warn_text
    assert "L4/L7" in warn_text or "toPorts" in warn_text
