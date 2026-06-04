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


def normalize_mcp_response(t_json, mcp_data):
    resources = []

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
