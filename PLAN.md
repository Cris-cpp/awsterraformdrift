# Terraform Drift Analyzer — Build Plan

## Overview

Build a Claude skill that detects infrastructure drift between declared Terraform
config (*.tf files) and live AWS resources, producing a single report.md with an
embedded Mermaid architecture diagram.

---

## Quick Reference

| Script | Input | Output | Purpose |
|--------|-------|--------|---------|
| `terraform_parser.py` | `.tf` files (directory) | `T.json` + `architecture.mmd` | Parse Terraform declarations into structured JSON + generate architecture diagram |
| `aws_discovery.py` | `T.json` | `A.json` (after MCP queries) | Fetch live AWS resources via AWS MCP, normalize into JSON |
| `drift_detector.py` | `T.json` + `A.json` | `diff.json` | Compare declared vs actual, identify matched/missing/unmanaged/mismatched resources |
| `report_generator.py` | `diff.json` + `architecture.mmd` | `report.md` | Format final user-facing report with Mermaid diagram and findings table |

**Pipeline flow:** `.tf files` → `T.json` → (AWS MCP) → `A.json` → `diff.json` → `report.md`

---

## Folder Structure to Create

```
terraform-drift-analyzer/
├── SKILL.md
├── scripts/
│   ├── terraform_parser.py
│   ├── aws_discovery.py
│   ├── drift_detector.py
│   └── report_generator.py
├── references/
│   └── usage.md
└── assets/
```

---

## Build Order

Build in this exact order. Do not skip ahead.

1. `scripts/terraform_parser.py`
2. `scripts/aws_discovery.py`
3. `scripts/drift_detector.py`
4. `scripts/report_generator.py`
5. `references/usage.md`
6. `SKILL.md`

---

## Script Specifications

### 1. terraform_parser.py

**Purpose:** Parse *.tf files into a structured JSON representation + generate a Mermaid diagram.

**Input:**
- Path to a directory containing *.tf files (passed as CLI arg)
- Must handle multi-file projects and `module {}` blocks (traverse full directory)

**Output:**
- `T.json` — structured resource list (see schema below)
- `architecture.mmd` — raw Mermaid diagram string (internal, used by report_generator)

**T.json schema:**
```json
{
  "resources": [
    {
      "type": "aws_instance",
      "name": "web_server",
      "config": {
        "instance_type": "t3.micro",
        "ami": "ami-0abcdef1234567890",
        "tags": { "Name": "web_server" }
      }
    }
  ],
  "modules": [
    {
      "name": "vpc_module",
      "source": "./modules/vpc",
      "resources": []
    }
  ]
}
```

**Supported resource types to parse:**
- `aws_instance`
- `aws_s3_bucket`
- `aws_iam_role`, `aws_iam_user`, `aws_iam_policy`
- `aws_security_group`

**Mermaid output format:**
- Use `graph TD` (top-down) layout
- Show each resource as a node with format: `ResourceType_name[label: Type: name]`
- Draw edges based on explicit references between resources:
  - `aws_instance` → `aws_security_group` (via `vpc_security_group_ids`, `security_groups`)
  - `aws_instance` → `aws_s3_bucket` (via `iam_instance_profile` IAM permissions)
  - `aws_iam_role` → `aws_iam_policy` (via `assume_role_policy`)
  - Any resource → referenced resource (via interpolations: `aws_X.name.id`)
- Label nodes with resource type + name (e.g., `EC2_web[EC2: web_server]`)
- If a reference cannot be resolved (resource not in project), skip that edge
- Example:
  ```mermaid
  graph TD
    EC2_web[EC2: web_server]
    SG_allow[SG: allow_web]
    EC2_web --> SG_allow
  ```

**Rules:**
- Deterministic — same input always produces same output
- Must handle missing/optional fields gracefully (use null, not exceptions)
- Use Python's `python-hcl2` library for HCL parsing
- Must handle variable interpolations (mark as `"<variable>"` if unresolvable)

