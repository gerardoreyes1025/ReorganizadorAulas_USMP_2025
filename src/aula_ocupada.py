from src.db.connection import create_connection
from src.db.queries import get_ocupaciones_aula
import csv

def exportar_ocupaciones_aula(connection, codigo_aula, ano, semestre, output_csv=None):
    ocupaciones = get_ocupaciones_aula(connection, codigo_aula, ano, semestre)
    print(f"Ocupaciones para el aula {codigo_aula}:")
    for o in ocupaciones:
        print(
            f"{o['CODIGODIA']} {o['HORAINICIO']}-{o['HORAFIN']} [{o['ORIGEN']}] "
            f"{o.get('NOMBRE_CURSO', '')} | {o.get('NOMBRE_PROGRAMA', '')} | {o.get('NOMBRE_DOCENTE', '')} | "
            f"{o.get('CAPACIDADMAXIMA', '')}"
        )
    if output_csv:
        with open(output_csv, 'w', newline='', encoding='UTF-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Dia', 'Hora Inicio', 'Hora Fin', 'Origen', 'Nombre Curso', 'Nombre Programa', 'Nombre Docente', 'Capacidad Maxima'])
            for o in ocupaciones:
                writer.writerow([
                    o['CODIGODIA'],
                    o['HORAINICIO'],
                    o['HORAFIN'],
                    o['ORIGEN'],
                    o.get('NOMBRE_CURSO', ''),
                    o.get('NOMBRE_PROGRAMA', ''),
                    o.get('NOMBRE_DOCENTE', ''),
                    o.get('CAPACIDADMAXIMA', '')
                ])
        print(f"Exportado a {output_csv}")

# El main solo sirve para pruebas manuales
if __name__ == "__main__":
    connection = create_connection()
    exportar_ocupaciones_aula(connection, codigo_aula='2101105', ano='2025', semestre='2', output_csv='ocupaciones_2101105.csv')
    connection.close()