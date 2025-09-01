from src.db.connection import create_connection
from src.priorizador import Priorizador
from src.evaluador_movimientos import EvaluadorMovimientos
from src.generador_soluciones import GeneradorSoluciones
import csv
import json
import argparse
from datetime import datetime

class ReorganizadorAutomatico:
    def __init__(self, connection):
        self.connection = connection
        self.priorizador = Priorizador(connection)
        self.evaluador = EvaluadorMovimientos(connection)
        self.generador = GeneradorSoluciones(connection)
    
    def reorganizar_aula(self, codigo_aula, configuracion=None):
        """
        Proceso completo de reorganización para una aula específica
        """
        if configuracion is None:
            configuracion = {
                'campus_code': 14,
                'pabellon_codes': [3, 4],
                'ano': '2025',
                'semestre': '2',
                'archivo_priorizacion': None
            }
        
        print(f"\n{'='*60}")
        print(f"REORGANIZADOR AUTOMÁTICO - AULA {codigo_aula}")
        print(f"{'='*60}")
        print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Configuración: {configuracion}")
        
        # 1. Evaluar movimientos posibles (sin generar solución automática)
        movimientos_posibles = self.evaluador.evaluar_movimientos_aula(
            codigo_aula,
            campus_code=configuracion['campus_code'],
            pabellon_codes=configuracion['pabellon_codes'],
            ano=configuracion['ano'],
            semestre=configuracion['semestre']
        )
        
        # Ahora movimientos_posibles SIEMPRE tendrá elementos (con o sin opciones)
        if not movimientos_posibles:
            print("❌ No se encontraron ocupaciones para evaluar en esta aula.")
            return None
        
        # 2. Generar catálogos de opciones
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        prefijo_archivo = f"catalogo_{codigo_aula}_{timestamp}"
        
        # Catálogo completo con todas las opciones
        self.generador.exportar_catalogo_completo_opciones(
            movimientos_posibles, 
            f"{prefijo_archivo}_completo.csv"
        )
        
        # Catálogo resumido con estadísticas
        self.generador.exportar_catalogo_resumido(
            movimientos_posibles, 
            f"{prefijo_archivo}_resumido.csv"
        )
        
        # 3. Generar solución automática (opcional)
        print(f"\n¿Deseas generar también la solución automática? (s/n): ", end="")
        generar_automatica = input().strip().lower() in ['s', 'si', 'sí', 'y', 'yes']
        
        if generar_automatica:
            solucion = self.generador.generar_solucion_completa(
                codigo_aula,
                campus_code=configuracion['campus_code'],
                pabellon_codes=configuracion['pabellon_codes'],
                ano=configuracion['ano'],
                semestre=configuracion['semestre']
            )
            
            if solucion:
                # Mostrar resultados
                self.generador.mostrar_solucion(solucion)
                
                # Exportar solución automática
                self.generador.exportar_solucion_csv(solucion, f"{prefijo_archivo}_solucion_automatica.csv")
                self.generador.exportar_solucion_json(solucion, f"{prefijo_archivo}_solucion_automatica.json")
                
                print(f"\n✅ Solución automática generada:")
                print(f"   🤖 {prefijo_archivo}_solucion_automatica.csv")
                print(f"   🤖 {prefijo_archivo}_solucion_automatica.json")
                print(f"   ⚠️  Los cursos sin opciones aparecen como '❌ NO HAY AULAS DISPONIBLES'")
            
            return solucion
        else:
            print(f"\n✅ Solo se generaron los catálogos de opciones.")
            return None
    
    def _exportar_catalogo_sin_opciones(self, codigo_aula, archivo_csv):
        """
        Exporta un CSV informativo cuando no se encuentran opciones para un aula
        """
        with open(archivo_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Aula_Origen', 'Estado', 'Mensaje', 'Fecha_Generacion', 'Configuracion'
            ])
            writer.writerow([
                codigo_aula,
                '❌ SIN_OPCIONES_DISPONIBLES',
                'No se encontraron aulas libres que puedan recibir los cursos de esta aula',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Revisar configuración de pabellones, campus, año y semestre'
            ])
        
        print(f"📋 CSV informativo generado: {archivo_csv}")
    
    def reorganizar_multiples_aulas(self, codigos_aulas, configuracion=None):
        """
        Reorganiza múltiples aulas y genera un reporte consolidado
        """
        if configuracion is None:
            configuracion = {
                'campus_code': 14,
                'pabellon_codes': [3, 4],
                'ano': '2025',
                'semestre': '2'
            }
        
        print(f"\n{'='*60}")
        print(f"REORGANIZADOR AUTOMÁTICO - MÚLTIPLES AULAS")
        print(f"{'='*60}")
        print(f"Aulas a procesar: {len(codigos_aulas)}")
        print(f"Aulas: {', '.join(codigos_aulas)}")
        
        resultados = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for i, codigo_aula in enumerate(codigos_aulas, 1):
            print(f"\n--- Procesando aula {i}/{len(codigos_aulas)}: {codigo_aula} ---")
            
            try:
                solucion = self.reorganizar_aula(codigo_aula, configuracion)
                resultados.append({
                    'aula': codigo_aula,
                    'exito': solucion is not None,
                    'solucion': solucion
                })
            except Exception as e:
                print(f"❌ Error procesando aula {codigo_aula}: {str(e)}")
                resultados.append({
                    'aula': codigo_aula,
                    'exito': False,
                    'error': str(e)
                })
        
        # Generar reporte consolidado
        self._generar_reporte_consolidado(resultados, timestamp, configuracion)
        
        return resultados
    
    def _generar_reporte_consolidado(self, resultados, timestamp, configuracion):
        """
        Genera un reporte consolidado de todos los resultados
        """
        archivo_reporte = f"reporte_consolidado_{timestamp}.csv"
        
        with open(archivo_reporte, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Aula', 'Estado', 'Movimientos_Exitosos', 'Conflictos', 'Aulas_Utilizadas',
                'Score_Promedio', 'Porcentaje_Exito', 'Es_Valida', 'Error'
            ])
            
            for resultado in resultados:
                if resultado['exito'] and resultado['solucion']:
                    stats = resultado['solucion']['estadisticas']
                    writer.writerow([
                        resultado['aula'],
                        'EXITOSO',
                        stats['total_movimientos'],
                        stats['total_conflictos'],
                        stats['aulas_utilizadas'],
                        stats['score_promedio'],
                        stats['porcentaje_exito'],
                        'SÍ' if resultado['solucion']['es_valida'] else 'NO',
                        ''
                    ])
                else:
                    writer.writerow([
                        resultado['aula'],
                        'FALLIDO',
                        '', '', '', '', '', '',
                        resultado.get('error', 'Error desconocido')
                    ])
        
        # Mostrar resumen
        exitosos = sum(1 for r in resultados if r['exito'])
        fallidos = len(resultados) - exitosos
        
        print(f"\n{'='*60}")
        print(f"REPORTE CONSOLIDADO")
        print(f"{'='*60}")
        print(f"Total de aulas procesadas: {len(resultados)}")
        print(f"Exitosos: {exitosos}")
        print(f"Fallidos: {fallidos}")
        print(f"Archivo de reporte: {archivo_reporte}")
        
        if exitosos > 0:
            # Calcular estadísticas promedio de las soluciones exitosas
            soluciones_exitosas = [r['solucion'] for r in resultados if r['exito'] and r['solucion']]
            if soluciones_exitosas:
                movimientos_promedio = sum(s['estadisticas']['total_movimientos'] for s in soluciones_exitosas) / len(soluciones_exitosas)
                score_promedio = sum(s['estadisticas']['score_promedio'] for s in soluciones_exitosas) / len(soluciones_exitosas)
                print(f"Movimientos promedio por aula: {movimientos_promedio:.1f}")
                print(f"Score promedio: {score_promedio:.1f}")

