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
    "aws_security_group": ["tags"],  # ingress/egress skipped: AWS API format differs from HCL
}


def _normalize_val(v):
    return str(v) if not isinstance(v, (dict, list)) else v


def _compare_tags(declared_tags, actual_tags):
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

    # Primary index: match by (type, AWS Name tag / resource name)
    actual_by_name = {}
    for r in actual:
        key = (r["type"], r["name"])
        actual_by_name.setdefault(key, []).append(r)

    # Fallback index: match by terraform:resource tag (format: "aws_instance.web_server")
    actual_by_tf_tag = {}
    for r in actual:
        tags = (r.get("config") or {}).get("tags") or {}
        tf_tag = tags.get("terraform:resource")
        if tf_tag:
            actual_by_tf_tag[tf_tag] = r

    declared_keys = {(r["type"], r["name"]) for r in declared}

    # Track actual resources claimed via fallback tag matching
    claimed_actual_names = set()
    for d in declared:
        key = (d["type"], d["name"])
        if not actual_by_name.get(key):
            tf_tag_key = f"{d['type']}.{d['name']}"
            fallback = actual_by_tf_tag.get(tf_tag_key)
            if fallback:
                claimed_actual_names.add((fallback["type"], fallback["name"]))

    findings = []

    for d in declared:
        key = (d["type"], d["name"])
        matches = actual_by_name.get(key, [])

        # Fallback: check terraform:resource tag when no Name-tag match found
        if not matches:
            tf_tag_key = f"{d['type']}.{d['name']}"
            fallback = actual_by_tf_tag.get(tf_tag_key)
            if fallback:
                matches = [fallback]

        if not matches:
            findings.append({
                "resource_type": d["type"],
                "resource_name": d["name"],
                "status": "missing",
                "declared": d.get("config", {}),
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
                "declared": d.get("config", {}),
                "actual": a.get("config", {}),
                "aws_id": a.get("id", ""),
                "drift_fields": drift_fields,
            })

    for a in actual:
        key = (a["type"], a["name"])
        if key not in declared_keys and key not in claimed_actual_names:
            findings.append({
                "resource_type": a["type"],
                "resource_name": a["name"],
                "status": "unmanaged",
                "declared": None,
                "actual": a.get("config", {}),
                "aws_id": a.get("id", ""),
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

    for path in [args.t_json, args.a_json]:
        if not os.path.exists(path):
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
