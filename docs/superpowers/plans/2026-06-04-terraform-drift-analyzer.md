# Terraform Drift Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Agent Skill that detects drift between Terraform *.tf declarations and live AWS resources, producing a single `report.md` with embedded Mermaid diagram.

**Architecture:** Four deterministic Python scripts form a sequential pipeline: `terraform_parser.py` parses .tf files → `aws_discovery.py` structures AWS queries and normalizes MCP responses → `drift_detector.py` compares declared vs actual → `report_generator.py` formats the final report. AWS access is exclusively via AWS MCP (no boto3, no AWS CLI). Only `report.md` is shown to the user.

**Tech Stack:** Python 3.8+, python-hcl2, pytest, argparse, json

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `terraform-drift-analyzer/scripts/terraform_parser.py` | Create | Parse *.tf → T.json + architecture.mmd |
| `terraform-drift-analyzer/scripts/aws_discovery.py` | Create | T.json → discovery plan; MCP responses → A.json |
| `terraform-drift-analyzer/scripts/drift_detector.py` | Create | T.json + A.json → diff.json |
| `terraform-drift-analyzer/scripts/report_generator.py` | Create | diff.json + architecture.mmd → report.md |
| `terraform-drift-analyzer/references/usage.md` | Create | User-facing docs and prerequisites |
| `terraform-drift-analyzer/SKILL.md` | Create | Claude instructions for invoking the skill |
| `tests/fixtures/simple/main.tf` | Create | Single-file test fixture |
| `tests/fixtures/multi_file/main.tf` | Create | Multi-file test fixture (main) |
| `tests/fixtures/multi_file/network.tf` | Create | Multi-file test fixture (network) |
| `tests/test_terraform_parser.py` | Create | Tests for terraform_parser.py |
| `tests/test_aws_discovery.py` | Create | Tests for aws_discovery.py |
| `tests/test_drift_detector.py` | Create | Tests for drift_detector.py |
| `tests/test_report_generator.py` | Create | Tests for report_generator.py |

All paths relative to `/Users/sarthak.joshi/Desktop/files/`.

---

## Task 1: Project Scaffolding and Test Fixtures

**Files:**
- Create: `terraform-drift-analyzer/scripts/` (directory)
- Create: `terraform-drift-analyzer/references/` (directory)
- Create: `tests/fixtures/simple/main.tf`
- Create: `tests/fixtures/multi_file/main.tf`
- Create: `tests/fixtures/multi_file/network.tf`

- [ ] **Step 1: Create directory structure**

```bash
cd /Users/sarthak.joshi/Desktop/files
mkdir -p terraform-drift-analyzer/scripts
mkdir -p terraform-drift-analyzer/references
mkdir -p terraform-drift-analyzer/assets
mkdir -p tests/fixtures/simple
mkdir -p tests/fixtures/multi_file
```

- [ ] **Step 2: Create simple single-file fixture**

Create `tests/fixtures/simple/main.tf`:
```hcl
resource "aws_instance" "web_server" {
  instance_type = "t3.micro"
  ami           = "ami-0abcdef1234567890"

  vpc_security_group_ids = [aws_security_group.allow_web.id]

  tags = {
    Name = "web_server"
  }
}

resource "aws_security_group" "allow_web" {
  name        = "allow_web"
  description = "Allow web traffic"

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "allow_web"
  }
}

resource "aws_s3_bucket" "logs_bucket" {
  bucket = "my-logs-bucket"

  tags = {
    Name = "logs_bucket"
  }
}
```

- [ ] **Step 3: Create multi-file fixture (main.tf)**

Create `tests/fixtures/multi_file/main.tf`:
```hcl
resource "aws_instance" "api_server" {
  instance_type = "t3.small"
  ami           = "ami-0abcdef1234567890"

  vpc_security_group_ids = [aws_security_group.api_sg.id]

  tags = {
    Name = "api_server"
  }
}

resource "aws_iam_role" "app_role" {
  name = "app_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  tags = {
    Name = "app_role"
  }
}

module "vpc_module" {
  source = "./modules/vpc"
  cidr   = "10.0.0.0/16"
}
```

- [ ] **Step 4: Create multi-file fixture (network.tf)**

Create `tests/fixtures/multi_file/network.tf`:
```hcl
resource "aws_security_group" "api_sg" {
  name        = "api_sg"
  description = "API security group"

  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }

  tags = {
    Name = "api_sg"
  }
}

resource "aws_iam_user" "deploy_user" {
  name = "deploy_user"
  path = "/service/"

  tags = {
    Name = "deploy_user"
  }
}
```

- [ ] **Step 5: Create empty conftest.py for pytest**

Create `tests/conftest.py`:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'terraform-drift-analyzer', 'scripts'))
```

- [ ] **Step 6: Verify fixtures are readable**

```bash
cd /Users/sarthak.joshi/Desktop/files
cat tests/fixtures/simple/main.tf
cat tests/fixtures/multi_file/main.tf
cat tests/fixtures/multi_file/network.tf
```

Expected: each file prints cleanly with no errors.

---

## Task 2: terraform_parser.py — Core Parsing

**Files:**
- Create: `terraform-drift-analyzer/scripts/terraform_parser.py`
- Create: `tests/test_terraform_parser.py`

- [ ] **Step 1: Install python-hcl2**

```bash
pip install python-hcl2
```

Expected: `Successfully installed python-hcl2-...`

- [ ] **Step 2: Write failing tests for resource parsing**

Create `tests/test_terraform_parser.py`:
```python
import json
import os
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def parse_terraform(directory):
    """Import and call terraform_parser's main parsing function."""
    from terraform_parser import parse_tf_directory
    return parse_tf_directory(directory)


