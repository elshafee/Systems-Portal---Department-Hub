from openpyxl import Workbook

# 1. Create a new Workbook and select the active sheet
wb = Workbook()
sheet = wb.active
sheet.title = "My Manual Data"

# 2. Add some headers to the first row
headers = ["Name", "Email", "Age", "Status"]
sheet.append(headers)

# 3. Define the data you want to save
new_data = [
    ["Alice", "alice@example.com", 28, "Active"],
    ["Bob", "bob@example.com", 32, "Inactive"],
    ["Charlie", "charlie@example.com", 25, "Active"]
]

# 4. Loop through your data and append each row to the sheet
for row in new_data:
    sheet.append(row)

# 5. Save the file locally
file_name = "Manual_Export.xlsx"
wb.save(file_name)

print(f"✅ Success! File saved locally as '{file_name}'.")