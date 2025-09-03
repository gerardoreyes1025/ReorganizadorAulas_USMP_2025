from src.db.connection import create_connection
from src.logic.aula_logic import AulaLogic
import csv

def consultar_aulas_libres(connection, dia, hora_inicio, hora_fin, campus_code=14, pabellon_codes=None, capacidad_minima=None, output_csv=None):
    aula_logic = AulaLogic(connection)
    
    # Si no se especifican pabellones, usar todos los disponibles
    if pabellon_codes is None:
        pabellon_codes = [1, 2, 3, 4, 5, 7, 17]  # O los que tengas por defecto
    
    # Obtener todas las aulas libres
    libres = aula_logic.fetch_libres(campus_code, pabellon_codes, ano='2025', semestre='2')
    
    # Filtrar por los criterios especificados
    candidatos = []
    for (aula_codigo, aula_nombre, aula_capacidad), bloques in libres.items():
        # Filtrar por capacidad mínima
        if capacidad_minima and aula_capacidad < capacidad_minima:
            continue
            
        # Buscar bloques libres que contengan completamente el rango especificado
        bloques_que_cubren_rango = []
        tiempo_total_libre = 0
        
        for bloque in bloques:
            if bloque['dia'] == dia:
                # Verificar si el bloque libre contiene completamente el rango solicitado
                if (bloque['inicio'] <= hora_inicio and bloque['fin'] >= hora_fin):
                    # Calcular tiempo libre en minutos
                    inicio_min = int(hora_inicio.split(':')[0]) * 60 + int(hora_inicio.split(':')[1])
                    fin_min = int(hora_fin.split(':')[0]) * 60 + int(hora_fin.split(':')[1])
                    tiempo_libre = fin_min - inicio_min
                    
                    bloques_que_cubren_rango.append({
                        'inicio': hora_inicio,
                        'fin': hora_fin,
                        'tiempo_libre': tiempo_libre,
                        'bloque_completo_inicio': bloque['inicio'],
                        'bloque_completo_fin': bloque['fin']
                    })
                    tiempo_total_libre += tiempo_libre
        
        # Si hay bloques que cubren completamente el rango, agregar el aula a candidatos
        if bloques_que_cubren_rango:
            candidatos.append({
                'codigo': aula_codigo,
                'nombre': aula_nombre,
                'capacidad': aula_capacidad,
                'pabellon': aula_codigo[:2] if len(aula_codigo) >= 2 else 'N/A',
                'bloques_libres': bloques_que_cubren_rango,
                'tiempo_total_libre': tiempo_total_libre
            })
    
    # Mostrar resultados
    print(f"Aulas libres para {dia} {hora_inicio}-{hora_fin}:")
    if candidatos:
        for i, aula in enumerate(candidatos, 1):
            print(f"{i}. {aula['codigo']} - {aula['nombre']} (Cap: {aula['capacidad']}, Pab: {aula['pabellon']})")
            print(f"   Tiempo solicitado disponible: {aula['tiempo_total_libre']} minutos ({aula['tiempo_total_libre']//60}h {aula['tiempo_total_libre']%60}min)")
            print(f"   Bloques que cubren el rango solicitado:")
            for bloque in aula['bloques_libres']:
                print(f"     - Rango solicitado: {bloque['inicio']} a {bloque['fin']} ({bloque['tiempo_libre']} min)")
                print(f"       (Dentro del bloque libre: {bloque['bloque_completo_inicio']} a {bloque['bloque_completo_fin']})")
            print()
    else:
        print("No se encontraron aulas libres con los criterios especificados.")
    
    # Exportar a CSV si se solicita
    if output_csv:
        with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Codigo', 'Nombre', 'Capacidad', 'Pabellon', 'Tiempo_Solicitado_Min', 'Tiempo_Solicitado_Horas', 'Rango_Solicitado', 'Bloque_Libre_Completo'])
            for aula in candidatos:
                # Formatear información para CSV
                rango_solicitado = f"{hora_inicio}-{hora_fin}"
                bloque_completo = f"{aula['bloques_libres'][0]['bloque_completo_inicio']}-{aula['bloques_libres'][0]['bloque_completo_fin']}"
                
                # Calcular horas y minutos
                horas = aula['tiempo_total_libre'] // 60
                minutos = aula['tiempo_total_libre'] % 60
                tiempo_formato = f"{horas}h {minutos}min"
                
                writer.writerow([
                    aula['codigo'], 
                    aula['nombre'], 
                    aula['capacidad'], 
                    aula['pabellon'],
                    aula['tiempo_total_libre'],
                    tiempo_formato,
                    rango_solicitado,
                    bloque_completo
                ])
        print(f"Resultados exportados a {output_csv}")
    
    return candidatos

# Main de prueba
if __name__ == "__main__":
    connection = create_connection()
    consultar_aulas_libres(
        connection,
        dia='MA',
        hora_inicio='20:01',
        hora_fin='22:15',
        campus_code=14,
        pabellon_codes=[3, 4],  # Solo pabellones 3 y 4
        capacidad_minima=30,    # Mínimo 30 estudiantes
        output_csv='consulta_aulas.csv'
    )
    connection.close()