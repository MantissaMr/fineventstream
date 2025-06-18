# terraform/iam.tf

# --- IAM Role for EC2 Instances (Producers) ---
resource "aws_iam_role" "ec2_producer_role" {
  name = "${var.project_name}-ec2-producer-role"

  # Policy that allows EC2 instances to assume this role
  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [
      {
        Action    = "sts:AssumeRole",
        Effect    = "Allow",
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Purpose = "Allows EC2 producer instances to send data to Kinesis and logs to CloudWatch"
    # Other default tags from provider.tf will also be applied
  }
}

# --- Policies for EC2 Producer Role ---

# 1. Policy to allow writing to Kinesis Data Streams
resource "aws_iam_policy" "ec2_kinesis_write_policy" {
  name        = "${var.project_name}-ec2-kinesis-write-policy"
  description = "Allows EC2 instances to write to specific Kinesis Data Streams"

  policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "kinesis:PutRecord",
          "kinesis:PutRecords" // Good to have for batch writes
        ],
        Resource = [
          aws_kinesis_stream.stock_quotes_stream.arn,    # Reference to our stock quotes stream
          aws_kinesis_stream.company_news_stream.arn     # Reference to our company news stream
        ]
      }
    ]
  })
}

# Attach Kinesis write policy to the EC2 role
resource "aws_iam_role_policy_attachment" "ec2_attach_kinesis_write_policy" {
  role       = aws_iam_role.ec2_producer_role.name
  policy_arn = aws_iam_policy.ec2_kinesis_write_policy.arn
}

# 2. Policy to allow writing logs to CloudWatch Logs
resource "aws_iam_policy" "ec2_cloudwatch_logs_policy" {
  name        = "${var.project_name}-ec2-cloudwatch-logs-policy"
  description = "Allows EC2 instances to write logs to CloudWatch Logs"

  policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "logs:CreateLogGroup",    # Allows creating a log group if it doesn't exist
          "logs:CreateLogStream",   # Allows creating a log stream within a group
          "logs:PutLogEvents",      # Allows sending log events
          "logs:DescribeLogStreams" # Often needed by log agents to check stream status
        ],
        Resource = "arn:aws:logs:*:*:*" # Allows logging to any log group/stream.
                                        # Can be restricted further if specific log group names are known.
      }
    ]
  })
}

# Attach CloudWatch Logs policy to the EC2 role
resource "aws_iam_role_policy_attachment" "ec2_attach_cloudwatch_logs_policy" {
  role       = aws_iam_role.ec2_producer_role.name
  policy_arn = aws_iam_policy.ec2_cloudwatch_logs_policy.arn
}

# We will need an EC2 Instance Profile to attach the role to EC2 instances
resource "aws_iam_instance_profile" "ec2_producer_instance_profile" {
  name = "${var.project_name}-ec2-producer-profile"
  role = aws_iam_role.ec2_producer_role.name
}


# --- IAM Role for Lambda Functions (Consumers)  ---
resource "aws_iam_role" "lambda_processor_role" {
  name = "${var.project_name}-lambda-processor-role"

  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [
      {
        Action    = "sts:AssumeRole",
        Effect    = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Purpose = "Allows Lambda functions to process data from Kinesis and store in S3"
  }
}

# --- Policies for Lambda Processor Role ---

# 1. Basic Lambda execution policy (allows writing to CloudWatch Logs)
resource "aws_iam_role_policy_attachment" "lambda_attach_basic_execution_policy" {
  role       = aws_iam_role.lambda_processor_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# 2. Policy to allow Lambda to read from Kinesis Data Streams
resource "aws_iam_policy" "lambda_kinesis_read_policy" {
  name        = "${var.project_name}-lambda-kinesis-read-policy"
  description = "Allows Lambda to read from our Kinesis Data Streams"

  policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "kinesis:GetRecords",
          "kinesis:GetShardIterator",
          "kinesis:DescribeStream",
          "kinesis:ListStreams",
          "kinesis:ListShards"
        ],
        Resource = [
          aws_kinesis_stream.stock_quotes_stream.arn,
          aws_kinesis_stream.company_news_stream.arn
        ]
      }
    ]
  })
}

# Attach the Kinesis read policy to the Lambda role
resource "aws_iam_role_policy_attachment" "lambda_attach_kinesis_read" {
  role       = aws_iam_role.lambda_processor_role.name
  policy_arn = aws_iam_policy.lambda_kinesis_read_policy.arn
}

# 3. Policy to allow Lambda to write to the S3 Data Lake bucket
resource "aws_iam_policy" "lambda_s3_write_policy" {
  name        = "${var.project_name}-lambda-s3-write-policy"
  description = "Allows Lambda to write processed data objects to the S3 data lake bucket"

  policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "s3:PutObject"
        ],
        Resource = [
          aws_s3_bucket.data_lake_bucket.arn,
          "${aws_s3_bucket.data_lake_bucket.arn}/*" # Allow actions on objects inside the bucket
        ]
      }
    ]
  })
}

# Attach the S3 write policy to the Lambda role
resource "aws_iam_role_policy_attachment" "lambda_attach_s3_write" {
  role       = aws_iam_role.lambda_processor_role.name
  policy_arn = aws_iam_policy.lambda_s3_write_policy.arn
}


# --- Outputs for IAM Roles ---
output "ec2_producer_role_arn" {
  description = "The ARN of the IAM role for EC2 producers."
  value       = aws_iam_role.ec2_producer_role.arn
}

output "ec2_producer_instance_profile_arn" {
  description = "The ARN of the IAM instance profile for EC2 producers."
  value       = aws_iam_instance_profile.ec2_producer_instance_profile.arn
}

output "lambda_processor_role_arn" {
  description = "The ARN of the IAM role for Lambda processors."
  value       = aws_iam_role.lambda_processor_role.arn
}