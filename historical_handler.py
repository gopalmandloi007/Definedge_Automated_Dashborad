"""
historical_handler.py

Higher-level orchestration:
- update_batch_by_tokens(session_key, tokens_list, ...) : update many tokens sequentially (batch-friendly)
- update_all_from_master(session_key, segment="NSE_CASH", batch_size=500, timeframe="day", start_date=None)
- helper to convert master symbols list -> token sequences
"""
import time
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from masterfile_handler import get_symbols_from_master, batch_symbols
from historical_utils import update_incremental

def update_batch(session_key: str, batch: List[Dict], segment: str = "NSE", timeframe: str = "day", start_date: Optional[str] = None, sleep_per: float = 0.05):
    """
    Update a given list of symbol dicts sequentially.
    Each dict in batch has keys: token, tradingsymbol, lotsize, segment (optional).
    Returns list of tuples (token, path, rowcount)
    """
    results = []
    for rec in batch:
        token = rec.get("token")
        seg = rec.get("segment", segment)
        try:
            path, df = update_incremental(session_key, seg, token, timeframe, start_date)
            results.append((token, path, len(df)))
        except Exception as e:
            results.append((token, None, 0))
        time.sleep(sleep_per)  # gentle throttle
    return results


def update_all_from_master(session_key: str, master_segment: str = "NSE_CASH", batch_size: int = 500, timeframe: str = "day", start_date: Optional[str] = None, sleep_per: float = 0.05):
    """
    Iterate through master file in batches and update historical data.
    Yields per-batch results.
    """
    for batch in batch_symbols(master_segment, batch_size):
        # each batch is a list of records in shape [{token, tradingsymbol, ...}, ...]
        res = update_batch(session_key, batch, segment="NSE", timeframe=timeframe, start_date=start_date, sleep_per=sleep_per)
        yield res


if __name__ == "__main__":
    # quick CLI demo (not executed in Streamlit)
    import os
    SESSION_KEY = os.environ.get("INTEGRATE_SESSION_KEY", "PUT_SESSION_KEY_HERE")
    # Example: update first 100 symbols (for speed)
    from masterfile_handler import get_symbols_from_master
    first100 = get_symbols_from_master("NSE_CASH", limit=100)
    print("Updating first 100 symbols... (this could take time)")
    out = update_batch(SESSION_KEY, first100, segment="NSE", timeframe="day", start_date="01012020")
    print("done", out[:3])
