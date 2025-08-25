# historical_handler.py
import time
from typing import List, Dict, Optional, Callable, Iterator

from debug_utils import debug_log
from masterfile_handler import batch_symbols, get_symbols_from_master
from historical_utils import update_incremental

def update_batch(session_key: Optional[str], batch: List[Dict], segment: str = "NSE", timeframe: str = "day",
                 start_date: Optional[str] = None, sleep_per: float = 0.05,
                 progress_callback: Optional[Callable[[str,int,int,str,int], None]] = None) -> List[tuple]:
    """
    Update a given list of symbol dicts sequentially.
    Each dict: {token, tradingsymbol, ...}
    progress_callback(token, idx, total, status, rows)
    Returns list[(token, path, rows_count_or_0)]
    """
    results = []
    total = len(batch)
    for idx, rec in enumerate(batch, start=1):
        token = rec.get("token")
        seg = rec.get("segment", segment)
        try:
            path, df = update_incremental(session_key, seg, token, timeframe, start_date)
            rows = len(df) if df is not None else 0
            results.append((token, path, rows))
            status = "OK"
            debug_log(f"Updated token={token} rows={rows}")
        except Exception as e:
            results.append((token, None, 0))
            status = f"ERR:{e}"
            debug_log(f"Error updating token={token}: {e}")
        if progress_callback:
            try:
                progress_callback(token, idx, total, status, results[-1][2])
            except Exception:
                pass
        time.sleep(sleep_per)
    return results


def update_all_from_master(session_key: Optional[str], master_segment: str = "NSE_CASH", batch_size: int = 500,
                           timeframe: str = "day", start_date: Optional[str] = None, sleep_per: float = 0.05,
                           progress_callback: Optional[Callable[[str,int,int,str,int], None]] = None) -> Iterator[List[tuple]]:
    """
    Iterate through master file in batches and update historical data.
    Yields results per batch (list of (token,path,rows))
    """
    for batch in batch_symbols(master_segment, batch_size):
        debug_log(f"Processing batch of {len(batch)} symbols from master {master_segment}")
        res = update_batch(session_key, batch, segment="NSE", timeframe=timeframe, start_date=start_date, sleep_per=sleep_per, progress_callback=progress_callback)
        yield res


if __name__ == "__main__":
    import os
    SESSION_KEY = os.environ.get("INTEGRATE_SESSION_KEY", None)
    # quick test with first 20
    from masterfile_handler import get_symbols_from_master
    sample = get_symbols_from_master("NSE_CASH", limit=20)
    print("Starting sample update (20 symbols)...")
    out = update_batch(SESSION_KEY, sample, segment="NSE", timeframe="day", start_date="01012020")
    print("Done sample, results:", out[:3])
