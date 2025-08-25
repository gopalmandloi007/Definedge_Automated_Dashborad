# historical_utils.py
import os
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pandas as pd
import requests
from dateutil import parser

from debug_utils import debug_log
import session_utils  # to get active session automatically

HIST_DIR = os.path.join("data", "historical")
os.makedirs(HIST_DIR, exist_ok=True)


def get_data_path(segment: str, token: str, timeframe: str) -> str:
    seg_dir = os.path.join(HIST_DIR, segment.upper())
    os.makedirs(seg_dir, exist_ok=True)
    fname = f"{token}_{timeframe}.csv"
    return os.path.join(seg_dir, fname)


def _try_parse_datetime(s: str) -> Optional[datetime]:
    if s is None:
        return None
    s = str(s).strip().strip('"')
    # try flexible parser
    try:
        return parser.parse(s)
    except Exception:
        pass
    # epoch fallback
    if s.isdigit():
        try:
            ts = int(s)
            if len(s) == 13:
                ts = ts // 1000
            return datetime.utcfromtimestamp(ts)
        except Exception:
            pass
    return None


def parse_api_csv(text: str, timeframe: str) -> pd.DataFrame:
    """
    Parse CSV returned by historical API (no headers).
    day/minute -> datetime, open, high, low, close, volume, [oi]
    tick -> utc(epoch) , ltp, ltq, [oi]
    """
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    if not lines:
        return pd.DataFrame()

    rows = [l.split(",") for l in lines]
    if timeframe in ("day", "minute"):
        out = []
        for r in rows:
            if len(r) < 6:
                continue
            dt = _try_parse_datetime(r[0])
            if not dt:
                continue
            try:
                o = float(r[1]) if r[1] != "" else None
                h = float(r[2]) if r[2] != "" else None
                l = float(r[3]) if r[3] != "" else None
                c = float(r[4]) if r[4] != "" else None
                v = int(float(r[5])) if r[5] != "" else 0
            except Exception:
                continue
            oi = None
            if len(r) >= 7 and r[6] != "":
                try:
                    oi = float(r[6])
                except Exception:
                    oi = None
            out.append([dt, o, h, l, c, v, oi])
        df = pd.DataFrame(out, columns=["datetime", "open", "high", "low", "close", "volume", "oi"])
        if df.empty:
            return df
        df = df.drop_duplicates(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
        return df

    # tick
    out = []
    for r in rows:
        if len(r) < 3:
            continue
        dt = _try_parse_datetime(r[0])
        if not dt:
            continue
        try:
            ltp = float(r[1]) if r[1] != "" else None
            ltq = int(float(r[2])) if r[2] != "" else 0
        except Exception:
            continue
        oi = None
        if len(r) >= 4 and r[3] != "":
            try:
                oi = float(r[3])
            except Exception:
                oi = None
        out.append([dt, ltp, ltq, oi])
    df = pd.DataFrame(out, columns=["datetime", "ltp", "ltq", "oi"])
    if df.empty:
        return df
    df = df.drop_duplicates(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    return df


def fetch_historical_raw(session_key: Optional[str], segment: str, token: str, timeframe: str, from_dt: str, to_dt: str, timeout: int = 60) -> str:
    """
    Return raw CSV text from Definedge historical endpoint. If session_key is None,
    attempt to fetch from session_utils.get_active_session().
    from_dt and to_dt should be in ddMMyyyyHHmm
    """
    if not session_key:
        s = session_utils.get_active_session()
        if not s:
            raise RuntimeError("No active session. Please login through Streamlit.")
        session_key = s.get("api_session_key")

    url = f"https://data.definedgesecurities.com/sds/history/{segment}/{token}/{timeframe}/{from_dt}/{to_dt}"
    headers = {"Authorization": session_key}
    debug_log(f"fetch_historical_raw: GET {url}")
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code == 401:
        # session invalid -> remove local session to force re-login
        try:
            session_utils.logout_session()
        except Exception:
            pass
        raise RuntimeError("Session expired/unauthorized (401). Please login again.")
    resp.raise_for_status()
    return resp.text


def update_incremental(session_key: Optional[str], segment: str, token: str, timeframe: str = "day",
                       start_date: Optional[str] = None, max_retry: int = 2, delay_sec: float = 0.05) -> Tuple[str, pd.DataFrame]:
    """
    Update local cached CSV for (segment, token, timeframe).
    If session_key is None this function will use session_utils.get_active_session().
    Returns (path, dataframe)
    """
    debug_log(f"update_incremental(segment={segment}, token={token}, timeframe={timeframe}, start_date={start_date})")
    path = get_data_path(segment, token, timeframe)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # load existing if present
    existing = pd.DataFrame()
    last_dt = None
    if os.path.exists(path):
        try:
            existing = pd.read_csv(path, parse_dates=["datetime"])
            if not existing.empty:
                last_dt = existing["datetime"].max().to_pydatetime()
        except Exception as e:
            debug_log(f"Failed to read existing historical file {path}: {e}")
            existing = pd.DataFrame()
            last_dt = None

    # determine next_dt
    if last_dt is not None:
        if timeframe == "day":
            next_dt = (last_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            next_dt = last_dt + timedelta(minutes=1)
    else:
        if start_date:
            if len(start_date) == 8:
                next_dt = datetime.strptime(start_date, "%d%m%Y")
            else:
                next_dt = datetime.strptime(start_date, "%d%m%Y%H%M")
        else:
            # choose reasonable backfill start
            next_dt = datetime(2015, 1, 1)

    now = datetime.now()
    if next_dt >= now:
        debug_log(f"No new data to fetch for token={token}. next_dt >= now")
        return path, existing

    from_str = next_dt.strftime("%d%m%Y%H%M")
    to_str = now.strftime("%d%m%Y%H%M")

    # attempt fetch with retries
    df_new = pd.DataFrame()
    last_exception = None
    for attempt in range(max_retry):
        try:
            raw = fetch_historical_raw(session_key, segment, token, timeframe, from_str, to_str)
            df_new = parse_api_csv(raw, timeframe)
            break
        except Exception as e:
            last_exception = e
            debug_log(f"Attempt {attempt+1} fetch failed for token={token}: {e}")
            time.sleep(delay_sec * (attempt + 1))
    if df_new is None or df_new.empty:
        # nothing new
        if existing is None or existing.empty:
            # ensure existence of an empty file
            existing.to_csv(path, index=False)
        debug_log(f"No new rows fetched for token={token}")
        return path, existing

    # unify and save
    try:
        df_new["datetime"] = pd.to_datetime(df_new["datetime"])
    except Exception:
        pass
    if not existing.empty:
        try:
            existing["datetime"] = pd.to_datetime(existing["datetime"])
        except Exception:
            pass
        final = pd.concat([existing, df_new], ignore_index=True)
        final = final.drop_duplicates(subset=["datetime"], keep="last")
    else:
        final = df_new

    final = final.sort_values("datetime").reset_index(drop=True)
    final.to_csv(path, index=False)
    debug_log(f"Wrote {len(final)} rows to {path} (added {len(df_new)} new rows)")
    return path, final
