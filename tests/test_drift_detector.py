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
