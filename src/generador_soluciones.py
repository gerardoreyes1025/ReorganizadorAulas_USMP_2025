from src.db.connection import create_connection
from src.evaluador_movimientos import EvaluadorMovimientos
import csv
import json
from datetime import datetime

class GeneradorSoluciones:
    def __init__(self, connection):
        self.connection = connection
        self.evaluador = EvaluadorMovimientos(connection)
    
    def generar_solucion_completa(self, codigo_aula_origen, campus_code=14, pabellon_codes=None, ano='2025', semestre='2'):
        """
        Genera una solución completa para liberar un aula
        """
        print(f"\n=== GENERANDO SOLUCIÓN COMPLETA PARA AULA {codigo_aula_origen} ===")
        
        # 1. Evaluar todos los movimientos posibles
        movimientos_posibles = self.evaluador.evaluar_movimientos_aula(
            codigo_aula_origen, campus_code, pabellon_codes, ano, semestre
        )
        
        if not movimientos_posibles:
            print("No se encontraron movimientos posibles.")
            return None
        
        # 2. Generar plan de movimientos
        plan_movimientos = self._generar_plan_movimientos(movimientos_posibles)
        
        # 3. Validar la solución
        es_valida = self._validar_solucion(plan_movimientos)
        
        # 4. Crear solución final
        solucion = {
            'aula_origen': codigo_aula_origen,
            'fecha_generacion': datetime.now().isoformat(),
            'es_valida': es_valida,
            'plan_movimientos': plan_movimientos,
            'estadisticas': self._calcular_estadisticas_solucion(plan_movimientos),
            'configuracion': {
                'campus_code': campus_code,
                'pabellon_codes': pabellon_codes,
                'ano': ano,
                'semestre': semestre
            }
        }
        
        # Convertir set a list para serialización JSON
        if 'aulas_utilizadas' in solucion['plan_movimientos']:
            solucion['plan_movimientos']['aulas_utilizadas'] = list(solucion['plan_movimientos']['aulas_utilizadas'])
        
        return solucion
    
    def _generar_plan_movimientos(self, movimientos_posibles):
        """
        Genera un plan de movimientos optimizado
        """
        plan = {
            'movimientos': [],
            'aulas_utilizadas': set(),
            'conflictos': []
        }
        
        # Ordenar movimientos por prioridad y score
        movimientos_ordenados = sorted(
            movimientos_posibles,
            key=lambda x: (x['prioridad']['peso'], x['mejor_opcion']['score'] if x['mejor_opcion'] else 0),
            reverse=True
        )
        
        for movimiento in movimientos_ordenados:
            if not movimiento['aulas_candidatas']:
                plan['conflictos'].append({
                    'tipo': 'SIN_DESTINO',
                    'ocupacion': movimiento['ocupacion'],
                    'prioridad': movimiento['prioridad']
                })
                continue
            
            # Buscar la mejor aula disponible
            aula_seleccionada = self._seleccionar_mejor_aula_disponible(
                movimiento['aulas_candidatas'], plan['aulas_utilizadas']
            )
            
            if aula_seleccionada:
                plan['movimientos'].append({
                    'ocupacion': movimiento['ocupacion'],
                    'prioridad': movimiento['prioridad'],
                    'aula_origen': movimiento['ocupacion'].get('CODIGOAULA', ''),
                    'aula_destino': aula_seleccionada,
                    'score': aula_seleccionada['score']
                })
                plan['aulas_utilizadas'].add(aula_seleccionada['codigo'])
            else:
                plan['conflictos'].append({
                    'tipo': 'AULA_OCUPADA',
                    'ocupacion': movimiento['ocupacion'],
                    'prioridad': movimiento['prioridad'],
                    'aulas_candidatas': movimiento['aulas_candidatas']
                })
        
        return plan
    
    def _seleccionar_mejor_aula_disponible(self, aulas_candidatas, aulas_utilizadas):
        """
        Selecciona la mejor aula disponible de la lista de candidatas
        """
        for aula in aulas_candidatas:
            if aula['codigo'] not in aulas_utilizadas:
                return aula
        return None
    
    def _validar_solucion(self, plan_movimientos):
        """
        Valida si la solución es factible
        """
        # Una solución es válida si no hay conflictos o si los conflictos son mínimos
        conflictos_criticos = sum(1 for c in plan_movimientos['conflictos'] if c['tipo'] == 'SIN_DESTINO')
        total_movimientos = len(plan_movimientos['movimientos'])
        
        # Si más del 50% de los movimientos son imposibles, la solución no es válida
        if total_movimientos == 0:
            return False
        
        ratio_exitoso = total_movimientos / (total_movimientos + conflictos_criticos)
        return ratio_exitoso >= 0.5
    
    def _calcular_estadisticas_solucion(self, plan_movimientos):
        """
        Calcula estadísticas de la solución
        """
        total_movimientos = len(plan_movimientos['movimientos'])
        total_conflictos = len(plan_movimientos['conflictos'])
        aulas_utilizadas = len(plan_movimientos['aulas_utilizadas'])
        
        # Calcular score promedio
        scores = [m['score'] for m in plan_movimientos['movimientos']]
        score_promedio = sum(scores) / len(scores) if scores else 0
        
        return {
            'total_movimientos': total_movimientos,
            'total_conflictos': total_conflictos,
            'aulas_utilizadas': aulas_utilizadas,
            'score_promedio': round(score_promedio, 2),
            'porcentaje_exito': round((total_movimientos / (total_movimientos + total_conflictos)) * 100, 1) if (total_movimientos + total_conflictos) > 0 else 0
        }
    
    def exportar_solucion_csv(self, solucion, archivo_csv='solucion_reorganizacion.csv'):
        """
        Exporta la solución a CSV
        """
        with open(archivo_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Aula_Origen', 'Aula_Destino', 'Tier', 'Dia', 'Hora_Inicio', 'Hora_Fin',
                'Curso', 'Programa', 'Docente', 'Capacidad_Requerida', 'Capacidad_Destino',
                'Score_Compatibilidad', 'Estado'
            ])
            
            # Escribir movimientos exitosos
            for movimiento in solucion['plan_movimientos']['movimientos']:
                ocupacion = movimiento['ocupacion']
                prioridad = movimiento['prioridad']
                aula_destino = movimiento['aula_destino']
                
                writer.writerow([
                    movimiento['aula_origen'],
                    aula_destino['codigo'],
                    prioridad['tier'],
                    ocupacion['CODIGODIA'],
                    ocupacion['HORAINICIO'],
                    ocupacion['HORAFIN'],
                    ocupacion.get('NOMBRE_CURSO', ''),
                    ocupacion.get('NOMBRE_PROGRAMA', ''),
                    ocupacion.get('NOMBRE_DOCENTE', ''),
                    ocupacion.get('CAPACIDADMAXIMA') or '',
                    aula_destino['capacidad'],
                    movimiento['score'],
                    'MOVIMIENTO_EXITOSO'
                ])
            
            # Escribir conflictos
            for conflicto in solucion['plan_movimientos']['conflictos']:
                ocupacion = conflicto['ocupacion']
                prioridad = conflicto['prioridad']
                
                writer.writerow([
                    ocupacion.get('CODIGOAULA', ''),
                    '',
                    prioridad['tier'],
                    ocupacion['CODIGODIA'],
                    ocupacion['HORAINICIO'],
                    ocupacion['HORAFIN'],
                    ocupacion.get('NOMBRE_CURSO', ''),
                    ocupacion.get('NOMBRE_PROGRAMA', ''),
                    ocupacion.get('NOMBRE_DOCENTE', ''),
                    ocupacion.get('CAPACIDADMAXIMA') or '',
                    '',
                    '',
                    f"CONFLICTO_{conflicto['tipo']}"
                ])
        
        print(f"Solución exportada a {archivo_csv}")
    
    def exportar_solucion_json(self, solucion, archivo_json='solucion_reorganizacion.json'):
        """
        Exporta la solución completa a JSON
        """
        with open(archivo_json, 'w', encoding='utf-8') as jsonfile:
            json.dump(solucion, jsonfile, indent=2, ensure_ascii=False)
        
        print(f"Solución completa exportada a {archivo_json}")
    
    def mostrar_solucion(self, solucion):
        """
        Muestra la solución de manera legible
        """
        print(f"\n=== SOLUCIÓN PARA AULA {solucion['aula_origen']} ===")
        print(f"Fecha de generación: {solucion['fecha_generacion']}")
        print(f"¿Es válida?: {'SÍ' if solucion['es_valida'] else 'NO'}")
        
        stats = solucion['estadisticas']
        print(f"\n--- ESTADÍSTICAS ---")
        print(f"Movimientos exitosos: {stats['total_movimientos']}")
        print(f"Conflictos: {stats['total_conflictos']}")
        print(f"Aulas utilizadas: {stats['aulas_utilizadas']}")
        print(f"Score promedio: {stats['score_promedio']}")
        print(f"Porcentaje de éxito: {stats['porcentaje_exito']}%")
        
        print(f"\n--- MOVIMIENTOS PLANIFICADOS ---")
        for i, movimiento in enumerate(solucion['plan_movimientos']['movimientos'], 1):
            ocupacion = movimiento['ocupacion']
            prioridad = movimiento['prioridad']
            aula_destino = movimiento['aula_destino']
            
            print(f"{i}. Tier {prioridad['tier']}: {ocupacion['CODIGODIA']} {ocupacion['HORAINICIO']}-{ocupacion['HORAFIN']}")
            print(f"   {ocupacion.get('NOMBRE_CURSO', '')} → {aula_destino['codigo']} (Score: {movimiento['score']})")
        
        if solucion['plan_movimientos']['conflictos']:
            print(f"\n--- CONFLICTOS ---")
            for conflicto in solucion['plan_movimientos']['conflictos']:
                ocupacion = conflicto['ocupacion']
                print(f"✗ {ocupacion['CODIGODIA']} {ocupacion['HORAINICIO']}-{ocupacion['HORAFIN']} | {ocupacion.get('NOMBRE_CURSO', '')} - {conflicto['tipo']}")

    def exportar_catalogo_completo_opciones(self, movimientos_posibles, archivo_csv='catalogo_completo_opciones.csv'):
        """
        Exporta un catálogo completo con TODAS las opciones disponibles para cada curso
        Permite selección manual de la mejor opción
        """
        with open(archivo_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Tier', 'Dia', 'Hora_Inicio', 'Hora_Fin', 'Curso', 'Programa', 'Docente', 
                'Capacidad_Requerida', 'Aula_Origen', 'Aula_Destino', 'Capacidad_Destino', 
                'Score_Compatibilidad', 'Pabellon_Destino', 'Estado', 'Ranking_Opción'
            ])
            
            for movimiento in movimientos_posibles:
                ocupacion = movimiento['ocupacion']
                prioridad = movimiento['prioridad']
                aulas_candidatas = movimiento['aulas_candidatas']
                
                if aulas_candidatas:
                    # Escribir todas las opciones disponibles, ordenadas por score
                    for i, aula_candidata in enumerate(aulas_candidatas, 1):
                        pabellon_destino = aula_candidata['codigo'][:2] if len(aula_candidata['codigo']) >= 2 else 'N/A'
                        
                        writer.writerow([
                            prioridad['tier'],
                            ocupacion['CODIGODIA'],
                            ocupacion['HORAINICIO'],
                            ocupacion['HORAFIN'],
                            ocupacion.get('NOMBRE_CURSO', ''),
                            ocupacion.get('NOMBRE_PROGRAMA', ''),
                            ocupacion.get('NOMBRE_DOCENTE', ''),
                            ocupacion.get('CAPACIDADMAXIMA') or '',
                            ocupacion.get('CODIGOAULA', ''),
                            aula_candidata['codigo'],
                            aula_candidata['capacidad'],
                            aula_candidata['score'],
                            pabellon_destino,
                            'DISPONIBLE',
                            f"Opción {i} de {len(aulas_candidatas)}"
                        ])
                else:
                    # Escribir fila para cursos sin opciones - MUY CLARO
                    writer.writerow([
                        prioridad['tier'],
                        ocupacion['CODIGODIA'],
                        ocupacion['HORAINICIO'],
                        ocupacion['HORAFIN'],
                        ocupacion.get('NOMBRE_CURSO', ''),
                        ocupacion.get('NOMBRE_PROGRAMA', ''),
                        ocupacion.get('NOMBRE_DOCENTE', ''),
                        ocupacion.get('CAPACIDADMAXIMA') or '',
                        ocupacion.get('CODIGOAULA', ''),
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ SIN_OPCIONES_DISPONIBLES',
                        '❌ 0 OPCIONES'
                    ])
        
        print(f"Catálogo completo exportado a {archivo_csv}")
        print(f"📋 Este archivo contiene TODAS las opciones disponibles para cada curso.")
        print(f"💡 Puedes revisar manualmente y seleccionar la mejor opción para cada caso.")
        print(f"⚠️  Los cursos sin opciones aparecen como '❌ NO HAY AULAS DISPONIBLES'")
    
    def exportar_catalogo_resumido(self, movimientos_posibles, archivo_csv='catalogo_resumido.csv'):
        """
        Exporta un catálogo resumido con las mejores opciones y estadísticas
        """
        with open(archivo_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Tier', 'Dia', 'Hora_Inicio', 'Hora_Fin', 'Curso', 'Programa', 'Docente', 
                'Capacidad_Requerida', 'Aula_Origen', 'Mejor_Aula_Destino', 'Capacidad_Destino', 
                'Score_Mejor_Opción', 'Total_Opciones', 'Opciones_Score_Alto', 'Opciones_Score_Medio', 'Estado'
            ])
            
            for movimiento in movimientos_posibles:
                ocupacion = movimiento['ocupacion']
                prioridad = movimiento['prioridad']
                aulas_candidatas = movimiento['aulas_candidatas']
                
                if aulas_candidatas:
                    mejor_opcion = aulas_candidatas[0]
                    
                    # Contar opciones por categoría de score
                    opciones_alto = sum(1 for a in aulas_candidatas if a['score'] >= 90)
                    opciones_medio = sum(1 for a in aulas_candidatas if 70 <= a['score'] < 90)
                    
                    writer.writerow([
                        prioridad['tier'],
                        ocupacion['CODIGODIA'],
                        ocupacion['HORAINICIO'],
                        ocupacion['HORAFIN'],
                        ocupacion.get('NOMBRE_CURSO', ''),
                        ocupacion.get('NOMBRE_PROGRAMA', ''),
                        ocupacion.get('NOMBRE_DOCENTE', ''),
                        ocupacion.get('CAPACIDADMAXIMA') or '',
                        ocupacion.get('CODIGOAULA', ''),
                        mejor_opcion['codigo'],
                        mejor_opcion['capacidad'],
                        mejor_opcion['score'],
                        len(aulas_candidatas),
                        opciones_alto,
                        opciones_medio,
                        'MÚLTIPLES_OPCIONES'
                    ])
                else:
                    writer.writerow([
                        prioridad['tier'],
                        ocupacion['CODIGODIA'],
                        ocupacion['HORAINICIO'],
                        ocupacion['HORAFIN'],
                        ocupacion.get('NOMBRE_CURSO', ''),
                        ocupacion.get('NOMBRE_PROGRAMA', ''),
                        ocupacion.get('NOMBRE_DOCENTE', ''),
                        ocupacion.get('CAPACIDADMAXIMA') or '',
                        ocupacion.get('CODIGOAULA', ''),
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ 0 OPCIONES',
                        '❌ 0 OPCIONES',
                        '❌ SIN_OPCIONES_DISPONIBLES'
                    ])
        
        print(f"Catálogo resumido exportado a {archivo_csv}")
        print(f"📊 Este archivo muestra solo la mejor opción por curso y estadísticas.")
        print(f"⚠️  Los cursos sin opciones aparecen como '❌ NO HAY AULAS DISPONIBLES'")

# Función de prueba
def probar_generador():
    connection = create_connection()
    generador = GeneradorSoluciones(connection)
    
    # Generar solución para un aula específica
    solucion = generador.generar_solucion_completa(
        codigo_aula_origen='2101105',
        campus_code=14,
        pabellon_codes=[3, 4],  # Solo pabellones 3 y 4
        ano='2025',
        semestre='2'
    )
    
    if solucion:
        # Mostrar solución
        generador.mostrar_solucion(solucion)
        
        # Exportar soluciones
        generador.exportar_solucion_csv(solucion)
        generador.exportar_solucion_json(solucion)
    else:
        print("No se pudo generar una solución.")
    
    connection.close()

if __name__ == "__main__":
    probar_generador() 