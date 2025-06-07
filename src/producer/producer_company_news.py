# src/producer/producer_company_news.py
# Producer for fetching company news from Finnhub API

import os
import requests
import json
import time
import logging
import datetime
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# --- Early Config Import & Validation ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s") # Basic for immediate use
temp_logger = logging.getLogger("company_news_config_setup") 

try:
    from src import config
    temp_logger.info("Successfully imported configuration from src.config.")
    # Essential config checks
    if not all(hasattr(config, attr) for attr in ['SYMBOLS_TO_TRACK', 'FINNHUB_API_BASE_URL']):
        temp_logger.critical("Config error: Essential variables missing in src.config.py. Exiting.")
        exit(1)

except ImportError as e:
    temp_logger.critical(f"Failed to import 'config' from 'src': {e}. Ensure PYTHONPATH is set. Exiting.")
    exit(1)
except Exception as e: # Catch any other unexpected error during config access
    temp_logger.critical(f"An unexpected error occurred during configuration loading: {e}. Exiting.")
    exit(1)

# --- Main Script Configuration ---
load_dotenv() 
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
KINESIS_STREAM_NAME = os.getenv("KINESIS_STREAM_NAME_NEWS") # Specific env var for this stream
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "af-south-1")

if not all([FINNHUB_API_KEY, KINESIS_STREAM_NAME]):
    temp_logger.critical("Critical environment variables FINNHUB_API_KEY or KINESIS_STREAM_NAME_NEWS are not set. Exiting.")
    exit(1)

FINNHUB_NEWS_URL = f"{config.FINNHUB_API_BASE_URL}/company-news"
POLLING_INTERVAL_SECONDS = 60 * 15  # Poll news every 15 minutes
NEWS_LOOKBACK_DAYS = 2 # How many days back to check for news to catch up/avoid missing items.

# --- Main Logging Setup  ---
logging.basicConfig(
    level=logging.INFO, # Set to DEBUG for more verbose API call/response details
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__) # Main logger for this module

# --- State Management for last seen news ID per symbol (in-memory) ---
# NOTE: This state is lost if the script restarts. For robust production, we'll persist this externally.
last_seen_news_ids = {} # Example: {"AAPL": 12345, "MSFT": 67890}

# --- Helper Functions ---
def fetch_company_news(api_key, symbol, from_date_str, to_date_str):
    """Fetches company news for a given symbol and date range from Finnhub."""
    if not api_key:
        logger.error(f"Finnhub API key is not set for fetching news for {symbol}.")
        return None
    
    params = {
        "symbol": symbol,
        "from": from_date_str,
        "to": to_date_str,
        "token": api_key
    }
    try:
        logger.debug(f"Fetching news for {symbol} from {from_date_str} to {to_date_str} with params: {params}")
        response = requests.get(FINNHUB_NEWS_URL, params=params, timeout=20) 
        response.raise_for_status()
        news_data_list = response.json() 
        if isinstance(news_data_list, list):
            logger.info(f"Successfully fetched {len(news_data_list)} news articles for {symbol} for range {from_date_str}-{to_date_str}.")
            return news_data_list
        else:
            logger.warning(f"Unexpected data format for {symbol} news (expected list): {type(news_data_list)}. Response: {str(news_data_list)[:200]}")
            return [] # Return empty list if format is not a list
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error for {symbol} news: {http_err} - Status: {response.status_code} - Response: {response.text[:200]}")
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error for {symbol} news: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f"Timeout error for {symbol} news: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"API request error for {symbol} news: {req_err}")
    except json.JSONDecodeError as json_err:
        logger.error(f"Error decoding JSON for {symbol} news: {json_err} - Response was: {response.text[:200]}")
    return None


