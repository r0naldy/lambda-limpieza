import boto3
import csv
import json
import io
import re
from datetime import datetime

s3 = boto3.client('s3')

def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except:
        return False

def is_numeric(value):
    try:
        float(value)
        return True
    except:
        return False

def sanitize_country(value):
    return re.sub(r'[^\w\s]', '', value).strip()  # elimina emojis y símbolos

def lambda_handler(event, context):
    try:
        bucket = event['Records'][0]['s3']['bucket']['name']
        key    = event['Records'][0]['s3']['object']['key']

        # Leer CSV desde S3
        response = s3.get_object(Bucket=bucket, Key=key)
        csv_content = response['Body'].read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_content))

        clean_data = []
        seen = set()

        for row in reader:
            # 1: QUANTITYORDERED - eliminar si vacío o cero
            if not row.get('QUANTITYORDERED') or row['QUANTITYORDERED'].strip() in ["", "0"]:
                continue

            # 2: PRICEEACH - eliminar si negativo o no numérico
            if not is_numeric(row.get('PRICEEACH', '')) or float(row['PRICEEACH']) < 0:
                continue

            # 3: STATUS - corregir errores comunes
            status = row.get('STATUS', '').strip().upper()
            if status == "DLEIVERED":
                row['STATUS'] = "DELIVERED"
            elif status == "":
                row['STATUS'] = "UNKNOWN"

            # 4: ORDERDATE - descartar si fecha inválida
            if not is_valid_date(row.get('ORDERDATE', '')):
                continue

            # 5 & 11: SALES - convertir a número o descartar si inválido o vacío
            sales = row.get('SALES', '')
            if not is_numeric(sales):
                continue
            row['SALES'] = float(sales)

            # 6: Eliminar registros duplicados
            unique_key = json.dumps(row, sort_keys=True)
            if unique_key in seen:
                continue
            seen.add(unique_key)

            # 7: PRODUCTCODE - truncar a 15 caracteres
            row['PRODUCTCODE'] = row.get('PRODUCTCODE', '')[:15]

            # 8 y 9: ORDERNUMBER / ORDERLINENUMBER - eliminar si vacío o no numérico
            if not row.get('ORDERNUMBER') or not row['ORDERNUMBER'].isdigit():
                continue
            if not row.get('ORDERLINENUMBER') or not row['ORDERLINENUMBER'].isdigit():
                continue

            # 13: PRODUCTLINE - truncar a 30 caracteres
            row['PRODUCTLINE'] = row.get('PRODUCTLINE', '')[:30]

            # 14: NUMERICCODE - descartar si contiene letras
            if not is_numeric(row.get('NUMERICCODE', '')):
                continue

            # 18: ORDERLINENUMBER - descartar si texto tipo "LINEA-X"
            if not row['ORDERLINENUMBER'].isdigit():
                continue

            # 19: COUNTRY - quitar emojis
            row['COUNTRY'] = sanitize_country(row.get('COUNTRY', ''))

            # 20: CITY - si vacío, asignar "SIN CIUDAD"
            row['CITY'] = row.get('CITY', '').strip() or "SIN CIUDAD"

            # Agregar fila limpia
            clean_data.append(row)

        # Guardar JSON limpio en S3
        output_key = key.replace('.csv', '.json')
        s3.put_object(
            Bucket='bucket-json-clear',
            Key=output_key,
            Body=json.dumps(clean_data, indent=2),
            ContentType='application/json'
        )

        return {
            'statusCode': 200,
            'body': f'Archivo procesado exitosamente: {output_key}'
        }

    except Exception as e:
        print("❌ Error:", e)
        return {
            'statusCode': 500,
            'body': f'Error al procesar archivo: {str(e)}'
        }
