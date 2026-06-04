resource "aws_instance" "web_server" {
  instance_type = "t3.micro"
  ami           = "ami-0abcdef1234567890"

  vpc_security_group_ids = [aws_security_group.allow_web.id]

  tags = {
    Name = "web_server"
  }
}

resource "aws_security_group" "allow_web" {
  name        = "allow_web"
  description = "Allow web traffic"

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "allow_web"
  }
}

resource "aws_s3_bucket" "logs_bucket" {
  bucket = "my-logs-bucket"

  tags = {
    Name = "logs_bucket"
  }
}
