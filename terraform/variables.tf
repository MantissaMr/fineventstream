# terraform/variables.tf

variable "aws_region" {
  description = "The AWS region where resources will be created."
  type        = string
  default     = "af-south-1"
}

variable "project_name" {
  description = "A short name for the project, used for naming and tagging resources."
  type        = string
  default     = "fineventstream"
}

variable "environment" {
  description = "The deployment environment."
  type        = string
  default     = "dev"
}

# Variables for Kinesis Stream names
variable "stock_quotes_stream_name" {
  description = "Name for the Kinesis Data Stream for stock quotes."
  type        = string
  default     = "fineventstream-stock-quotes"
}

variable "company_news_stream_name" {
  description = "Name for the Kinesis Data Stream for company news."
  type        = string
  default     = "fineventstream-company-news"
}

# Variables for S3 bucket names
variable "s3_bucket_name_prefix" {
  description = "Prefix for the S3 data lake bucket name. A random suffix will be added."
  type        = string
  default     = "fineventstream-data"
}