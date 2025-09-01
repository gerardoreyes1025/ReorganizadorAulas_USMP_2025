import json
import os
from src.db.connection import create_connection
from src.logic.aula_logic import AulaLogic
from src.aula_ocupada import get_ocupaciones_aula
from src.candidatos_para_oferta import asignar_ofertas_sin_cruce

CONFIG_DIR = "reorg_configs"

def listar_configuraciones():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    archivos = [f for f in os.listdir(CONFIG_DIR) if f.endswith('.json')]
    return archivos

def cargar_configuracion(nombre):
    with open(os.path.join(CONFIG_DIR, nombre), 'r', encoding='utf-8') as f:
        return json.load(f)

def guardar_configuracion(nombre, data):
    with open(os.path.join(CONFIG_DIR, nombre), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def nueva_configuracion():
    nombre = input("Nombre para la nueva reorganización: ") + ".json"
    config = {
        "movimientos": [],
        "aulas_liberadas": [],
        "sugerencias": [],
        "aprobados": [],
        "rechazados": []
    }
    guardar_configuracion(nombre, config)
    return nombre, config
    
# def obtener_ocupaciones_ficticias(config):
#     # Mapea (aula_codigo, dia) -> lista de (inicio, fin)
#     ocupadas = {}
#     for mov in config.get("movimientos", []):
#         aula = mov["aula_sugerida"]
#         if aula:
#             aula_codigo, aula_nombre, aula_capacidad = aula
#             dia = mov["oferta"]["CODIGODIA"]
#             ini = mov["oferta"]["HORAINICIO"]
#             fin = mov["oferta"]["HORAFIN"]
#             key = (aula_codigo, dia)
#             if key not in ocupadas:
#                 ocupadas[key] = []
#             ocupadas[key].append((ini, fin))
#     return ocupadas

def obtener_ocupaciones_ficticias(config):
    # Mapea (aula_codigo, dia) -> lista de (inicio, fin)
    ocupadas = {}
    for mov in config.get("movimientos", []):
        aula = mov["aula_sugerida"]
        if aula:
            aula_codigo, aula_nombre, aula_capacidad = aula
            dia = mov["oferta"]["CODIGODIA"]
            ini = mov["oferta"]["HORAINICIO"]
            fin = mov["oferta"]["HORAFIN"]
            key = (aula_codigo, dia)
            if key not in ocupadas:
                ocupadas[key] = []
            ocupadas[key].append((ini, fin))
    return ocupadas

def seleccionar_configuracion():
    archivos = listar_configuraciones()
    if not archivos:
        print("No hay reorganizaciones guardadas.")
        return nueva_configuracion()
    print("Reorganizaciones disponibles:")
    for i, archivo in enumerate(archivos):
        print(f"{i+1}. {archivo}")
    idx = int(input("Seleccione una reorganización: ")) - 1
    nombre = archivos[idx]
    config = cargar_configuracion(nombre)
    return nombre, config

def liberar_y_mover_aulas(config, connection, campus_code, pabellon_codes, ano, semestre, codigos_a_liberar):
    aula_logic = AulaLogic(connection)
    libres = aula_logic.fetch_libres(campus_code, pabellon_codes, ano, semestre)
    ocupaciones_ficticias = obtener_ocupaciones_ficticias(config)
    codigos = codigos_a_liberar
    for codigo_aula in codigos:
        ocupaciones = get_ocupaciones_aula(connection, codigo_aula, ano, semestre)
        asignaciones = asignar_ofertas_sin_cruce(ocupaciones, libres, codigo_aula, ocupaciones_ficticias)
        config["aulas_liberadas"].append(codigo_aula)
        for item in asignaciones:
            movimiento = {
                "aula_origen": codigo_aula,
                "oferta": item["oferta"],
                "aula_sugerida": item["aula"]
            }
            config["movimientos"].append(movimiento)
            config["sugerencias"].append(movimiento)
            # Actualiza ocupaciones ficticias para siguientes iteraciones
            if item["aula"]:
                aula_codigo, aula_nombre, aula_capacidad = item["aula"]
                key = (aula_codigo, item["oferta"]["CODIGODIA"])
                if key not in ocupaciones_ficticias:
                    ocupaciones_ficticias[key] = []
                ocupaciones_ficticias[key].append(
                    (item["oferta"]["HORAINICIO"], item["oferta"]["HORAFIN"])
                )
        print(f"Movimientos sugeridos para aula {codigo_aula} generados: {len(asignaciones)}")
    return config
# def liberar_y_mover_aulas(config, connection, campus_code, pabellon_codes, ano, semestre):
#     aula_logic = AulaLogic(connection)
#     libres = aula_logic.fetch_libres(campus_code, pabellon_codes, ano, semestre)
#     ocupaciones_ficticias = obtener_ocupaciones_ficticias(config)
#     codigos = input("Ingrese códigos de aula a liberar (separados por coma): ").split(",")
#     codigos = [c.strip() for c in codigos if c.strip()]
#     for codigo_aula in codigos:
#         ocupaciones = get_ocupaciones_aula(connection, codigo_aula, ano, semestre)
#         asignaciones = asignar_ofertas_sin_cruce(ocupaciones, libres, codigo_aula, ocupaciones_ficticias)
#         config["aulas_liberadas"].append(codigo_aula)
#         for item in asignaciones:
#             movimiento = {
#                 "aula_origen": codigo_aula,
#                 "oferta": item["oferta"],
#                 "aula_sugerida": item["aula"]
#             }
#             config["movimientos"].append(movimiento)
#             config["sugerencias"].append(movimiento)
#             # Actualiza ocupaciones ficticias para siguientes iteraciones
#             if item["aula"]:
#                 aula_codigo, aula_nombre, aula_capacidad = item["aula"]
#                 key = (aula_codigo, item["oferta"]["CODIGODIA"])
#                 if key not in ocupaciones_ficticias:
#                     ocupaciones_ficticias[key] = []
#                 ocupaciones_ficticias[key].append(
#                     (item["oferta"]["HORAINICIO"], item["oferta"]["HORAFIN"])
#                 )
#         print(f"Movimientos sugeridos para aula {codigo_aula} generados: {len(asignaciones)}")
#     return config

def reorganizar_aulas_cli(config_name, codigos_a_liberar, campus_code, pabellon_codes, ano, semestre):
    # Carga o crea la configuración
    config_path = os.path.join(CONFIG_DIR, config_name)
    if config_name and os.path.exists(config_path):
        config = cargar_configuracion(config_name)
    else:
        config = {
            "movimientos": [],
            "aulas_liberadas": [],
            "sugerencias": [],
            "aprobados": [],
            "rechazados": []
        }
    connection = create_connection()
    try:
        config = liberar_y_mover_aulas(
            config, connection, campus_code, pabellon_codes, ano, semestre, codigos_a_liberar
        )
        guardar_configuracion(config_name, config)
    finally:
        connection.close()
    print(f"Reorganización guardada en {config_name}")
    
def menu_modificar_oferta(config, connection, campus_code, pabellon_codes, ano, semestre):
    # 1. Listar ofertas movidas
    print("Ofertas movidas en la simulación:")
    for idx, mov in enumerate(config["movimientos"]):
        oferta = mov["oferta"]
        aula_origen = mov["aula_origen"]
        aula_sugerida = mov["aula_sugerida"]
        print(f"{idx+1}. {oferta['NOMBRE_CURSO']} ({oferta['CODIGODIA']} {oferta['HORAINICIO']}-{oferta['HORAFIN']}) | Origen: {aula_origen} | Sugerida: {aula_sugerida}")

    seleccion = int(input("Seleccione el número de la oferta a modificar: ")) - 1
    mov = config["movimientos"][seleccion]
    oferta = mov["oferta"]

    # 2. Pedir pabellones a considerar
    pabellones = input("Ingrese los códigos de pabellón a considerar (separados por coma): ").split(",")
    pabellones = [int(p.strip()) for p in pabellones if p.strip()]

    # 3. Buscar aulas candidatas para ese rango
    from src.logic.aula_logic import AulaLogic
    from src.candidatos_para_oferta import buscar_candidatos
    aula_logic = AulaLogic(connection)
    libres = aula_logic.fetch_libres(campus_code, pabellones, ano, semestre)
    ocupaciones_ficticias = obtener_ocupaciones_ficticias(config)
    candidatos = buscar_candidatos(
        libres,
        oferta['CODIGODIA'],
        oferta['HORAINICIO'],
        oferta['HORAFIN'],
        excluido=mov["aula_origen"],
        capacidad_requerida=oferta.get('CAPACIDADMAXIMA', 0) or 0,
        ocupaciones_ficticias=ocupaciones_ficticias
    )

    # 4. Elegir nueva aula sugerida
    print("Aulas candidatas disponibles:")
    for i, (codigo, nombre, capacidad) in enumerate(candidatos):
        print(f"{i+1}. {codigo} - {nombre} (Cap: {capacidad})")
    idx = int(input("Seleccione el número de aula sugerida (o 0 para dejar sin asignar): "))
    if idx == 0:
        mov["aula_sugerida"] = None
    else:
        mov["aula_sugerida"] = candidatos[idx-1]

    print("Movimiento actualizado en la simulación.")

def main():
    print("¿Desea iniciar una nueva reorganización (N) o cargar una existente (C)?")
    opcion = input("N/C: ").strip().upper()
    if opcion == "N":
        nombre, config = nueva_configuracion()
    else:
        nombre, config = seleccionar_configuracion()

    # Parámetros de campus y periodo (puedes pedirlos por input si lo deseas)
    campus_code = 14
    pabellon_codes = [3, 4]
    ano = '2025'
    semestre = '2'

    connection = create_connection()

    while True:
        print("\nOpciones:")
        print("1. Liberar aulas y mover ofertas")
        print("2. Ver movimientos y sugerencias")
        print("3. Guardar y salir")
        print("4. Modificar una oferta individual")
        op = input("Seleccione opción: ")
        if op == "1":
            codigos_a_liberar = input("Ingrese códigos de aula a liberar (separados por coma): ").split(",")
            codigos_a_liberar = [c.strip() for c in codigos_a_liberar if c.strip()]
            config = liberar_y_mover_aulas(config, connection, campus_code, pabellon_codes, ano, semestre, codigos_a_liberar)
        elif op == "2":
            print(json.dumps(config, indent=2, ensure_ascii=False))
        elif op == "3":
            guardar_configuracion(nombre, config)
            print(f"Configuración guardada en {nombre}")
            break
        elif op == "4":
            menu_modificar_oferta(config, connection, campus_code, pabellon_codes, ano, semestre)

    connection.close()

if __name__ == "__main__":
    main()

