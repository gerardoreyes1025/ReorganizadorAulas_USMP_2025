def create_connection():
    import mysql.connector

    # Parámetros de conexión a la base de datos
    connection = mysql.connector.connect(
        host="204.236.249.180",
        port=3306,
        user="gramos",
        password="Iniciousmp2025*",
        database="sap"
    )

    return connection