def process_news_data(news_articles_raw, symbol_ticker):
    """Processes raw news articles: filters by last_seen_id, selects fields, adds timestamps."""
    if news_articles_raw is None: # Fetch failed
        return []
    if not isinstance(news_articles_raw, list):
        logger.warning(f"process_news_data received non-list input for {symbol_ticker}: {type(news_articles_raw)}")
        return []

    processed_new_articles = []
    fetch_timestamp_utc_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Sort articles by datetime (published time), then by ID, both ascending.
    # This ensures we process oldest first and can reliably update last_seen_id with the true newest.
    try:
        # Robust sorting: handle cases where 'datetime' or 'id' might be missing or not integers
        sorted_articles = sorted(
            news_articles_raw, 
            key=lambda x: (
                x.get('datetime', 0) if isinstance(x.get('datetime'), int) else 0, 
                x.get('id', 0) if isinstance(x.get('id'), int) else 0
            )
        )
    except TypeError as te: # Should be rare with the isinstance checks in key
        logger.error(f"TypeError during sorting news for {symbol_ticker}: {te}. Processing unsorted. Articles: {str(news_articles_raw)[:300]}")
        sorted_articles = news_articles_raw # Fallback to unsorted if critical error in sorting

    current_max_id_for_symbol_in_batch = last_seen_news_ids.get(symbol_ticker, 0) 
    new_articles_this_run_count = 0

    for article_raw in sorted_articles:
        if not isinstance(article_raw, dict):
            continue # Skip any non-dict entries (shouldn't happen, but just in case)
        article_id = article_raw.get("id")
        if not isinstance(article_id, int):
            logger.warning(f"Article for {symbol_ticker} (Headline: '{str(article_raw.get('headline'))[:50]}...') has missing or invalid ID type ('{article_id}'). Skipping ID-based de-duplication for this article")
            # We will still process this article if it's otherwise valid, but won't use its ID to update last_seen_news_ids
            # Or, stricter: if article_id is None: logger.warning(...); continue # to skip it entirely
        elif article_id <= last_seen_news_ids.get(symbol_ticker, 0): # Compare against the global last_seen for this symbol
            logger.debug(f"Skipping article for {symbol_ticker} with ID {article_id} as it is not newer than last seen ID {last_seen_news_ids.get(symbol_ticker, 'N/A')}.")
            continue 
        
        # If we reach here, the article is new (or has an invalid ID we're processing anyway)
        new_articles_this_run_count +=1
        # Update the highest ID encountered *in this specific processing batch so far*
        if isinstance(article_id, int):
             current_max_id_for_symbol_in_batch = max(current_max_id_for_symbol_in_batch, article_id)


        article_datetime_unix = article_raw.get("datetime")
        article_datetime_utc_str = None
        if article_datetime_unix is not None:
            try:
                article_datetime_utc_str = datetime.datetime.fromtimestamp(int(article_datetime_unix), tz=datetime.timezone.utc).isoformat()
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not convert news datetime '{article_datetime_unix}' for {symbol_ticker} article ID {article_id}: {e}")

        processed_article = {
            "symbol": symbol_ticker,
            "news_id": article_id, # May be None if original was invalid
            "fetch_timestamp_utc": fetch_timestamp_utc_str,
            "article_published_unix": article_datetime_unix,
            "article_published_utc": article_datetime_utc_str,
            "category": article_raw.get("category"),
            "headline": article_raw.get("headline"),
            "summary": article_raw.get("summary"),
            "source": article_raw.get("source"),
            "url": article_raw.get("url"),
            "image_url": article_raw.get("image"),
        }
        processed_new_articles.append(processed_article)

    # After iterating through all articles for the symbol in this batch,
    # if we found any new valid IDs, update the global last_seen_news_ids.
    if current_max_id_for_symbol_in_batch > last_seen_news_ids.get(symbol_ticker, 0):
        last_seen_news_ids[symbol_ticker] = current_max_id_for_symbol_in_batch
        logger.info(f"Updated last_seen_news_id for {symbol_ticker} to {current_max_id_for_symbol_in_batch}.")
    
    if new_articles_this_run_count > 0:
        logger.info(f"Found and processed {new_articles_this_run_count} new articles for {symbol_ticker}.")
    elif news_articles_raw: # We fetched articles, but none were newer than last_seen_id
        logger.info(f"No new articles found for {symbol_ticker} since ID {last_seen_news_ids.get(symbol_ticker, 'N/A')}.")

    return processed_new_articles

