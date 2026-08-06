# --- KMS CMK for the SSM SecureString parameters (security item M3) -------
#
# With the account-default alias/aws/ssm key, ANY principal allowed to call
# ssm:GetParameter --with-decryption can read every service's SecureStrings.
# A dedicated CMK gates decryption of THIS service's parameters by this key
# policy: only the instance role (and account admins via root delegation)
# can decrypt. Cost: USD 1/mo per CMK + negligible request charges.

resource "aws_kms_key" "ssm" {
  description         = "${local.service_name}: encrypts the service's SSM SecureString parameters"
  enable_key_rotation = true

  # Explicit tags: the TFC run role's KMS permissions are ABAC-conditioned
  # on Service=vehicle-sales-service — do NOT rely on default_tags here.
  tags = local.standard_tags

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Root delegation: key administration via normal IAM policies
        # (TFC run role, human admins). Standard KMS pattern — without it
        # the key becomes unmanageable.
        Sid       = "AccountRootAdmin"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        # deploy.sh on the instance: ssm get-parameter --with-decryption.
        # Decrypt only, and only through SSM in this region.
        Sid       = "InstanceRoleDecryptViaSsm"
        Effect    = "Allow"
        Principal = { AWS = aws_iam_role.instance.arn }
        Action    = "kms:Decrypt"
        Resource  = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "ssm.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_kms_alias" "ssm" {
  name          = "alias/${local.service_name}-ssm"
  target_key_id = aws_kms_key.ssm.key_id
}

# --- KMS CMK for RDS (storage + managed master-user secret) ---------------
#
# aws_db_instance.app points at this key EXPLICITLY (kms_key_id and
# master_user_secret_kms_key_id): with no explicit key, RDS falls back to
# the AWS-managed aws/rds and aws/secretsmanager keys, which the
# least-privilege TFC run role cannot touch (all its KMS actions are scoped
# to service-tagged keys) — real-AWS apply failed with
# KMSKeyNotAccessibleFault. Cost: USD 1/mo.

resource "aws_kms_key" "rds" {
  description         = "${local.service_name}: encrypts RDS storage and the managed master-user secret"
  enable_key_rotation = true

  # Explicit tags: the TFC run role's KMS permissions are ABAC-conditioned
  # on Service=vehicle-sales-service — do NOT rely on default_tags here.
  tags = local.standard_tags

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Root delegation: key administration and service usage authorized
        # through normal IAM policies (TFC run role holds the tag-scoped
        # kms actions, incl. CreateGrant for the RDS service grant).
        Sid       = "AccountRootAdmin"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        # deploy.sh on the instance: secretsmanager get-secret-value for
        # DATABASE_PASSWORD. Decrypt only, only through Secrets Manager.
        Sid       = "InstanceRoleDecryptViaSecretsManager"
        Effect    = "Allow"
        Principal = { AWS = aws_iam_role.instance.arn }
        Action    = "kms:Decrypt"
        Resource  = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${local.service_name}-rds"
  target_key_id = aws_kms_key.rds.key_id
}
