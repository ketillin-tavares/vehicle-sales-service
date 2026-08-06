# GitHub Actions OIDC federation — no long-lived AWS keys in GitHub secrets.
#
# TWO flags, deliberately split (vehicle-core-service has a single one):
#
# - var.create_github_oidc_provider (default FALSE) — AWS allows exactly ONE
#   aws_iam_openid_connect_provider per URL per account, and
#   vehicle-core-service already owns the one for
#   token.actions.githubusercontent.com. This stack READS it with a data
#   source. Flipping this to true in a second account (or after Core is gone)
#   makes this stack own it instead.
# - var.enable_github_oidc (default TRUE) — gates only the DEPLOY ROLE.
#   Set to false ONLY in the Floci local root: the emulator implements
#   neither CreateOpenIDConnectProvider nor GetOpenIDConnectProvider, so the
#   data source has to be counted out there too.
#
# Collapsing these back into one flag would mean "do not create the shared
# provider" implies "do not create a deploy role", leaving this service with
# no CD identity and a null deploy_role_arn output.

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.enable_github_oidc && var.create_github_oidc_provider ? 1 : 0

  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
}

# The shared provider created by vehicle-core-service's stack. Read-only —
# this stack must never be able to update its thumbprints or delete it (see
# infra/tfc-run-role-policy.json, Sid ReadSharedGithubOidcProvider), because
# doing so would break Core's CD as well as this one.
data "aws_iam_openid_connect_provider" "github" {
  count = var.enable_github_oidc && !var.create_github_oidc_provider ? 1 : 0

  url = "https://token.actions.githubusercontent.com"
}

locals {
  github_repository = "${var.github_org}/${local.service_name}"

  # Exactly one of the resource and the data source above is ever active;
  # the inactive one's splat is empty and one() yields null. A ternary rather
  # than coalesce() so the Floci root (enable_github_oidc = false, BOTH
  # empty) evaluates to null instead of failing with "no non-null arguments".
  github_oidc_provider_arn = (var.create_github_oidc_provider
    ? one(aws_iam_openid_connect_provider.github[*].arn)
  : one(data.aws_iam_openid_connect_provider.github[*].arn))

  # Two exact forms of the OIDC `sub` claim, both pinned in the trust policy.
  #
  # GitHub currently emits the IMMUTABLE-IDENTIFIER form: owner and repository
  # names each carry an `@<numeric id>` suffix (confirmed via CloudTrail — the
  # `userName` of an AssumeRoleWithWebIdentity event IS the `sub` claim). The
  # plain-name form is kept so the deploy does not break if the emitted format
  # changes back. Both are exact strings under StringEquals (arrays are
  # evaluated as OR), so the trust boundary is unchanged — no wildcards.
  #
  # Same owner id as vehicle-core-service, DIFFERENT repository id — both
  # default to this repo's real values in variables.tf.
  github_subject_by_name = "repo:${local.github_repository}:ref:refs/heads/main"
  github_subject_by_id   = "repo:${var.github_org}@${var.github_owner_id}/${local.service_name}@${var.github_repository_id}:ref:refs/heads/main"
}

# Deploy role: assumable ONLY by this repo's main branch (security item 2 —
# exact StringEquals on aud and sub, no wildcards).
resource "aws_iam_role" "deploy" {
  count = var.enable_github_oidc ? 1 : 0

  name = "${local.service_name}-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Federated = local.github_oidc_provider_arn }
        Action    = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = [
              local.github_subject_by_name,
              local.github_subject_by_id,
            ]
          }
        }
      }
    ]
  })
}

# Least-privilege deploy policy (security item 5 + ECR push):
# - ssm:SendCommand restricted to the AWS-RunShellScript document AND to
#   instances carrying the Service tag;
# - ssm:GetCommandInvocation to read command results;
# - ec2:DescribeInstances so CD can resolve the instance id by tag
#   (read-only; not resource-scopable, by AWS design);
# - ECR auth + push limited to the app repository;
# - nothing else.
resource "aws_iam_role_policy" "deploy" {
  count = var.enable_github_oidc ? 1 : 0

  name = "${local.service_name}-deploy-policy"
  role = aws_iam_role.deploy[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SendCommandDocument"
        Effect   = "Allow"
        Action   = "ssm:SendCommand"
        Resource = "arn:aws:ssm:${data.aws_region.current.name}::document/AWS-RunShellScript"
      },
      {
        Sid      = "SendCommandTaggedInstance"
        Effect   = "Allow"
        Action   = "ssm:SendCommand"
        Resource = "arn:aws:ec2:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:instance/*"
        Condition = {
          StringEquals = {
            "ssm:resourceTag/Service" = local.service_name
          }
        }
      },
      {
        Sid      = "ReadCommandResult"
        Effect   = "Allow"
        Action   = "ssm:GetCommandInvocation"
        Resource = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Sid      = "ResolveInstanceByTag"
        Effect   = "Allow"
        Action   = "ec2:DescribeInstances"
        Resource = "*" # read-only; not resource-scopable, by AWS design
      },
      {
        Sid      = "EcrAuthToken"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*" # not resource-scopable, by AWS design
      },
      {
        Sid    = "EcrPushAppRepo"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
        ]
        Resource = aws_ecr_repository.app.arn
      }
    ]
  })
}