def send_to_kinesis(kinesis_client, stream_name, data_record):
    """Sends a single data record to the specified Kinesis Data Stream"""
    try:
        partition_key = data_record['symbol']
        data_bytes = json.dumps(data_record).encode('utf-8')

        response = kinesis_client.put_record(
            StreamName=stream_name,
            Data=data_bytes,
            PartitionKey=partition_key
        )
        logger.debug(f"Successfully sent record to Kinesis. ShardId: {response.get('ShardId')}, SequenceNumber: {response.get('SequenceNumber')}")
        return True
    except ClientError as e:
        logger.error(f"Failed to send record to Kinesis stream {stream_name}. Error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred when sending to Kinesis: {e}")
    return False

# --- Main Execution ---
if __name__ == "__main__":
    logger.info("Starting Company News Producer...")
    
    kinesis_client = boto3.client("kinesis", region_name=AWS_REGION) # Initialize Kinesis client

    num_symbols = len(config.SYMBOLS_TO_TRACK)
    MIN_INTER_SYMBOL_SLEEP_SECONDS = 5 # News requests can be heavier; allow more time

    try:
        while True:
            logger.info(f"--- Starting new news polling cycle for {num_symbols} symbols ---")
            cycle_start_time = time.time()

            to_date = datetime.date.today()
            from_date = to_date - datetime.timedelta(days=NEWS_LOOKBACK_DAYS)
            to_date_str = to_date.strftime("%Y-%m-%d")
            from_date_str = from_date.strftime("%Y-%m-%d")
            logger.info(f"Targeting news for date range: {from_date_str} to {to_date_str}")

            total_new_articles_in_cycle = 0
            for i, stock_symbol_iter in enumerate(config.SYMBOLS_TO_TRACK):
                logger.info(f"Fetching company news for {stock_symbol_iter} ({i+1}/{num_symbols})...")
                
                raw_news_list = fetch_company_news(FINNHUB_API_KEY, stock_symbol_iter, from_date_str, to_date_str)

                if raw_news_list is not None: 
                    final_news_messages = process_news_data(raw_news_list, stock_symbol_iter)
                    if final_news_messages:
                        total_new_articles_in_cycle += len(final_news_messages)
                        for news_message in final_news_messages:
                            success = send_to_kinesis(kinesis_client, KINESIS_STREAM_NAME, news_message)
                            if not success:
                                logger.error(f"Failed to send news article (ID: {news_message.get('news_id')}) for {stock_symbol_iter} to Kinesis.")
                else:
                    logger.warning(f"Fetch attempt for {stock_symbol_iter} news failed or returned None.")
                
                if i < num_symbols - 1:
                    logger.debug(f"Pausing for {MIN_INTER_SYMBOL_SLEEP_SECONDS}s before next symbol.")
                    time.sleep(MIN_INTER_SYMBOL_SLEEP_SECONDS)
            
            cycle_duration_seconds = time.time() - cycle_start_time
            logger.info(f"--- News polling cycle (fetched for all symbols) took {cycle_duration_seconds:.2f} seconds. Found {total_new_articles_in_cycle} total new articles this cycle. ---")

            sleep_until_next_cycle_seconds = POLLING_INTERVAL_SECONDS - cycle_duration_seconds
            if sleep_until_next_cycle_seconds < 0:
                logger.warning(f"News polling cycle duration ({cycle_duration_seconds:.2f}s) exceeded interval. Sleeping briefly.")
                sleep_until_next_cycle_seconds = 10 
            
            logger.info(f"Next full news polling cycle in {sleep_until_next_cycle_seconds:.0f} seconds.")
            HEARTBEAT_INTERVAL_SECONDS = 10
            remaining_sleep_seconds = sleep_until_next_cycle_seconds
            while remaining_sleep_seconds > 0.01:
                current_sleep_chunk_seconds = min(HEARTBEAT_INTERVAL_SECONDS, remaining_sleep_seconds)
                time.sleep(current_sleep_chunk_seconds)
                remaining_sleep_seconds -= current_sleep_chunk_seconds
                if remaining_sleep_seconds > HEARTBEAT_INTERVAL_SECONDS / 2:
                    logger.info(f"... news producer alive, next poll in {remaining_sleep_seconds:.0f} seconds ...")
            logger.info("News producer sleep complete. Preparing for next polling cycle.")

    except KeyboardInterrupt:
        logger.info("Company News Producer stopped by user.")
    except Exception as e:
        logger.critical(f"Unhandled critical error in Company News Producer main loop: {e}", exc_info=True)
    finally:
        logger.info("Company News Producer shutting down.")