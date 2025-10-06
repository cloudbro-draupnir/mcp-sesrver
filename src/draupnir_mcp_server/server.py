from __future__ import annotations

import argparse
import json
import os
import subprocess
import yaml
from pathlib import Path, PurePosixPath
from typing import Iterable, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import (
    Resource,
    ResourceContents,
    TextContent,
)

APP_NAME = "draupnir-mcp-server"
DEFAULT_DATA_DIR = Path(os.environ.get("STATIC_MCP_DATA_DIR", "./data")).resolve()

mcp = FastMCP(APP_NAME)

# Utilities
def _iter_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    for p in root.rglob("*"):
        if p.is_file():
            yield p

def _enforce_under(path: Path, base: Path) -> None:
    try:
        path.relative_to(base)
    except Exception:
        raise PermissionError(f"Access outside data dir is not allowed: {path}")

def _guess_mime(ext: str) -> Optional[str]:
    ext = ext.lower()
    return {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".json": "application/json",
        ".csv": "text/csv",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
    }.get(ext)

def _expand_brace_patterns(pattern: str) -> List[str]:
    if "{" not in pattern or "}" not in pattern:
        return [pattern]
    pre, _, rest = pattern.partition("{")
    inner, sep, post = rest.partition("}")
    if not sep:
        return [pattern]
    return [pre + opt + post for opt in inner.split(",")]

def _normalize_patterns(pattern: str) -> List[str]:
    pats = _expand_brace_patterns(pattern)
    out: List[str] = []
    for pat in pats:
        out.append(pat)
        if pat.startswith("**/"):
            out.append(pat[3:])
    return out

def _matches(path: str, pattern: str) -> bool:
    for pat in _normalize_patterns(pattern):
        if PurePosixPath(path).match(pat):
            return True
    return False

# Resources (conditionally register for FastMCP variants)
if hasattr(mcp, "resource"):
    @mcp.resource("file://")
    def list_resources() -> List[Resource]:
        resources: List[Resource] = []
        for file_path in _iter_files(DEFAULT_DATA_DIR):
            rel = file_path.relative_to(DEFAULT_DATA_DIR)
            uri = f"file://{file_path}"
            resources.append(
                Resource(
                    uri=uri,
                    name=str(rel),
                    description=f"Static file '{rel}' from {DEFAULT_DATA_DIR}",
                    mimeType=_guess_mime(file_path.suffix),
                )
            )
        return resources
else:
    def list_resources() -> List[Resource]:
        resources: List[Resource] = []
        for file_path in _iter_files(DEFAULT_DATA_DIR):
            rel = file_path.relative_to(DEFAULT_DATA_DIR)
            uri = f"file://{file_path}"
            resources.append(
                Resource(
                    uri=uri,
                    name=str(rel),
                    description=f"Static file '{rel}' from {DEFAULT_DATA_DIR}",
                    mimeType=_guess_mime(file_path.suffix),
                )
            )
        return resources

if hasattr(mcp, "resource_contents"):
    @mcp.resource_contents()
    def read_resource(uri: str) -> ResourceContents:
        if not uri.startswith("file://"):
            raise ValueError("Only file:// URIs are supported")
        file_path = Path(uri[len("file://") :])
        data = file_path.read_text(encoding="utf-8")
        return [TextContent(type="text", text=data)]
else:
    def read_resource(uri: str) -> ResourceContents:
        if not uri.startswith("file://"):
            raise ValueError("Only file:// URIs are supported")
        file_path = Path(uri[len("file://") :])
        data = file_path.read_text(encoding="utf-8")
        return [TextContent(type="text", text=data)]

# Generic Tools
@mcp.tool()
def list_files(pattern: Optional[str] = None) -> List[str]:
    files = [p.relative_to(DEFAULT_DATA_DIR).as_posix() for p in _iter_files(DEFAULT_DATA_DIR)]
    if pattern:
        files = [f for f in files if _matches(f, pattern)]
    return files

@mcp.tool()
def read_text(path: str) -> str:
    fp = (DEFAULT_DATA_DIR / path).resolve()
    _enforce_under(fp, DEFAULT_DATA_DIR)
    return fp.read_text(encoding="utf-8")

@mcp.tool()
def search_text(query: str, path_glob: str = "**/*") -> List[dict]:
    results: List[dict] = []
    q = query.lower()
    for p in _iter_files(DEFAULT_DATA_DIR):
        rel = p.relative_to(DEFAULT_DATA_DIR).as_posix()
        if path_glob and not _matches(rel, path_glob):
            continue
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, start=1):
            if q in line.lower():
                results.append({"path": rel, "line_no": i, "line": line})
    return results

@mcp.tool()
def healthcheck() -> str:
    return f"OK: data_dir={DEFAULT_DATA_DIR}"