def cargar_aulas_desde_csv(archivo_csv):
    """
    Carga códigos de aulas desde un archivo CSV
    """
    aulas = []
    try:
        with open(archivo_csv, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                codigo_aula = row.get('codigo_aula', '').strip()
                if codigo_aula:
                    aulas.append(codigo_aula)
        print(f"Cargadas {len(aulas)} aulas desde {archivo_csv}")
    except FileNotFoundError:
        print(f"Archivo {archivo_csv} no encontrado.")
    except Exception as e:
        print(f"Error leyendo archivo {archivo_csv}: {str(e)}")
    
    return aulas

def main():
    """
    Función principal con interfaz de línea de comandos
    """
    parser = argparse.ArgumentParser(description='Reorganizador Automático de Aulas')
    parser.add_argument('--aula', type=str, help='Código de aula específica a reorganizar')
    parser.add_argument('--aulas-csv', type=str, help='Archivo CSV con códigos de aulas a reorganizar')
    parser.add_argument('--solo-catalogos', action='store_true', help='Generar solo catálogos de opciones (sin solución automática)')
    parser.add_argument('--campus', type=int, default=14, help='Código de campus (default: 14)')
    parser.add_argument('--pabellones', type=str, help='Códigos de pabellones separados por coma (default: todos)')
    parser.add_argument('--ano', type=str, default='2025', help='Año académico (default: 2025)')
    parser.add_argument('--semestre', type=str, default='2', help='Semestre (default: 2)')
    parser.add_argument('--priorizacion', type=str, help='Archivo CSV con tabla de priorización')
    
    args = parser.parse_args()
    
    # Configurar pabellones
    pabellon_codes = None
    if args.pabellones:
        pabellon_codes = [int(p.strip()) for p in args.pabellones.split(',')]
    
    configuracion = {
        'campus_code': args.campus,
        'pabellon_codes': pabellon_codes,
        'ano': args.ano,
        'semestre': args.semestre,
        'archivo_priorizacion': args.priorizacion
    }
    
    connection = create_connection()
    reorganizador = ReorganizadorAutomatico(connection)
    
    try:
        if args.aula:
            if args.solo_catalogos:
                # Generar solo catálogos de opciones
                print(f"\n=== GENERANDO CATÁLOGOS PARA AULA {args.aula} ===")
                movimientos_posibles = reorganizador.evaluador.evaluar_movimientos_aula(
                    args.aula,
                    campus_code=configuracion['campus_code'],
                    pabellon_codes=configuracion['pabellon_codes'],
                    ano=configuracion['ano'],
                    semestre=configuracion['semestre']
                )
                
                # Ahora movimientos_posibles SIEMPRE tendrá elementos (con o sin opciones)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                prefijo_archivo = f"catalogo_{args.aula}_{timestamp}"
                
                reorganizador.generador.exportar_catalogo_completo_opciones(
                    movimientos_posibles, 
                    f"{prefijo_archivo}_completo.csv"
                )
                
                reorganizador.generador.exportar_catalogo_resumido(
                    movimientos_posibles, 
                    f"{prefijo_archivo}_resumido.csv"
                )
                
                print(f"\n✅ Catálogos generados:")
                print(f"   📋 {prefijo_archivo}_completo.csv (TODAS las opciones disponibles)")
                print(f"   📊 {prefijo_archivo}_resumido.csv (Resumen con estadísticas)")
                print(f"   ⚠️  Los cursos sin opciones aparecen como '❌ NO HAY AULAS DISPONIBLES'")
            else:
                # Reorganizar una aula específica
                reorganizador.reorganizar_aula(args.aula, configuracion)
        
        elif args.aulas_csv:
            # Reorganizar múltiples aulas desde CSV
            aulas = cargar_aulas_desde_csv(args.aulas_csv)
            if aulas:
                reorganizador.reorganizar_multiples_aulas(aulas, configuracion)
            else:
                print("No se pudieron cargar aulas desde el archivo CSV.")
        
        else:
            # Modo interactivo
            print("=== REORGANIZADOR AUTOMÁTICO DE AULAS ===")
            print("1. Reorganizar una aula específica")
            print("2. Reorganizar múltiples aulas desde CSV")
            print("3. Generar solo catálogos de opciones (sin solución automática)")
            
            opcion = input("\nSeleccione una opción (1, 2 o 3): ").strip()
            
            if opcion == "1":
                aula = input("Ingrese el código de aula: ").strip()
                if aula:
                    reorganizador.reorganizar_aula(aula, configuracion)
                else:
                    print("Código de aula no válido.")
            
            elif opcion == "2":
                archivo = input("Ingrese el nombre del archivo CSV: ").strip()
                if archivo:
                    aulas = cargar_aulas_desde_csv(archivo)
                    if aulas:
                        reorganizador.reorganizar_multiples_aulas(aulas, configuracion)
                    else:
                        print("No se pudieron cargar aulas desde el archivo.")
                else:
                    print("Nombre de archivo no válido.")
            
            elif opcion == "3":
                aula = input("Ingrese el código de aula: ").strip()
                if aula:
                    # Generar solo catálogos sin solución automática
                    movimientos_posibles = reorganizador.evaluador.evaluar_movimientos_aula(
                        aula, 
                        campus_code=configuracion['campus_code'],
                        pabellon_codes=configuracion['pabellon_codes'],
                        ano=configuracion['ano'],
                        semestre=configuracion['semestre']
                    )
                    
                    # Ahora movimientos_posibles SIEMPRE tendrá elementos (con o sin opciones)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    prefijo_archivo = f"catalogo_{aula}_{timestamp}"
                    
                    reorganizador.generador.exportar_catalogo_completo_opciones(
                        movimientos_posibles, 
                        f"{prefijo_archivo}_completo.csv"
                    )
                    
                    reorganizador.generador.exportar_catalogo_resumido(
                        movimientos_posibles, 
                        f"{prefijo_archivo}_resumido.csv"
                    )
                    
                    print(f"\n✅ Catálogos generados:")
                    print(f"   📋 {prefijo_archivo}_completo.csv (TODAS las opciones disponibles)")
                    print(f"   📊 {prefijo_archivo}_resumido.csv (Resumen con estadísticas)")
                    print(f"   ⚠️  Los cursos sin opciones aparecen como '❌ NO HAY AULAS DISPONIBLES'")
                else:
                    print("Código de aula no válido.")
            
            else:
                print("Opción no válida.")
    
    finally:
        connection.close()

if __name__ == "__main__":
    main() 