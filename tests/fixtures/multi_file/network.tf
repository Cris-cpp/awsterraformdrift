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
