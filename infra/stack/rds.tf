# --- RDS PostgreSQL (production database — replaces the postgres container)

resource "aws_db_subnet_group" "app" {
  name       = "${local.service_name}-db"
  subnet_ids = data.aws_subnets.default.ids
}

# Dedicated SG: 5432 only from the app instance SG — no CIDRs.
resource "aws_security_group" "db" {
  name        = "${local.service_name}-db-sg"
  description = "vehicle-sales-service RDS: PostgreSQL from the app SG only"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "PostgreSQL from app instance"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
}

resource "aws_db_instance" "app" {
  identifier     = local.service_name
  engine         = "postgres"
  engine_version = "17"
  instance_class = "db.t4g.micro" # free-tier-friendly, single-AZ

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true
  # Explicit CMK: the AWS-managed aws/rds default is NOT accessible to the
  # least-privilege TFC run role (KMS actions scoped to service-tagged keys).
  kms_key_id = aws_kms_key.rds.arn

  db_name  = "vehicle_sales"
  username = "vehicle_sales_user"
  # Master password managed by RDS in Secrets Manager — never in TF state.
  # Same explicit CMK (default would be the aws/secretsmanager managed key).
  manage_master_user_password   = true
  master_user_secret_kms_key_id = aws_kms_key.rds.arn

  db_subnet_group_name   = aws_db_subnet_group.app.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  multi_az               = false

  # Student MVP: destroy must work without manual steps.
  deletion_protection = false
  skip_final_snapshot = true
}

# deploy.sh materializes DATABASE_PASSWORD from the RDS-managed secret.
resource "aws_iam_role_policy" "instance_db_secret" {
  name = "${local.service_name}-db-secret-read"
  role = aws_iam_role.instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadRdsMasterSecret"
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = aws_db_instance.app.master_user_secret[0].secret_arn
      }
    ]
  })
}
