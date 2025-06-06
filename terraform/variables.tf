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

# --- Variables for EC2 Instances ---

variable "ec2_instance_type" {
  description = "The EC2 instance type to use for the producers."
  type        = string
  default     = "t3.micro" 
}

variable "github_repo_url" {
  description = "The HTTPS URL of the public GitHub repository to clone."
  type        = string
}

variable "my_ip_with_cidr" {
  description = "Your public IP address with a /32 CIDR block for SSH access."
  type        = string
}

variable "ec2_key_pair_name" {
  description = "The name of the EC2 key pair to allow SSH access."
  type        = string
}

variable "finnhub_api_key" {
  description = "The Finnhub API key."
  type        = string
  sensitive   = true # Prevents Terraform from showing this value in CLI output
}