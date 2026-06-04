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

# Terraform Drift Analyzer — Pipeline Guide

You are running the terraform-drift-analyzer skill. Follow each step in order.
Do not skip steps. Do not surface intermediate files to the user.

---

## Step 0: Prerequisites Check

Before doing anything else:

1. Verify AWS MCP is connected by attempting a simple AWS MCP call (e.g., list EC2 instances or describe S3 buckets). If the call fails or no AWS MCP server is available, **stop immediately** and tell the user:

   > "Connect AWS MCP first — see the skill's references/usage.md for setup instructions. Do not proceed until AWS MCP is connected."

2. If the user has not provided a path to their Terraform directory, ask:

   > "Please provide the path to your Terraform directory (the folder containing your *.tf files)."

   Do not proceed until you have a valid directory path.

3. Locate the skill scripts directory by running:

```bash
SKILL_DIR=$(find ~/.claude/plugins ~/.claude/skills .claude/skills -name "terraform_parser.py" -path "*/terraform-drift-analyzer/*" 2>/dev/null | head -1 | xargs dirname 2>/dev/null)
echo "Skill scripts: $SKILL_DIR"
```

If `SKILL_DIR` is empty, fall back to checking the current directory:
```bash
[ -z "$SKILL_DIR" ] && SKILL_DIR="terraform-drift-analyzer/scripts"
```

Use `$SKILL_DIR` in all commands below.

---

## Step 1: Parse Terraform Files

Run:

```bash
python3 $SKILL_DIR/terraform_parser.py <terraform_directory>
```

Replace `<terraform_directory>` with the path the user provided.

**Expected outputs:**
- `drift-workspace/T.json` — normalized Terraform resource inventory
- `drift-workspace/architecture.mmd` — Mermaid architecture diagram

**Error handling:**
- If the script exits with code 1 and output contains "No .tf files found": tell the user "No .tf files found in that directory. Check the path." and stop.
- If the script exits with code 1 and output contains "Invalid HCL syntax" or a filename: tell the user "Syntax error in `<filename>`. Fix the HCL and try again." and stop.
- If `drift-workspace/T.json` is empty or contains no resources: tell the user "No supported resources found. Only EC2, S3, IAM, and Security Groups are supported in v1." and stop.

---

## Step 2: Discover Live AWS Resources

### 2a. Generate the discovery plan

Run:

```bash
python3 $SKILL_DIR/aws_discovery.py drift-workspace/T.json plan
```

This prints a JSON object with a `queries` array. Each query has:
- `resource_type` — the Terraform resource type (e.g., `aws_instance`)
- `mcp_action` — the AWS MCP action to call
- `description` — human-readable description of what to query

### 2b. Execute each MCP query

For each entry in the `queries` array, execute the AWS MCP call described by `mcp_action` and `description`. Collect all results.

**MCP queries by resource type:**

| Resource Type | What to query via AWS MCP |
|---|---|
| `aws_instance` | List all EC2 instances (describe-instances), return all instances with their Name tag, instance type, state, AMI, security groups, and tags |
| `aws_s3_bucket` | List all S3 buckets (list-buckets), return bucket names and tags |
| `aws_iam_role` | List all IAM roles (list-roles), return role names, ARNs, assume-role policy, and tags |
| `aws_iam_user` | List all IAM users (list-users), return usernames, ARNs, and tags |
| `aws_iam_policy` | List all customer-managed IAM policies (list-policies with scope=Local), return policy names, ARNs, and tags |
| `aws_security_group` | List all security groups (describe-security-groups), return group names, IDs, VPC IDs, ingress/egress rules, and tags |

If an MCP call times out, tell the user:

> "AWS MCP timed out querying `<resource_type>`. Check your connection and try again."

Then stop.

### 2c. Assemble MCP responses

Save all MCP responses into `drift-workspace/mcp_response.json` with this structure:

```json
{
  "aws_instance": [...],
  "aws_s3_bucket": [...],
  "aws_iam_role": [...],
  "aws_iam_user": [...],
  "aws_iam_policy": [...],
  "aws_security_group": [...]
}
```

Include only the resource types that were queried (based on what appears in T.json). Omit resource types that had no results as empty arrays.

### 2d. Normalize MCP responses

Run:

```bash
python3 $SKILL_DIR/aws_discovery.py drift-workspace/T.json normalize drift-workspace/mcp_response.json
```

**Expected output:** `drift-workspace/A.json` — normalized AWS resource inventory.

---

## Step 3: Detect Drift

Run:

```bash
python3 $SKILL_DIR/drift_detector.py drift-workspace/T.json drift-workspace/A.json
```

**Expected output:** `drift-workspace/diff.json` — full drift analysis.

The script prints a summary line to stdout. Print that line to the user as a progress update (e.g., "Drift detection complete: 3 matched, 1 missing, 2 unmanaged, 1 mismatched").

**Drift status definitions:**
- `matched` — resource exists in .tf and in AWS, configuration agrees
- `missing` — resource exists in .tf but was NOT found in AWS
- `unmanaged` — resource exists in AWS but is NOT declared in .tf
- `mismatched` — resource exists in both but one or more config fields differ

---

## Step 4: Generate Report

Run:

```bash
python3 $SKILL_DIR/report_generator.py drift-workspace/diff.json drift-workspace/architecture.mmd --output report.md
```

**Expected output:** `report.md` in the current working directory.

---

## Step 5: Present Results

Read the full contents of `report.md` and display them to the user.

**Rules:**
- Show ONLY `report.md` — never mention or show the contents of T.json, A.json, diff.json, architecture.mmd, or mcp_response.json.
- Do not summarize or paraphrase the report — show it in full.
- After presenting the report, ask the user if they have any questions about the findings.

---

## Error Reference

| Situation | What to tell the user |
|---|---|
| AWS MCP not connected | "Connect AWS MCP first — see terraform-drift-analyzer/references/usage.md" |
| No .tf files in directory | "No .tf files found in that directory. Check the path." |
| Invalid HCL syntax | "Syntax error in `<filename>`. Fix the HCL and try again." |
| MCP timeout | "AWS MCP timed out querying `<type>`. Check your connection." |
| Empty T.json / no supported resources | "No supported resources found. Only EC2, S3, IAM, and Security Groups are supported." |
| Script exits with unexpected error | Show the error message from stderr. Do not show a Python traceback to the user — paraphrase the error clearly. |

---

## Intermediate Files (never surface to user)

All intermediate files live in `./drift-workspace/`. Never mention these files to the user:

| File | Purpose |
|---|---|
| `drift-workspace/T.json` | Parsed Terraform resource inventory |
| `drift-workspace/A.json` | Normalized live AWS resource inventory |
| `drift-workspace/diff.json` | Raw drift comparison results |
| `drift-workspace/architecture.mmd` | Mermaid source for architecture diagram |
| `drift-workspace/mcp_response.json` | Raw MCP response data |

The only file the user ever sees is `report.md`.
