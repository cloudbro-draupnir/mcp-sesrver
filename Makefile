\
# Draupnir MCP Server (Cilium / Zero-Trust)

PROJECT ?= draupnir-mcp-server
DATA_DIR ?= data
ZIP ?=

.PHONY: help setup run run-http lint import sample clean client-config submodule-add submodule-update package ui

help:
	@echo "$(PROJECT) — targets:"
	@echo "  setup          Install deps with uv"
	@echo "  run            Run MCP over stdio"
	@echo "  run-http       Run MCP over HTTP/SSE (port 8765)"
	@echo "  ui             Launch Streamlit UI (ui/app.py)"
	@echo "  import         Import Draupnir ZIP into $(DATA_DIR) (use ZIP=/path.zip)"
	@echo "  submodule-add  Add git submodule (SUBMODULE_URL=… SUBMODULE_PATH=vendor/draupnir)"
	@echo "  submodule-update Update/init the submodule (SUBMODULE_PATH=vendor/draupnir)"
	@echo "  sample         Add sample CNPs"
	@echo "  lint           Ruff lint"
	@echo "  client-config  Print Claude MCP JSON snippet"
	@echo "  package        Build distributable zip at dist/"
	@echo "  clean          Remove $(DATA_DIR)"

setup:
	uv python install 3.12
	uv sync

run:
	uv run draupnir-mcp-server

run-http:
	uv run draupnir-mcp-server --http 0.0.0.0:8765

lint:
	uv run ruff check .

ui:
	uv run streamlit run ui/app.py

import:
	@if [ -z "$(ZIP)" ]; then echo "ZIP=/absolute/path/to/draupnir.zip required"; exit 1; fi
	uv run cnp-ingest --zip $(ZIP) --dest $(DATA_DIR)

submodule-add:
	@if [ -z "$(SUBMODULE_URL)" ]; then echo "SUBMODULE_URL is required"; exit 1; fi
	@if [ -z "$(SUBMODULE_PATH)" ]; then echo "SUBMODULE_PATH is required"; exit 1; fi
	git submodule add $(SUBMODULE_URL) $(SUBMODULE_PATH) || true
	git submodule update --init --recursive $(SUBMODULE_PATH)

submodule-update:
	@if [ -z "$(SUBMODULE_PATH)" ]; then echo "SUBMODULE_PATH is required"; exit 1; fi
	git submodule update --init --recursive $(SUBMODULE_PATH)

sample:
	mkdir -p $(DATA_DIR)
	@echo "apiVersion: cilium.io/v2\nkind: CiliumNetworkPolicy\nmetadata:\n  name: demo-allow-web\n  namespace: default\nspec:\n  endpointSelector: {matchLabels: {app: web}}\n  ingress:\n  - fromEndpoints: [{matchLabels: {app: web}}]\n    toPorts: [{ports: [{port: \"80\", protocol: TCP}]}]\n  egress:\n  - toFQDNs: [{matchName: \"example.com\"}]\n" > $(DATA_DIR)/demo-allow-web.yaml
	@echo "Wrote $(DATA_DIR)/demo-allow-web.yaml"

client-config:
	@echo '{\n  "mcpServers": {\n    "draupnir-mcp-server": {\n      "command": "uv",\n      "args": ["run", "draupnir-mcp-server"],\n      "env": { "STATIC_MCP_DATA_DIR": "$$PWD/$(DATA_DIR)" }\n    }\n  }\n}'

package:
	@mkdir -p dist
	@zip -r dist/$(PROJECT).zip pyproject.toml README.md Makefile src $(DATA_DIR) >/dev/null
	@echo "Built dist/$(PROJECT).zip"

clean:
	rm -rf $(DATA_DIR)


# --- Kubernetes helpers ---
.PHONY: kctx kinfo ksa kverdicts

kctx:
	@if [ -z "$(CONTEXT)" ]; then echo "CONTEXT is required"; exit 1; fi
	kubectl config use-context $(CONTEXT)

kinfo:
	kubectl cluster-info || true
	kubectl get nodes -o wide || true

ksa:
	kubectl get sa -A -o wide || true

kverdicts:
	@which hubble >/dev/null 2>&1 || (echo "hubble CLI not found"; exit 1)
	@D="$(DURATION)"; if [ -z "$$D" ]; then D="15s"; fi; \
	V="$(VERDICT)"; if [ -n "$$V" ]; then V="--verdict $$V"; fi; \
	hubble observe $$V --since $$D | head -n 200


test:
	uv run pytest
