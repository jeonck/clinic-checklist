# Local jev (open-jev) wrapper. Apple silicon only (MLX). Add open-jev/ to .gitignore.
OPENJEV ?= open-jev
MODEL   ?= models/gemma-3-4b-it-4bit
HF_REPO ?= mlx-community/gemma-3-4b-it-4bit
PORT    ?= 8000

.PHONY: help setup serve health

help:
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

setup: ## clone open-jev, create venv, download $(HF_REPO)
	@test -d $(OPENJEV) || git clone --depth 1 https://github.com/daseinlabs/open-jev $(OPENJEV)
	$(MAKE) -C $(OPENJEV) setup MODEL=$(MODEL) HF_REPO=$(HF_REPO)

serve: ## start jev server on :$(PORT)  (POST /v1/systemone, GET /health)
	$(MAKE) -C $(OPENJEV) serve MODEL=$(MODEL) PORT=$(PORT)

health: ## check the server
	@curl -s localhost:$(PORT)/health; echo

.PHONY: validate test eval
validate: ## checklist library, draft mode (drop --allow-unverified for production)
	python3 scripts/validate_checklist.py checklists/ --allow-unverified
test: ## unit tests, no server needed
	python3 -m pytest -q tests/
eval: ## run eval set against the local server
	python3 eval/run.py --model jev-1.13.0 --cases eval/cases/ --out eval/results/$$(date +%F).json
