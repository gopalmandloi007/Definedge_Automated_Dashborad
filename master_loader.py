import pandas as pd

def extract_symbol(row):
    # If symbol is non-empty, use it
    if row.get('symbol', '').strip():
        return row['symbol'].strip()
    # Otherwise, try to extract symbol from company name (remove spaces, take first word, etc)
    company = row.get('company', '').strip()
    if company:
        # Example logic: take first word, uppercase
        return company.split()[0].upper()
    # Fallback: use token if available
    token = row.get('token', '').strip()
    if token:
        return token
    return ""

def load_watchlist(filename):
    # Read the file, ignore blank lines
    with open(filename, "r", encoding="utf-8") as f:
        lines = [line for line in f if line.strip()]
    records = [line.strip().split("\t") for line in lines]
    # Ignore rows with fewer than 3 columns (junk rows)
    records = [row for row in records if len(row) >= 3]
    # Always assign exactly 15 columns
    base_columns = [
        "segment", "token", "symbol", "symbol_series", "series", "unknown1",
        "unknown2", "unknown3", "series2", "unknown4", "unknown5", "unknown6",
        "isin", "unknown7", "company"
    ]
    # If more columns, trim; if fewer, pad
    for i, row in enumerate(records):
        if len(row) < len(base_columns):
            row += [""] * (len(base_columns) - len(row))
        elif len(row) > len(base_columns):
            row = row[:len(base_columns)]
        records[i] = row
    df = pd.DataFrame(records, columns=base_columns)
    # Ensure required columns always exist
    for col in ["segment", "token", "symbol", "series", "company"]:
        if col not in df.columns:
            df[col] = ""
    # Fix symbol column: fill missing/blank symbols automatically
    df['symbol'] = df.apply(extract_symbol, axis=1)
    # Return only the columns you need (add more if you need in scanner)
    return df[["segment", "token", "symbol", "series", "company"]]

if __name__ == "__main__":
    df = load_watchlist("master.csv")
    print(df.head())
