from __future__ import annotations

import os
import importlib
from pathlib import Path
from typing import List

import streamlit as st


st.set_page_config(page_title="Draupnir MCP Server UI", layout="wide")


def _reload_server(data_dir: Path):
    os.environ["STATIC_MCP_DATA_DIR"] = str(data_dir)
    # Lazy import + reload to pick up new data dir on each change
    mod = importlib.import_module("draupnir_mcp_server.server")
    return importlib.reload(mod)


def init_state():
    if "data_dir" not in st.session_state:
        st.session_state.data_dir = Path(os.environ.get("STATIC_MCP_DATA_DIR", "./data")).resolve()
    if "server" not in st.session_state:
        st.session_state.server = _reload_server(st.session_state.data_dir)


def sidebar_controls():
    st.sidebar.header("Configuration")
    data_dir_input = st.sidebar.text_input(
        "Data directory (STATIC_MCP_DATA_DIR)",
        value=str(st.session_state.data_dir),
        help="Directory containing policy YAMLs and assets",
    )
    col1, col2 = st.sidebar.columns([1, 1])
    with col1:
        if st.button("Load", width="stretch"):
            st.session_state.data_dir = Path(data_dir_input).expanduser().resolve()
            st.session_state.server = _reload_server(st.session_state.data_dir)
            st.sidebar.success(f"Loaded: {st.session_state.data_dir}")
    with col2:
        if st.button("Refresh", width="stretch"):
            st.session_state.server = _reload_server(st.session_state.data_dir)
            st.sidebar.info("Module reloaded")

    st.sidebar.caption("Tip: Make sure files are under the data dir.")


def tab_files():
    server = st.session_state.server
    st.subheader("Browse Files")

    pattern = st.text_input("Glob", value="**/*", help="e.g., **/*.yaml, policies/**/*.yml")
    files: List[str] = server.list_files(pattern or "**/*")

    left, right = st.columns([1, 2])
    with left:
        st.write(f"Found {len(files)} files")
        selected = st.selectbox("Select a file", options=[""] + files, index=0)
    with right:
        if selected:
            try:
                content = server.read_text(selected)
                st.code(content, language="yaml" if selected.endswith((".yml", ".yaml")) else "text")
                st.download_button("Download", data=content, file_name=Path(selected).name)
            except Exception as e:
                st.error(str(e))


def tab_validate():
    server = st.session_state.server
    st.subheader("Validate Cilium Policy")
    yaml_files = [f for f in server.list_files("**/*.{yml,yaml}")]
    choice = st.selectbox("YAML file", options=[""] + yaml_files)
    if choice and st.button("Validate", type="primary"):
        try:
            res = server.validate_cilium_policy(choice)
            cols = st.columns(3)
            cols[0].metric("Kind", res.get("kind") or "-")
            cols[1].metric("Has Ingress", str(res.get("summary", {}).get("has_ingress")))
            cols[2].metric("Has Egress", str(res.get("summary", {}).get("has_egress")))
            if res.get("errors"):
                st.error("Errors:\n" + "\n".join(res["errors"]))
            if res.get("warnings"):
                st.warning("Warnings:\n" + "\n".join(res["warnings"]))
            with st.expander("Raw Result"):
                st.json(res)
        except Exception as e:
            st.error(str(e))


def tab_template():
    server = st.session_state.server
    st.subheader("Generate Policy Template")
    c1, c2 = st.columns(2)
    with c1:
        app = st.text_input("App", value="web")
        ns = st.text_input("Namespace", value="default")
    with c2:
        ingress_ports = st.text_input("Ingress ports (comma)", value="80/TCP,443/TCP")
        egress_fqdns = st.text_input("Egress FQDNs (comma)", value="*.amazonaws.com")
    if st.button("Generate", type="primary"):
        try:
            ports = [p.strip() for p in ingress_ports.split(",") if p.strip()]
            fqdns = [f.strip() for f in egress_fqdns.split(",") if f.strip()]
            yaml_txt = server.generate_policy_template(app=app, namespace=ns, ingress_ports=ports, egress_fqdns=fqdns)
            st.code(yaml_txt, language="yaml")
            st.download_button("Download YAML", data=yaml_txt, file_name=f"{app}-ztp.yaml")
        except Exception as e:
            st.error(str(e))


def tab_checklist():
    server = st.session_state.server
    st.subheader("Zero‑Trust Checklist")
    glob = st.text_input("Policy glob", value="**/*.{yml,yaml}")
    if st.button("Scan"):
        try:
            res = server.zero_trust_checklist(glob)
            stats = res.get("stats", {})
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Total", stats.get("total", 0))
            c2.metric("CNP", stats.get("cnp", 0))
            c3.metric("CCNP", stats.get("ccnp", 0))
            c4.metric("With L7", stats.get("with_l7", 0))
            c5.metric("DNS OK", stats.get("dns_ok", 0))
            st.dataframe(res.get("details", []), width="stretch")
        except Exception as e:
            st.error(str(e))


def tab_hubble():
    server = st.session_state.server
    st.subheader("Hubble Filters")
    c1, c2, c3 = st.columns(3)
    with c1:
        src = st.text_input("from")
    with c2:
        dst = st.text_input("to")
    with c3:
        verdict = st.selectbox("verdict", options=["", "FORWARDED", "DROPPED", "ERROR"], index=0)
    out = server.hubble_filters(src=src, dst=dst, verdict=verdict)
    st.code(out.get("cli", "hubble observe"), language="bash")
    with st.expander("JSON"):
        st.json(out)


def main():
    st.title("Draupnir MCP Server — Streamlit UI")
    init_state()
    sidebar_controls()

    tabs = st.tabs(["Files", "Validate", "Template", "Checklist", "Hubble"])
    with tabs[0]:
        tab_files()
    with tabs[1]:
        tab_validate()
    with tabs[2]:
        tab_template()
    with tabs[3]:
        tab_checklist()
    with tabs[4]:
        tab_hubble()


if __name__ == "__main__":
    main()
