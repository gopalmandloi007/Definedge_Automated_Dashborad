import os
import requests
import zipfile
import io
import pandas as pd
from datetime import datetime

MASTER_FILE_URLS = {
    "NSE_CASH": "https://app.definedgesecurities.com/public/nsecash.zip",
    "NSE_FNO": "https://app.definedgesecurities.com/public/nsefno.zip",
    "BSE_CASH": "https://app.definedgesecurities.com/public/bsecash.zip",
    "BSE_FNO": "https://app.definedgesecurities.com/public/bsefno.zip",
    "NSE_CDS": "https://app.definedgesecurities.com/public/cdsfno.zip",
    "MCX_FNO": "https://app.definedgesecurities.com/public/mcxfno.zip",
    "ALL": "https://app.definedgesecurities.com/public/allmaster.zip"
}

DATA_DIR = os.path.join("data", "master_file")
os.makedirs(DATA_DIR, exist_ok=True)


def download_master(segment: str = "NSE_CASH") -> str:
    """
    Download master file zip for given segment and save as CSV in data/master_file/.
    Returns extracted CSV file path.
    """
    if segment not in MASTER_FILE_URLS:
        raise ValueError(f"Invalid segment: {segment}. Available: {list(MASTER_FILE_URLS.keys())}")

    url = MASTER_FILE_URLS[segment]
    print(f"Downloading master file for {segment} from {url}...")

    response = requests.get(url)
    response.raise_for_status()

    # Unzip
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        csv_name = zf.namelist()[0]  # assume only 1 csv inside
        extracted_path = os.path.join(DATA_DIR, f"{segment}_{datetime.now().strftime('%Y%m%d')}.csv")
        zf.extract(csv_name, DATA_DIR)
        os.rename(os.path.join(DATA_DIR, csv_name), extracted_path)

    print(f"Master file saved at: {extracted_path}")
    return extracted_path


def load_master(segment: str = "NSE_CASH") -> pd.DataFrame:
    """
    Load today's master file as pandas DataFrame.
    If not available, downloads automatically.
    """
    today_tag = datetime.now().strftime("%Y%m%d")
    expected_path = os.path.join(DATA_DIR, f"{segment}_{today_tag}.csv")

    if not os.path.exists(expected_path):
        expected_path = download_master(segment)

    df = pd.read_csv(expected_path)
    return df


if __name__ == "__main__":
    # Example usage
    df = load_master("NSE_CASH")
    print(df.head())