# Cilium / Draupnir‑aligned Tools
CILIUM_KINDS = {"CiliumNetworkPolicy", "CiliumClusterwideNetworkPolicy"}

@mcp.tool()
def list_cilium_policies(path_glob: str = "**/*.{yml,yaml}") -> List[str]:
    """List YAML files that look like Cilium (CNP/CCNP)."""
    hits: List[str] = []
    for p in _iter_files(DEFAULT_DATA_DIR):
        rel = p.relative_to(DEFAULT_DATA_DIR).as_posix()
        if path_glob and not _matches(rel, path_glob):
            continue
        if p.suffix.lower() not in {".yaml", ".yml"}:
            continue
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(doc, dict) and doc.get("kind") in CILIUM_KINDS:
            hits.append(rel)
    return hits

@mcp.tool()
def validate_cilium_policy(path: str) -> dict:
    """Basic validation & hardening hints for a single Cilium policy file."""
    fp = (DEFAULT_DATA_DIR / path).resolve()
    _enforce_under(fp, DEFAULT_DATA_DIR)
    data = yaml.safe_load(fp.read_text(encoding="utf-8"))

    result = {"path": path, "errors": [], "warnings": [], "kind": None, "metadata": {}, "summary": {}}

    if not isinstance(data, dict):
        result["errors"].append("YAML root must be a mapping")
        return result

    kind = data.get("kind")
    result["kind"] = kind
    if kind not in CILIUM_KINDS:
        result["errors"].append("Not a Cilium {CNP|CCNP} kind")
        return result

    meta = data.get("metadata", {}) or {}
    if "name" not in meta:
        result["errors"].append("metadata.name is required")
    result["metadata"] = {k: meta.get(k) for k in ("name", "namespace", "labels")}

    spec = data.get("spec") or {}
    if not spec:
        result["errors"].append("spec is required")
        return result

    # Basic zero‑trust posture checks
    have_ingress = bool(spec.get("ingress"))
    have_egress = bool(spec.get("egress"))
    result["summary"].update({"has_ingress": have_ingress, "has_egress": have_egress})

    if not have_ingress and not have_egress:
        result["warnings"].append("No ingress/egress rules present (might not enforce anything)")

    # L7 ports presence
    def _has_l7_ports(rules):
        for rule in rules or []:
            for tp in rule.get("toPorts", []):
                if tp.get("ports") or tp.get("rules"):
                    return True
        return False

    if have_ingress and not _has_l7_ports(spec.get("ingress")):
        result["warnings"].append("Ingress has no L4/L7 ports (coarse allow?)")
    if have_egress and not _has_l7_ports(spec.get("egress")):
        result["warnings"].append("Egress has no L4/L7 ports (coarse allow?)")

    # DNS egress recommendation
    if have_egress:
        text = yaml.safe_dump(spec.get("egress"))
        if "53" not in text and "toFQDNs" not in text:
            result["warnings"].append("No explicit DNS egress (add kube-dns:53 or toFQDNs)")

    return result

@mcp.tool()
def generate_policy_template(
    app: str,
    namespace: str,
    ingress_ports: Optional[List[str]] = None,
    egress_fqdns: Optional[List[str]] = None,
) -> str:
    """Generate a CiliumNetworkPolicy skeleton for an app."""
    ingress_ports = ingress_ports or ["80/TCP", "443/TCP"]
    egress_fqdns = egress_fqdns or ["*.amazonaws.com"]

    def port_obj(p: str):
        port, proto = p.split("/") if "/" in p else (p, "TCP")
        return {"ports": [{"port": str(port), "protocol": proto}]}

    doc = {
        "apiVersion": "cilium.io/v2",
        "kind": "CiliumNetworkPolicy",
        "metadata": {"name": f"{app}-ztp", "namespace": namespace},
        "spec": {
            "endpointSelector": {"matchLabels": {"k8s:io.kubernetes.pod.namespace": namespace, "app": app}},
            "ingress": [
                {"fromEndpoints": [{"matchLabels": {"app": app}}], "toPorts": [port_obj(p) for p in ingress_ports]},
            ],
            "egress": [
                {"toFQDNs": [{"matchName": fqdn} for fqdn in egress_fqdns]},
                {"toEndpoints": [{"matchLabels": {"k8s:io.kubernetes.pod.namespace": "kube-system", "k8s-app": "kube-dns"}}],
                 "toPorts": [{"ports": [{"port": "53", "protocol": "UDP"}]}]},
            ],
        },
    }
    return yaml.safe_dump(doc, sort_keys=False)

