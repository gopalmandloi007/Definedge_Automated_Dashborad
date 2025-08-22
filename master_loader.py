import pandas as pd

def load_watchlist(filename):
    # Read the file, ignore blank lines
    with open(filename, "r", encoding="utf-8") as f:
        lines = [line for line in f if line.strip()]
    records = [line.strip().split("\t") for line in lines]
    # Ignore rows with fewer than 3 columns (junk rows)
    records = [row for row in records if len(row) >= 3]
    # Convert to DataFrame
    df = pd.DataFrame(records)
    # Always assign exactly 15 columns
    base_columns = [
        "segment", "token", "symbol", "symbol_series", "series", "unknown1",
        "unknown2", "unknown3", "series2", "unknown4", "unknown5", "unknown6",
        "isin", "unknown7", "company"
    ]
    df.columns = base_columns[:df.shape[1]]
    # Ensure these columns always exist
    for col in ["segment", "token", "symbol", "series", "company"]:
        if col not in df.columns:
            df[col] = ""
    # Return only the columns you need (add more if you need in scanner)
    return df[["segment", "token", "symbol", "series", "company"]]

if __name__ == "__main__":
    df = load_watchlist("master.csv")
    print(df.head())
