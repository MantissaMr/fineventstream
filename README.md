# FinEventStream: A Streaming Data Pipeline

An end-to-end, event-driven data pipeline on AWS that ingests stock quotes and company news from the Finnhub API, processes the data in near real-time, and stores it in a data lake.

---
### Architecture Diagram

![Architecture Diagram](docs/architectureDiagram.svg) 

**Producers (EC2):** Two Python scripts running on separate EC2 instances poll Finnhub API endpoints for stock quotes and company news.

**Stream (Kinesis):** Producers send data to two distinct Kinesis Data Streams. Each stream serves as a dedicated topic (stock-quotes and company-news)

**Process (Lambda):** Two Lambda functions are independently triggered by their respective Kinesis streams. They process batches of records and prepare them for storage.

**Store (S3):** The processed data is written in JSON Lines format to an S3 bucket, partitioned by `year/month/day/hour` for efficient querying.

---
### Tech Stack

*   **Cloud:** AWS
*   **Infrastructure as Code:** Terraform
*   **Producers:** EC2 instances
*   **Broker:** Amazon Kinesis Data Streams
*   **Consumers:** AWS Lambda
*   **Data Lake:** Amazon S3

---
### Next Feats

**Analytics Layer:** Defining table schemas with Glue and using Athena to query the data lake.

**State Management:** Persisting the news producer's `last_seen_id` state in DynamoDB for resilience across restarts.

**CI/CD:** Building a GitHub Actions workflow to automate testing and `terraform apply`.

**Data Quality:** Integrating a framework like GX for data validation within the pipeline.

**Containerization:** Packaging the Python producers as Docker containers for more consistent deployment.

**Monitoring & Alerting:** Creating a detailed CloudWatch Dashboard for pipeline metrics and setting up SNS alarms for failures.