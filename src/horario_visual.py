import csv
from collections import defaultdict, OrderedDict

# Configura los días y el orden de columnas
DIAS = ['LU', 'MA', 'MI', 'JU', 'VI', 'SA', 'DO']

def leer_asignaciones(path):
    asignaciones = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            asignaciones.append(row)
    return asignaciones

def construir_horario(asignaciones):
    # Mapea (hora_inicio, hora_fin) -> {dia: info}
    horario = OrderedDict()
    for row in asignaciones:
        dia = row['Dia']
        hora = f"{row['Hora Inicio']}-{row['Hora Fin']}"
        key = (row['Hora Inicio'], row['Hora Fin'])
        info = f"{row['Capacidad Requerida']} | {row['Nombre Curso']} | {row['Nombre Programa']} | {row['Aula Asignada']}"
        if key not in horario:
            horario[key] = {d: "" for d in DIAS}
        horario[key][dia] = info
    return horario

def exportar_horario(horario, output_path):
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        header = ['Hora'] + DIAS
        writer.writerow(header)

        for (ini, fin) in sorted(horario.keys(), key=lambda x: (int(x[0][:2]), int(x[0][3:]))):
            dias_info = horario[(ini, fin)]
            row = [f"{ini}-{fin}"]
        # for (ini, fin), dias_info in horario.items():
        #     row = [f"{ini}-{fin}"]
            for d in DIAS:
                row.append(dias_info.get(d, ""))
            writer.writerow(row)
    print(f"Exportado a {output_path}")

def generar_intervalos(hora_inicio='07:16', hora_fin='23:00', duracion=45):
    from datetime import datetime, timedelta
    fmt = "%H:%M"
    h_ini = datetime.strptime(hora_inicio, fmt)
    h_fin = datetime.strptime(hora_fin, fmt)
    intervalos = []
    actual = h_ini
    while actual < h_fin:
        siguiente = actual + timedelta(minutes=duracion)
        if siguiente > h_fin:
            siguiente = h_fin
        intervalos.append((actual.strftime(fmt), (siguiente - timedelta(minutes=1)).strftime(fmt)))
        actual = siguiente
    return intervalos

def construir_horario_estandar(asignaciones, intervalos):
    # Mapea (intervalo) -> {dia: info}
    horario = OrderedDict()
    for ini, fin in intervalos:
        horario[(ini, fin)] = {d: "" for d in DIAS}
    for row in asignaciones:
        dia = row['Dia']
        bloque_ini = row['Hora Inicio']
        bloque_fin = row['Hora Fin']
        info = f"{row['Capacidad Requerida']} | {row['Nombre Curso']} | {row['Nombre Programa']} | {row['Aula Asignada']}"
        for (ini, fin) in horario.keys():
            # Si el intervalo estándar se solapa con el bloque asignado
            if not (fin < bloque_ini or ini > bloque_fin):
                horario[(ini, fin)][dia] = info
    return horario

def main():
    asignaciones = leer_asignaciones('asignacion_sin_cruce.csv')
    intervalos = generar_intervalos('07:16', '23:00', 45)  # o el rango/duración que prefieras
    horario = construir_horario_estandar(asignaciones, intervalos)
    exportar_horario(horario, 'horario_visual.csv')

if __name__ == "__main__":
    main()