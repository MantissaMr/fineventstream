# src/producer/producer_stock_quotes.py
# Producer for fetching stock quotes from Finnhub API

import os
import requests
import json
import time
import logging # Keep logging import at the top
import datetime
from dotenv import load_dotenv

# --- Early Config Import & Validation ---
# This section attempts to load essential configuration early.
# If it fails, the script should not proceed.

# A basic temporary logger for initial setup messages.. this will be replaced later by the main logger,
# but ensures we can log critical errors if config import fails.
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
temp_logger = logging.getLogger("config_setup") # A distinct name for this initial logger

try:
    from src import config
    temp_logger.info(f"Successfully imported configuration from src.config.")
    # Perform essential config checks immediately
    if not hasattr(config, 'SYMBOLS_TO_TRACK') or not config.SYMBOLS_TO_TRACK:
        temp_logger.critical("Config error: SYMBOLS_TO_TRACK is not defined or empty in src.config.py. Exiting.")
        exit(1)
    if not hasattr(config, 'FINNHUB_API_BASE_URL') or not config.FINNHUB_API_BASE_URL:
        temp_logger.critical("Config error: FINNHUB_API_BASE_URL is not defined or empty in src.config.py. Exiting.")
        exit(1)
    temp_logger.info(f"Configuration loaded. Tracking symbols: {config.SYMBOLS_TO_TRACK}")

except ImportError as e:
    temp_logger.critical(f"Failed to import 'config' from 'src': {e}. Ensure PYTHONPATH is set correctly to include the project root. Exiting.")
    exit(1)
except Exception as e: # Catch any other unexpected error during config access
    temp_logger.critical(f"An unexpected error occurred during configuration loading: {e}. Exiting.")
    exit(1)

# --- Main Script Configuration (using loaded config) ---
load_dotenv() # Load .env file from project root
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
if not FINNHUB_API_KEY: # Check for API key immediately after trying to load it
    temp_logger.critical("FINNHUB_API_KEY not found in .env file or environment. Exiting.")
    exit(1)

FINNHUB_QUOTE_URL = f"{config.FINNHUB_API_BASE_URL}/quote"
POLLING_INTERVAL_SECONDS = 60 * 1

# --- Main Logging Setup (Overrides the basicConfig used by temp_logger) ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", # %(name)s for module-specific logger
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Get a logger specific to this module (e.g., 'src.producer.producer_stock_quotes')
logger = logging.getLogger(__name__) # This is the logger for the rest of the script.

# --- Helper Functions (fetch_stock_quote, process_quote_data, possibly more in the future) ---
def fetch_stock_quote(api_key, symbol):
    if not api_key:
        logger.error(f"Finnhub API key is not set for fetching {symbol}.")
        return None
    params = {"symbol": symbol, "token": api_key}
    try:
        response = requests.get(FINNHUB_QUOTE_URL, params=params, timeout=10)
        response.raise_for_status() 
        data = response.json()
        if 'c' in data and 't' in data and data.get('c') is not None:
            logger.info(f"Successfully fetched quote for {symbol}: Current Price {data.get('c')}")
            return data
        else:
            logger.warning(f"No valid price data in quote for {symbol} or unexpected format: {data}")
            return None
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error for {symbol}: {http_err} - Status: {response.status_code} - Response: {response.text[:200]}")
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error for {symbol}: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f"Timeout error for {symbol}: {timeout_err}")
    except requests.exceptions.RequestException as req_err: 
        logger.error(f"API request error for {symbol}: {req_err}")
    except json.JSONDecodeError as json_err: 
        logger.error(f"Error decoding JSON for {symbol}: {json_err} - Response was: {response.text[:200]}")
    return None

