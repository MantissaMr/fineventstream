# terraform/s3.tf

# Resource to generate a random suffix for S3 bucket global uniqueness
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# S3 Bucket for storing processed data (our data lake)
resource "aws_s3_bucket" "data_lake_bucket" {
  bucket = "${var.s3_bucket_name_prefix}-${random_id.bucket_suffix.hex}"
  force_destroy = true # Allows deletion of non-empty bucket
  tags = {
    Purpose = "Data Lake for FinEventStream"
  }
}

# Separate resource for S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "data_lake_bucket_versioning" {
  bucket = aws_s3_bucket.data_lake_bucket.id # Reference the bucket created above

  versioning_configuration {
    status = "Enabled" # Can be "Enabled" or "Suspended"
  }
  depends_on = [aws_s3_bucket.data_lake_bucket]
}

# Separate resource for S3 Bucket Server-Side Encryption configuration 
resource "aws_s3_bucket_server_side_encryption_configuration" "data_lake_bucket_sse" {
  bucket = aws_s3_bucket.data_lake_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # SSE-S3 (default encryption)
    }
    # In case we'd use SSE-KMS, it'd be:
    # sse_algorithm     = "aws:kms"
    # kms_master_key_id = "alias/aws/s3" # or our CMK ARN
  }
  depends_on = [aws_s3_bucket.data_lake_bucket]
}

# Separate resource for S3 Bucket Public Access Block settings
resource "aws_s3_bucket_public_access_block" "data_lake_bucket_pab" {
  bucket = aws_s3_bucket.data_lake_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  depends_on = [aws_s3_bucket.data_lake_bucket]
}

# S3 Bucket Ownership Controls
resource "aws_s3_bucket_ownership_controls" "data_lake_bucket_ownership" {
  bucket = aws_s3_bucket.data_lake_bucket.id

  rule {
    object_ownership = "BucketOwnerEnforced" # Simplifies permissions
  }
  depends_on = [aws_s3_bucket.data_lake_bucket]
}

# --- Outputs for S3 Bucket ---
output "data_lake_bucket_name" {
  description = "The globally unique name of the S3 data lake bucket."
  value       = aws_s3_bucket.data_lake_bucket.bucket 
}

output "data_lake_bucket_arn" {
  description = "The ARN of the S3 data lake bucket."
  value       = aws_s3_bucket.data_lake_bucket.arn
}