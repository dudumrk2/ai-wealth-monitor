import os

file_path = r'd:\AICode\ai-wealth-monitor\backend\app.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the yields description for clarity
old_yields = """      "yield_1yr": number,
      "yield_3yr": number,
      "yield_5yr": number"""

new_yields = """      "yield_1yr": number, # תשואה לשנה (YTD)
      "yield_3yr": number, # תשואה מצטברת ל-3 שנים (Cumulative)
      "yield_5yr": number  # תשואה מצטברת ל-5 שנים (Cumulative)"""

if old_yields in content:
    content = content.replace(old_yields, new_yields)
    print("✅ Yield structure updated.")
else:
    # Try with single space indentation just in case
    old_yields_2 = """      "yield_1yr": number,
      "yield_3yr": number,
      "yield_5yr": number"""
    # Wait, the previous view showed 14 spaces or something. 
    # I'll use a more flexible regex-like approach or just find the line.
    lines = content.splitlines()
    updated = False
    for i in range(len(lines)):
        if '"yield_1yr": number,' in lines[i]:
            lines[i] = lines[i] + ' # תשואה לשנה (YTD)'
            if i+1 < len(lines) and '"yield_3yr": number,' in lines[i+1]:
                lines[i+1] = lines[i+1].replace('number,', 'number, # חובה: תשואה מצטברת (Cumulative)')
            if i+2 < len(lines) and '"yield_5yr": number' in lines[i+2]:
                lines[i+2] = lines[i+2].replace('number', 'number  # חובה: תשואה מצטברת (Cumulative)')
            updated = True
            break
    if updated:
        content = "\n".join(lines)
        print("✅ Yield lines updated via line search.")

# 2. Add the explicit instruction block
instruction_marker = 'CRITICAL:'
new_instructions = """הנחיות קריטיות לחילוץ תשואות (Yields):
- עבור תשואה ל-3 שנים (yield_3yr) ותשואה ל-5 שנים (yield_5yr), חלץ אך ורק את התשואה ה**מצטברת** (Cumulative Yield).
- אל תשתמש בתשואה שנתית ממוצעת (Average Annual Yield) עבור שדות אלו.
- דוגמה: אם בדוח מופיע "תשואה מצטברת 60%" ו-"תשואה שנתית ממוצעת 10%", עליך להחזיר 60.

CRITICAL:"""

if instruction_marker in content:
    content = content.replace(instruction_marker, new_instructions)
    print("✅ Extraction instructions added.")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("🚀 All fixes applied to app.py")