def process_quote_data(quote_data_raw, symbol_ticker):
    if not quote_data_raw:
        return None
    
    fetch_timestamp_utc_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    quote_timestamp_unix = quote_data_raw.get("t")
    quote_timestamp_utc_str = None
    if quote_timestamp_unix is not None:
        try:
            quote_timestamp_utc_str = datetime.datetime.fromtimestamp(int(quote_timestamp_unix), tz=datetime.timezone.utc).isoformat()
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not convert quote timestamp '{quote_timestamp_unix}' for {symbol_ticker}: {e}")

    processed_quote = {
        "symbol": symbol_ticker,
        "fetch_timestamp_utc": fetch_timestamp_utc_str,
        "quote_timestamp_unix": quote_timestamp_unix,
        "quote_timestamp_utc": quote_timestamp_utc_str,
        "current_price": quote_data_raw.get("c"),
        "change": quote_data_raw.get("d"),
        "percent_change": quote_data_raw.get("dp"),
        "high_price_day": quote_data_raw.get("h"),
        "low_price_day": quote_data_raw.get("l"),
        "open_price_day": quote_data_raw.get("o"),
        "previous_close_price": quote_data_raw.get("pc"),
    }
    return processed_quote

# --- Main Execution ---
if __name__ == "__main__":
    logger.info("Main execution: Starting Stock Quotes Producer...") # Now uses the main logger
    # The SYMBOLS_TO_TRACK and API key checks are already done above, so we can be confident here.

    num_symbols = len(config.SYMBOLS_TO_TRACK) # num_symbols will be > 0 due to earlier checks
    
    MIN_INTER_SYMBOL_SLEEP_SECONDS = 2

    try:
        while True:
            logger.info(f"--- Starting new polling cycle for {num_symbols} symbols ---")
            cycle_start_time = time.time()
            
            for i, stock_symbol_iter in enumerate(config.SYMBOLS_TO_TRACK):
                logger.info(f"Fetching quote for {stock_symbol_iter} ({i+1}/{num_symbols})...")
                raw_quote_data = fetch_stock_quote(FINNHUB_API_KEY, stock_symbol_iter)

                if raw_quote_data:
                    final_quote_message = process_quote_data(raw_quote_data, stock_symbol_iter)
                    if final_quote_message:
                        print(json.dumps(final_quote_message, indent=2)) 
                    else:
                        logger.warning(f"Could not process quote data for {stock_symbol_iter} after fetching.")
                else:
                    logger.warning(f"No data returned from fetch_stock_quote for {stock_symbol_iter}.")
                
                if i < num_symbols - 1: 
                    logger.debug(f"Pausing for {MIN_INTER_SYMBOL_SLEEP_SECONDS}s before next symbol.")
                    time.sleep(MIN_INTER_SYMBOL_SLEEP_SECONDS) 

            cycle_duration_seconds = time.time() - cycle_start_time
            logger.info(f"--- Polling cycle for all symbols took {cycle_duration_seconds:.2f} seconds. ---")

            sleep_until_next_cycle_seconds = POLLING_INTERVAL_SECONDS - cycle_duration_seconds
            if sleep_until_next_cycle_seconds < 0:
                logger.warning(
                    f"Polling cycle duration ({cycle_duration_seconds:.2f}s) "
                    f"exceeded POLLING_INTERVAL_SECONDS ({POLLING_INTERVAL_SECONDS}s). "
                    "Sleeping for a minimum fallback duration."
                )
                sleep_until_next_cycle_seconds = 5 

            logger.info(f"Next full polling cycle in {sleep_until_next_cycle_seconds:.0f} seconds.")
            
            HEARTBEAT_INTERVAL_SECONDS = 10 
            remaining_sleep_seconds = sleep_until_next_cycle_seconds
            while remaining_sleep_seconds > 0.01: 
                current_sleep_chunk_seconds = min(HEARTBEAT_INTERVAL_SECONDS, remaining_sleep_seconds)
                time.sleep(current_sleep_chunk_seconds)
                remaining_sleep_seconds -= current_sleep_chunk_seconds
                if remaining_sleep_seconds > HEARTBEAT_INTERVAL_SECONDS / 2: 
                    logger.info(f"... producer alive, next poll in {remaining_sleep_seconds:.0f} seconds ...")
            logger.info("Sleep complete. Preparing for next polling cycle.")

    except KeyboardInterrupt:
        logger.info("Producer stopped by user (KeyboardInterrupt).")
    except Exception as e: 
        logger.critical(f"An unhandled critical error occurred in main loop: {e}", exc_info=True) 
    finally:
        logger.info("Stock Quotes Producer shutting down.")