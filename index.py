import boto3
import csv
import json
import io
import re
from datetime import datetime

s3 = boto3.client('s3')

DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y",
    "%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M %p"
]

def parse_date(date_str):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime('%Y-%m-%d')
        except:
            continue
    return None

def is_numeric(value):
    try:
        float(value)
        return True
    except:
        return False

def sanitize_text(value):
    if not value:
        return ""
    return re.sub(r'[^\w\s]', '', value).strip()

def sanitize_phone(phone):
    if not phone:
        return None
    cleaned = re.sub(r'\D', '', phone)
    return cleaned if len(cleaned) >= 7 else None

def is_valid_numericcode(code):
    return code.isdigit() if code else False

def handler(event, context):
    try:
        bucket_name = event['Records'][0]['s3']['bucket']['name']
        object_key  = event['Records'][0]['s3']['object']['key']

        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        body = response['Body'].read()

        try:
            csv_content = body.decode('utf-8')
        except UnicodeDecodeError:
            csv_content = body.decode('latin-1')

        reader = csv.DictReader(io.StringIO(csv_content))

        clean_rows = []
        seen_rows = set()

        territory_map = {
            "USA": "NA",
            "France": "EMEA",
            "Australia": "APAC",
            "Japan": "APAC",
            "Germany": "EMEA",
            "UK": "EMEA",
            "Spain": "EMEA"
        }

        for row in reader:

            qty = row.get('QUANTITYORDERED', '').strip()
            if not qty or qty == "0" or not qty.isdigit():
                continue
            row['QUANTITYORDERED'] = int(qty)

            price = row.get('PRICEEACH', '').strip()
            if not is_numeric(price) or float(price) < 0:
                continue
            row['PRICEEACH'] = float(price)

            status = row.get('STATUS', '').strip().upper()
            row['STATUS'] = "DELIVERED" if status == "DLEIVERED" else (status or "UNKNOWN")

            order_date = parse_date(row.get('ORDERDATE', ''))
            if not order_date:
                continue
            row['ORDERDATE'] = order_date

            sales_str = row.get('SALES', '').strip()
            if not is_numeric(sales_str):
                continue
            sales = float(sales_str)
            calc_sales = row['QUANTITYORDERED'] * row['PRICEEACH']
            row['SALES'] = round(calc_sales, 2) if abs(sales - calc_sales) > 0.1 else sales

            msrp_str = row.get('MSRP', '').strip()
            if is_numeric(msrp_str):
                msrp = float(msrp_str)
                row['MSRP'] = msrp
                row['MSRP_ISSUE'] = row['PRICEEACH'] > msrp
            else:
                row['MSRP'] = None
                row['MSRP_ISSUE'] = False

            row['PRODUCTCODE'] = row.get('PRODUCTCODE', '')[:15]

            if not row.get('ORDERNUMBER', '').isdigit():
                continue
            if not row.get('ORDERLINENUMBER', '').isdigit():
                continue

            row['PRODUCTLINE'] = row.get('PRODUCTLINE', '')[:60]

            country = sanitize_text(row.get('COUNTRY', ''))
            row['COUNTRY'] = country

            city = row.get('CITY', '').strip()
            row['CITY'] = city if city else "SIN CIUDAD"

            if not row.get('TERRITORY'):
                row['TERRITORY'] = territory_map.get(country, '')

            postal_code = row.get('POSTALCODE', '')
            if not postal_code or not re.search(r'\d', postal_code):
                row['POSTALCODE'] = None

            if country == "USA" and not row.get('STATE'):
                row['STATE'] = "UNKNOWN"

            row['PHONE'] = sanitize_phone(row.get('PHONE', ''))

            row['CONTACTLASTNAME'] = sanitize_text(row.get('CONTACTLASTNAME', ''))
            row['CONTACTFIRSTNAME'] = sanitize_text(row.get('CONTACTFIRSTNAME', ''))

            row['DEALSIZE'] = sanitize_text(row.get('DEALSIZE', ''))

            num_code = row.get('NUMERICCODE', '').strip()
            row['NUMERICCODE'] = num_code if is_valid_numericcode(num_code) else None

            key_unique = json.dumps(row, sort_keys=True)
            if key_unique in seen_rows:
                continue
            seen_rows.add(key_unique)

            clean_rows.append(row)

        output_key = object_key.rsplit('.', 1)[0] + '.json'
        s3.put_object(
            Bucket='bucket-json-clear',
            Key=output_key,
            Body=json.dumps(clean_rows, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )

        return {
            'statusCode': 200,
            'body': f' Archivo procesado exitosamente: {output_key}'
        }

    except Exception as e:
        print("Error:", e)
        return {
            'statusCode': 500,
            'body': f'Error al procesar archivos: {str(e)}'
        }
