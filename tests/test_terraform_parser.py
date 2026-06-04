import json
import os
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def parse_terraform(directory):
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

    def test_missing_optional_fields_are_null(self, tmp_path):
        (tmp_path / "main.tf").write_text('''
resource "aws_instance" "minimal" {
  instance_type = "t3.micro"
  ami = "ami-111"
}
''')
        result = parse_terraform(str(tmp_path))
        instance = next(r for r in result["resources"] if r["name"] == "minimal")
        # tags is optional and not declared — should be null, not missing
        assert "tags" in instance["config"]
        assert instance["config"]["tags"] is None
