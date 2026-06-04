import pytest
from pathlib import Path

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

    def test_mismatched_tag_shows_values(self):
        diff = {
            "summary": {"total_declared": 1, "total_found": 1, "total_missing": 0, "total_unmanaged": 0, "total_mismatched": 1},
            "findings": [{
                "resource_type": "aws_instance",
                "resource_name": "web",
                "status": "mismatched",
                "declared": {"instance_type": "t3.micro", "tags": {"Env": "prod"}},
                "actual": {"instance_type": "t3.micro", "tags": {"Env": "staging"}},
                "aws_id": "i-001",
                "drift_fields": ["tags.Env"],
            }],
        }
        report = generate_report(diff, "graph TD")
        assert "prod" in report
        assert "staging" in report
