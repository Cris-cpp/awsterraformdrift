# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

`terraform-drift-analyzer` — a Claude Agent Skill detecting drift between Terraform `*.tf` declarations and live AWS resources. Produces a single `report.md` with a Mermaid diagram and drift findings.

Full specifications and JSON schemas: [PLAN.md](PLAN.md)

## Setup

```bash
pip install python-hcl2 pytest
```

Intermediate files go to `./drift-workspace/` (auto-created, gitignored).

## Commands

```bash
# Parse .tf files
python3 terraform-drift-analyzer/scripts/terraform_parser.py <tf_dir>

# Generate AWS MCP discovery plan
python3 terraform-drift-analyzer/scripts/aws_discovery.py drift-workspace/T.json plan

# Normalize MCP responses → A.json
python3 terraform-drift-analyzer/scripts/aws_discovery.py drift-workspace/T.json normalize <mcp_response.json>

# Compare declared vs actual → diff.json
python3 terraform-drift-analyzer/scripts/drift_detector.py drift-workspace/T.json drift-workspace/A.json

# Generate report.md
python3 terraform-drift-analyzer/scripts/report_generator.py drift-workspace/diff.json drift-workspace/architecture.mmd

# Run tests
pytest tests/ -v
```

## Pipeline

```
*.tf files → terraform_parser.py → T.json + architecture.mmd
                                 ↓
              aws_discovery.py → A.json  (AWS MCP only — no boto3)
                                 ↓
              drift_detector.py → diff.json
                                 ↓
           report_generator.py → report.md  ← only user-facing output
```

## Hard Constraints

- **No boto3, no AWS CLI.** AWS access via AWS MCP only.
- **`report.md` is the only output shown to users.** `drift-workspace/` is internal.
- **No `.tfstate`.** Declaration vs live AWS state only.
- **`python-hcl2` for HCL parsing** — not regex.

## Supported Resource Types (v1 — fixed)

| Terraform | AWS |
|---|---|
| `aws_instance` | EC2 |
| `aws_s3_bucket` | S3 |
| `aws_iam_role` | IAM Role |
| `aws_iam_user` | IAM User |
| `aws_iam_policy` | IAM Policy |
| `aws_security_group` | Security Group |

## Drift Statuses

`matched` · `missing` · `unmanaged` · `mismatched` — see PLAN.md for definitions.

## Code Standards

- `argparse` CLI, `if __name__ == "__main__":`, progress → stdout, errors → stderr
- Exit code 1 on failure, never unhandled exceptions
- JSON output: `indent=2` to `drift-workspace/`
- Missing optional fields → `None`, not omitted

## Out of Scope

`.tfstate`, multi-cloud, remote modules, compliance auditing, remediation, resources beyond the 6 types above.
