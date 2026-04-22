import sys
import pandas as pd
import glob
import os

search_paths = [
    r"C:\Users\Dudu\Downloads\Portfolio*.xlsx",
    r"C:\Users\Dudu\Desktop\Portfolio*.xlsx",
]

file_path = sys.argv[1] if len(sys.argv) > 1 else None
if not file_path:
    for pattern in search_paths:
        matches = glob.glob(pattern)
        if matches:
            file_path = sorted(matches)[-1]
            break

if not file_path or not os.path.exists(file_path):
    print("File not found.")
    sys.exit(1)

xl = pd.ExcelFile(file_path)
out_lines = [f"File: {file_path}\n"]
for sheet in xl.sheet_names:
    df = xl.parse(sheet)
    out_lines.append(f"=== Sheet: {sheet} ({len(df)} rows) ===")
    out_lines.append(f"Columns: {list(df.columns)}")
    out_lines.append(df.head(20).to_string())
    out_lines.append("")

with open("excel_debug.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines))

print("Written to excel_debug.txt")
