import json
import base64
import logging
import boto3
import os
import datetime

# --- Configuration & Initialization ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)

DESTINATION_S3_BUCKET = os.getenv("DESTINATION_S3_BUCKET")
if not DESTINATION_S3_BUCKET:
    raise ValueError("FATAL: Environment variable DESTINATION_S3_BUCKET is not set.")

s3_client = boto3.client("s3")


def lambda_handler(event, context):
    """
    Main handler for processing a batch of Kinesis records containing company news.
    """
    logger.info(f"Processing {len(event.get('Records', []))} Kinesis records.")

    processed_records_for_s3 = ""

    for record in event.get("Records", []):
        try:
            payload_b64 = record.get("kinesis", {}).get("data")
            if not payload_b64:
                logger.warning("Skipping record with no kinesis.data payload.")
                continue

            payload_decoded = base64.b64decode(payload_b64).decode("utf-8")
            news_data = json.loads(payload_decoded)

            # NOTE: No further processing for now, trusting producer format.
            # Could add schema validation or enrichment here in the future.

            processed_records_for_s3 += json.dumps(news_data) + "\n"

        except json.JSONDecodeError as e:
            logger.error(
                f"JSON DECODE ERROR: Could not parse record payload. Payload (first 100 chars): '{payload_decoded[:100]}'. Error: {e}"
            )
            continue
        except Exception as e:
            logger.error(f"UNEXPECTED RECORD-LEVEL ERROR: {e}", exc_info=True)

    # --- S3 Batch Write ---
    if processed_records_for_s3:
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            # IMPORTANT: Write to a different S3 prefix than the quotes processor!
            s3_partition_prefix = now.strftime("year=%Y/month=%m/day=%d/hour=%H/")
            file_name = f"company_news_{now.strftime('%Y-%m-%d-%H-%M-%S')}_{context.aws_request_id}.jsonl"
            s3_key = f"processed/company_news/{s3_partition_prefix}{file_name}"  # <-- Changed prefix

            logger.info(
                f"Writing {len(processed_records_for_s3.strip().splitlines())} records to s3://{DESTINATION_S3_BUCKET}/{s3_key}"
            )

            s3_client.put_object(
                Bucket=DESTINATION_S3_BUCKET,
                Key=s3_key,
                Body=processed_records_for_s3.encode("utf-8"),
            )
        except Exception as e:
            logger.critical(
                f"S3 WRITE FAILED: Raising exception to retry Kinesis batch. Error: {e}",
                exc_info=True,
            )
            raise e
    else:
        logger.info("No valid records in this batch to write to S3.")

    return {"statusCode": 200, "body": json.dumps("Processing complete.")}