**Edge cases:**
- **Duplicate resource names:** If two resources have the same type and name in different files, use only the first occurrence (deterministic). Log a warning to stdout.
- **Unresolvable variables:** Variables like `var.instance_type`, `local.tags`, `module.vpc.id` that cannot be resolved should be marked as `{"value": "<variable>", "type": "unresolved"}` in the output
- **Missing optional fields:** Fields like `tags`, `description` should be `null` if not present, not omitted from JSON
- **Module references:** Record module name, source path, and any resources declared within (even if source is remote/external)
- **Invalid HCL syntax:** Exit with code 1 and message: `"ERROR: Invalid HCL syntax in <filename>: <python-hcl2 error>"`
- **No .tf files found:** Exit with code 1 and message: `"ERROR: No .tf files found in <directory>"`

---

### 2. aws_discovery.py

**Purpose:** Read T.json and produce a structured A.json of live AWS resources.

**Input:**
- `T.json` (path as CLI arg)
- AWS access via AWS MCP (Claude handles MCP calls — this script structures the input/output)

**Output:**
- `A.json` — live AWS resources (same schema structure as T.json resources array)

**How it works:**
- Reads T.json to determine which resource types to look up
- For each resource type present in T.json, outputs a discovery plan (list of MCP queries needed)
- After Claude executes MCP queries and returns results, script normalizes the raw MCP response into A.json

**A.json schema:**
```json
{
  "resources": [
    {
      "type": "aws_instance",
      "id": "i-0abc123def456",
      "name": "web_server",
      "config": {
        "instance_type": "t3.micro",
        "state": "running",
        "tags": { "Name": "web_server" }
      }
    }
  ]
}
```

**Resource matching strategy:**
- Primary: match Terraform resource `name` → AWS resource `Name` tag
- Fallback: match via `terraform:resource` tag on AWS resource
- If neither matches: resource is flagged as unmanaged

**AWS MCP queries needed per resource type:**
- `aws_instance` → describe EC2 instances with all tags
- `aws_s3_bucket` → list S3 buckets + get tagging for each
- `aws_iam_role` / `aws_iam_user` / `aws_iam_policy` → list IAM entities
- `aws_security_group` → describe security groups with all tags

**Rules:**
- Deterministic — given the same MCP response, always produces same A.json
- Do not call AWS directly (no boto3, no AWS CLI)

**Error handling:**
- **AWS MCP not connected:** Exit with code 1 and message: `"ERROR: AWS MCP is not connected. Please connect AWS MCP before running this skill."`
- **Invalid T.json:** Exit with code 1 and message: `"ERROR: Invalid or missing T.json: <parse error>"`
- **MCP query timeout:** Exit with code 1 and message: `"ERROR: AWS MCP query timed out. Check AWS MCP connection and try again."`
- **No resources requested:** If T.json has no resources, exit with code 1 and message: `"ERROR: No resources found in T.json"`

**Edge cases:**
- **Resource not found in AWS:** Create resource entry in A.json with status `"not_found"` (used by drift_detector)
- **Duplicate AWS resources:** If multiple AWS resources have the same `Name` tag, include all in A.json (drift_detector will flag as ambiguous)
- **Empty tag lists:** If an AWS resource has no tags, set `tags: {}` (not null)
- **Resource ID formats:** Always normalize AWS resource IDs (e.g., EC2 instance ID format: `i-0abc123def456`)

---

### 3. drift_detector.py

**Purpose:** Compare T.json and A.json and produce diff.json.

**Input:**
- `T.json` (path as CLI arg)
- `A.json` (path as CLI arg)

**Output:**
- `diff.json`

