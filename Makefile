# Production text-to-SQL on AWS — build/deploy/test entrypoints.
# Recipes are single commands so they work with GNU make on Linux/macOS and
# with GnuWin32 make on Windows (cmd or sh). Requires: make, terraform, aws CLI, python 3.12.
ENV ?= dev
REGION ?= us-east-1
AWS_PROFILE ?= banking
ifeq ($(strip $(AWS_PROFILE)),)
AWS_PROFILE := banking
endif
export AWS_PROFILE
ACCOUNT_ID := $(shell aws --profile $(AWS_PROFILE) sts get-caller-identity --query Account --output text)
TF := terraform -chdir=terraform/envs/$(ENV)

.PHONY: help init plan apply build deploy refresh glossary smoke evaluate test fmt lint typecheck scan clean

help:
	@echo "targets: init plan apply build deploy refresh smoke evaluate test fmt lint typecheck scan clean"

init:
	$(TF) init -backend-config="bucket=text2sql-$(ENV)-tfstate-$(ACCOUNT_ID)" -backend-config="key=$(ENV)/terraform.tfstate" -backend-config="region=$(REGION)" -backend-config="dynamodb_table=text2sql-$(ENV)-tfstate-lock" -backend-config="encrypt=true" -backend-config="use_lockfile=true"

plan:
	$(TF) plan

apply:
	$(TF) apply

build:
	python scripts/build_lambdas.py

deploy: build plan
	$(TF) apply

refresh:
	python scripts/refresh.py --env $(ENV)

glossary:
	python scripts/upload_glossary.py --env $(ENV)

smoke:
	python scripts/smoke_test.py --env $(ENV)

evaluate:
	python scripts/run_evaluation.py --env $(ENV)

test:
	python -m pytest -q

fmt:
	terraform fmt -recursive
	python -m ruff format src scripts tests

lint:
	python -m ruff check src scripts tests

typecheck:
	python -m mypy src scripts

scan:
	python -m checkov -d terraform

clean:
	python -c "import shutil; [shutil.rmtree(d, ignore_errors=True) for d in ('build','dist','.ruff_cache','.mypy_cache','.pytest_cache')]"
