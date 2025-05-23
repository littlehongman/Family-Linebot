provider "aws" {
  region = "us-east-1"  # change as needed
}

terraform {
  backend "s3" {
    bucket         = "my-terraform-state-bucket-github-actions"
    key            = "lambda/terraform.tfstate"
    region         = "us-east-1"
  }
}

resource "aws_iam_role" "lambda_exec_role" {
  name = "lambda_exec_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Principal = {
        Service = "lambda.amazonaws.com"
      },
      Effect = "Allow",
      Sid = ""
    }]
  })
}

resource "aws_iam_role_policy_attachment" "basic_lambda_policy" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "my_lambda" {
  function_name = "FamilyLineBot-LangGraph"
  runtime       = "python3.11"
  role          = aws_iam_role.lambda_exec_role.arn
  handler       = "lambda_function.lambda_handler"
  timeout       = 15

  filename         = "${path.module}/../lambda_package.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambda_package.zip")

  environment {
    variables = {
      CHANNEL_ACCESS_TOKEN = var.channel_access_token
      CHANNEL_SECRET        = var.channel_secret
      OPENAI_API_KEY        = var.openai_api_key
      REDIS_KEY             = var.redis_key
      SUPABASE_KEY          = var.supabase_key
    }
  }
}

resource "aws_lambda_function_url" "test_latest" {
  function_name      = aws_lambda_function.my_lambda.function_name
  authorization_type = "NONE"
}
