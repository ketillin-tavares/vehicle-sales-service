# --- Networking (default VPC — cost/simplicity, see ADR-0001) ------------

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# --- AMI ------------------------------------------------------------------

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

# --- Security group -------------------------------------------------------

resource "aws_security_group" "app" {
  name        = "${local.service_name}-sg"
  description = "vehicle-sales-service: app port only, no SSH (access via SSM)"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Application HTTP"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- IAM instance profile (SSM managed instance, no SSH keys) -------------

resource "aws_iam_role" "instance" {
  name = "${local.service_name}-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "instance_ssm" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# AmazonSSMManagedInstanceCore grants ssm:GetParameter* on Resource "*", so
# without this the instance could read the PEER service's plain-String
# db_config parameters (host/user/db name/secret ARN). An explicit Deny wins
# over any Allow.
#
# Scoped to the peer's prefix rather than written as a NotResource allow-list:
# NotResource would also deny the SSM agent's own reads under /aws/service/*
# and break the managed-instance channel.
resource "aws_iam_role_policy" "instance_deny_peer_params" {
  name = "${local.service_name}-deny-peer-ssm"
  role = aws_iam_role.instance.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "DenyPeerServiceParameters"
      Effect   = "Deny"
      Action   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
      Resource = "arn:aws:ssm:*:*:parameter/${local.peer_service_name}/*"
    }]
  })
}

resource "aws_iam_instance_profile" "instance" {
  name = "${local.service_name}-instance-profile"
  role = aws_iam_role.instance.name
}

# --- EC2 instance ---------------------------------------------------------

resource "aws_instance" "app" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.instance.name

  user_data = file("${path.module}/user_data.sh")

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1
  }

  root_block_device {
    encrypted   = true
    volume_type = "gp3"
    volume_size = 16
  }

  # Explicit tags: two IAM conditions target this instance's Service tag
  # (deploy role ssm:SendCommand, TFC run role Terminate/Stop) — do NOT
  # rely on default_tags propagation.
  tags = merge(local.standard_tags, {
    Name = local.service_name
  })
}

# --- Elastic IP (stable endpoint) -----------------------------------------

resource "aws_eip" "app" {
  domain = "vpc"

  tags = {
    Name = local.service_name
  }
}

resource "aws_eip_association" "app" {
  instance_id   = aws_instance.app.id
  allocation_id = aws_eip.app.id
}
