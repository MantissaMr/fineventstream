import base64
import datetime
import json
import logging
import os

import boto3

# --- Configuration & Initialization ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)

DESTINATION_S3_BUCKET = os.getenv("DESTINATION_S3_BUCKET")
if not DESTINATION_S3_BUCKET:
    raise ValueError("FATAL: Environment variable DESTINATION_S3_BUCKET is not set.")

# Initialize clients outside the handler for performance/reuse.
s3_client = boto3.client("s3")


def lambda_handler(event, context):
    """
    Main handler for processing a batch of Kinesis records containing stock quotes.

    Decodes records, aggregates them into a JSON Lines string, and writes
    the batch to a partitioned S3 path.
    """
    logger.info(f"Processing {len(event.get('Records', []))} Kinesis records.")

    processed_records_for_s3 = ""

    for record in event.get("Records", []):
        try:
            # Kinesis record data is Base64 encoded.
            payload_b64 = record.get("kinesis", {}).get("data")
            if not payload_b64:
                logger.warning("Skipping record with no kinesis.data payload.")
                continue

            # Decode from Base64, then decode the resulting bytes as a UTF-8 string.
            payload_decoded = base64.b64decode(payload_b64).decode("utf-8")

            # The payload is a JSON string; parse it into a Python dict.
            quote_data = json.loads(payload_decoded)

            # --- Optional: Further data validation or enrichment could be added here. ---
            # For this pipeline, our data's coming from a controlled source so there isn't much that needs doing
            # Examples of what could be added:
            # - Schema validation, using using a library like Pydantic or Marshmallow
            # - Data enrichment (adding a 'market_cap_category' based on price and shares outstanding, for instance).
            # - Anomaly detections, like flagging if 'percent_change' is unusually large.

            # Append the JSON string to our batch, followed by a newline (JSON Lines format).
            processed_records_for_s3 += json.dumps(quote_data) + "\n"

        except json.JSONDecodeError as e:
            logger.error(
                f"JSON DECODE ERROR: Could not parse record payload. Payload (first 100 chars): '{payload_decoded[:100]}'. Error: {e}"
            )
            continue  # Skip bad records
        except Exception as e:
            logger.error(f"UNEXPECTED RECORD-LEVEL ERROR: {e}", exc_info=True)

    # --- S3 Batch Write ---
    if processed_records_for_s3:
        try:
            # Generate a hive-style partition prefix based on the current UTC time.
            now = datetime.datetime.now(datetime.timezone.utc)
            s3_partition_prefix = now.strftime("year=%Y/month=%m/day=%d/hour=%H/")

            # Create a unique filename to prevent overwrites.
            file_name = f"stock_quotes_{now.strftime('%Y-%m-%d-%H-%M-%S')}_{context.aws_request_id}.jsonl"
            s3_key = f"processed/stock_quotes/{s3_partition_prefix}{file_name}"

            logger.info(
                f"Writing {len(processed_records_for_s3.strip().splitlines())} records to s3://{DESTINATION_S3_BUCKET}/{s3_key}"
            )

            s3_client.put_object(
                Bucket=DESTINATION_S3_BUCKET,
                Key=s3_key,
                Body=processed_records_for_s3.encode("utf-8"),
            )
        except Exception as e:
            # If the S3 write fails, re-raise the exception to have Lambda retry the entire batch.
            # Crucial for preventing data loss.
            logger.critical(
                f"S3 WRITE FAILED: Raising exception to retry Kinesis batch. Error: {e}",
                exc_info=True,
            )  # exc_info=True will log the full traceback
            raise e
    else:
        logger.info("No valid records in this batch to write to S3.")

    return {"statusCode": 200, "body": json.dumps("Processing complete.")}
