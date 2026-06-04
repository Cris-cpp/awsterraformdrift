import json
import pytest
from pathlib import Path


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
