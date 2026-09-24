SHELL := /bin/bash
.DEFAULT_GOAL := help

BOOTSTRAP_COMPOSE := compose/bootstrap.yaml
CA_COMPOSE := compose/ca.yaml
TOOLS_IMAGE := supply-tools:m0-fabric3.1.5-ca1.5.22
BOOTSTRAP := docker compose -p supplyledger -f $(BOOTSTRAP_COMPOSE) --profile bootstrap
ALL_SERVICES := docker compose -p supplyledger -f $(BOOTSTRAP_COMPOSE) -f $(CA_COMPOSE) --profile bootstrap --profile ca

.PHONY: help tools-build doctor compose-config ca-config verify-m0 pki network-up channel-create chaincode-deploy app-up verify test-e2e test-fault backup restore stop down reset

help:
	@printf '%s\n' \
	  'M0: tools-build, doctor, compose-config, verify-m0' \
	  'M1: ca-config; stop, down, reset cover all declared CA services and volumes' \
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
	$(ALL_SERVICES) config --quiet
	@printf '%s\n' 'PASS: M1 CA Compose config; formal network Compose NOT RUN'

verify-m0:
	bash scripts/verify-m0.sh

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
