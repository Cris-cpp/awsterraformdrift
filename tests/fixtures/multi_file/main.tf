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
