# lambda-limpieza

# 🧼 CSV Cleaner con AWS Lambda + S3

Este proyecto implementa una función AWS Lambda que se activa automáticamente cuando se sube un archivo CSV a un bucket de entrada del S3. La función lambda limpia, transforma y valida los datos del archivo, aplicando 20 reglas de negocio, y luego guarda el resultado en formato JSON que se envía a otro bucket de salida con los archivos procesados.

---

## 📌 Funcionalidad

- Escucha eventos de carga de archivos en un bucket S3 (archivo `.csv`)
- Procesa cada fila del archivo:
  - Convierte fechas al formato estándar `YYYY-MM-DD`
  - Verifica y convierte valores numéricos
  - Limpia texto y símbolos no deseados
  - Recalcula campos si hay inconsistencias
  - Descarta filas inválidas o duplicadas
- Guarda los resultados en formato `.json` en otro bucket

---

## 🧠 Reglas de negocio aplicadas

Estas son las 20 reglas implementadas en el código de limpieza y validación:

1. **QUANTITYORDERED** debe ser numérico y mayor a 0.
2. **PRICEEACH** debe ser un número decimal positivo.
3. **ORDERDATE** debe tener un formato válido y ser convertida a `YYYY-MM-DD`.
4. **SALES** se recalcula si no coincide con `QUANTITYORDERED * PRICEEACH`.
5. **STATUS**: si el valor es `DLEIVERED`, se corrige a `DELIVERED`. Si está vacío, se reemplaza por `UNKNOWN`.
6. **MSRP**: si no es numérico, se omite; si lo es, se evalúa si `PRICEEACH > MSRP` (marcando `MSRP_ISSUE`).
7. **PRODUCTCODE**: se limita a máximo 15 caracteres.
8. **PRODUCTLINE**: se limita a máximo 60 caracteres.
9. **ORDERNUMBER** y **ORDERLINENUMBER** deben ser completamente numéricos.
10. **COUNTRY**: se limpia eliminando símbolos no deseados.
11. **CITY**: si está vacío, se reemplaza con `"SIN CIUDAD"`.
12. **TERRITORY**: si está vacío, se completa automáticamente con base en el país.
13. **POSTALCODE**: si no contiene números, se descarta.
14. **STATE**: si el país es USA y el estado está vacío, se reemplaza por `"UNKNOWN"`.
15. **PHONE**: se limpia de símbolos y se valida que tenga al menos 7 dígitos.
16. **CONTACTFIRSTNAME** y **CONTACTLASTNAME**: se limpian eliminando símbolos especiales.
17. **DEALSIZE**: se limpia eliminando caracteres no alfanuméricos.
18. **NUMERICCODE**: si no es completamente numérico, se reemplaza con `null`.
19. **Filas duplicadas** (basado en hash JSON del contenido) son eliminadas.
20. **Filas con errores críticos** en campos clave se descartan y se reportan en los logs.

---

## 🏗️ Arquitectura

```
[S3 Bucket - CSV Entrada]
        |
        ▼
[Lambda - Procesamiento]
        |
        ▼
[S3 Bucket - JSON Limpio]
```

---

### Archivo `requirements.txt`

El archivo `requirements.txt` no fue necesario en esta implementación ya que las librerías utilizadas ya vienen preinstaladas en el entorno Lambda de AWS las cuales son:

```python
import boto3
import csv
import json
import io
import re
from datetime import datetime
```

No se agregaron dependencias externas como `pandas` o `matploit` ya que esas librerias superan el límite de 50MB que impone AWS para las subida del zip al lambda.

---

## Validaciones por Campo

| Campo             | Validación                                                     |
| ----------------- | -------------------------------------------------------------- |
| `ORDERDATE`       | Convertido a `YYYY-MM-DD`, múltiples formatos aceptados        |
| `QUANTITYORDERED` | Entero mayor a 0                                               |
| `PRICEEACH`       | Decimal positivo                                               |
| `SALES`           | Se recalcula si hay diferencia significativa con `qty * price` |
| `MSRP`            | Verifica si `PRICEEACH > MSRP`                                 |
| `ORDERNUMBER`     | Debe ser numérico                                              |
| `TERRITORY`       | Se completa automáticamente según país                         |
| `PHONE`           | Limpieza de símbolos, requiere al menos 7 dígitos              |
| `NUMERICCODE`     | Acepta solo valores numéricos                                  |
| Duplicados        | Se eliminan usando hash de la fila completa                    |

---

## Ejemplo de Entrada (CSV)

```csv
ORDERDATE,QUANTITYORDERED,PRICEEACH,STATUS,SALES,MSRP,PRODUCTCODE,ORDERNUMBER,ORDERLINENUMBER,PRODUCTLINE,COUNTRY,CITY,TERRITORY,POSTALCODE,STATE,PHONE,CONTACTLASTNAME,CONTACTFIRSTNAME,DEALSIZE,NUMERICCODE
06/30/2025,10,20.0,Delivered,200.0,25.0,S10_1678,10101,1,Motorcycles,USA,New York,,10001,,(212) 555-1212,Doe,John,Medium,12345
```

---

## Ejemplo de Salida (JSON)

```json
[
  {
    "ORDERDATE": "2025-06-30",
    "QUANTITYORDERED": 10,
    "PRICEEACH": 20.0,
    "STATUS": "DELIVERED",
    "SALES": 200.0,
    "MSRP": 25.0,
    "MSRP_ISSUE": false,
    "PRODUCTCODE": "S10_1678",
    "ORDERNUMBER": "10101",
    "ORDERLINENUMBER": "1",
    "PRODUCTLINE": "Motorcycles",
    "COUNTRY": "USA",
    "CITY": "New York",
    "TERRITORY": "NA",
    "POSTALCODE": "10001",
    "STATE": "UNKNOWN",
    "PHONE": "2125551212",
    "CONTACTLASTNAME": "Doe",
    "CONTACTFIRSTNAME": "John",
    "DEALSIZE": "Medium",
    "NUMERICCODE": "12345"
  }
]
```

---

## Registro de Errores por Fila

Cuando una fila es descartada, se imprime en el log el motivo:

```
Fila 2 descartada: ORDERDATE inválido, QUANTITYORDERED inválido, PRICEEACH inválido
```

---

## Despliegue

### 1. Crear función Lambda en AWS

- Lenguaje: Python 3.12 o compatible
- Permisos: acceso a S3 (GetObject, PutObject)

### 2. Conectar Trigger del Bucket

- Tipo: Evento `s3:ObjectCreated:*`
- Archivo esperado: `.csv`

---

## Licencia

Este proyecto está bajo licencia MIT. Puedes usarlo, modificarlo y distribuirlo libremente.

---