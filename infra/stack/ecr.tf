# --- ECR repository (container images — pushed by CD, pulled by the EC2) --

resource "aws_ecr_repository" "app" {
  name                 = local.service_name
  image_tag_mutability = "MUTABLE" # required for the moving `latest` tag
  force_delete         = true      # student MVP: destroy must work on a non-empty repo

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only the last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      }
    ]
  })
}

# EC2 pulls images with its instance role — no registry credentials ever go
# through SSM parameters or SendCommand (resolves security item 6).
resource "aws_iam_role_policy" "instance_ecr_pull" {
  name = "${local.service_name}-ecr-pull"
  role = aws_iam_role.instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrAuthToken"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*" # not resource-scopable, by AWS design
      },
      {
        Sid    = "EcrPullAppRepo"
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchCheckLayerAvailability",
        ]
        Resource = aws_ecr_repository.app.arn
      }
    ]
  })
}
