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


def _strip_quotes(s):
    """Remove surrounding double-quotes that hcl2 adds to string tokens."""
    if isinstance(s, str) and s.startswith('"') and s.endswith('"') and len(s) >= 2:
        return s[1:-1]
    return s


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
                    for raw_res_type, res_instances in block.items():
                        res_type = _strip_quotes(raw_res_type)
                        if res_type not in SUPPORTED_TYPES:
                            continue
                        for raw_res_name, res_config in res_instances.items():
                            res_name = _strip_quotes(raw_res_name)
                            key = (res_type, res_name)
                            if key in seen:
                                print(
                                    f"WARNING: Duplicate resource {res_type}.{res_name} in {tf_file}, using first occurrence."
                                )
                                continue
                            seen.add(key)
                            resources.append(
                                {
                                    "type": res_type,
                                    "name": res_name,
                                    "config": _normalize_config(res_config),
                                }
                            )

            elif block_type == "module":
                for block in blocks:
                    for raw_mod_name, mod_config in block.items():
                        mod_name = _strip_quotes(raw_mod_name)
                        raw_source = mod_config.get("source", None)
                        modules.append(
                            {
                                "name": mod_name,
                                "source": _strip_quotes(raw_source) if raw_source is not None else None,
                                "resources": [],
                            }
                        )

    return {"resources": resources, "modules": modules}


def _normalize_config(config):
    if not isinstance(config, dict):
        return config
    result = {}
    for k, v in config.items():
        # Skip internal hcl2 metadata keys
        if k == "__is_block__":
            continue
        if isinstance(v, str):
            v_stripped = _strip_quotes(v)
            if "${" in v_stripped or v_stripped.startswith("var.") or v_stripped.startswith("local."):
                result[k] = {"value": f"<variable: {v_stripped}>", "type": "unresolved"}
            else:
                result[k] = v_stripped
        elif isinstance(v, list) and len(v) == 1 and isinstance(v[0], dict):
            result[k] = _normalize_config(v[0])
        elif isinstance(v, list):
            result[k] = [
                _normalize_config(i) if isinstance(i, dict) else (_strip_quotes(i) if isinstance(i, str) else i)
                for i in v
            ]
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

        for sg_ref_field in ("vpc_security_group_ids", "security_groups"):
            refs = config.get(sg_ref_field, [])
            if isinstance(refs, list):
                for ref in refs:
                    _maybe_add_edge(lines, node_ids, src_id, ref, "aws_security_group")

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
    parser = argparse.ArgumentParser(
        description="Parse Terraform .tf files into T.json and architecture.mmd"
    )
    parser.add_argument("directory", help="Path to directory containing .tf files")
    parser.add_argument(
        "--workspace", default=WORKSPACE, help="Output workspace directory"
    )
    args = parser.parse_args()

    os.makedirs(args.workspace, exist_ok=True)

    print(f"Parsing .tf files in {args.directory}...")
    parsed = parse_tf_directory(args.directory)

    t_json_path = os.path.join(args.workspace, "T.json")
    with open(t_json_path, "w") as f:
        json.dump(parsed, f, indent=2)
    print(
        f"Written: {t_json_path} ({len(parsed['resources'])} resources, {len(parsed['modules'])} modules)"
    )

    mmd_path = os.path.join(args.workspace, "architecture.mmd")
    mmd = generate_mermaid(parsed)
    with open(mmd_path, "w") as f:
        f.write(mmd)
    print(f"Written: {mmd_path}")


if __name__ == "__main__":
    main()
