SHELL := /bin/bash
.DEFAULT_GOAL := help

BOOTSTRAP_COMPOSE := compose/bootstrap.yaml
CA_COMPOSE := compose/ca.yaml
NETWORK_COMPOSE := compose/network.yaml
TOOLS_IMAGE := supply-tools:m0-fabric3.1.5-ca1.5.22
M1_RUNTIME_DIR ?= .runtime
M2_CHANNEL_DIR ?= .runtime/channel
M2_SOURCE_RUNTIME_DIR ?= .runtime
M2_OUTPUT_RUNTIME_DIR ?= .runtime
M2_SECRETS_DIR ?= .secrets
M2_INSPECT_BLOCK ?=
BOOTSTRAP := docker compose -p supplyledger -f $(BOOTSTRAP_COMPOSE) --profile bootstrap
CA_SERVICES := docker compose -p supplyledger -f $(BOOTSTRAP_COMPOSE) -f $(CA_COMPOSE) --profile bootstrap --profile ca
ALL_SERVICES := docker compose -p supplyledger -f $(BOOTSTRAP_COMPOSE) -f $(CA_COMPOSE) -f $(NETWORK_COMPOSE) --profile bootstrap --profile ca

.PHONY: help tools-build doctor compose-config ca-config network-config test-m2-compose verify-m2-initial-block prepare-m2-nodes verify-m2-nodes verify-m2-node-block test-m2-nodes verify-m0 verify-m1 verify-m1-tls pki network-up channel-create chaincode-deploy app-up verify test-e2e test-fault backup restore stop down reset

help:
	@printf '%s\n' \
	  'M0: tools-build, doctor, compose-config, verify-m0' \
	  'M1: ca-config, verify-m1, verify-m1-tls; stop, down, reset retain declared data volumes' \
	  'M2: network-config/test-m2-compose check topology; verify-m2-initial-block audits NET-03' \
	  'M2: prepare-m2-nodes renders ignored node inputs; verify-m2-nodes/test-m2-nodes check them' \
	  'Later stages: pki (M1), network-up/channel-create (M2), chaincode-deploy (M3),' \
	  'app-up (M6), verify/test-e2e (M3+), test-fault/backup/restore (M9).' \
	  'Later-stage targets exit with NOT RUN until their native first-run steps are recorded.'

tools-build:
	docker buildx build --load -t $(TOOLS_IMAGE) -f docker/tools/Dockerfile docker/tools

doctor:
	bash scripts/doctor.sh

compose-config:
	$(BOOTSTRAP) config --quiet
	@printf '%s\n' 'PASS: M0 bootstrap Compose config; formal network Compose NOT RUN'

ca-config:
	$(CA_SERVICES) config --quiet
	@printf '%s\n' 'PASS: M1 CA Compose config; use network-config for the M2 overlay'

network-config:
	$(ALL_SERVICES) config --no-env-resolution --quiet
	python3 scripts/verify-m2-compose.py

test-m2-compose:
	python3 scripts/test-verify-m2-compose.py

verify-m2-initial-block:
	python3 scripts/verify-m2-initial-block.py --inspect-block "$(M2_CHANNEL_DIR)/inspect-block.json" --m1-runtime-dir "$(abspath $(M1_RUNTIME_DIR))" --consenter-certs "$(M2_CHANNEL_DIR)/consenter-certs"

prepare-m2-nodes:
	python3 scripts/prepare-m2-nodes.py prepare --m1-runtime "$(M2_SOURCE_RUNTIME_DIR)" --output-runtime "$(M2_OUTPUT_RUNTIME_DIR)" --secrets-dir "$(M2_SECRETS_DIR)"

verify-m2-nodes:
	python3 scripts/prepare-m2-nodes.py verify --m1-runtime "$(M2_SOURCE_RUNTIME_DIR)" --output-runtime "$(M2_OUTPUT_RUNTIME_DIR)" --secrets-dir "$(M2_SECRETS_DIR)"

verify-m2-node-block:
	@test -n "$(M2_INSPECT_BLOCK)" || { printf '%s\n' 'NOT RUN: set M2_INSPECT_BLOCK to the native #17 inspect-block.json path' >&2; exit 2; }
	python3 scripts/prepare-m2-nodes.py verify --m1-runtime "$(M2_SOURCE_RUNTIME_DIR)" --output-runtime "$(M2_OUTPUT_RUNTIME_DIR)" --secrets-dir "$(M2_SECRETS_DIR)" --inspect-block "$(M2_INSPECT_BLOCK)"

test-m2-nodes:
	python3 scripts/test-prepare-m2-nodes.py --m1-runtime "$(M2_SOURCE_RUNTIME_DIR)" $(if $(M2_INSPECT_BLOCK),--inspect-block "$(M2_INSPECT_BLOCK)")

verify-m0:
	bash scripts/verify-m0.sh

verify-m1:
	@set -o pipefail; M1_RUNTIME_DIR="$(abspath $(M1_RUNTIME_DIR))" python3 scripts/inspect-local-certs.py | cmp - evidence/m1/issue-10-certificates.csv
	@printf '%s\n' 'PASS: 41 local certificate rows match the committed M1 inventory'
	@M1_RUNTIME_DIR="$(abspath $(M1_RUNTIME_DIR))" python3 scripts/assemble-msps.py verify
	@$(MAKE) --no-print-directory verify-m1-tls M1_RUNTIME_DIR="$(abspath $(M1_RUNTIME_DIR))"
	@printf '%s\n' 'M1 static identity, MSP, and TLS verification: PASS; live network tests NOT RUN'

verify-m1-tls:
	python3 scripts/verify-m1-tls-trust.py --runtime-dir "$(M1_RUNTIME_DIR)"

define unavailable
	@printf 'NOT RUN: make %s belongs to %s; complete the native first-run steps in SPEC.md §19 before automation.\n' '$@' '$(1)' >&2; exit 2
endef

pki:
	$(call unavailable,M1)

network-up channel-create:
	$(call unavailable,M2)

chaincode-deploy:
	$(call unavailable,M3)

app-up:
	$(call unavailable,M6)

verify test-e2e:
	$(call unavailable,M3 and later)

test-fault backup restore:
	$(call unavailable,M9)

stop:
	$(ALL_SERVICES) stop

down:
	$(ALL_SERVICES) down

reset:
	bash scripts/reset.sh
