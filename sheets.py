import gspread
from oauth2client.service_account import ServiceAccountCredentials

def append_order(order_data: dict, spreadsheet_id: str = None, worksheet_name: str = None) -> bool:
    try:
        scope = [
            "https://spreadsheets.google.com/feeds", 
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
        
        available_sheets = client.openall()
        if not available_sheets:
            print("CRITICAL ERROR: Service account has no access to any spreadsheets.")
            return False
            
        spreadsheet = available_sheets[0]
        
        try:
            if worksheet_name:
                sheet = spreadsheet.worksheet(worksheet_name)
            else:
                sheet = spreadsheet.get_worksheet(0)
        except gspread.exceptions.WorksheetNotFound:
            sheet = spreadsheet.get_worksheet(0)
            
        row = [
            str(order_data.get("name", "")),
            str(order_data.get("phone", "")),
            str(order_data.get("region", "")),
            str(order_data.get("address", "")),
            str(order_data.get("product", "")),
            int(order_data.get("amount", 0))
        ]
        
        sheet.append_row(row)
        print("SUCCESS: Data successfully written to the sheet.")
        return True
        
    except Exception as e:
        print(f"CRITICAL SYSTEM ERROR: {e}")
        return False
