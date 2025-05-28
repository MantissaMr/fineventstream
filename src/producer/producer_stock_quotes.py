import os
import requests
import json
import time
import logging
import datetime # Added for timestamp conversion
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"
SYMBOLS_TO_TRACK = ["AAPL", "MSFT", "GOOGL"] # Example symbols, keep it small for testing
POLLING_INTERVAL_SECONDS = 60 * 1  # Poll every 1 minute for all symbols

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def fetch_stock_quote(api_key, symbol):
    """
    Fetches a real-time quote for a given stock symbol from the Finnhub API.
    """
    if not api_key:
        logger.error(f"Finnhub API key is not set for fetching {symbol}.")
        return None

    params = {
        "symbol": symbol,
        "token": api_key
    }
    try:
        response = requests.get(FINNHUB_QUOTE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        # Check for essential fields to confirm a valid quote response
        if 'c' in data and 't' in data and data.get('c') is not None: # current price 'c' and timestamp 't' should exist and 'c' not be None
            logger.info(f"Successfully fetched quote for {symbol}: Current Price {data.get('c')}")
            return data
        else:
            # It's possible to get a 200 OK but with no actual price data if symbol is wrong or data unavailable
            logger.warning(f"No valid price data in quote for {symbol} or unexpected format: {data}")
            return None
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error for {symbol}: {http_err} - Status: {response.status_code} - Response: {response.text[:200]}")
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error for {symbol}: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f"Timeout error for {symbol}: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Unexpected API request error for {symbol}: {req_err}")
    except json.JSONDecodeError as json_err:
        # This can happen if response.text is not valid JSON (e.g. HTML error page)
        logger.error(f"Error decoding JSON for {symbol}: {json_err} - Response: {response.text[:200]}")
    return None


def process_quote_data(quote_data_raw, symbol_ticker):
    """
    Processes the raw quote data, selects relevant fields, and adds timestamps.
    """
    if not quote_data_raw:
        return None

    fetch_timestamp_utc_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Convert Finnhub's Unix timestamp 't' to ISO 8601 UTC string
    quote_timestamp_unix = quote_data_raw.get("t")
    quote_timestamp_utc_str = None
    if quote_timestamp_unix is not None:
        try:
            quote_timestamp_utc_str = datetime.datetime.fromtimestamp(quote_timestamp_unix, tz=datetime.timezone.utc).isoformat()
        except Exception as e:
            logger.warning(f"Could not convert quote timestamp {quote_timestamp_unix} for {symbol_ticker}: {e}")

    processed_quote = {
        "symbol": symbol_ticker,
        "fetch_timestamp_utc": fetch_timestamp_utc_str,
        "quote_timestamp_unix": quote_timestamp_unix,
        "quote_timestamp_utc": quote_timestamp_utc_str, # Human-readable quote time
        "current_price": quote_data_raw.get("c"),
        "change": quote_data_raw.get("d"),
        "percent_change": quote_data_raw.get("dp"),
        "high_price_day": quote_data_raw.get("h"),
        "low_price_day": quote_data_raw.get("l"),
        "open_price_day": quote_data_raw.get("o"),
        "previous_close_price": quote_data_raw.get("pc"),
        # "raw_quote_data": quote_data_raw # Optional: include for debugging, remove for production Kinesis messages to save space
    }
    return processed_quote

# --- Main Execution ---
if __name__ == "__main__":
    logger.info("Starting Stock Quotes Producer...")

    if not FINNHUB_API_KEY:
        logger.critical("FINNHUB_API_KEY not found in environment. Exiting.")
        exit()

    try:
        while True:
            logger.info(f"Starting new polling cycle for symbols: {SYMBOLS_TO_TRACK}")
            
            for stock_symbol_iter in SYMBOLS_TO_TRACK:
                logger.info(f"Fetching quote for {stock_symbol_iter}...")
                raw_quote_data = fetch_stock_quote(FINNHUB_API_KEY, stock_symbol_iter)

                if raw_quote_data:
                    final_quote_message = process_quote_data(raw_quote_data, stock_symbol_iter)
                    if final_quote_message:
                        # For now, print to console. Later, send to Kinesis.
                        print(json.dumps(final_quote_message, indent=2))
                    else:
                        logger.warning(f"Could not process quote data for {stock_symbol_iter} after fetching.")
                else:
                    logger.warning(f"Failed to fetch quote for {stock_symbol_iter} or no data returned in this attempt.")
                
                # Be kind to the API: brief pause between fetching different symbols
                # Finnhub free tier limit is often 60 calls/minute.
                # If SYMBOLS_TO_TRACK has 3 symbols, this loop runs 3 times.
                # 60 seconds / 3 symbols = 20 seconds per symbol if we want to max out.
                # A 1-2 second pause is just polite and helps avoid hitting rapid-fire limits.
                time.sleep(2) 

            logger.info(f"Polling cycle complete. Sleeping for {POLLING_INTERVAL_SECONDS - (len(SYMBOLS_TO_TRACK) * 2)} seconds before next cycle...") # Adjust sleep based on work done
            # Ensure the main polling interval is roughly maintained
            effective_sleep = POLLING_INTERVAL_SECONDS - (len(SYMBOLS_TO_TRACK) * 2) # Subtract time spent on intra-symbol sleeps
            if effective_sleep < 0:
                effective_sleep = 5 # Ensure at least a small positive sleep if processing took too long
            time.sleep(effective_sleep)


    except KeyboardInterrupt:
        logger.info("Producer stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.error(f"An unhandled critical error occurred in main loop: {e}", exc_info=True) # Use error for unhandled
    finally:
        logger.info("Stock Quotes Producer shutting down.")