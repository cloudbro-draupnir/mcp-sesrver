# Draupnir MCP Server (Cilium Zero‑Trust edition)

**목표:** Cilium 기반 Zero Trust 레퍼런스(예: Draupnir)의 구성을 다루는 정적 MCP 서버. `data/` 폴더의 YAML/MD/코드들을 **리소스**로 노출하고, Cilium 네트워크 정책(CNP/CCNP)을 위한 **검증/템플릿/체크리스트/허블 필터** 생성 **툴**과 **프롬프트**를 제공.

## Quick start (uv)
```bash
uv python install 3.12
uv sync

# 샘플 데이터
mkdir -p data && echo "apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: allow-dns
spec:
  endpointSelector: {}
  egress:
  - toEndpoints:
    - matchLabels: {k8s:io.kubernetes.pod.namespace: kube-system}
    toPorts:
    - ports: [{ port: \"53\", protocol: UDP }]
" > data/allow-dns.yaml

# stdio 실행
uv run draupnir-mcp-server
```

## Draupnir 리포지토리 가져오기
두 가지 방식을 지원합니다.

**A) ZIP 기반 (권장: 빠르게 시도할 때)**
```bash
# ZIP 지정 (예: /mnt/data/draupnir-main.zip)
make import ZIP=/absolute/path/to/draupnir.zip
# 또는
uv run cnp-ingest --zip /absolute/path/to/draupnir.zip --dest data
```

**B) Git submodule 기반 (권장: 업스트림을 지속 추적할 때)**
```bash
# 프로젝트 루트에서
make submodule-add SUBMODULE_URL=https://github.com/cloudbro-draupnir/draupnir.git SUBMODULE_PATH=vendor/draupnir
# 최신 반영
make submodule-update SUBMODULE_PATH=vendor/draupnir
# 정책/샘플을 data/에 동기화하고 싶다면 (필요 시 rsync 등 후처리 추가)
#   rsync -av vendor/draupnir/policies/ data/policies/
```

> ZIP은 간편함, 서브모듈은 장기 유지/동기화에 유리합니다. 두 방법을 혼용해도 무방합니다.

## MCP 클라이언트 설정 예시 (Claude Desktop)
`~/Library/Application Support/Claude/mcp.json`:
```json
{
  "mcpServers": {
    "draupnir-mcp-server": {
      "command": "uv",
      "args": ["run", "draupnir-mcp-server"],
      "env": { "STATIC_MCP_DATA_DIR": "${HOME}/path/to/project/data" }
    }
  }
}
```

## 제공 기능
- **Resources**: `data/`의 파일들을 `file://` URI로 노출
- **Tools**
  - `list_files(pattern)`
  - `read_text(path)` / `search_text(query, glob)`
  - `healthcheck()`
  - `list_cilium_policies(glob)` — CNP/CCNP만 필터링
  - `validate_cilium_policy(path)` — 필수 필드/안전성 경고
  - `generate_policy_template(app, namespace, ...)` — Zero‑Trust 템플릿
  - `hubble_filters(src, dst, verdict)` — 허블 관측 스니펫
  - `zero_trust_checklist(glob)` — ZT posture 요약
- **Prompts**
  - `hardening-review` — 하드닝 리뷰 가이드
  - `write-cilium-policy` — 신규 서비스 정책 템플릿

### 대시보드/가이드 참고
- Grafana: Cilium Policy Verdicts (ID 18015)
- Isovalent Labs: Cilium Zero‑Trust Visibility

## HTTP/SSE 모드 (옵션)
```bash
uv run draupnir-mcp-server --http 0.0.0.0:8765
```

## Streamlit UI (옵션)
```bash
make setup          # ensure deps
make ui             # launches Streamlit at http://localhost:8501
```
환경 변수 `STATIC_MCP_DATA_DIR`를 UI 사이드바에서 설정/로드할 수 있습니다.

## Makefile
자동화 타깃 포함: `setup`, `run`, `run-http`, `lint`, `import`, `submodule-add`, `submodule-update`, `sample`, `client-config`, `package`, `clean`


## Kubernetes 통합
`.kube/config`가 이미 설정되어 있고, `kubectl config use-context <CTX>`로 컨텍스트를 전환했다고 가정합니다.

### MCP 툴
- `k8s_context()` : 현재 컨텍스트 확인
- `k8s_cluster_info()` : `kubectl cluster-info` + `kubectl get nodes -o wide`
- `k8s_service_accounts(all_namespaces=True)` : `kubectl get sa -A -o json` 요약

### Make 타깃 (kubectl 전제)
```bash
make kctx CONTEXT=gke_reflecting-surf-472800-e7_asia-northeast2-a_cluster2   # 컨텍스트 전환
make kinfo                                                                  # cluster-info + nodes
make ksa                                                                    # SA 요약 (전 네임스페이스)
# (옵션) Hubble CLI가 설치되어 있다면
make kverdicts VERDICT=DROPPED DURATION=30s                                 # 최근 verdict 관측
```

## Developer Examples
Quick dev usage (direct import):
```bash
export STATIC_MCP_DATA_DIR=data
python - <<'PY'
from draupnir_mcp_server import server
print(server.list_files("**/*.yaml")[:3])
print(server.validate_cilium_policy("allow-dns.yaml")["warnings"])
PY
```

Template test example (pytest):
```python
def test_my_tool(tmp_path, monkeypatch):
    import os, importlib
    os.environ["STATIC_MCP_DATA_DIR"] = str(tmp_path / "data")
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    server = importlib.reload(importlib.import_module("draupnir_mcp_server.server"))
    # result = server.my_tool(...)
    # assert result == expected
```

## Contributing
- Contributor guide: see `AGENTS.md` for project structure, commands, style, and examples.
- Examples: see “MCP Tools & Examples” and “Testing Guidelines” sections in `AGENTS.md`.
