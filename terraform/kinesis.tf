# terraform/kinesis.tf

# Kinesis Data Stream for Stock Quotes
resource "aws_kinesis_stream" "stock_quotes_stream" {
  name             = var.stock_quotes_stream_name # From variables.tf
  shard_count      = 1
  retention_period = 24

  # Stream encryption (KMS)
  stream_mode_details {
    stream_mode = "PROVISIONED" #Using provisioned mode instead of "ON_DEMAND" for predictable performance

  }
  encryption_type = "KMS"
  kms_key_id      = "alias/aws/kinesis" # Default AWS managed key for Kinesis

  tags = {
    Purpose = "To stream real-time stock quote data from producers."
    # The default_tags from provider.tf will also be applied here
  }
}

# Kinesis Data Stream for Company News
resource "aws_kinesis_stream" "company_news_stream" {
  name             = var.company_news_stream_name
  shard_count      = 1
  retention_period = 24

  # Adding these for consistency and explicitness:
  stream_mode_details {
    stream_mode = "PROVISIONED"
  }
  encryption_type = "KMS"
  kms_key_id      = "alias/aws/kinesis" # AWS managed key for Kinesis

  tags = {
    Purpose = "To stream company news articles from producers."
    # Default tags from provider.tf will also be applied
  }
}

# --- Outputs for Kinesis Streams (Optional but useful) ---
# Outputs to provide information about the created Kinesis streams


output "stock_quotes_stream_arn" {
  description = "The ARN of the stock quotes Kinesis Data Stream."
  value       = aws_kinesis_stream.stock_quotes_stream.arn
}

output "stock_quotes_stream_name_output" {
  description = "The name of the stock quotes Kinesis Data Stream."
  value       = aws_kinesis_stream.stock_quotes_stream.name
}

output "company_news_stream_arn" {
  description = "The ARN of the company news Kinesis Data Stream."
  value       = aws_kinesis_stream.company_news_stream.arn
}

output "company_news_stream_name_output" {
  description = "The name of the company news Kinesis Data Stream."
  value       = aws_kinesis_stream.company_news_stream.name
}