# masterfile_handler.py
import os
import zipfile
import io
import datetime
from typing import List, Dict, Iterator, Optional

import requests
import pandas as pd

from debug_utils import debug_log

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
    debug_log(f"download_master(segment={segment}, force={force})")
    if segment not in MASTER_FILE_URLS:
        raise ValueError(f"Unknown segment '{segment}'. Valid: {list(MASTER_FILE_URLS.keys())}")

    out_path = os.path.join(DATA_DIR, f"{segment}_{_today_tag()}.csv")
    if os.path.exists(out_path) and not force:
        debug_log(f"Master already present: {out_path}")
        return out_path

    url = MASTER_FILE_URLS[segment]
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise RuntimeError("No CSV file found inside master zip")
        csv_name = names[0]
        extracted = zf.read(csv_name)
        with open(out_path, "wb") as f:
            f.write(extracted)
    debug_log(f"Saved master to {out_path}")
    return out_path


def _find_latest_master(segment: str) -> Optional[str]:
    candidate_today = os.path.join(DATA_DIR, f"{segment}_{_today_tag()}.csv")
    if os.path.exists(candidate_today):
        return candidate_today
    files = [os.path.join(DATA_DIR, f) for f in os.listdir(DATA_DIR) if f.startswith(segment + "_") and f.endswith(".csv")]
    if not files:
        return None
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

    df = pd.read_csv(path, header=None, dtype=str, encoding="utf-8", low_memory=False)
    if df.shape[1] >= len(COLUMN_NAMES):
        df = df.iloc[:, : len(COLUMN_NAMES)]
        df.columns = COLUMN_NAMES
    else:
        df.columns = [f"COL{i}" for i in range(df.shape[1])]
    debug_log(f"Loaded master {path} with shape {df.shape}")
    return df


def get_symbols_from_master(segment: str = "NSE_CASH", limit: Optional[int] = None) -> List[Dict]:
    """
    Return list of dicts with keys: segment, token, symbol, tradingsymbol, isin, lotsize
    """
    df = load_master(segment)
    out = []
    for _, row in df.iterrows():
        token = str(row.get("TOKEN", "")).strip()
        lotsize = 1
        try:
            lotsize_raw = row.get("LOTSIZE", None)
            if pd.notna(lotsize_raw) and str(lotsize_raw).strip().isdigit():
                lotsize = int(str(lotsize_raw).strip())
        except Exception:
            lotsize = 1

        rec = {
            "segment": str(row.get("SEGMENT", segment)).strip(),
            "token": token,
            "symbol": str(row.get("SYMBOL", "")).strip(),
            "tradingsymbol": str(row.get("TRADINGSYM", "")).strip(),
            "isin": str(row.get("ISIN", "")).strip(),
            "lotsize": lotsize
        }
        out.append(rec)
        if limit and len(out) >= limit:
            break
    debug_log(f"get_symbols_from_master(segment={segment}, limit={limit}) -> {len(out)} symbols")
    return out


def batch_symbols(segment: str = "NSE_CASH", batch_size: int = 500) -> Iterator[List[Dict]]:
    """
    Yield lists of symbol dicts of size batch_size based on master file.
    """
    symbols = get_symbols_from_master(segment)
    for i in range(0, len(symbols), batch_size):
        yield symbols[i: i + batch_size]


if __name__ == "__main__":
    df = load_master("NSE_CASH")
    print("Loaded master:", df.shape)
