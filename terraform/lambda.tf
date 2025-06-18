# terraform/lambda.tf

# This file defines the Lambda function that processes what our producers 
# are sending to Kinesis, tapping from the output of Kinesis streams, and stores the result in an S3 bucket.
data "archive_file" "stock_quotes_processor_zip" {
  type        = "zip"
  source_file = "${path.root}/../src/lambda_processor/processor_stock_quotes.py" # Path relative to this .tf file's location
  output_path = "${path.root}/../dist/stock_quotes_processor.zip" # Output ZIP to a dist/ directory at project root
}


# --- Lambda Function for Stock Quotes Processor ---
resource "aws_lambda_function" "stock_quotes_processor_lambda" {
  function_name = "${var.project_name}-stock-quotes-processor"
  
  # Reference the ZIP file we created above
  filename         = data.archive_file.stock_quotes_processor_zip.output_path
  source_code_hash = data.archive_file.stock_quotes_processor_zip.output_base64sha256

  # The handler is in the format: filename.function_name
  handler = "processor_stock_quotes.lambda_handler"
  runtime = "python3.9" # Or your preferred supported Python version

  # Assign the IAM role we defined in iam.tf
  role = aws_iam_role.lambda_processor_role.arn

  # Lambda configuration
  memory_size = 128 # MB, default, sufficient for this function
  timeout     = 30  # seconds, default is 3.. increasing the buffer in case Kinesis processing takes longer.

  # Set environment variables for the Lambda function
  environment {
    variables = {
        # The S3 bucket where processed data will be stored
      DESTINATION_S3_BUCKET = aws_s3_bucket.data_lake_bucket.bucket
    }
  }

  tags = {
    Purpose = "Processes stock quote data from Kinesis and stores it in S3."
  }
}

# --- Kinesis Event Source Mapping (Trigger) ---
# This resource connects our Kinesis stream to our Lambda function.
resource "aws_lambda_event_source_mapping" "stock_quotes_kinesis_trigger" {
  event_source_arn  = aws_kinesis_stream.stock_quotes_stream.arn # Which stream to listen to
  function_name     = aws_lambda_function.stock_quotes_processor_lambda.arn # Which Lambda to trigger
  starting_position = "LATEST" # Start processing new records, not old ones
  
  # Optional: Batching configuration
  batch_size = 100 # Max number of records to send to Lambda in one batch
  maximum_batching_window_in_seconds = 10 # Max time to wait to build a batch
}

# --- Packaging for Company News Lambda ---
data "archive_file" "company_news_processor_zip" {
  type        = "zip"
  source_file = "${path.module}/../src/lambda_processor/processor_company_news.py"
  output_path = "${path.module}/../dist/company_news_processor.zip"
}

# --- Lambda Function for Company News Processor ---
resource "aws_lambda_function" "company_news_processor_lambda" {
  function_name = "${var.project_name}-company-news-processor"
  
  filename         = data.archive_file.company_news_processor_zip.output_path
  source_code_hash = data.archive_file.company_news_processor_zip.output_base64sha256

  handler = "processor_company_news.lambda_handler"
  runtime = "python3.9"

  # NOTE: We use the SAME IAM role as the other Lambda.
  role = aws_iam_role.lambda_processor_role.arn

  memory_size = 128 # MB
  timeout     = 30  # seconds

  environment {
    variables = {
      DESTINATION_S3_BUCKET = aws_s3_bucket.data_lake_bucket.bucket
    }
  }

  tags = {
    Purpose = "Processes company news data from Kinesis and stores it in S3."
  }
}

# --- Kinesis Event Source Mapping (Trigger) for Company News ---
resource "aws_lambda_event_source_mapping" "company_news_kinesis_trigger" {
  event_source_arn  = aws_kinesis_stream.company_news_stream.arn # <-- Triggers from the news stream
  function_name     = aws_lambda_function.company_news_processor_lambda.arn # <-- Triggers the new news lambda
  starting_position = "LATEST"
  
  batch_size = 100
  maximum_batching_window_in_seconds = 10
}


# --- Outputs for Stock Quotes Processor ---
output "stock_quotes_processor_lambda_arn" {
  description = "The ARN of the Stock Quotes Processor Lambda function."
  value       = aws_lambda_function.stock_quotes_processor_lambda.arn
}

# --- Outputs for the Company News Processor ---
output "company_news_processor_lambda_arn" {
  description = "The ARN of the Company News Processor Lambda function."
  value       = aws_lambda_function.company_news_processor_lambda.arn
}