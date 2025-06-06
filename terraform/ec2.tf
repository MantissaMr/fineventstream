# terraform/ec2.tf

# --- Data Source to find the latest Amazon Linux 2 AMI ---
data "aws_ami" "amazon_linux_2" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# --- Security Group for EC2 Producer Instances ---
# This acts as a virtual firewall for the instances.
resource "aws_security_group" "producer_sg" {
  name        = "${var.project_name}-producer-sg"
  description = "Allow outbound traffic and inbound SSH from my IP"

  # Ingress (inbound) rule: SSH from my IP address
  ingress {
    from_port   = 22 # Port for SSH
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_with_cidr] # Restricts access to your IP
  }

  # Egress (outbound) rule: Allow all outbound traffic
  # Needed for producers to call Finnhub API, AWS services (Kinesis, SSM), and run yum updates.
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1" # all protocols
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- EC2 Instance for Stock Quotes Producer ---
resource "aws_instance" "stock_quotes_producer" {
  ami           = data.aws_ami.amazon_linux_2.id
  instance_type = var.ec2_instance_type
  key_name      = var.ec2_key_pair_name

  # Attach the IAM role via the instance profile created in iam.tf
  iam_instance_profile = aws_iam_instance_profile.ec2_producer_instance_profile.name

  # Attach the security group
  vpc_security_group_ids = [aws_security_group.producer_sg.id]

  # Render the user data template with variables specific to this producer
  user_data = templatefile("${path.module}/templates/user_data.sh.tpl", {
    github_repo_url  = var.github_repo_url
    script_to_run    = "producer_stock_quotes.py"
    finnhub_api_key  = var.finnhub_api_key
  })

  # Override the default tag for 'Name' to easily identify the instance
  tags = {
    Name = "${var.project_name}-stock-quotes-producer"
  }
}

# --- EC2 Instance for Company News Producer ---
resource "aws_instance" "company_news_producer" {
  ami           = data.aws_ami.amazon_linux_2.id
  instance_type = var.ec2_instance_type
  key_name      = var.ec2_key_pair_name

  iam_instance_profile = aws_iam_instance_profile.ec2_producer_instance_profile.name
  vpc_security_group_ids = [aws_security_group.producer_sg.id]

  # Render the user data template with variables specific to this producer
  user_data = templatefile("${path.module}/templates/user_data.sh.tpl", {
    github_repo_url  = var.github_repo_url
    script_to_run    = "producer_company_news.py"
    finnhub_api_key  = var.finnhub_api_key
  })

  tags = {
    Name = "${var.project_name}-company-news-producer"
  }
}


# --- Outputs for EC2 Instances ---
output "stock_quotes_producer_public_ip" {
  description = "The public IP address of the stock quotes producer instance."
  value       = aws_instance.stock_quotes_producer.public_ip
}

output "company_news_producer_public_ip" {
  description = "The public IP address of the company news producer instance."
  value       = aws_instance.company_news_producer.public_ip
}