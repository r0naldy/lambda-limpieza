import boto3
import csv
import json
import io
import re
from datetime import datetime

s3 = boto3.client('s3')

def is_valid_date(date_str):
    formats = ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M %p"]
    for fmt in formats:
        try:
            datetime.strptime(date_str.strip(), fmt)
            return True
        except:
            continue
    return False

def normalize_date(date_str):
    formats = ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M %p"]
    for fmt in formats:
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

def sanitize_country(value):
    return re.sub(r'[^\w\s]', '', value).strip()

def handler(event, context):
    try:
        bucket = event['Records'][0]['s3']['bucket']['name']
        key    = event['Records'][0]['s3']['object']['key']

        response = s3.get_object(Bucket=bucket, Key=key)
        body = response['Body'].read()

        try:
            csv_content = body.decode('utf-8')
        except UnicodeDecodeError:
            csv_content = body.decode('latin-1')

        reader = csv.DictReader(io.StringIO(csv_content))

        clean_data = []
        seen = set()

        # Mapeo de países a territorios
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
            # Validación de QUANTITYORDERED
            if not row.get('QUANTITYORDERED') or row['QUANTITYORDERED'].strip() in ["", "0"]:
                continue

            # Validación PRICEEACH
            if not is_numeric(row.get('PRICEEACH', '')) or float(row['PRICEEACH']) < 0:
                continue
            row['PRICEEACH'] = float(row['PRICEEACH'])

            # STATUS - corrección
            status = row.get('STATUS', '').strip().upper()
            if status == "DLEIVERED":
                row['STATUS'] = "DELIVERED"
            elif status == "":
                row['STATUS'] = "UNKNOWN"
            else:
                row['STATUS'] = status

            # Validación y normalización de ORDERDATE
            normalized_date = normalize_date(row.get('ORDERDATE', ''))
            if not normalized_date:
                continue
            row['ORDERDATE'] = normalized_date

            # Validación SALES
            if not is_numeric(row.get('SALES', '')):
                continue
            calculated_sales = float(row['QUANTITYORDERED']) * float(row['PRICEEACH'])
            if abs(float(row['SALES']) - calculated_sales) > 0.1:
                row['SALES'] = round(calculated_sales, 2)
            else:
                row['SALES'] = float(row['SALES'])

            # Validación MSRP
            if is_numeric(row.get('MSRP', '')):
                if float(row['PRICEEACH']) > float(row['MSRP']):
                    row['MSRP_ISSUE'] = True
                row['MSRP'] = float(row['MSRP'])
            else:
                row['MSRP'] = None

            # Evitar duplicados
            unique_key = json.dumps(row, sort_keys=True)
            if unique_key in seen:
                continue
            seen.add(unique_key)

            # PRODUCTCODE truncado
            row['PRODUCTCODE'] = row.get('PRODUCTCODE', '')[:15]

            # Validación ORDERNUMBER y ORDERLINENUMBER
            if not row.get('ORDERNUMBER') or not row['ORDERNUMBER'].isdigit():
                continue
            if not row.get('ORDERLINENUMBER') or not row['ORDERLINENUMBER'].isdigit():
                continue

            # PRODUCTLINE truncado
            row['PRODUCTLINE'] = row.get('PRODUCTLINE', '')[:60]

            # COUNTRY sanitizado
            row['COUNTRY'] = sanitize_country(row.get('COUNTRY', ''))

            # CITY por defecto
            row['CITY'] = row.get('CITY', '').strip() or "SIN CIUDAD"

            # TERRITORY por COUNTRY
            if not row.get('TERRITORY') and row['COUNTRY'] in territory_map:
                row['TERRITORY'] = territory_map[row['COUNTRY']]

            # POSTALCODE validación básica
            if not row.get('POSTALCODE') or not re.search(r'\d', row['POSTALCODE']):
                row['POSTALCODE'] = None

            # STATE para USA
            if row.get('COUNTRY') == "USA" and not row.get('STATE'):
                row['STATE'] = "UNKNOWN"

            # Agregar fila limpia
            clean_data.append(row)

        # Guardar resultado
        output_key = key.replace('.csv', '.json')
        s3.put_object(
            Bucket='bucket-json-clear',
            Key=output_key,
            Body=json.dumps(clean_data, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )

        return {
            'statusCode': 200,
            'body': f'✅ Archivo procesado exitosamente: {output_key}'
        }

    except Exception as e:
        print("❌ Error:", e)
        return {
            'statusCode': 500,
            'body': f'Error al procesar archivos: {str(e)}'
        }