**diff.json schema:**
```json
{
  "summary": {
    "total_declared": 5,
    "total_found": 4,
    "total_missing": 1,
    "total_unmanaged": 2,
    "total_mismatched": 1
  },
  "findings": [
    {
      "resource_type": "aws_instance",
      "resource_name": "web_server",
      "status": "mismatched",
      "declared": { "instance_type": "t3.micro" },
      "actual": { "instance_type": "t3.large" },
      "drift_fields": ["instance_type"]
    },
    {
      "resource_type": "aws_s3_bucket",
      "resource_name": "logs_bucket",
      "status": "missing",
      "declared": { "bucket": "my-logs-bucket" },
      "actual": null,
      "drift_fields": []
    },
    {
      "resource_type": "aws_instance",
      "resource_name": "old_worker",
      "status": "unmanaged",
      "declared": null,
      "actual": { "instance_type": "t2.medium" },
      "drift_fields": []
    }
  ]
}
```

**Drift status definitions:**
- `matched` — declared in .tf and found in AWS, config agrees
- `missing` — declared in .tf but NOT found in AWS
- `unmanaged` — found in AWS but NOT in .tf
- `mismatched` — found in both but one or more config fields differ

**Fields to compare per resource type:**
- `aws_instance`: instance_type, ami, tags
- `aws_s3_bucket`: bucket name, tags
- `aws_iam_role`: assume_role_policy, tags
- `aws_iam_user`: path, tags
- `aws_iam_policy`: policy document, tags
- `aws_security_group`: ingress rules, egress rules, tags

**Rules:**
- Deterministic — same T.json + A.json always produces same diff.json
- Ignore fields not in the comparison list above
- Tag comparison: only compare tags that exist in the Terraform declaration

**Error handling:**
- **Invalid T.json:** Exit with code 1 and message: `"ERROR: Invalid T.json: <parse error>"`
- **Invalid A.json:** Exit with code 1 and message: `"ERROR: Invalid A.json: <parse error>"`
- **Both files empty:** Exit with code 1 and message: `"ERROR: No resources in T.json or A.json"`

**Edge cases:**
- **Resource name conflicts:** If Terraform has two resources with same type+name in different files, use the first parsed (consistent with terraform_parser behavior)
- **Missing fields in config:** Null or missing fields should not cause status change; only explicitly different values trigger `mismatched` status
- **Tag comparison:** Only compare tags present in Terraform declaration. If AWS has extra tags, ignore them. If Terraform declares a tag missing in AWS, flag as `mismatched`.
- **Numeric field comparison:** Convert all numeric fields to strings for comparison (HCL and AWS may differ in representation)
- **Empty resource lists:** If both T.json and A.json have zero resources, create diff.json with empty findings array and all counts = 0

---

### 4. report_generator.py

**Purpose:** Read diff.json + architecture.mmd and produce the final report.md.

**Input:**
- `diff.json` (path as CLI arg)
- `architecture.mmd` (path as CLI arg)

**Output:**
- `report.md`

**report.md structure:**
```markdown
# Terraform Drift Report
Generated: <timestamp>

## Architecture

```mermaid
<contents of architecture.mmd>
```

## Summary

| Metric | Count |
|--------|-------|
| Total Declared | 5 |
| Total Found | 4 |
| Missing | 1 |
| Unmanaged | 2 |
| Mismatched | 1 |

## Drift Findings

### EC2 Instances
- ✅ web_server — matched
- ❌ api_server — missing in AWS
- ⚠️ worker — mismatched (instance_type: declared t3.micro, actual t3.large)

### S3 Buckets
...

### IAM
...

### Security Groups
...

## Unmanaged Resources
Resources found in AWS not declared in Terraform:
- EC2: old_worker (i-0abc123def456)
```

**Status icons:**
- ✅ matched
- ❌ missing
- ⚠️ mismatched
- 🔍 unmanaged

**Rules:**
- Keep prose minimal — DevOps audience, terse and factual
- Always include the summary table at the top
- Group findings by resource type
- Unmanaged resources get their own section at the bottom
- Include AWS resource ID where available for mismatched/unmanaged resources

**Error handling:**
- **Invalid diff.json:** Exit with code 1 and message: `"ERROR: Invalid diff.json: <parse error>"`
- **Missing architecture.mmd:** Exit with code 1 and message: `"ERROR: Missing or unreadable architecture.mmd"`
- **Both files empty:** Create minimal report.md with summary showing all zeros