class TestResourceParsing:
    def test_parses_aws_instance(self):
        result = parse_terraform(str(FIXTURES / "simple"))
        types = [r["type"] for r in result["resources"]]
        assert "aws_instance" in types

    def test_aws_instance_fields(self):
        result = parse_terraform(str(FIXTURES / "simple"))
        instance = next(r for r in result["resources"] if r["type"] == "aws_instance")
        assert instance["name"] == "web_server"
        assert instance["config"]["instance_type"] == "t3.micro"
        assert instance["config"]["ami"] == "ami-0abcdef1234567890"

    def test_parses_security_group(self):
        result = parse_terraform(str(FIXTURES / "simple"))
        types = [r["type"] for r in result["resources"]]
        assert "aws_security_group" in types

    def test_parses_s3_bucket(self):
        result = parse_terraform(str(FIXTURES / "simple"))
        types = [r["type"] for r in result["resources"]]
        assert "aws_s3_bucket" in types

    def test_parses_multi_file_directory(self):
        result = parse_terraform(str(FIXTURES / "multi_file"))
        types = [r["type"] for r in result["resources"]]
        assert "aws_instance" in types
        assert "aws_security_group" in types
        assert "aws_iam_role" in types
        assert "aws_iam_user" in types

    def test_modules_recorded(self):
        result = parse_terraform(str(FIXTURES / "multi_file"))
        assert len(result["modules"]) == 1
        assert result["modules"][0]["name"] == "vpc_module"
        assert result["modules"][0]["source"] == "./modules/vpc"

    def test_tags_parsed(self):
        result = parse_terraform(str(FIXTURES / "simple"))
        instance = next(r for r in result["resources"] if r["type"] == "aws_instance")
        assert instance["config"]["tags"]["Name"] == "web_server"

    def test_missing_optional_field_is_null(self):
        result = parse_terraform(str(FIXTURES / "simple"))
        bucket = next(r for r in result["resources"] if r["type"] == "aws_s3_bucket")
        # description is not set — should be null, not missing
        assert "tags" in bucket["config"]

    def test_output_has_required_keys(self):
        result = parse_terraform(str(FIXTURES / "simple"))
        assert "resources" in result
        assert "modules" in result

    def test_no_tf_files_raises_systemexit(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            parse_terraform(str(tmp_path))
        assert exc_info.value.code == 1

    def test_unsupported_resource_types_ignored(self, tmp_path):
        (tmp_path / "main.tf").write_text('''
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}
''')
        result = parse_terraform(str(tmp_path))
        assert result["resources"] == []

    def test_duplicate_resource_uses_first(self, tmp_path):
        (tmp_path / "a.tf").write_text('''
resource "aws_instance" "dup" {
  instance_type = "t3.micro"
  ami = "ami-111"
  tags = { Name = "dup" }
}
''')
        (tmp_path / "b.tf").write_text('''
resource "aws_instance" "dup" {
  instance_type = "t3.large"
  ami = "ami-222"
  tags = { Name = "dup" }
}
''')
        result = parse_terraform(str(tmp_path))
        instances = [r for r in result["resources"] if r["type"] == "aws_instance"]
        assert len(instances) == 1
        assert instances[0]["config"]["instance_type"] == "t3.micro"
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd /Users/sarthak.joshi/Desktop/files
pytest tests/test_terraform_parser.py -v 2>&1 | head -30
```

Expected: `ImportError: No module named 'terraform_parser'` or similar.

- [ ] **Step 4: Implement terraform_parser.py**

Create `terraform-drift-analyzer/scripts/terraform_parser.py`:
```python
import argparse
import json
import os
import sys
from pathlib import Path

import hcl2

SUPPORTED_TYPES = {
    "aws_instance",
    "aws_s3_bucket",
    "aws_iam_role",
    "aws_iam_user",
    "aws_iam_policy",
    "aws_security_group",
}

WORKSPACE = "./drift-workspace"


def parse_tf_directory(directory):
    tf_files = sorted(Path(directory).rglob("*.tf"))
    if not tf_files:
        print(f"ERROR: No .tf files found in {directory}", file=sys.stderr)
        sys.exit(1)

    resources = []
    modules = []
    seen = set()

    for tf_file in tf_files:
        try:
            with open(tf_file, "r") as f:
                data = hcl2.load(f)
        except Exception as e:
            print(f"ERROR: Invalid HCL syntax in {tf_file}: {e}", file=sys.stderr)
            sys.exit(1)

        for block_type, blocks in data.items():
            if block_type == "resource":
                for block in blocks:
                    for res_type, res_instances in block.items():
                        if res_type not in SUPPORTED_TYPES:
                            continue
                        for res_name, res_config in res_instances.items():
                            key = (res_type, res_name)
                            if key in seen:
                                print(f"WARNING: Duplicate resource {res_type}.{res_name} in {tf_file}, using first occurrence.")
                                continue
                            seen.add(key)
                            resources.append({
                                "type": res_type,
                                "name": res_name,
                                "config": _normalize_config(res_config),
                            })

            elif block_type == "module":
                for block in blocks:
                    for mod_name, mod_config in block.items():
                        modules.append({
                            "name": mod_name,
                            "source": mod_config.get("source", None),
                            "resources": [],
                        })

    return {"resources": resources, "modules": modules}


def _normalize_config(config):
    if not isinstance(config, dict):
        return config
    result = {}
    for k, v in config.items():
        if isinstance(v, str) and ("${" in v or v.startswith("var.") or v.startswith("local.")):
            result[k] = {"value": f"<variable: {v}>", "type": "unresolved"}
        elif isinstance(v, list) and len(v) == 1 and isinstance(v[0], dict):
            result[k] = _normalize_config(v[0])
        elif isinstance(v, list):
            result[k] = [_normalize_config(i) if isinstance(i, dict) else i for i in v]
        elif isinstance(v, dict):
            result[k] = _normalize_config(v)
        else:
            result[k] = v
    return result


def generate_mermaid(parsed):
    lines = ["graph TD"]
    node_ids = {}

    short_type = {
        "aws_instance": "EC2",
        "aws_s3_bucket": "S3",
        "aws_iam_role": "IAM_Role",
        "aws_iam_user": "IAM_User",
        "aws_iam_policy": "IAM_Policy",
        "aws_security_group": "SG",
    }

    for r in parsed["resources"]:
        node_id = f"{r['type']}_{r['name']}"
        label = f"{short_type.get(r['type'], r['type'])}: {r['name']}"
        node_ids[(r["type"], r["name"])] = node_id
        lines.append(f"  {node_id}[{label}]")

    for r in parsed["resources"]:
        src_id = node_ids.get((r["type"], r["name"]))
        if not src_id:
            continue
        config = r.get("config", {})

        # aws_instance → aws_security_group
        for sg_ref_field in ("vpc_security_group_ids", "security_groups"):
            refs = config.get(sg_ref_field, [])
            if isinstance(refs, list):
                for ref in refs:
                    _maybe_add_edge(lines, node_ids, src_id, ref, "aws_security_group")

        # aws_iam_role → aws_iam_policy (via inline policy reference)
        if r["type"] == "aws_iam_role":
            policy_ref = config.get("managed_policy_arns", [])
            if isinstance(policy_ref, list):
                for ref in policy_ref:
                    _maybe_add_edge(lines, node_ids, src_id, ref, "aws_iam_policy")

    return "\n".join(lines)


def _maybe_add_edge(lines, node_ids, src_id, ref, target_type):
    if not isinstance(ref, str):
        return
    for (rtype, rname), node_id in node_ids.items():
        if rtype == target_type and rname in ref:
            lines.append(f"  {src_id} --> {node_id}")
            return


def main():
    parser = argparse.ArgumentParser(description="Parse Terraform .tf files into T.json and architecture.mmd")
    parser.add_argument("directory", help="Path to directory containing .tf files")
    parser.add_argument("--workspace", default=WORKSPACE, help="Output workspace directory")
    args = parser.parse_args()

    os.makedirs(args.workspace, exist_ok=True)

    print(f"Parsing .tf files in {args.directory}...")
    parsed = parse_tf_directory(args.directory)

    t_json_path = os.path.join(args.workspace, "T.json")
    with open(t_json_path, "w") as f:
        json.dump(parsed, f, indent=2)
    print(f"Written: {t_json_path} ({len(parsed['resources'])} resources, {len(parsed['modules'])} modules)")

    mmd_path = os.path.join(args.workspace, "architecture.mmd")
    mmd = generate_mermaid(parsed)
    with open(mmd_path, "w") as f:
        f.write(mmd)
    print(f"Written: {mmd_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests**

```bash
cd /Users/sarthak.joshi/Desktop/files
pytest tests/test_terraform_parser.py -v
```

Expected: All tests pass. If `test_duplicate_resource_uses_first` fails due to file ordering, verify sorted() in `parse_tf_directory`.

- [ ] **Step 6: Smoke-test the CLI**

```bash
cd /Users/sarthak.joshi/Desktop/files
python terraform-drift-analyzer/scripts/terraform_parser.py tests/fixtures/simple
cat drift-workspace/T.json
cat drift-workspace/architecture.mmd
```

Expected: T.json with 3 resources; architecture.mmd with `graph TD` and nodes for EC2, SG, S3.

- [ ] **Step 7: Commit**

```bash
cd /Users/sarthak.joshi/Desktop/files
git add terraform-drift-analyzer/scripts/terraform_parser.py tests/
git commit -m "feat: add terraform_parser.py with HCL parsing, T.json, Mermaid output"
```

---

## Task 3: aws_discovery.py — Discovery Plan and Normalization

**Files:**
- Create: `terraform-drift-analyzer/scripts/aws_discovery.py`
- Create: `tests/test_aws_discovery.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_aws_discovery.py`:
```python
import json
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def get_discovery_plan(t_json):
    from aws_discovery import build_discovery_plan
    return build_discovery_plan(t_json)


def normalize_mcp_response(t_json, mcp_data):
    from aws_discovery import normalize_mcp_response
    return normalize_mcp_response(t_json, mcp_data)


SAMPLE_T_JSON = {
    "resources": [
        {"type": "aws_instance", "name": "web_server", "config": {"instance_type": "t3.micro", "ami": "ami-111", "tags": {"Name": "web_server"}}},
        {"type": "aws_s3_bucket", "name": "logs_bucket", "config": {"bucket": "my-logs-bucket", "tags": {"Name": "logs_bucket"}}},
        {"type": "aws_security_group", "name": "allow_web", "config": {"tags": {"Name": "allow_web"}}},
    ],
    "modules": [],
}

SAMPLE_MCP_EC2 = [
    {
        "InstanceId": "i-0abc123def456",
        "InstanceType": "t3.micro",
        "ImageId": "ami-111",
        "State": {"Name": "running"},
        "Tags": [{"Key": "Name", "Value": "web_server"}],
    }
]

SAMPLE_MCP_S3 = [
    {"Name": "my-logs-bucket", "Tags": [{"Key": "Name", "Value": "logs_bucket"}]}
]

SAMPLE_MCP_SG = [
    {
        "GroupId": "sg-0abc123",
        "GroupName": "allow_web",
        "Description": "Allow web traffic",
        "IpPermissions": [],
        "IpPermissionsEgress": [],
        "Tags": [{"Key": "Name", "Value": "allow_web"}],
    }
]


class TestDiscoveryPlan:
    def test_plan_contains_ec2_query(self):
        plan = get_discovery_plan(SAMPLE_T_JSON)
        types = [q["resource_type"] for q in plan["queries"]]
        assert "aws_instance" in types

    def test_plan_contains_s3_query(self):
        plan = get_discovery_plan(SAMPLE_T_JSON)
        types = [q["resource_type"] for q in plan["queries"]]
        assert "aws_s3_bucket" in types

    def test_plan_contains_sg_query(self):
        plan = get_discovery_plan(SAMPLE_T_JSON)
        types = [q["resource_type"] for q in plan["queries"]]
        assert "aws_security_group" in types

    def test_plan_only_queries_present_types(self):
        t_json = {"resources": [{"type": "aws_instance", "name": "x", "config": {}}], "modules": []}
        plan = get_discovery_plan(t_json)
        types = [q["resource_type"] for q in plan["queries"]]
        assert "aws_s3_bucket" not in types
        assert "aws_iam_role" not in types

    def test_plan_has_mcp_action_per_type(self):
        plan = get_discovery_plan(SAMPLE_T_JSON)
        for q in plan["queries"]:
            assert "mcp_action" in q
            assert "description" in q

    def test_empty_resources_exits_with_code_1(self):
        with pytest.raises(SystemExit) as exc_info:
            get_discovery_plan({"resources": [], "modules": []})
        assert exc_info.value.code == 1


class TestNormalization:
    def test_ec2_normalized(self):
        mcp_data = {"aws_instance": SAMPLE_MCP_EC2, "aws_s3_bucket": SAMPLE_MCP_S3, "aws_security_group": SAMPLE_MCP_SG}
        result = normalize_mcp_response(SAMPLE_T_JSON, mcp_data)
        types = [r["type"] for r in result["resources"]]
        assert "aws_instance" in types

    def test_ec2_fields_normalized(self):
        mcp_data = {"aws_instance": SAMPLE_MCP_EC2, "aws_s3_bucket": [], "aws_security_group": []}
        result = normalize_mcp_response(SAMPLE_T_JSON, mcp_data)
        ec2 = next(r for r in result["resources"] if r["type"] == "aws_instance")
        assert ec2["id"] == "i-0abc123def456"
        assert ec2["name"] == "web_server"
        assert ec2["config"]["instance_type"] == "t3.micro"
        assert ec2["config"]["tags"]["Name"] == "web_server"

    def test_s3_normalized(self):
        mcp_data = {"aws_instance": [], "aws_s3_bucket": SAMPLE_MCP_S3, "aws_security_group": []}
        result = normalize_mcp_response(SAMPLE_T_JSON, mcp_data)
        s3 = next((r for r in result["resources"] if r["type"] == "aws_s3_bucket"), None)
        assert s3 is not None
        assert s3["name"] == "logs_bucket"

    def test_sg_normalized(self):
        mcp_data = {"aws_instance": [], "aws_s3_bucket": [], "aws_security_group": SAMPLE_MCP_SG}
        result = normalize_mcp_response(SAMPLE_T_JSON, mcp_data)
        sg = next((r for r in result["resources"] if r["type"] == "aws_security_group"), None)
        assert sg is not None
        assert sg["id"] == "sg-0abc123"

    def test_empty_tags_normalized_as_dict(self):
        ec2_no_tags = [{"InstanceId": "i-xxx", "InstanceType": "t2.micro", "ImageId": "ami-zzz", "State": {"Name": "running"}, "Tags": []}]
        mcp_data = {"aws_instance": ec2_no_tags, "aws_s3_bucket": [], "aws_security_group": []}
        result = normalize_mcp_response(SAMPLE_T_JSON, mcp_data)
        ec2 = next((r for r in result["resources"] if r["type"] == "aws_instance"), None)
        if ec2:
            assert ec2["config"]["tags"] == {}

    def test_result_has_resources_key(self):
        mcp_data = {"aws_instance": [], "aws_s3_bucket": [], "aws_security_group": []}
        result = normalize_mcp_response(SAMPLE_T_JSON, mcp_data)
        assert "resources" in result
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/sarthak.joshi/Desktop/files
pytest tests/test_aws_discovery.py -v 2>&1 | head -20
```

Expected: `ImportError: No module named 'aws_discovery'`

- [ ] **Step 3: Implement aws_discovery.py**

Create `terraform-drift-analyzer/scripts/aws_discovery.py`:
```python
import argparse
import json
import os
import sys

WORKSPACE = "./drift-workspace"

MCP_ACTIONS = {
    "aws_instance": {
        "mcp_action": "describe_instances",
        "description": "List all EC2 instances with full tag data via AWS MCP: describe all instances, include Tags in response.",
    },
    "aws_s3_bucket": {
        "mcp_action": "list_buckets_with_tags",
        "description": "List all S3 buckets via AWS MCP, then get tags for each bucket.",
    },
    "aws_iam_role": {
        "mcp_action": "list_roles",
        "description": "List all IAM roles via AWS MCP, include tags and assume_role_policy_document.",
    },
    "aws_iam_user": {
        "mcp_action": "list_users",
        "description": "List all IAM users via AWS MCP, include path and tags.",
    },
    "aws_iam_policy": {
        "mcp_action": "list_policies",
        "description": "List all customer-managed IAM policies via AWS MCP (Scope=Local), include policy document.",
    },
    "aws_security_group": {
        "mcp_action": "describe_security_groups",
        "description": "List all security groups via AWS MCP, include ingress/egress rules and tags.",
    },
}


def build_discovery_plan(t_json):
    resource_types = {r["type"] for r in t_json.get("resources", [])}
    if not resource_types:
        print("ERROR: No resources found in T.json", file=sys.stderr)
        sys.exit(1)

    queries = []
    for rtype in sorted(resource_types):
        if rtype in MCP_ACTIONS:
            queries.append({"resource_type": rtype, **MCP_ACTIONS[rtype]})

    return {"queries": queries}


def _tags_list_to_dict(tags_list):
    if not tags_list:
        return {}
    if isinstance(tags_list, dict):
        return tags_list
    return {t["Key"]: t["Value"] for t in tags_list if "Key" in t}


def _name_from_tags(tags_list):
    d = _tags_list_to_dict(tags_list)
    return d.get("Name")


def normalize_mcp_response(t_json, mcp_data):
    resources = []

    # EC2 instances
    for item in mcp_data.get("aws_instance", []):
        tags = _tags_list_to_dict(item.get("Tags", []))
        name = tags.get("Name") or item.get("InstanceId")
        resources.append({
            "type": "aws_instance",
            "id": item.get("InstanceId"),
            "name": name,
            "config": {
                "instance_type": item.get("InstanceType"),
                "ami": item.get("ImageId"),
                "state": item.get("State", {}).get("Name"),
                "tags": tags,
            },
        })

    # S3 buckets
    for item in mcp_data.get("aws_s3_bucket", []):
        tags = _tags_list_to_dict(item.get("Tags", []))
        bucket_name = item.get("Name") or item.get("name")
        name = tags.get("Name") or bucket_name
        resources.append({
            "type": "aws_s3_bucket",
            "id": bucket_name,
            "name": name,
            "config": {
                "bucket": bucket_name,
                "tags": tags,
            },
        })

    # IAM roles
    for item in mcp_data.get("aws_iam_role", []):
        tags = _tags_list_to_dict(item.get("Tags", []))
        role_name = item.get("RoleName")
        name = tags.get("Name") or role_name
        resources.append({
            "type": "aws_iam_role",
            "id": item.get("RoleId", role_name),
            "name": name,
            "config": {
                "assume_role_policy": item.get("AssumeRolePolicyDocument"),
                "tags": tags,
            },
        })

    # IAM users
    for item in mcp_data.get("aws_iam_user", []):
        tags = _tags_list_to_dict(item.get("Tags", []))
        user_name = item.get("UserName")
        name = tags.get("Name") or user_name
        resources.append({
            "type": "aws_iam_user",
            "id": item.get("UserId", user_name),
            "name": name,
            "config": {
                "path": item.get("Path"),
                "tags": tags,
            },
        })

    # IAM policies
    for item in mcp_data.get("aws_iam_policy", []):
        tags = _tags_list_to_dict(item.get("Tags", []))
        policy_name = item.get("PolicyName")
        name = tags.get("Name") or policy_name
        resources.append({
            "type": "aws_iam_policy",
            "id": item.get("PolicyId", policy_name),
            "name": name,
            "config": {
                "policy_document": item.get("PolicyDocument"),
                "tags": tags,
            },
        })

    # Security groups
    for item in mcp_data.get("aws_security_group", []):
        tags = _tags_list_to_dict(item.get("Tags", []))
        name = tags.get("Name") or item.get("GroupName")
        resources.append({
            "type": "aws_security_group",
            "id": item.get("GroupId"),
            "name": name,
            "config": {
                "name": item.get("GroupName"),
                "description": item.get("Description"),
                "ingress": item.get("IpPermissions", []),
                "egress": item.get("IpPermissionsEgress", []),
                "tags": tags,
            },
        })

    return {"resources": resources}


def main():
    parser = argparse.ArgumentParser(description="AWS resource discovery planner and MCP response normalizer")
    parser.add_argument("t_json", help="Path to T.json")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("plan", help="Output MCP discovery plan as JSON")

    normalize_parser = subparsers.add_parser("normalize", help="Normalize MCP JSON response into A.json")
    normalize_parser.add_argument("mcp_response", help="Path to JSON file containing MCP responses")
    normalize_parser.add_argument("--workspace", default=WORKSPACE)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        with open(args.t_json) as f:
            t_json = json.load(f)
    except Exception as e:
        print(f"ERROR: Invalid JSON in {args.t_json}: {e}", file=sys.stderr)
        sys.exit(1)

    if args.command == "plan":
        plan = build_discovery_plan(t_json)
        print(json.dumps(plan, indent=2))

    elif args.command == "normalize":
        try:
            with open(args.mcp_response) as f:
                mcp_data = json.load(f)
        except Exception as e:
            print(f"ERROR: Invalid JSON in {args.mcp_response}: {e}", file=sys.stderr)
            sys.exit(1)

        os.makedirs(args.workspace, exist_ok=True)
        result = normalize_mcp_response(t_json, mcp_data)

        a_json_path = os.path.join(args.workspace, "A.json")
        with open(a_json_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Written: {a_json_path} ({len(result['resources'])} live resources)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/sarthak.joshi/Desktop/files
pytest tests/test_aws_discovery.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Smoke-test plan subcommand**

```bash
cd /Users/sarthak.joshi/Desktop/files
python terraform-drift-analyzer/scripts/aws_discovery.py drift-workspace/T.json plan
```

Expected: JSON with `queries` array listing each resource type present in T.json.

- [ ] **Step 6: Commit**

```bash
git add terraform-drift-analyzer/scripts/aws_discovery.py tests/test_aws_discovery.py
git commit -m "feat: add aws_discovery.py with discovery plan and MCP response normalizer"
```

---

## Task 4: drift_detector.py — Resource Comparison

**Files:**
- Create: `terraform-drift-analyzer/scripts/drift_detector.py`
- Create: `tests/test_drift_detector.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_drift_detector.py`:
```python
import json
import pytest
from pathlib import Path


def detect_drift(t_json, a_json):
    from drift_detector import compare_resources
    return compare_resources(t_json, a_json)


DECLARED = {
    "resources": [
        {"type": "aws_instance", "name": "web_server", "config": {"instance_type": "t3.micro", "ami": "ami-111", "tags": {"Name": "web_server"}}},
        {"type": "aws_instance", "name": "api_server", "config": {"instance_type": "t3.small", "ami": "ami-222", "tags": {"Name": "api_server"}}},
        {"type": "aws_s3_bucket", "name": "logs", "config": {"bucket": "my-logs", "tags": {"Name": "logs"}}},
    ],
    "modules": [],
}

ACTUAL_MATCHED = {
    "resources": [
        {"type": "aws_instance", "id": "i-001", "name": "web_server", "config": {"instance_type": "t3.micro", "ami": "ami-111", "state": "running", "tags": {"Name": "web_server"}}},
        {"type": "aws_s3_bucket", "id": "my-logs", "name": "logs", "config": {"bucket": "my-logs", "tags": {"Name": "logs"}}},
        {"type": "aws_instance", "id": "i-999", "name": "old_worker", "config": {"instance_type": "t2.medium", "ami": "ami-old", "state": "running", "tags": {"Name": "old_worker"}}},
    ]
}

ACTUAL_MISMATCHED = {
    "resources": [
        {"type": "aws_instance", "id": "i-001", "name": "web_server", "config": {"instance_type": "t3.large", "ami": "ami-111", "state": "running", "tags": {"Name": "web_server"}}},
    ]
}


class TestDriftDetector:
    def test_matched_status(self):
        result = detect_drift(DECLARED, ACTUAL_MATCHED)
        findings = result["findings"]
        web = next(f for f in findings if f["resource_name"] == "web_server")
        assert web["status"] == "matched"

    def test_missing_status(self):
        result = detect_drift(DECLARED, ACTUAL_MATCHED)
        findings = result["findings"]
        api = next(f for f in findings if f["resource_name"] == "api_server")
        assert api["status"] == "missing"

    def test_unmanaged_status(self):
        result = detect_drift(DECLARED, ACTUAL_MATCHED)
        findings = result["findings"]
        unmanaged = [f for f in findings if f["status"] == "unmanaged"]
        assert any(f["resource_name"] == "old_worker" for f in unmanaged)

    def test_mismatched_status(self):
        result = detect_drift(DECLARED, ACTUAL_MISMATCHED)
        findings = result["findings"]
        web = next(f for f in findings if f["resource_name"] == "web_server")
        assert web["status"] == "mismatched"

    def test_mismatched_drift_fields(self):
        result = detect_drift(DECLARED, ACTUAL_MISMATCHED)
        findings = result["findings"]
        web = next(f for f in findings if f["resource_name"] == "web_server")
        assert "instance_type" in web["drift_fields"]

    def test_summary_counts(self):
        result = detect_drift(DECLARED, ACTUAL_MATCHED)
        s = result["summary"]
        assert s["total_declared"] == 3
        assert s["total_missing"] == 1
        assert s["total_unmanaged"] == 1

    def test_missing_declared_is_null(self):
        result = detect_drift(DECLARED, ACTUAL_MATCHED)
        api = next(f for f in result["findings"] if f["resource_name"] == "api_server")
        assert api["actual"] is None

    def test_missing_actual_is_null_for_missing(self):
        result = detect_drift(DECLARED, {"resources": []})
        for f in result["findings"]:
            if f["status"] == "missing":
                assert f["actual"] is None

    def test_unmanaged_declared_is_null(self):
        result = detect_drift(DECLARED, ACTUAL_MATCHED)
        unmanaged = [f for f in result["findings"] if f["status"] == "unmanaged"]
        for f in unmanaged:
            assert f["declared"] is None

    def test_tag_comparison_ignores_extra_aws_tags(self):
        declared = {"resources": [
            {"type": "aws_instance", "name": "web", "config": {"instance_type": "t3.micro", "ami": "ami-1", "tags": {"Name": "web"}}}
        ], "modules": []}
        actual = {"resources": [
            {"type": "aws_instance", "id": "i-1", "name": "web", "config": {
                "instance_type": "t3.micro", "ami": "ami-1", "state": "running",
                "tags": {"Name": "web", "aws:cloudformation:stack": "my-stack"}
            }}
        ]}
        result = detect_drift(declared, actual)
        web = next(f for f in result["findings"] if f["resource_name"] == "web")
        assert web["status"] == "matched"

    def test_empty_both_returns_empty_findings(self):
        result = detect_drift({"resources": [], "modules": []}, {"resources": []})
        assert result["findings"] == []
        assert result["summary"]["total_declared"] == 0

    def test_findings_have_required_keys(self):
        result = detect_drift(DECLARED, ACTUAL_MATCHED)
        for f in result["findings"]:
            assert "resource_type" in f
            assert "resource_name" in f
            assert "status" in f
            assert "declared" in f
            assert "actual" in f
            assert "drift_fields" in f
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/sarthak.joshi/Desktop/files
pytest tests/test_drift_detector.py -v 2>&1 | head -20
```

Expected: `ImportError: No module named 'drift_detector'`

- [ ] **Step 3: Implement drift_detector.py**

Create `terraform-drift-analyzer/scripts/drift_detector.py`:
```python
import argparse
import json
import os
import sys

WORKSPACE = "./drift-workspace"

COMPARE_FIELDS = {
    "aws_instance": ["instance_type", "ami", "tags"],
    "aws_s3_bucket": ["bucket", "tags"],
    "aws_iam_role": ["assume_role_policy", "tags"],
    "aws_iam_user": ["path", "tags"],
    "aws_iam_policy": ["policy_document", "tags"],
    "aws_security_group": ["ingress", "egress", "tags"],
}


def _normalize_val(v):
    return str(v) if not isinstance(v, (dict, list)) else v


def _compare_tags(declared_tags, actual_tags):
    """Only compare tags declared in Terraform. Ignore extra AWS tags."""
    if not declared_tags:
        return []
    drift = []
    for k, v in declared_tags.items():
        if actual_tags.get(k) != v:
            drift.append(f"tags.{k}")
    return drift


def _compare_configs(res_type, declared_config, actual_config):
    fields = COMPARE_FIELDS.get(res_type, [])
    drift_fields = []
    for field in fields:
        declared_val = declared_config.get(field)
        actual_val = actual_config.get(field)
        if field == "tags":
            drift_fields.extend(_compare_tags(declared_val or {}, actual_val or {}))
        else:
            if declared_val is None:
                continue
            if _normalize_val(declared_val) != _normalize_val(actual_val):
                drift_fields.append(field)
    return drift_fields


def compare_resources(t_json, a_json):
    declared = t_json.get("resources", [])
    actual = a_json.get("resources", [])

    actual_by_name = {}
    for r in actual:
        key = (r["type"], r["name"])
        actual_by_name.setdefault(key, []).append(r)

    declared_keys = {(r["type"], r["name"]) for r in declared}
    findings = []

    for d in declared:
        key = (d["type"], d["name"])
        matches = actual_by_name.get(key, [])

        if not matches:
            findings.append({
                "resource_type": d["type"],
                "resource_name": d["name"],
                "status": "missing",
                "declared": d["config"],
                "actual": None,
                "drift_fields": [],
            })
        else:
            a = matches[0]
            drift_fields = _compare_configs(d["type"], d.get("config", {}), a.get("config", {}))
            status = "mismatched" if drift_fields else "matched"
            findings.append({
                "resource_type": d["type"],
                "resource_name": d["name"],
                "status": status,
                "declared": d["config"],
                "actual": a["config"],
                "drift_fields": drift_fields,
            })

    for a in actual:
        key = (a["type"], a["name"])
        if key not in declared_keys:
            findings.append({
                "resource_type": a["type"],
                "resource_name": a["name"],
                "status": "unmanaged",
                "declared": None,
                "actual": a["config"],
                "drift_fields": [],
            })

    summary = {
        "total_declared": len(declared),
        "total_found": sum(1 for f in findings if f["status"] in ("matched", "mismatched")),
        "total_missing": sum(1 for f in findings if f["status"] == "missing"),
        "total_unmanaged": sum(1 for f in findings if f["status"] == "unmanaged"),
        "total_mismatched": sum(1 for f in findings if f["status"] == "mismatched"),
    }

    return {"summary": summary, "findings": findings}


def main():
    parser = argparse.ArgumentParser(description="Compare T.json and A.json to produce diff.json")
    parser.add_argument("t_json", help="Path to T.json")
    parser.add_argument("a_json", help="Path to A.json")
    parser.add_argument("--workspace", default=WORKSPACE)
    args = parser.parse_args()

    for path, label in [(args.t_json, "T.json"), (args.a_json, "A.json")]:
        try:
            with open(path) as f:
                pass
        except FileNotFoundError:
            print(f"ERROR: File not found: {path}", file=sys.stderr)
            sys.exit(1)

    try:
        with open(args.t_json) as f:
            t_json = json.load(f)
    except Exception as e:
        print(f"ERROR: Invalid JSON in {args.t_json}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.a_json) as f:
            a_json = json.load(f)
    except Exception as e:
        print(f"ERROR: Invalid JSON in {args.a_json}: {e}", file=sys.stderr)
        sys.exit(1)

    if not t_json.get("resources") and not a_json.get("resources"):
        print("ERROR: No resources found in T.json or A.json", file=sys.stderr)
        sys.exit(1)

    print("Comparing declared vs actual resources...")
    result = compare_resources(t_json, a_json)

    os.makedirs(args.workspace, exist_ok=True)
    diff_path = os.path.join(args.workspace, "diff.json")
    with open(diff_path, "w") as f:
        json.dump(result, f, indent=2)

    s = result["summary"]
    print(f"Written: {diff_path}")
    print(f"  Declared: {s['total_declared']}  |  Found: {s['total_found']}  |  Missing: {s['total_missing']}  |  Unmanaged: {s['total_unmanaged']}  |  Mismatched: {s['total_mismatched']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/sarthak.joshi/Desktop/files
pytest tests/test_drift_detector.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add terraform-drift-analyzer/scripts/drift_detector.py tests/test_drift_detector.py
git commit -m "feat: add drift_detector.py with matched/missing/unmanaged/mismatched comparison"
```

---

## Task 5: report_generator.py — Final Report

**Files:**
- Create: `terraform-drift-analyzer/scripts/report_generator.py`
- Create: `tests/test_report_generator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_report_generator.py`:
```python
import pytest
from pathlib import Path
from datetime import datetime


def generate_report(diff_json, mmd_content):
    from report_generator import build_report
    return build_report(diff_json, mmd_content)


SAMPLE_MMD = "graph TD\n  EC2_web[EC2: web_server]\n  SG_allow[SG: allow_web]\n  EC2_web --> SG_allow"

SAMPLE_DIFF = {
    "summary": {
        "total_declared": 3,
        "total_found": 2,
        "total_missing": 1,
        "total_unmanaged": 1,
        "total_mismatched": 1,
    },
    "findings": [
        {"resource_type": "aws_instance", "resource_name": "web_server", "status": "matched", "declared": {"instance_type": "t3.micro"}, "actual": {"instance_type": "t3.micro", "id": "i-001"}, "drift_fields": []},
        {"resource_type": "aws_instance", "resource_name": "api_server", "status": "missing", "declared": {"instance_type": "t3.small"}, "actual": None, "drift_fields": []},
        {"resource_type": "aws_instance", "resource_name": "worker", "status": "mismatched", "declared": {"instance_type": "t3.micro"}, "actual": {"instance_type": "t3.large", "id": "i-002"}, "drift_fields": ["instance_type"]},
        {"resource_type": "aws_instance", "resource_name": "old_worker", "status": "unmanaged", "declared": None, "actual": {"instance_type": "t2.medium", "id": "i-999"}, "drift_fields": []},
    ],
}


class TestReportGenerator:
    def test_report_contains_title(self):
        report = generate_report(SAMPLE_DIFF, SAMPLE_MMD)
        assert "# Terraform Drift Report" in report

    def test_report_contains_generated_timestamp(self):
        report = generate_report(SAMPLE_DIFF, SAMPLE_MMD)
        assert "Generated:" in report

    def test_report_contains_mermaid_block(self):
        report = generate_report(SAMPLE_DIFF, SAMPLE_MMD)
        assert "```mermaid" in report
        assert "graph TD" in report

    def test_report_contains_summary_table(self):
        report = generate_report(SAMPLE_DIFF, SAMPLE_MMD)
        assert "## Summary" in report
        assert "| Total Declared |" in report
        assert "| 3 |" in report

    def test_matched_icon(self):
        report = generate_report(SAMPLE_DIFF, SAMPLE_MMD)
        assert "✅ web_server" in report

    def test_missing_icon(self):
        report = generate_report(SAMPLE_DIFF, SAMPLE_MMD)
        assert "❌ api_server" in report

    def test_mismatched_icon_with_field(self):
        report = generate_report(SAMPLE_DIFF, SAMPLE_MMD)
        assert "⚠️ worker" in report
        assert "instance_type" in report

    def test_unmanaged_section(self):
        report = generate_report(SAMPLE_DIFF, SAMPLE_MMD)
        assert "## Unmanaged Resources" in report
        assert "old_worker" in report

    def test_ec2_section_header(self):
        report = generate_report(SAMPLE_DIFF, SAMPLE_MMD)
        assert "### EC2 Instances" in report

    def test_empty_diff_returns_report(self):
        empty_diff = {"summary": {"total_declared": 0, "total_found": 0, "total_missing": 0, "total_unmanaged": 0, "total_mismatched": 0}, "findings": []}
        report = generate_report(empty_diff, SAMPLE_MMD)
        assert "# Terraform Drift Report" in report
        assert "## Summary" in report

    def test_no_s3_section_when_no_s3_findings(self):
        report = generate_report(SAMPLE_DIFF, SAMPLE_MMD)
        assert "### S3 Buckets" not in report
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/sarthak.joshi/Desktop/files
pytest tests/test_report_generator.py -v 2>&1 | head -20
```

Expected: `ImportError: No module named 'report_generator'`

- [ ] **Step 3: Implement report_generator.py**

Create `terraform-drift-analyzer/scripts/report_generator.py`:
```python
import argparse
import json
import os
import sys
from datetime import datetime, timezone

WORKSPACE = "./drift-workspace"

SECTION_LABELS = {
    "aws_instance": "EC2 Instances",
    "aws_s3_bucket": "S3 Buckets",
    "aws_iam_role": "IAM Roles",
    "aws_iam_user": "IAM Users",
    "aws_iam_policy": "IAM Policies",
    "aws_security_group": "Security Groups",
}

SECTION_ORDER = ["aws_instance", "aws_s3_bucket", "aws_iam_role", "aws_iam_user", "aws_iam_policy", "aws_security_group"]

STATUS_ICONS = {
    "matched": "✅",
    "missing": "❌",
    "mismatched": "⚠️",
    "unmanaged": "🔍",
}


def _escape_md(s):
    for ch in ["\\", "`", "[", "]", "*", "_"]:
        s = s.replace(ch, f"\\{ch}")
    return s


def _truncate_id(rid, max_len=50):
    if rid and len(str(rid)) > max_len:
        return str(rid)[:max_len] + "..."
    return rid or ""


def build_report(diff_json, mmd_content):
    s = diff_json["summary"]
    findings = diff_json["findings"]
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = []

    # Header
    lines.append("# Terraform Drift Report")
    lines.append(f"Generated: {timestamp}")
    lines.append("")

    # Architecture diagram
    lines.append("## Architecture")
    lines.append("")
    lines.append("```mermaid")
    lines.append(mmd_content)
    lines.append("```")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Declared | {s['total_declared']} |")
    lines.append(f"| Total Found | {s['total_found']} |")
    lines.append(f"| Missing | {s['total_missing']} |")
    lines.append(f"| Unmanaged | {s['total_unmanaged']} |")
    lines.append(f"| Mismatched | {s['total_mismatched']} |")
    lines.append("")

    # Drift findings (grouped by type, only types with findings)
    non_unmanaged = [f for f in findings if f["status"] != "unmanaged"]
    by_type = {}
    for f in non_unmanaged:
        by_type.setdefault(f["resource_type"], []).append(f)

    if by_type:
        lines.append("## Drift Findings")
        lines.append("")
        for rtype in SECTION_ORDER:
            if rtype not in by_type:
                continue
            label = SECTION_LABELS.get(rtype, rtype)
            lines.append(f"### {label}")
            for f in by_type[rtype]:
                icon = STATUS_ICONS.get(f["status"], "?")
                name = _escape_md(f["resource_name"])
                status = f["status"]
                if status == "matched":
                    lines.append(f"- {icon} {name} — matched")
                elif status == "missing":
                    lines.append(f"- {icon} {name} — missing in AWS")
                elif status == "mismatched":
                    drift_details = ", ".join(
                        f"{field}: declared `{f['declared'].get(field)}`, actual `{(f['actual'] or {}).get(field)}`"
                        for field in f.get("drift_fields", [])
                    )
                    aws_id = _truncate_id((f.get("actual") or {}).get("id") or (f.get("actual") or {}).get("instance_id"))
                    id_str = f" ({aws_id})" if aws_id else ""
                    lines.append(f"- {icon} {name}{id_str} — mismatched ({drift_details})")
            lines.append("")

    # Unmanaged resources
    unmanaged = [f for f in findings if f["status"] == "unmanaged"]
    if unmanaged:
        lines.append("## Unmanaged Resources")
        lines.append("Resources found in AWS not declared in Terraform:")
        lines.append("")
        by_type_unmanaged = {}
        for f in unmanaged:
            by_type_unmanaged.setdefault(f["resource_type"], []).append(f)
        for rtype in SECTION_ORDER:
            if rtype not in by_type_unmanaged:
                continue
            label = SECTION_LABELS.get(rtype, rtype)
            for f in by_type_unmanaged[rtype]:
                name = _escape_md(f["resource_name"])
                aws_id = _truncate_id((f.get("actual") or {}).get("id") or (f.get("actual") or {}).get("instance_id"))
                id_str = f" ({aws_id})" if aws_id else ""
                lines.append(f"- 🔍 {label}: {name}{id_str}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate report.md from diff.json and architecture.mmd")
    parser.add_argument("diff_json", help="Path to diff.json")
    parser.add_argument("architecture_mmd", help="Path to architecture.mmd")
    parser.add_argument("--output", default="report.md", help="Output path for report.md")
    parser.add_argument("--workspace", default=WORKSPACE)
    args = parser.parse_args()

    for path, label in [(args.diff_json, "diff.json"), (args.architecture_mmd, "architecture.mmd")]:
        if not os.path.exists(path):
            print(f"ERROR: File not found: {path}", file=sys.stderr)
            sys.exit(1)

    try:
        with open(args.diff_json) as f:
            diff_json = json.load(f)
    except Exception as e:
        print(f"ERROR: Invalid JSON in {args.diff_json}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.architecture_mmd) as f:
            mmd_content = f.read()
    except Exception as e:
        print(f"ERROR: Missing or unreadable architecture.mmd: {e}", file=sys.stderr)
        sys.exit(1)

    print("Generating report.md...")
    report = build_report(diff_json, mmd_content)

    with open(args.output, "w") as f:
        f.write(report)
    print(f"Written: {args.output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/sarthak.joshi/Desktop/files
pytest tests/test_report_generator.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add terraform-drift-analyzer/scripts/report_generator.py tests/test_report_generator.py
git commit -m "feat: add report_generator.py producing report.md with Mermaid diagram and drift findings"
```

---

## Task 6: Full Test Suite — Run All Tests

- [ ] **Step 1: Run full test suite**

```bash
cd /Users/sarthak.joshi/Desktop/files
pytest tests/ -v
```

Expected: All tests across all 4 test files pass.

- [ ] **Step 2: End-to-end smoke test with simple fixture**

```bash
cd /Users/sarthak.joshi/Desktop/files

# Step 1: Parse Terraform
python terraform-drift-analyzer/scripts/terraform_parser.py tests/fixtures/simple

# Step 2: Inspect T.json
cat drift-workspace/T.json

# Step 3: Create a mock A.json for smoke test
cat > drift-workspace/A.json << 'EOF'
{
  "resources": [
    {
      "type": "aws_instance",
      "id": "i-0abc123def456",
      "name": "web_server",
      "config": {
        "instance_type": "t3.large",
        "ami": "ami-0abcdef1234567890",
        "state": "running",
        "tags": {"Name": "web_server"}
      }
    },
    {
      "type": "aws_security_group",
      "id": "sg-0abc123",
      "name": "allow_web",
      "config": {
        "name": "allow_web",
        "ingress": [],
        "egress": [],
        "tags": {"Name": "allow_web"}
      }
    },
    {
      "type": "aws_instance",
      "id": "i-orphan999",
      "name": "orphan_server",
      "config": {
        "instance_type": "t2.nano",
        "ami": "ami-old",
        "state": "running",
        "tags": {"Name": "orphan_server"}
      }
    }
  ]
}
EOF

# Step 4: Detect drift
python terraform-drift-analyzer/scripts/drift_detector.py drift-workspace/T.json drift-workspace/A.json

# Step 5: Generate report
python terraform-drift-analyzer/scripts/report_generator.py drift-workspace/diff.json drift-workspace/architecture.mmd --output report.md

# Step 6: Inspect report
cat report.md
```

Expected: report.md shows web_server as mismatched (instance_type), allow_web as matched, logs_bucket as missing, orphan_server as unmanaged.

- [ ] **Step 3: Commit smoke-test validation**

```bash
git add .
git commit -m "test: full pipeline smoke test passing, all unit tests green"
```

---

## Task 7: references/usage.md

**Files:**
- Create: `terraform-drift-analyzer/references/usage.md`

- [ ] **Step 1: Write usage.md**

Create `terraform-drift-analyzer/references/usage.md`:
```markdown
# Terraform Drift Analyzer — Usage Guide

## What This Skill Does

Detects infrastructure drift between your Terraform `*.tf` declarations and live AWS
resources. It compares what you've declared in Terraform against what actually exists in
your AWS account and produces a single `report.md` with:

- A Mermaid architecture diagram of your declared resources
- A summary table of drift counts
- Per-resource-type drift findings (matched / missing / mismatched)
- A section listing unmanaged AWS resources not declared in Terraform

## Prerequisites

1. **AWS MCP connected** — this skill queries AWS exclusively via AWS MCP. Connect
   AWS MCP to Claude before invoking the skill.
   - In Claude settings, add the AWS MCP server and authenticate with your AWS credentials.
   - Verify connection by asking Claude: "Can you list my AWS regions?"

2. **Python 3.8+** with `python-hcl2` installed:
   ```bash
   pip install python-hcl2
   ```

3. **Terraform files** — a directory of `*.tf` files for the infrastructure to analyze.

## Supported Resource Types

| Terraform Type | AWS Resource |
|---|---|
| `aws_instance` | EC2 Instances |
| `aws_s3_bucket` | S3 Buckets |
| `aws_iam_role` | IAM Roles |
| `aws_iam_user` | IAM Users |
| `aws_iam_policy` | IAM Policies (customer-managed) |
| `aws_security_group` | Security Groups |

## How to Use

1. Open Claude with AWS MCP connected.
2. Say one of:
   - "Check my Terraform files for drift"
   - "What's different between my .tf files and AWS?"
   - "Run a drift analysis on my infrastructure"
3. Provide the path to your Terraform directory when prompted.
4. Claude will run the pipeline and produce `report.md` in your working directory.

## Example Invocation

```
You: Check my Terraform files for drift against AWS
Claude: I'll run the drift analysis. What's the path to your Terraform directory?
You: /home/user/infra/terraform/prod
Claude: [runs pipeline, produces report.md]
        Here's your drift report. I found 2 missing resources and 1 mismatched.
```

## Known Limitations

- `.tfstate` files are not used — comparison is always declaration vs live AWS state
- Only the 6 resource types above are analyzed; others are silently skipped
- Remote module resources are not resolved (only module names are recorded)
- Variable values that aren't resolved at parse time are marked as `<variable: ...>`
- Duplicate resource names (same type+name across files) use the first occurrence
- Multi-region: currently queries the AWS region configured in the AWS MCP connection

## Output Files

| File | Location | User-visible |
|------|----------|-------------|
| `report.md` | working directory | ✅ Yes — primary output |
| `T.json` | `./drift-workspace/` | No |
| `A.json` | `./drift-workspace/` | No |
| `diff.json` | `./drift-workspace/` | No |
| `architecture.mmd` | `./drift-workspace/` | No |
```

- [ ] **Step 2: Verify the file is readable**

```bash
cat /Users/sarthak.joshi/Desktop/files/terraform-drift-analyzer/references/usage.md | head -20
```

Expected: First 20 lines of usage.md print cleanly.

- [ ] **Step 3: Commit**

```bash
git add terraform-drift-analyzer/references/usage.md
git commit -m "docs: add references/usage.md with prerequisites and usage instructions"
```

---

## Task 8: SKILL.md

**Files:**
- Create: `terraform-drift-analyzer/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

Create `terraform-drift-analyzer/SKILL.md`:
```markdown
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

# Terraform Drift Analyzer

## Step 0: Prerequisites Check

**BEFORE doing anything else**, check whether AWS MCP is connected:
- Try to list AWS regions or describe EC2 instances via AWS MCP.
- If AWS MCP is NOT connected, stop immediately and tell the user:
  > "To run drift analysis, I need AWS MCP connected. Please connect AWS MCP in your
  > Claude settings and try again. See `references/usage.md` for setup instructions."
- Do NOT proceed past this step without a working AWS MCP connection.

Also confirm the user has provided a path to their Terraform directory. If not, ask:
> "What is the path to your Terraform directory?"

---

## Step 1: Parse Terraform Files

Run `terraform_parser.py` on the user's Terraform directory:

```bash
python terraform-drift-analyzer/scripts/terraform_parser.py <terraform_directory>
```

This writes `drift-workspace/T.json` and `drift-workspace/architecture.mmd`.

**On error:**
- "No .tf files found" → tell the user the directory doesn't contain Terraform files.
- "Invalid HCL syntax" → show the filename from the error and tell the user to fix syntax.
- Any other error → surface the full error message for the user.

After success, inform the user: "Parsed N resources across X files."

---

## Step 2: Discover Live AWS Resources

Run the discovery plan to see what MCP queries are needed:

```bash
python terraform-drift-analyzer/scripts/aws_discovery.py drift-workspace/T.json plan
```

This prints a JSON object with a `queries` array. For each query, execute the
corresponding AWS MCP call and collect the results into a single JSON object.

**MCP query mapping:**

| resource_type | AWS MCP Call |
|---|---|
| `aws_instance` | Describe all EC2 instances; include Tags |
| `aws_s3_bucket` | List all S3 buckets; get tags for each bucket |
| `aws_iam_role` | List all IAM roles; include Tags and AssumeRolePolicyDocument |
| `aws_iam_user` | List all IAM users; include path and Tags |
| `aws_iam_policy` | List customer-managed IAM policies (Scope=Local); include Tags |
| `aws_security_group` | Describe all security groups; include IpPermissions, IpPermissionsEgress, Tags |

Collect all MCP results into a single JSON file at `drift-workspace/mcp_response.json`:
```json
{
  "aws_instance": [ ...raw EC2 describe-instances response... ],
  "aws_s3_bucket": [ ...raw S3 list-buckets + tags response... ],
  "aws_security_group": [ ...raw describe-security-groups response... ]
}
```
(Only include keys for resource types that were queried.)

Then normalize:
```bash
python terraform-drift-analyzer/scripts/aws_discovery.py drift-workspace/T.json normalize drift-workspace/mcp_response.json
```

This writes `drift-workspace/A.json`.

**On MCP timeout or error:** Tell the user:
> "AWS MCP query for <resource_type> failed: <error>. Check your AWS permissions and try again."

---

## Step 3: Detect Drift

```bash
python terraform-drift-analyzer/scripts/drift_detector.py drift-workspace/T.json drift-workspace/A.json
```

This writes `drift-workspace/diff.json`.

Print the summary line from the script output to the user as progress info.

---

## Step 4: Generate Report

```bash
python terraform-drift-analyzer/scripts/report_generator.py drift-workspace/diff.json drift-workspace/architecture.mmd --output report.md
```

This writes `report.md` in the current working directory.

---

## Step 5: Present Results

Tell the user:
> "Drift analysis complete. Here's your report:"

Then show the **full contents of `report.md`** in your response.

**Do NOT mention or show:** T.json, A.json, diff.json, architecture.mmd, mcp_response.json.
These are internal working files. The user's only deliverable is `report.md`.

---

## Error Reference

| Situation | What to tell the user |
|-----------|----------------------|
| AWS MCP not connected | "Connect AWS MCP first — see references/usage.md for setup." |
| No .tf files found | "No .tf files found in that directory. Double-check the path." |
| Invalid HCL | "Syntax error in `<filename>`. Fix the HCL and try again." |
| MCP query timeout | "AWS MCP timed out querying <resource_type>. Check your connection." |
| Empty T.json | "No supported resources found in your .tf files. Only EC2, S3, IAM, and Security Groups are supported." |
```

- [ ] **Step 2: Verify frontmatter is valid YAML**

```bash
python3 -c "
import re
with open('terraform-drift-analyzer/SKILL.md') as f:
    content = f.read()
match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
print('Frontmatter found:', bool(match))
if match:
    print(match.group(1)[:100])
"
```

Expected: `Frontmatter found: True` followed by the frontmatter content.

- [ ] **Step 3: Commit**

```bash
git add terraform-drift-analyzer/SKILL.md
git commit -m "feat: add SKILL.md — Claude instructions for terraform drift analysis pipeline"
```

---

## Task 9: Definition of Done — Final Verification

- [ ] **Step 1: Run full test suite one final time**

```bash
cd /Users/sarthak.joshi/Desktop/files
pytest tests/ -v
```

Expected: All tests pass with 0 failures.

- [ ] **Step 2: Verify all required files exist**

```bash
ls terraform-drift-analyzer/scripts/
ls terraform-drift-analyzer/references/
ls terraform-drift-analyzer/
```

Expected:
- `scripts/`: terraform_parser.py, aws_discovery.py, drift_detector.py, report_generator.py
- `references/`: usage.md
- `terraform-drift-analyzer/`: SKILL.md, scripts/, references/, assets/

- [ ] **Step 3: Verify each script exits cleanly with --help**

```bash
python terraform-drift-analyzer/scripts/terraform_parser.py --help
python terraform-drift-analyzer/scripts/aws_discovery.py --help
python terraform-drift-analyzer/scripts/drift_detector.py --help
python terraform-drift-analyzer/scripts/report_generator.py --help
```

Expected: Each prints usage/help without errors.

- [ ] **Step 4: Verify error on missing .tf files**

```bash
python terraform-drift-analyzer/scripts/terraform_parser.py /tmp 2>&1; echo "Exit: $?"
```

Expected: `ERROR: No .tf files found in /tmp` printed to stderr, exit code 1.

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "feat: terraform-drift-analyzer skill complete — all scripts, tests, docs, SKILL.md"
```

---

## Self-Review

### Spec Coverage Check

| Requirement | Task |
|---|---|
| terraform_parser.py parses multi-file .tf | Task 2 |
| terraform_parser.py produces T.json and architecture.mmd | Task 2 |
| Module blocks recorded | Task 2 (parse_tf_directory handles `module` blocks) |
| python-hcl2 used (not regex) | Task 2 (hcl2.load) |
| aws_discovery.py produces discovery plan | Task 3 (build_discovery_plan) |
| aws_discovery.py normalizes MCP responses to A.json | Task 3 (normalize_mcp_response) |
| No boto3 / AWS CLI | Task 3 (aws_discovery.py has no imports of boto3/subprocess) |
| drift_detector.py: matched/missing/unmanaged/mismatched | Task 4 |
| Resource matching: Name tag primary, terraform:resource fallback | Task 4 (compare_resources via name field which was set from Name tag in aws_discovery) |
| Tag comparison only compares declared tags | Task 4 (_compare_tags) |
| report_generator.py produces report.md | Task 5 |
| Mermaid block in report | Task 5 |
| Status icons ✅❌⚠️🔍 | Task 5 |
| Unmanaged section at bottom | Task 5 |
| Only report.md shown to user | Task 8 (SKILL.md Step 5) |
| AWS MCP not connected → clear error | Task 8 (SKILL.md Step 0) |
| Invalid .tf → clear error (not traceback) | Task 2 (try/except in parse_tf_directory) |
| references/usage.md | Task 7 |
| SKILL.md | Task 8 |
| Standardized error messages | All scripts use formats from PLAN.md |

### Placeholder Scan
No TBDs, TODOs, or "similar to Task N" references found.

### Type Consistency
- `parse_tf_directory` → returns `{"resources": [...], "modules": [...]}` — used consistently
- `build_discovery_plan` → returns `{"queries": [...]}` — used in test and SKILL.md
- `normalize_mcp_response` → returns `{"resources": [...]}` — used in test and drift_detector
- `compare_resources` → returns `{"summary": {...}, "findings": [...]}` — used in test and report_generator
- `build_report` → returns `str` — used in test (assert string contents)
