from src.db.connection import create_connection
from src.logic.aula_logic import AulaLogic

import csv

def exportar_aulas_libres(aula_logic, campus_code, pabellon_codes, ano, semestre, output_csv='aulas_libres1.csv'):
    libres = aula_logic.fetch_libres(campus_code, pabellon_codes, ano, semestre)
    # Mostrar en consola
    for (aula_codigo, aula_nombre, capacidad), bloques in libres.items():
        print(f"Aula: {aula_codigo} - {aula_nombre} (Capacidad: {capacidad})")
        for bloque in bloques:
            if 'nombre_curso' in bloque:
                print(f"{bloque['dia']} {bloque['inicio']}-{bloque['fin']} | {bloque['nombre_curso']} | {bloque['nombre_programa']} | {bloque['nombre_docente']}")
            else:
                print(f"{bloque['dia']} {bloque['inicio']}-{bloque['fin']}")
    # Exportar a CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Aula Codigo', 'Aula Nombre', 'Capacidad', 'Dia', 'Hora Inicio', 'Hora Fin'])
        for (aula_codigo, aula_nombre, capacidad), bloques in libres.items():
            for bloque in bloques:
                writer.writerow([aula_codigo, aula_nombre, capacidad, bloque['dia'], bloque['inicio'], bloque['fin']])
    print(f"Exportado a {output_csv}") 


if __name__ == "__main__":
    connection = create_connection()
    aula_logic = AulaLogic(connection)
    exportar_aulas_libres(aula_logic, campus_code='14', pabellon_codes='4', ano='2025', semestre='2', output_csv='aulas_libres1.csv')
    connection.close()