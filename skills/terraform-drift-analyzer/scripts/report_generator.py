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

SECTION_ORDER = [
    "aws_instance",
    "aws_s3_bucket",
    "aws_iam_role",
    "aws_iam_user",
    "aws_iam_policy",
    "aws_security_group",
]

STATUS_ICONS = {
    "matched": "✅",
    "missing": "❌",
    "mismatched": "⚠️",
    "unmanaged": "🔍",
}


def _get_field_val(config, field):
    if config is None:
        return None
    parts = field.split(".", 1)
    if len(parts) == 2:
        return (config.get(parts[0]) or {}).get(parts[1])
    return config.get(field)


def _escape_md(s):
    s = str(s)  # guard against non-string resource names
    for ch in ["\\", "`", "[", "]", "*"]:
        s = s.replace(ch, f"\\{ch}")
    return s


def _truncate_id(rid, max_len=50):
    if rid and len(str(rid)) > max_len:
        return str(rid)[:max_len] + "..."
    return rid or ""


def _get_aws_id(finding):
    return _truncate_id(finding.get("aws_id", ""))


def build_report(diff_json, mmd_content):
    s = diff_json["summary"]
    findings = diff_json["findings"]
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = []

    lines.append("# Terraform Drift Report")
    lines.append(f"Generated: {timestamp}")
    lines.append("")
    lines.append("## Architecture")
    lines.append("")
    lines.append("```mermaid")
    lines.append(mmd_content)
    lines.append("```")
    lines.append("")
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
            lines.append(f"### {SECTION_LABELS.get(rtype, rtype)}")
            for f in by_type[rtype]:
                icon = STATUS_ICONS.get(f["status"], "?")
                name = _escape_md(f["resource_name"])
                if f["status"] == "matched":
                    lines.append(f"- {icon} {name} — matched")
                elif f["status"] == "missing":
                    lines.append(f"- {icon} {name} — missing in AWS")
                elif f["status"] == "mismatched":
                    aws_id = _get_aws_id(f)
                    id_str = f" ({aws_id})" if aws_id else ""
                    drift_details = ", ".join(
                        f"{field}: declared `{_get_field_val(f.get('declared'), field)}`, actual `{_get_field_val(f.get('actual'), field)}`"
                        for field in f.get("drift_fields", [])
                    )
                    lines.append(f"- {icon} {name}{id_str} — mismatched ({drift_details})")
            lines.append("")

    unmanaged = [f for f in findings if f["status"] == "unmanaged"]
    if unmanaged:
        lines.append("## Unmanaged Resources")
        lines.append("Resources found in AWS not declared in Terraform:")
        lines.append("")
        by_type_u = {}
        for f in unmanaged:
            by_type_u.setdefault(f["resource_type"], []).append(f)
        for rtype in SECTION_ORDER:
            if rtype not in by_type_u:
                continue
            label = SECTION_LABELS.get(rtype, rtype)
            for f in by_type_u[rtype]:
                name = _escape_md(f["resource_name"])
                aws_id = _get_aws_id(f)
                id_str = f" ({aws_id})" if aws_id else ""
                lines.append(f"- 🔍 {label}: {name}{id_str}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate report.md from diff.json and architecture.mmd"
    )
    parser.add_argument("diff_json", help="Path to diff.json")
    parser.add_argument("architecture_mmd", help="Path to architecture.mmd")
    parser.add_argument("--output", default="report.md")
    parser.add_argument("--workspace", default=WORKSPACE)
    args = parser.parse_args()

    for path, label in [
        (args.diff_json, "diff.json"),
        (args.architecture_mmd, "architecture.mmd"),
    ]:
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
