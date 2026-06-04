# Terraform Drift Analyzer — Usage Reference

## What It Does

Compares your Terraform `*.tf` declarations against live AWS infrastructure and
produces a single `report.md` containing:

- An embedded Mermaid architecture diagram of your declared resources
- A per-resource drift status (matched / missing / mismatched / unmanaged)
- A summary table of drift counts by resource type

No AWS CLI, no boto3, no state file required. AWS access goes exclusively through
the AWS MCP server connected to your Claude session.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| AWS MCP server | Must be connected to your Claude session before invoking the skill |
| Python 3.8+ | Must be on `$PATH` |
| `python-hcl2` | `pip install python-hcl2` |

If the AWS MCP server is not connected, the skill will stop immediately and tell
you how to connect it. It will not fall back to boto3 or the AWS CLI.

---

## How to Use

1. Open a Claude Code session with the AWS MCP server connected.
2. Say something that triggers the skill (see examples below).
3. Provide the path to your Terraform directory when prompted (or include it in
   your message).
4. Wait. Claude runs the 4-step pipeline and writes `report.md` to your working
   directory.
5. Open `report.md`. That is the only output you need to look at.

Intermediate files (`T.json`, `A.json`, `diff.json`, `architecture.mmd`) are
written to `./drift-workspace/` and can be ignored.

---

## Trigger Phrases

Any of these will activate the skill:

- "Check my Terraform files for drift"
- "What's different between my .tf files and AWS?"
- "Run a drift analysis on my infrastructure"
- "Compare my Terraform code against live AWS"
- "What changed in AWS since I last applied?"

---

## Example Conversation

```
User:  Check my Terraform files for drift. My tf files are in ~/projects/infra/

Claude: Running drift analysis on ~/projects/infra/ ...

        Step 1/4 — Parsing Terraform files ... done (12 resources found)
        Step 2/4 — Querying AWS via MCP ... done
        Step 3/4 — Detecting drift ... done
        Step 4/4 — Generating report ... done

        Drift analysis complete. Results written to report.md

        Summary:
          matched    — 8
          missing    — 2
          mismatched — 1
          unmanaged  — 3
```

---

## Supported Resource Types

| Terraform Resource Type | AWS Resource |
|---|---|
| `aws_instance` | EC2 Instances |
| `aws_s3_bucket` | S3 Buckets |
| `aws_iam_role` | IAM Roles |
| `aws_iam_user` | IAM Users |
| `aws_iam_policy` | IAM Policies (customer-managed) |
| `aws_security_group` | Security Groups |

All other resource types are silently skipped in v1.

---

## Resource Matching

The drift detector links Terraform resources to live AWS resources using two
strategies, tried in order:

1. **Name tag (primary):** Terraform `resource_name` is matched against the AWS
   resource's `Name` tag.
2. **terraform:resource tag (fallback):** If no `Name` tag match is found, the
   detector checks for a `terraform:resource` tag on the AWS resource whose value
   equals the Terraform resource name.
3. **No match:** The AWS resource is flagged as `unmanaged`.

To ensure reliable matching, tag your AWS resources consistently:

```hcl
resource "aws_instance" "web_server" {
  # ...
  tags = {
    Name = "web_server"   # matches resource_name exactly
  }
}
```

---

## Drift Status Definitions

| Status | Icon | Meaning |
|---|---|---|
| `matched` | ✅ | Declared in .tf and found in AWS; config agrees |
| `missing` | ❌ | Declared in .tf but not found in AWS |
| `mismatched` | ⚠️ | Found in both but one or more config fields differ |
| `unmanaged` | 🔍 | Found in AWS but not declared in any .tf file |

---

## Known Limitations

- **No .tfstate support.** The skill never reads, writes, or references state
  files. Matching is done entirely by name/tag.
- **6 resource types only.** See the table above. All others are ignored in v1.
- **Terraform variables are not resolved.** If a field value is a variable
  reference (e.g., `var.instance_type`), it appears in the report as
  `<variable: var.instance_type>` and is excluded from config comparison.
- **Duplicate resource names.** If two resources of the same type share a name,
  only the first occurrence is used. A warning is printed to stdout.
- **No remote module resolution.** Module blocks are recorded by name but their
  contents are not fetched or expanded.
- **Single AWS account/region.** The skill queries whatever account and region
  the connected AWS MCP server is scoped to. Multi-account setups require
  separate runs.
