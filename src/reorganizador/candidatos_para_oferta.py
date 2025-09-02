from src.db.connection import create_connection

from src.logic.aula_logic import AulaLogic
from src.aula_ocupada import get_ocupaciones_aula
import csv


def buscar_candidatos(libres, dia, hora_inicio, hora_fin, excluido, capacidad_requerida, ocupaciones_ficticias=None):
    candidatos = []
    for (aula_codigo, aula_nombre, aula_capacidad), bloques in libres.items():
        if aula_codigo == excluido:
            continue
        if aula_capacidad < capacidad_requerida:
            continue
        # Verifica si el aula ya tiene una ocupación ficticia en ese horario
        if ocupaciones_ficticias:
            key = (aula_codigo, dia)
            ocupado = False
            for ini, fin in ocupaciones_ficticias.get(key, []):
                if not (hora_fin <= ini or hora_inicio >= fin):
                    ocupado = True
                    break
            if ocupado:
                continue
        for bloque in bloques:
            if bloque['dia'] == dia and bloque['inicio'] <= hora_inicio and bloque['fin'] >= hora_fin:
                candidatos.append((aula_codigo, aula_nombre, aula_capacidad))
                break
    return candidatos



def asignar_ofertas_sin_cruce(ocupaciones, libres, codigo_aula, ocupaciones_ficticias=None):
    asignaciones = {}
    resultado = []
    for o in ocupaciones:
        dia = o['CODIGODIA']
        hora_inicio = o['HORAINICIO']
        hora_fin = o['HORAFIN']
        capacidad_requerida = o.get('CAPACIDADMAXIMA', 0) or 0
        asignado = False
        candidatos = buscar_candidatos(
            libres, dia, hora_inicio, hora_fin, excluido=codigo_aula,
            capacidad_requerida=capacidad_requerida, ocupaciones_ficticias=ocupaciones_ficticias
        )
        for aula_codigo, aula_nombre, aula_capacidad in candidatos:
            key = (aula_codigo, aula_nombre, aula_capacidad)
            if key not in asignaciones:
                asignaciones[key] = []
            cruce = False
            for (d, ini, fin) in asignaciones[key]:
                if d == dia and not (hora_fin <= ini or hora_inicio >= fin):
                    cruce = True
                    break
            if not cruce:
                asignaciones[key].append((dia, hora_inicio, hora_fin))
                resultado.append({'oferta': o, 'aula': key})
                asignado = True
                break
        if not asignado:
            resultado.append({'oferta': o, 'aula': None})
    return resultado

def exportar_candidatos_para_oferta(connection, codigo_aula, campus_code, pabellon_codes, ano, semestre, output_candidatos='candidatos_por_oferta.csv', output_asignacion='asignacion_sin_cruce.csv'):
    aula_logic = AulaLogic(connection)
    ocupaciones = get_ocupaciones_aula(connection, codigo_aula, ano, semestre)
    libres = aula_logic.fetch_libres(campus_code, pabellon_codes, ano, semestre)

    print(f"Candidatos alternativos para cada horario ocupado en el aula {codigo_aula}:")
    with open(output_candidatos, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Dia', 'Hora Inicio', 'Hora Fin', 'Origen', 'Nombre Curso', 'Nombre Programa', 'Nombre Docente', 'Capacidad Requerida', 'Aulas Candidatas'])
        for o in ocupaciones:
            dia = o['CODIGODIA']
            hora_inicio = o['HORAINICIO']
            hora_fin = o['HORAFIN']
            capacidad_requerida = o.get('CAPACIDADMAXIMA', 0) or 0
            candidatos = buscar_candidatos(libres, dia, hora_inicio, hora_fin, excluido=codigo_aula, capacidad_requerida=capacidad_requerida)
            candidatos_str = "; ".join([f"{c[0]} - {c[1]} (Cap: {c[2]})" for c in candidatos]) if candidatos else "Ninguna"
            print(f"{dia} {hora_inicio}-{hora_fin} [{o['ORIGEN']}] {o.get('NOMBRE_CURSO','')} | {o.get('NOMBRE_PROGRAMA','')} | {o.get('NOMBRE_DOCENTE','')} | Capacidad requerida: {capacidad_requerida}: {candidatos_str}")
            writer.writerow([
                dia, hora_inicio, hora_fin, o['ORIGEN'],
                o.get('NOMBRE_CURSO',''), o.get('NOMBRE_PROGRAMA',''), o.get('NOMBRE_DOCENTE',''),
                capacidad_requerida, candidatos_str
            ])
    print(f"Exportado a {output_candidatos}")

    # Nuevo reporte: asignación sin cruces
    asignaciones = asignar_ofertas_sin_cruce(ocupaciones, libres, codigo_aula)
    with open(output_asignacion, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Dia', 'Hora Inicio', 'Hora Fin', 'Origen', 'Nombre Curso', 'Nombre Programa', 'Nombre Docente', 'Capacidad Requerida', 'Aula Asignada', 'Capacidad Aula'])
        for item in asignaciones:
            o = item['oferta']
            aula = item['aula']
            if aula:
                aula_codigo, aula_nombre, aula_capacidad = aula
                aula_str = f"{aula_codigo} - {aula_nombre}"
            else:
                aula_str = "Sin aula disponible"
                aula_capacidad = ""
            writer.writerow([
                o['CODIGODIA'], o['HORAINICIO'], o['HORAFIN'], o['ORIGEN'],
                o.get('NOMBRE_CURSO',''), o.get('NOMBRE_PROGRAMA',''), o.get('NOMBRE_DOCENTE',''),
                o.get('CAPACIDADMAXIMA', 0) or 0,
                aula_str, aula_capacidad
            ])
    print(f"Exportado a {output_asignacion}")

# Main de prueba manual
if __name__ == "__main__":
    from src.db.connection import create_connection
    connection = create_connection()
    exportar_candidatos_para_oferta(
        connection,
        codigo_aula='2101105',
        campus_code=14,
        pabellon_codes=[4,3],
        ano='2025',
        semestre='2',
        output_candidatos='candidatos_por_oferta.csv',
        output_asignacion='asignacion_sin_cruce.csv'
    )
    connection.close()