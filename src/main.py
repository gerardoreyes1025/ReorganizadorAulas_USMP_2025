import argparse
from src.db.connection import create_connection
from src.logic.aula_logic import AulaLogic
from src.aula_libre import exportar_aulas_libres
from src.aula_ocupada import exportar_ocupaciones_aula
from src.candidatos_para_oferta import exportar_candidatos_para_oferta
from src.reorganizador import reorganizar_aulas_cli

def main():
    parser = argparse.ArgumentParser(description="Herramienta de gestión de aulas")
    subparsers = parser.add_subparsers(dest="comando")

    # Subcomando para aulas_libres
    parser_libre = subparsers.add_parser("aulas_libres", help="Exportar aulas libres")
    parser_libre.add_argument("--campus", type=int, required=True, help="Código de campus")
    parser_libre.add_argument("--pabellones", nargs='+', type=int, required=True, help="Códigos de pabellones (separados por espacio)")
    parser_libre.add_argument("--ano", type=str, required=True, help="Año académico")
    parser_libre.add_argument("--semestre", type=str, required=True, help="Semestre académico")
    parser_libre.add_argument("--output", type=str, default="aulas_libres.csv", help="Archivo de salida CSV")

    # Subcomando para aula_ocupada
    parser_ocupada = subparsers.add_parser("aula_ocupada", help="Exportar cronograma de un aula")
    parser_ocupada.add_argument("--codigo_aula", type=str, required=True, help="Código del aula")
    parser_ocupada.add_argument("--ano", type=str, required=True, help="Año académico")
    parser_ocupada.add_argument("--semestre", type=str, required=True, help="Semestre académico")
    parser_ocupada.add_argument("--output", type=str, default=None, help="Archivo de salida CSV (opcional)")

    # Subcomando para candidatos_para_oferta
    parser_candidatos = subparsers.add_parser("candidatos", help="Exportar candidatos alternativos y asignación automática")
    parser_candidatos.add_argument("--codigo_aula", type=str, required=True, help="Código del aula de origen")
    parser_candidatos.add_argument("--campus", type=int, required=True, help="Código de campus")
    parser_candidatos.add_argument("--pabellones", nargs='+', type=int, required=True, help="Códigos de pabellones (separados por espacio)")
    parser_candidatos.add_argument("--ano", type=str, required=True, help="Año académico")
    parser_candidatos.add_argument("--semestre", type=str, required=True, help="Semestre académico")
    parser_candidatos.add_argument("--output_candidatos", type=str, default="candidatos_por_oferta.csv", help="Archivo de salida de candidatos")
    parser_candidatos.add_argument("--output_asignacion", type=str, default="asignacion_sin_cruce.csv", help="Archivo de salida de asignación automática")

    # Subcomando para reorganizar aulas
    parser_reorg = subparsers.add_parser("reorganizar", help="Reorganizar aulas y guardar movimientos")
    parser_reorg.add_argument("--config", type=str, required=True, help="Nombre del archivo de configuración (ej: julio5.json)")
    parser_reorg.add_argument("--aulas", nargs='+', type=str, required=True, help="Códigos de aula a liberar (separados por espacio)")
    parser_reorg.add_argument("--campus", type=int, required=True, help="Código de campus")
    parser_reorg.add_argument("--pabellones", nargs='+', type=int, required=True, help="Códigos de pabellones")
    parser_reorg.add_argument("--ano", type=str, required=True, help="Año académico")
    parser_reorg.add_argument("--semestre", type=str, required=True, help="Semestre académico")

    # Subcomando para consulta específica
    parser_consulta = subparsers.add_parser("consulta", help="Consultar aulas libres con filtros específicos")
    parser_consulta.add_argument("--dia", type=str, required=True, help="Día de la semana (ej: VI)")
    parser_consulta.add_argument("--hora_inicio", type=str, required=True, help="Hora de inicio (ej: 08:00)")
    parser_consulta.add_argument("--hora_fin", type=str, required=True, help="Hora de fin (ej: 10:00)")
    parser_consulta.add_argument("--campus", type=int, default=14, help="Código de campus (opcional)")
    parser_consulta.add_argument("--pabellones", nargs='+', type=int, help="Códigos de pabellones (opcional)")
    parser_consulta.add_argument("--capacidad_minima", type=int, help="Capacidad mínima requerida (opcional)")
    parser_consulta.add_argument("--output", type=str, help="Archivo de salida CSV (opcional)")

    args = parser.parse_args()

    if args.comando == "aulas_libres":
        connection = create_connection()
        aula_logic = AulaLogic(connection)
        try:
            exportar_aulas_libres(
                aula_logic,
                campus_code=args.campus,
                pabellon_codes=args.pabellones,
                ano=args.ano,
                semestre=args.semestre,
                output_csv=args.output
            )
        finally:
            connection.close()
    elif args.comando == "aula_ocupada":
        connection = create_connection()
        try:
            exportar_ocupaciones_aula(
                connection,
                codigo_aula=args.codigo_aula,
                ano=args.ano,
                semestre=args.semestre,
                output_csv=args.output
            )
        finally:
            connection.close()
    elif args.comando == "candidatos":
        connection = create_connection()
        try:
            exportar_candidatos_para_oferta(
                connection,
                codigo_aula=args.codigo_aula,
                campus_code=args.campus,
                pabellon_codes=args.pabellones,
                ano=args.ano,
                semestre=args.semestre,
                output_candidatos=args.output_candidatos,
                output_asignacion=args.output_asignacion
            )
        finally:
            connection.close()
    elif args.comando == "reorganizar":
        reorganizar_aulas_cli(
            config_name=args.config,
            codigos_a_liberar=args.aulas,
            campus_code=args.campus,
            pabellon_codes=args.pabellones,
            ano=args.ano,
            semestre=args.semestre
        )
    elif args.comando == "consulta":
        connection = create_connection()
        try:
            from src.consulta_aulas import consultar_aulas_libres
            consultar_aulas_libres(
                connection,
                dia=args.dia,
                hora_inicio=args.hora_inicio,
                hora_fin=args.hora_fin,
                campus_code=args.campus,
                pabellon_codes=args.pabellones,
                capacidad_minima=args.capacidad_minima,
                output_csv=args.output
            )
        finally:
            connection.close()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()