**Edge cases:**
- **Zero resources:** Report summary with all counts = 0, omit detailed finding sections
- **No mismatches/missing/unmanaged:** Only include sections for resource types that have findings (e.g., skip "S3 Buckets" if no S3 drift found)
- **Very long resource IDs:** Truncate AWS resource IDs longer than 50 chars with ellipsis (e.g., `i-0abc123def456...`)
- **Special characters in names:** Escape Markdown special characters in resource names (backticks, brackets, etc.)

---

## references/usage.md

Document the following:
- What this skill does
- Prerequisites (AWS MCP setup instructions)
- How to use (step by step)
- Example invocation
- Supported resource types
- Known limitations

---

## SKILL.md

Write this last. It must include:

**Frontmatter:**
```yaml
---
name: terraform-drift-analyzer
description: |
  Detects infrastructure drift between Terraform *.tf declarations and live AWS
  resources (EC2, S3, IAM, Security Groups). Give Claude your *.tf files and get
  a single report.md with an embedded Mermaid architecture diagram and a full
  drift analysis. Use this skill whenever the user mentions Terraform drift,
  infrastructure drift, tf files vs AWS, what changed in AWS, or wants to compare
  their Terraform code against live cloud resources.
---
```

**Body must cover:**
1. Prerequisites check — verify AWS MCP is connected before proceeding
2. Step-by-step instructions for Claude to follow (matching the pipeline)
3. How Claude should invoke each script
4. How Claude should handle AWS MCP queries (what to ask, how to pass results back)
5. Error handling — what to do if AWS MCP is not connected, if .tf files are invalid
6. Output — remind Claude the only user-facing output is report.md

---

## Variable Interpolation Handling

When `terraform_parser.py` encounters variable references, classify them as:

**Resolvable:**
- Local variables defined in the same .tf file (mark with actual value)
- Module outputs referenced by name (mark as `"<module.name.output>"`)
- Data source outputs (mark as `"<data.source.id>"`)

**Unresolvable:**
- `var.X` — input variables (values only known at apply time)
- `local.X` — local variables not defined in parsed files
- `module.X.Y` — module outputs from external/remote sources
- Cross-file references that weren't parsed

**Output format for unresolvable:** `{"value": "<variable: var.instance_type>", "type": "unresolved"}`

---

## Standardized Error Messages

All scripts must use these exact error message formats for consistency:

| Scenario | Exit Code | Message Format |
|----------|-----------|-----------------|
| Invalid HCL | 1 | `ERROR: Invalid HCL syntax in <filename>: <detail>` |
| Missing required file | 1 | `ERROR: File not found: <filepath>` |
| Invalid JSON | 1 | `ERROR: Invalid JSON in <filename>: <detail>` |
| AWS MCP not connected | 1 | `ERROR: AWS MCP is not connected. Please connect AWS MCP before running this skill.` |
| Empty input | 1 | `ERROR: No resources found in <filename>` |
| Parse failure | 1 | `ERROR: Failed to parse <type>: <detail>` |
| Timeout | 1 | `ERROR: <operation> timed out. <recovery suggestion>` |

All error messages print to stderr. Success messages and progress updates print to stdout.

---

## Rules for Claude Code

- Write all Python scripts with proper CLI argument parsing (`argparse`)
- All scripts must have a `if __name__ == "__main__":` entry point
- Use `python-hcl2` for Terraform parsing (not regex)
- No boto3, no AWS CLI — AWS access is via MCP only
- All intermediate files (T.json, A.json, diff.json, architecture.mmd) written to a
  working directory (default: `./drift-workspace/`)
- Scripts must print clear progress messages to stdout
- Scripts must exit with code 1 and a clear error message on failure (use standardized formats above)
- Do not hardcode AWS region — read from environment or MCP context
- Print errors to stderr, progress to stdout (use `sys.stderr.write()` for errors)
