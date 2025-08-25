"""
masterfile_handler.py

- download_master(segment) -> downloads the master zip, extracts csv into data/master_file/{segment}_{YYYYMMDD}.csv
- load_master(segment) -> returns pandas DataFrame (downloads if today's not present)
- get_symbols_from_master(segment, limit=None) -> yields rows with TOKEN, TRADINGSYM, SYMBOL, ISIN, LOTSIZE, etc.
- batch_symbols(segment, batch_size) -> yields batches of trading-symbol dicts for batching
"""
import os
import zipfile
import io
import datetime
from typing import List, Dict, Iterator, Optional

import requests
import pandas as pd

DATA_DIR = os.path.join("data", "master_file")
os.makedirs(DATA_DIR, exist_ok=True)

MASTER_FILE_URLS = {
    "NSE_CASH": "https://app.definedgesecurities.com/public/nsecash.zip",
    "NSE_FNO": "https://app.definedgesecurities.com/public/nsefno.zip",
    "BSE_CASH": "https://app.definedgesecurities.com/public/bsecash.zip",
    "BSE_FNO": "https://app.definedgesecurities.com/public/bsefno.zip",
    "NSE_CDS": "https://app.definedgesecurities.com/public/cdsfno.zip",
    "MCX_FNO": "https://app.definedgesecurities.com/public/mcxfno.zip",
    "ALL": "https://app.definedgesecurities.com/public/allmaster.zip"
}

# nominal column names according to docs (CSV without headers; we will map by count)
COLUMN_NAMES = [
    "SEGMENT", "TOKEN", "SYMBOL", "TRADINGSYM", "INSTRUMENT_TYPE", "EXPIRY",
    "TICKSIZE", "LOTSIZE", "OPTIONTYPE", "STRIKE", "PRICEPREC", "MULTIPLIER",
    "ISIN", "PRICEMULT", "COMPANY"
]


def _today_tag() -> str:
    return datetime.datetime.now().strftime("%Y%m%d")


def download_master(segment: str = "NSE_CASH", force: bool = False) -> str:
    """
    Download the master zip for `segment`, extract first csv inside and save as
    data/master_file/{segment}_{YYYYMMDD}.csv. Returns the saved filepath.
    """
    if segment not in MASTER_FILE_URLS:
        raise ValueError(f"Unknown segment '{segment}'. Valid: {list(MASTER_FILE_URLS.keys())}")

    out_path = os.path.join(DATA_DIR, f"{segment}_{_today_tag()}.csv")
    if os.path.exists(out_path) and not force:
        return out_path

    url = MASTER_FILE_URLS[segment]
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        # pick first CSV inside zip
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise RuntimeError("No CSV file found inside master zip")
        csv_name = names[0]
        extracted = zf.read(csv_name)
        with open(out_path, "wb") as f:
            f.write(extracted)

    return out_path


def _find_latest_master(segment: str) -> Optional[str]:
    # find file with today's date or any existing file for that segment
    candidate_today = os.path.join(DATA_DIR, f"{segment}_{_today_tag()}.csv")
    if os.path.exists(candidate_today):
        return candidate_today
    # fallback to any file for that segment
    files = [os.path.join(DATA_DIR, f) for f in os.listdir(DATA_DIR) if f.startswith(segment + "_") and f.endswith(".csv")]
    if not files:
        return None
    # pick newest by mtime
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def load_master(segment: str = "NSE_CASH", auto_download: bool = True) -> pd.DataFrame:
    """
    Load master file as DataFrame. If today's master not present and auto_download True,
    it will attempt to download.
    """
    path = _find_latest_master(segment)
    if not path and auto_download:
        path = download_master(segment)
    if not path:
        raise FileNotFoundError(f"No master file found for segment {segment} in {DATA_DIR}")

    # File is CSV without header - we will try to load and assign column names.
    df = pd.read_csv(path, header=None, dtype=str, encoding="utf-8", low_memory=False)
    # if number of columns >= expected, assign first N names
    if df.shape[1] >= len(COLUMN_NAMES):
        df = df.iloc[:, : len(COLUMN_NAMES)]
        df.columns = COLUMN_NAMES
    else:
        # fallback: name generically
        df.columns = [f"COL{i}" for i in range(df.shape[1])]
    return df


def get_symbols_from_master(segment: str = "NSE_CASH", limit: Optional[int] = None) -> List[Dict]:
    """
    Return list of dicts with keys: TOKEN, SYMBOL, TRADINGSYM, ISIN, LOTSIZE, SEGMENT
    """
    df = load_master(segment)
    out = []
    for _, row in df.iterrows():
        rec = {
            "segment": row.get("SEGMENT", segment),
            "token": str(row.get("TOKEN", "")).strip(),
            "symbol": str(row.get("SYMBOL", "")).strip(),
            "tradingsymbol": str(row.get("TRADINGSYM", "")).strip(),
            "isin": str(row.get("ISIN", "")).strip(),
            "lotsize": int(row.get("LOTSIZE", 1)) if row.get("LOTSIZE") and str(row.get("LOTSIZE")).isdigit() else 1
        }
        out.append(rec)
        if limit and len(out) >= limit:
            break
    return out


def batch_symbols(segment: str = "NSE_CASH", batch_size: int = 500) -> Iterator[List[Dict]]:
    """
    Yield lists of symbol dicts of size batch_size based on master file.
    """
    symbols = get_symbols_from_master(segment)
    for i in range(0, len(symbols), batch_size):
        yield symbols[i : i + batch_size]


if __name__ == "__main__":
    # quick demo
    df = load_master("NSE_CASH")
    print("Loaded master:", df.shape)
    print("Sample:", df.head().to_dict(orient="records")[:3])