@mcp.tool()
def hubble_filters(src: str = "", dst: str = "", verdict: str = "") -> dict:
    """Return CLI snippets and filter dicts for Hubble flows."""
    args = []
    if src:
        args += ["--from", src]
    if dst:
        args += ["--to", dst]
    if verdict:
        args += ["--verdict", verdict]
    return {
        "cli": "hubble observe " + " ".join(args),
        "filters": {"from": src or None, "to": dst or None, "verdict": verdict or None},
    }

@mcp.tool()
def zero_trust_checklist(path_glob: str = "**/*.{yml,yaml}") -> dict:
    """Scan policies and produce a summarized ZT posture checklist."""
    stats = {"total": 0, "cnp": 0, "ccnp": 0, "with_l7": 0, "dns_ok": 0}
    details: List[dict] = []

    for p in _iter_files(DEFAULT_DATA_DIR):
        rel = p.relative_to(DEFAULT_DATA_DIR).as_posix()
        if path_glob and not _matches(rel, path_glob):
            continue
        if p.suffix.lower() not in {".yaml", ".yml"}:
            continue
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        kind = doc.get("kind")
        if kind not in CILIUM_KINDS:
            continue
        stats["total"] += 1
        stats["cnp" if kind == "CiliumNetworkPolicy" else "ccnp"] += 1

        spec = doc.get("spec") or {}
        l7 = False
        dns = False
        for section in (spec.get("ingress") or []) + (spec.get("egress") or []):
            for tp in section.get("toPorts", []) or []:
                if tp.get("ports") or tp.get("rules"):
                    l7 = True
            if section.get("toFQDNs"):
                dns = True
            txt = yaml.safe_dump(section)
            if "port: '53'" in txt or "port: 53" in txt:
                dns = True
        if l7:
            stats["with_l7"] += 1
        if dns:
            stats["dns_ok"] += 1
        details.append({"path": rel, "kind": kind, "l7": l7, "dns_handled": dns})

    return {"stats": stats, "details": details}

# Prompts
@mcp.prompt("hardening-review")
def prompt_hardening_review() -> str:
    return (
        "You are a senior platform engineer reviewing Cilium policies for zero-trust.\n"
        "Checklist: default-deny posture, least-privilege, L7 toPorts, DNS egress, health & kube-dns, FQDN pinning, auditability.\n"
        "Provide findings and prioritized fixes (P0/P1/P2)."
    )

@mcp.prompt("write-cilium-policy")
def prompt_write_cilium_policy() -> str:
    return (
        "Draft a CiliumNetworkPolicy for a new app. Collect: app, namespace, ingress ports, egress FQDNs.\n"
        "Emit YAML only, with comments explaining key choices."
    )


# --- K8s-aware tools (kubectl) ---

def _run_cmd(cmd: list[str], timeout: int = 25) -> dict:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return {"code": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
    except Exception as e:
        return {"code": -1, "stdout": "", "stderr": str(e)}

@mcp.tool()
def k8s_context() -> dict:
    """Return current kubectl context."""
    res = _run_cmd(["kubectl", "config", "current-context"])
    return {"context": res["stdout"], "stderr": res["stderr"], "code": res["code"]}

@mcp.tool()
def k8s_cluster_info() -> dict:
    """Return cluster info + nodes summary (kubectl cluster-info; get nodes -o wide)."""
    info = _run_cmd(["kubectl", "cluster-info"])
    nodes = _run_cmd(["kubectl", "get", "nodes", "-o", "wide"])
    return {"cluster_info": info["stdout"], "nodes": nodes["stdout"], "stderr": "\n".join([info["stderr"], nodes["stderr"]]).strip()}

@mcp.tool()
def k8s_service_accounts(all_namespaces: bool = True) -> dict:
    """List service accounts (JSON), summarized to namespace/name/age if available."""
    args = ["kubectl", "get", "sa"]
    if all_namespaces:
        args.append("-A")
    args += ["-o", "json"]
    res = _run_cmd(args)
    items = []
    try:
        data = json.loads(res["stdout"] or "{}")
        for it in data.get("items", []):
            meta = it.get("metadata", {})
            items.append({
                "namespace": meta.get("namespace"),
                "name": meta.get("name"),
                "uid": meta.get("uid"),
                "creationTimestamp": meta.get("creationTimestamp"),
            })
    except Exception as e:
        return {"items": [], "stderr": res["stderr"] or str(e), "raw": res["stdout"]}
    return {"items": items, "stderr": res["stderr"]}

# Entrypoint
def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Draupnir MCP server (Cilium)")
    parser.add_argument("--http", help="Run HTTP/SSE server at host:port (e.g. 0.0.0.0:8765)")
    args = parser.parse_args(argv)

    if args.http:
        host, port_str = args.http.split(":", 1)
        mcp.settings.host = host
        mcp.settings.port = int(port_str)
        mcp.run("sse")
    else:
        mcp.run("stdio")

if __name__ == "__main__":
    main()
