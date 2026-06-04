# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What This Is

`terraform-drift-analyzer` — a Claude Agent Skill that detects drift between Terraform `*.tf` declarations and live AWS resources. It produces a single `report.md` with a Mermaid architecture diagram and drift findings.

See [PLAN.md](PLAN.md) for full specifications and schemas.

---

## Setup

```bash
pip install python-hcl2 pytest
```

Intermediate files write to `./drift-workspace/` (auto-created, gitignored).

---

## Running Scripts

```bash
# 1. Parse Terraform files → drift-workspace/T.json + architecture.mmd
python3 terraform-drift-analyzer/scripts/terraform_parser.py <tf_dir>

# 2a. Generate AWS MCP discovery plan
python3 terraform-drift-analyzer/scripts/aws_discovery.py drift-workspace/T.json plan

# 2b. Normalize MCP responses → drift-workspace/A.json
python3 terraform-drift-analyzer/scripts/aws_discovery.py drift-workspace/T.json normalize <mcp_response.json>

# 3. Compare declared vs actual → drift-workspace/diff.json
python3 terraform-drift-analyzer/scripts/drift_detector.py drift-workspace/T.json drift-workspace/A.json

# 4. Generate final report → report.md
python3 terraform-drift-analyzer/scripts/report_generator.py drift-workspace/diff.json drift-workspace/architecture.mmd
```

## Running Tests

```bash
pytest tests/ -v                          # all tests
pytest tests/test_terraform_parser.py -v  # one script
```

---

## Pipeline Architecture

```
*.tf files
    ↓ terraform_parser.py  → T.json + architecture.mmd
    ↓ aws_discovery.py     → A.json  (via AWS MCP — no boto3)
    ↓ drift_detector.py    → diff.json
    ↓ report_generator.py  → report.md  ← only file shown to user
```

Scripts 1–3 are purely deterministic Python. `aws_discovery.py` structures MCP queries and normalizes responses — Claude executes the actual MCP calls.

---

## Hard Constraints

- **No boto3, no AWS CLI** anywhere. AWS access is AWS MCP only.
- **`report.md` is the only user-facing output.** Everything in `drift-workspace/` is internal.
- **No `.tfstate` parsing.** Comparison is declaration vs live AWS state only.
- **Use `python-hcl2`** for HCL parsing — not regex, not string splitting.

---

## Supported Resource Types (v1 — fixed scope)

| Terraform Type | AWS Resource |
|---|---|
| `aws_instance` | EC2 Instances |
| `aws_s3_bucket` | S3 Buckets |
| `aws_iam_role` | IAM Roles |
| `aws_iam_user` | IAM Users |
| `aws_iam_policy` | IAM Policies |
| `aws_security_group` | Security Groups |

Do not add more types. Do not add boto3 fallback.

---

## Drift Statuses

| Status | Meaning |
|---|---|
| `matched` | In .tf and in AWS, config agrees |
| `missing` | In .tf but not found in AWS |
| `unmanaged` | In AWS but not in .tf |
| `mismatched` | In both but config fields differ |

---

## Code Standards

- All scripts: `argparse` CLI, `if __name__ == "__main__":`, progress to stdout, errors to stderr
- Exit code 1 on any failure — never raise unhandled exceptions
- Error format: `ERROR: <description>: <detail>` — see PLAN.md for exact strings
- JSON output: `indent=2`, written to `drift-workspace/`
- Missing optional fields → `None` in output (not omitted)
- Variable interpolations → `{"value": "<variable: var.foo>", "type": "unresolved"}`

---

## Out of Scope

- `.tfstate` files, multi-cloud, remote module resolution
- Security/compliance auditing, remediation suggestions
- AWS resources beyond the 6 types above
