# index.py
def handler(event, context):
    print("Lambda limpia CSV")
    return {"statusCode": 200, "body": "Función ejecutada correctamente"}
