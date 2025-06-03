# terraform/provider.tf

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend configuration we'll skip since we're using local state (for now)
  # It'll tell Terraform to store its state file (which keeps track of the resources it manages) in an S3 bucket 
  # and use DynamoDB for locking (to prevent multiple people from running terraform apply at the same time and corrupting state)
  # backend "s3" {
  #   bucket         = "terraform-state-bucket-name" 
  #   key            = "fineventstream/terraform.tfstate"
  #   region         = "aws-region" 
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks-table" # For state locking
  # }
}

provider "aws" {
  region = var.aws_region
  # Apply these tags to all taggable resources created by this provider
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "Alameen"
    }
  }
}