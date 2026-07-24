# Latch

![Python](https://img.shields.io/badge/Python-3.13-blue)
![Terraform](https://img.shields.io/badge/Infrastructure-Terraform-purple)
![License](https://img.shields.io/badge/License-Apache%202.0-green)

## What is Latch?

Latch is an operational admissibility engine that determines whether cloud infrastructure is operationally safe to retire before destructive operations are permitted.

Rather than treating retirement as a direct execution request, Latch evaluates operational evidence to determine whether a registered environment is admissible for retirement.

This transforms infrastructure retirement from a permission check into an evidence-based operational reasoning problem.

The following architecture illustrates the separation between trusted admission, operational reasoning, authoritative state, and claim-fenced execution.

![Latch Architecture Overview](docs/assets/latch-architecture-overview.png)

---

## The Operational Problem

Cloud environments often remain running long after they are no longer needed because engineering teams cannot confidently prove that they are operationally safe to retire.

Traditional authorization systems answer:

> **"May this action be performed?"**

They do not answer:

> **"Should this environment be retired?"**

---

## Why IAM Is Not Enough

IAM determines whether a caller is permitted to perform an action.

It does not determine whether performing that action is operationally safe.

Authorization answers:

> **"May this action be performed?"**

Operational admissibility answers:

> **"Should this environment be retired?"**

Latch complements authorization by answering the second question before destructive operations are permitted.

---

## How Latch Reasons

A retirement request initiates an evidence-based operational evaluation rather than immediate infrastructure destruction.

The evaluation follows a deterministic workflow:

```text
Registered Environment
        │
        ▼
Retirement Claim
        │
        ▼
Owner Approval
        │
        ▼
Operational Evidence Collection
        │
        ▼
Evidence Admission
        │
        ▼
Operational Admissibility Evaluation
        │
        ▼
SAFE
UNSAFE
UNVERIFIABLE
        │
        ▼
Claim-Fenced Execution Authorization
        │
        ▼
EC2 Termination
        │
        ▼
Independent Destruction Confirmation
        │
        ▼
Confirmed Deregistration
```

Only a **SAFE** verdict permits execution.

**UNSAFE** and **UNVERIFIABLE** are valid operational outcomes that preserve registration state by preventing retirement.

Execution remains fenced by the active retirement claim and registered owner. Infrastructure state changes only after independent confirmation that destruction has occurred.

---

## Design Principles

- Evidence precedes execution.
- Operational admissibility is distinct from authorization.
- Destructive operations require deterministic operational reasoning.
- Registration state is preserved until destruction is independently confirmed.
- Operational reasoning is separated from cloud-provider implementation.

---

## Current Capability (v0.1.0)

- Registered EC2 environment retirement
- Retirement claims
- Owner approval
- Operational evidence collection
- Evidence admission
- Deterministic operational admissibility evaluation
- SAFE / UNSAFE / UNVERIFIABLE verdicts
- Claim-fenced execution
- Independent destruction confirmation
- Confirmed deregistration

---

## Scope

The initial release intentionally focuses on one complete retirement workflow.

Out of scope:

- Multi-cloud providers
- Non-EC2 infrastructure resources
- User interface
- Scheduling
- Automated discovery
- Recommendation generation

---

## Repository Structure

```text
src/
└── latch/
    ├── application/
    ├── domain/
    └── infrastructure/

tests/

infrastructure/
└── terraform/

docs/
└── architecture/
```

---

## Local Development

### Requirements

- Python 3.13
- uv
- Terraform
- AWS CLI (`aws configure`)
- Valid AWS credentials

Verify AWS credentials:

```bash
aws sts get-caller-identity
```

### Development Infrastructure

A minimal Terraform configuration is provided under:

```text
infrastructure/terraform/dev
```

Provision the development DynamoDB table:

```bash
cd infrastructure/terraform/dev

terraform init
terraform apply
```

Terraform outputs:

- AWS Region
- Active registration table name

### Install

```bash
uv sync --dev
```

### Configure

Linux/macOS

```bash
export LATCH_DYNAMODB_REGION="us-east-1"
export LATCH_ACTIVE_REGISTRATION_TABLE="latch-active-registrations-dev"
```

Windows PowerShell

```powershell
$env:LATCH_DYNAMODB_REGION="us-east-1"
$env:LATCH_ACTIVE_REGISTRATION_TABLE="latch-active-registrations-dev"
```

### Run

```bash
uv run uvicorn latch.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

---

## Production Deployment

Production deployments may use an existing externally managed DynamoDB table.

The application requires:

- `LATCH_DYNAMODB_REGION`
- `LATCH_ACTIVE_REGISTRATION_TABLE`

The production Terraform consumes an existing table rather than creating one.

---

## Validation

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest

terraform -chdir=infrastructure/terraform fmt -check
terraform -chdir=infrastructure/terraform validate

uv run pre-commit run --all-files
```

---

## Roadmap

Future releases will expand supported infrastructure resources, operational evidence, and execution workflows while preserving the evidence-first operational reasoning model established in v0.1.0.

---

## Project Status

**Version:** v0.1.0

Latch implements the first complete end-to-end operational admissibility workflow for cloud infrastructure retirement.

The project is under active development, with future releases expanding supported infrastructure resources while preserving the core operational reasoning model.

---

## License

Apache License 2.0