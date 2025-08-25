"""
historical_utils.py

Low-level helpers:
- path management for cached historical CSVs
- fetch CSV from Definedge historical API (/sds/history/...)
- parse returned CSV text into DataFrame for day/minute/tick
- incremental update: detect last saved datetime and fetch ONLY missing range
"""
import os
import time
from typing import Optional, Tuple
from datetime import datetime, timedelta

import requests
import pandas as pd

HIST_DIR = os.path.join("data", "historical")
os.makedirs(HIST_DIR, exist_ok=True)

# Supported timeframes: 'day', 'minute', 'tick'
def get_data_path(segment: str, token: str, timeframe: str) -> str:
    seg_dir = os.path.join(HIST_DIR, segment.upper())
    os.makedirs(seg_dir, exist_ok=True)
    fname = f"{token}_{timeframe}.csv"
    return os.path.join(seg_dir, fname)


# ---------- parse CSV text returned by API ----------
def _try_parse_datetime(s: str) -> Optional[datetime]:
    # Try multiple common formats
    formats = [
        "%d%m%Y%H%M",       # 010620231530
        "%d-%m-%Y %H:%M:%S",# 01-06-2023 15:30:00
        "%Y-%m-%d %H:%M:%S",# 2023-06-01 15:30:00
        "%d-%m-%Y %H:%M",   # 01-06-2023 15:30
        "%d/%m/%Y %H:%M:%S",
        "%Y%m%d%H%M%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    # try epoch seconds (tick data sometimes uses UTC epoch)
    try:
        if s.isdigit() and (10 <= len(s) <= 13):
            # epoch in seconds or milliseconds
            ts = int(s)
            if len(s) == 13:
                ts = ts // 1000
            return datetime.utcfromtimestamp(ts)
    except Exception:
        pass
    return None


def parse_api_csv(text: str, timeframe: str) -> pd.DataFrame:
    """
    Parse API CSV (no headers) into DataFrame.
    For 'day'/'minute' -> columns: datetime, open, high, low, close, volume, oi (oi optional)
    For 'tick' -> columns: utc (datetime), ltp, ltq, oi
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return pd.DataFrame()

    rows = [l.split(",") for l in lines]
    # detect columns by row length
    first_len = len(rows[0])
    if timeframe in ("day", "minute"):
        out_rows = []
        for r in rows:
            # ensure at least 6 columns: date,open,high,low,close,volume,(oi optional)
            if len(r) < 6:
                continue
            dt = _try_parse_datetime(r[0])
            if not dt:
                # sometimes date is like "01-06-2023 00:00" with extra quotes/spaces
                try:
                    dt = _try_parse_datetime(r[0].replace('"', '').strip())
                except Exception:
                    dt = None
            if not dt:
                # skip if cannot parse date
                continue
            open_p = float(r[1]) if r[1] else None
            high_p = float(r[2]) if r[2] else None
            low_p = float(r[3]) if r[3] else None
            close_p = float(r[4]) if r[4] else None
            volume = int(float(r[5])) if r[5] else 0
            oi = None
            if len(r) >= 7 and r[6] != "":
                try:
                    oi = float(r[6])
                except:
                    oi = None
            out_rows.append([dt, open_p, high_p, low_p, close_p, volume, oi])
        df = pd.DataFrame(out_rows, columns=["datetime", "open", "high", "low", "close", "volume", "oi"])
        # sort & normalize
        df = df.drop_duplicates(subset=["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        return df

    # tick
    else:
        out_rows = []
        for r in rows:
            if len(r) < 3:
                continue
            # first col likely epoch seconds
            dt = _try_parse_datetime(r[0])
            if not dt:
                continue
            ltp = float(r[1]) if r[1] else None
            ltq = int(float(r[2])) if r[2] else 0
            oi = None
            if len(r) >= 4 and r[3] != "":
                try:
                    oi = float(r[3])
                except:
                    oi = None
            out_rows.append([dt, ltp, ltq, oi])
        df = pd.DataFrame(out_rows, columns=["datetime", "ltp", "ltq", "oi"])
        df = df.drop_duplicates(subset=["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        return df


# ---------- fetch from API ----------
def fetch_from_api(session_key: str, segment: str, token: str, timeframe: str, from_dt: str, to_dt: str, timeout: int = 30) -> pd.DataFrame:
    """
    from_dt and to_dt must be strings in ddMMyyyyHHmm format (as required by API).
    Returns parsed DataFrame or empty df.
    """
    url = f"https://data.definedgesecurities.com/sds/history/{segment}/{token}/{timeframe}/{from_dt}/{to_dt}"
    headers = {"Authorization": session_key}
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        # return empty DataFrame (caller will decide)
        return pd.DataFrame()
    text = resp.text or ""
    return parse_api_csv(text, timeframe)


# ---------- incremental update logic ----------
def update_incremental(session_key: str, segment: str, token: str, timeframe: str = "day", start_date: Optional[str] = None, max_retry: int = 2, delay_sec: float = 0.05) -> Tuple[str, pd.DataFrame]:
    """
    Update local cached file for given (segment, token, timeframe).
    - If file not present: fetch from `start_date` (ddMMyyyyHHmm) or default 01012000...
    - If file present: read last datetime and fetch from (last_datetime + smallest increment) to now.
    - Saves result to data/historical/{segment}/{token}_{timeframe}.csv
    Returns (file_path, DataFrame)
    """
    path = get_data_path(segment, token, timeframe)
    # ensure directory
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # read existing
    if os.path.exists(path):
        try:
            existing = pd.read_csv(path, parse_dates=["datetime"])
            if existing.empty:
                last_dt = None
            else:
                last_dt = existing["datetime"].max().to_pydatetime()
        except Exception:
            # fallback: no parseable existing file
            existing = pd.DataFrame()
            last_dt = None
    else:
        existing = pd.DataFrame()
        last_dt = None

    # determine from_dt (API requires ddMMyyyyHHmm)
    if last_dt is not None:
        # add smallest step: for day -> +1 day at 00:00; for minute/tick -> +1 minute
        if timeframe == "day":
            next_dt = (last_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            next_dt = last_dt + timedelta(minutes=1)
    else:
        if start_date:
            # accept start_date like "01012020" or "010120200000"
            if len(start_date) == 8:
                next_dt = datetime.strptime(start_date, "%d%m%Y")
            else:
                next_dt = datetime.strptime(start_date, "%d%m%Y%H%M")
        else:
            # default backfill start ~ 1 Jan 2000
            next_dt = datetime(2000, 1, 1)

    now = datetime.now()
    # API to requires to/from in ddMMyyyyHHmm
    from_str = next_dt.strftime("%d%m%Y%H%M")
    to_str = now.strftime("%d%m%Y%H%M")

    # Nothing to fetch?
    if next_dt >= now:
        # up to date
        return path, existing

    # fetch (with small retry)
    for attempt in range(max_retry):
        try:
            df_new = fetch_from_api(session_key, segment, token, timeframe, from_str, to_str)
            break
        except Exception:
            df_new = pd.DataFrame()
            time.sleep(delay_sec * (attempt + 1))
    else:
        df_new = pd.DataFrame()

    if df_new is None:
        df_new = pd.DataFrame()

    # If nowhere new rows returned -> simply return existing
    if df_new.empty:
        # Still save existing if not exist
        if existing.empty:
            existing.to_csv(path, index=False)
        return path, existing

    # unify existing + new: ensure 'datetime' col is datetime dtype
    if "datetime" in df_new.columns:
        df_new["datetime"] = pd.to_datetime(df_new["datetime"])
    # existing may already be datetime
    if existing is None or existing.empty:
        final = df_new
    else:
        if "datetime" in existing.columns:
            existing["datetime"] = pd.to_datetime(existing["datetime"])
        final = pd.concat([existing, df_new], ignore_index=True)
        final = final.drop_duplicates(subset=["datetime"], keep="last")
    final = final.sort_values("datetime").reset_index(drop=True)
    # Save as ISO timestamps for easy reading
    final.to_csv(path, index=False)
    return path, final
