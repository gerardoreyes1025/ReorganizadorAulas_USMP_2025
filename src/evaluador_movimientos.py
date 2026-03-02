from src.db.connection import create_connection
from src.db.queries import get_aula_libre
from src.logic.aula_logic import AulaLogic
from src.priorizador import Priorizador
import csv
import sys
import io
from datetime import datetime

# Forzar UTF-8 en la salida estándar para evitar errores en Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

class EvaluadorMovimientos:
    def __init__(self, connection):
        self.connection = connection
        self.aula_logic = AulaLogic(connection)
        self.priorizador = Priorizador(connection)
    
    def evaluar_movimientos_aula(self, codigo_aula_origen, campus_code=14, pabellon_codes=None, aulas_especificas=None, excluir_aulas=None, ano='2025', semestre='2'):
        """
        Evalúa qué movimientos son posibles para liberar un aula específica, permitiendo
        filtrar por posibles aulas de destino y/o excluir aulas particulares.
        """
        print(f"\n=== EVALUANDO MOVIMIENTOS PARA AULA {codigo_aula_origen} ===")
        
        # 1. Obtener ocupaciones del aula origen
        ocupaciones_origen = get_aula_libre(self.connection, codigo_aula_origen, ano, semestre)
        if not ocupaciones_origen:
            print(f"No hay ocupaciones para el aula {codigo_aula_origen}")
            return []
        # Inyectar el codigo de aula origen provisto en cada ocupación encontrada (por si la consulta no lo retorna explícitamente)
        for oc in ocupaciones_origen:
            if 'CODIGOAULA' not in oc or not oc['CODIGOAULA']:
                oc['CODIGOAULA'] = codigo_aula_origen
                
        # 2. Establecer priorización por defecto
        self.priorizador.establecer_priorizacion_por_defecto(ocupaciones_origen)
        
        # 3. Ordenar ocupaciones por prioridad
        ocupaciones_ordenadas = self.priorizador.ordenar_ocupaciones_por_prioridad(ocupaciones_origen)
        
        # 4. Obtener aulas libres
        if pabellon_codes is None:
            pabellon_codes = [3, 4]
        
        aulas_libres = self.aula_logic.fetch_libres(campus_code, pabellon_codes, ano, semestre)
        
        # 5. Evaluar cada ocupación
        movimientos_posibles = []
        
        for item in ocupaciones_ordenadas:
            ocupacion = item['ocupacion']
            prioridad = item['prioridad']
            
            print(f"\n--- Evaluando: Tier {prioridad['tier']} - {ocupacion['CODIGODIA']} {ocupacion['HORAINICIO']}-{ocupacion['HORAFIN']} | {ocupacion.get('NOMBRE_CURSO', '')}")
            
            # Buscar aulas candidatas para esta ocupación
            aulas_candidatas = self._buscar_aulas_candidatas(
                ocupacion, aulas_libres, codigo_aula_origen, aulas_especificas, excluir_aulas
            )
            
            if aulas_candidatas:
                movimientos_posibles.append({
                    'ocupacion': ocupacion,
                    'prioridad': prioridad,
                    'aulas_candidatas': aulas_candidatas,
                    'mejor_opcion': aulas_candidatas[0] if aulas_candidatas else None
                })
                
                print(f"  [OK] Encontradas {len(aulas_candidatas)} aulas candidatas")
                for i, candidata in enumerate(aulas_candidatas[:3], 1):  # Mostrar solo las 3 mejores
                    print(f"    {i}. {candidata['codigo']} - {candidata['nombre']} (Cap: {candidata['capacidad']})")
                if len(aulas_candidatas) > 3:
                    print(f"    ... y {len(aulas_candidatas) - 3} opciones mas")
            else:
                print(f"  [X] NO SE ENCONTRARON AULAS CANDIDATAS")
                print(f"      Este curso NO se puede mover a ninguna aula disponible")
                print(f"      Posibles razones: horario conflictivo, capacidad insuficiente, o no hay aulas libres")
        
        return movimientos_posibles
    
    def _buscar_aulas_candidatas(self, ocupacion, aulas_libres, aula_origen_excluir, aulas_especificas=None, excluir_aulas=None):
        """
        Busca aulas candidatas para una ocupación específica
        """
        candidatas = []
        dia = ocupacion['CODIGODIA']
        hora_inicio = ocupacion['HORAINICIO']
        hora_fin = ocupacion['HORAFIN']
        # Manejar el caso donde CAPACIDADMAXIMA puede ser None
        capacidad_raw = ocupacion.get('CAPACIDADMAXIMA')
        if capacidad_raw is None or capacidad_raw == '':
            capacidad_requerida = 0
        else:
            capacidad_requerida = int(capacidad_raw)
        
        for (aula_codigo, aula_nombre, aula_capacidad), bloques in aulas_libres.items():
            # Excluir el aula origen
            if aula_codigo == aula_origen_excluir:
                continue
            
            # Excluir aulas si se especificaron
            if excluir_aulas and aula_codigo in excluir_aulas:
                continue
                
            # Si se piden aulas específicas, ignorar las demás
            if aulas_especificas and aula_codigo not in aulas_especificas:
                continue
            
            # Verificar capacidad
            if capacidad_requerida > 0 and aula_capacidad < capacidad_requerida:
                continue
            
            # Verificar si está libre en el horario requerido
            for bloque in bloques:
                if (bloque['dia'] == dia and 
                    bloque['inicio'] <= hora_inicio and 
                    bloque['fin'] >= hora_fin):
                    
                    # Calcular score de compatibilidad
                    score = self._calcular_score_compatibilidad(
                        aula_capacidad, capacidad_requerida, aula_codigo
                    )
                    
                    candidatas.append({
                        'codigo': aula_codigo,
                        'nombre': aula_nombre,
                        'capacidad': aula_capacidad,
                        'score': score,
                        'bloque_libre': bloque
                    })
                    break
        
        # Ordenar por score (mayor score = mejor opción)
        candidatas.sort(key=lambda x: x['score'], reverse=True)
        return candidatas
    
    def _calcular_score_compatibilidad(self, capacidad_aula, capacidad_requerida, codigo_aula):
        """
        Calcula un score de compatibilidad para una aula candidata
        """
        score = 100
        
        # Penalizar si la capacidad es mucho mayor que la requerida
        if capacidad_requerida > 0:
            ratio = capacidad_aula / capacidad_requerida
            if ratio > 2.0:  # Más del doble de capacidad
                score -= 20
            elif ratio > 1.5:  # 50% más de capacidad
                score -= 10
        
        # Bonus por pabellón similar (asumiendo que los primeros dígitos son el pabellón)
        # Esto se puede ajustar según la lógica de tu institución
        
        return score
    
    def exportar_evaluacion_movimientos(self, movimientos_posibles, archivo_csv='evaluacion_movimientos.csv', solo_mejor_opcion=True):
        """
        Exporta la evaluacion de movimientos a CSV, permitiendo exportar solo
        la mejor opcion o todas las opciones posibles para revision manual.
        """
        with open(archivo_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Tier', 'Dia', 'Hora_Inicio', 'Hora_Fin', 'Curso', 'Programa', 'Docente', 
                'Capacidad_Requerida', 'Aula_Origen', 'Aula_Destino', 'Capacidad_Destino', 
                'Score_Compatibilidad', 'Estado'
            ])
            
            for movimiento in movimientos_posibles:
                ocupacion = movimiento['ocupacion']
                prioridad = movimiento['prioridad']
                
                if movimiento['aulas_candidatas']:
                    opciones_a_exportar = [movimiento['mejor_opcion']] if solo_mejor_opcion else movimiento['aulas_candidatas']
                    
                    for opcion in opciones_a_exportar:
                        writer.writerow([
                            prioridad['tier'],
                            ocupacion['CODIGODIA'],
                            ocupacion['HORAINICIO'],
                            ocupacion['HORAFIN'],
                            ocupacion.get('NOMBRE_CURSO', ''),
                            ocupacion.get('NOMBRE_PROGRAMA', ''),
                            ocupacion.get('NOMBRE_DOCENTE', ''),
                            ocupacion.get('CAPACIDADMAXIMA', ''),
                            ocupacion.get('CODIGOAULA', ''),
                            opcion['codigo'],
                            opcion['capacidad'],
                            opcion['score'],
                            'MOVIMIENTO_POSIBLE'
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
                        ocupacion.get('CAPACIDADMAXIMA', ''),
                        ocupacion.get('CODIGOAULA', ''),
                        '', '', '',
                        'SIN_DESTINO'
                    ])
        
        print(f"Evaluacion exportada a {archivo_csv}")
    
    def mostrar_resumen_movimientos(self, movimientos_posibles):
        """
        Muestra un resumen de los movimientos posibles
        """
        print(f"\n{'='*60}")
        print(f"📊 RESUMEN DE MOVIMIENTOS")
        print(f"{'='*60}")
        
        total_ocupaciones = len(movimientos_posibles)
        movimientos_posibles_count = sum(1 for m in movimientos_posibles if m['aulas_candidatas'])
        movimientos_imposibles = total_ocupaciones - movimientos_posibles_count
        
        print(f"Total de ocupaciones evaluadas: {total_ocupaciones}")
        print(f"[OK] Movimientos POSIBLES: {movimientos_posibles_count}")
        print(f"[X] Movimientos IMPOSIBLES: {movimientos_imposibles}")
        
        if movimientos_imposibles > 0:
            print(f"\nATENCION: {movimientos_imposibles} cursos NO se pueden mover")
            print(f"   Estos apareceran en el CSV como 'SIN_DESTINO'")
            print(f"   Revisa el catalogo completo para ver los detalles")
        
        if movimientos_posibles_count > 0:
            print(f"\n{movimientos_posibles_count} cursos SI se pueden mover")
            print(f"   Revisa el catalogo completo para ver todas las opciones disponibles")
        
        if movimientos_posibles_count > 0:
            print(f"\nMejores opciones por prioridad:")
            for movimiento in movimientos_posibles:
                if movimiento['aulas_candidatas']:
                    ocupacion = movimiento['ocupacion']
                    prioridad = movimiento['prioridad']
                    mejor_opcion = movimiento['aulas_candidatas'][0]
                    
                    print(f"Tier {prioridad['tier']}: {ocupacion['CODIGODIA']} {ocupacion['HORAINICIO']}-{ocupacion['HORAFIN']} -> {mejor_opcion['codigo']} (Score: {mejor_opcion['score']})")

# Función de prueba
def probar_evaluador():
    connection = create_connection()
    evaluador = EvaluadorMovimientos(connection)
    
    # Evaluar movimientos para un aula específica
    movimientos = evaluador.evaluar_movimientos_aula(
        codigo_aula_origen= '2101101',#'2101105',
        campus_code=14,
        pabellon_codes=[3, 4],  # Solo pabellones 3 y 4
        # aulas_especificas=['2101104', '2101106'],  # Quitar comentario para probar filtro
        excluir_aulas=['2101101', '2106101', '2101105', '2101305', '2101306', '2101307', '2101308'], # Quitar comentario para probar exclusión
        ano='2026',
        semestre='1'
    )
    
    # Mostrar resumen
    evaluador.mostrar_resumen_movimientos(movimientos)
    
    # Exportar evaluación
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 1. Exportar CSV con solo la mejor opción sugerida
    evaluador.exportar_evaluacion_movimientos(
        movimientos, 
        archivo_csv=f'evaluacion_sugerencias_{timestamp}.csv',
        solo_mejor_opcion=True
    )
    
    # 2. Exportar CSV con absolutamente todas las opciones mapeadas
    evaluador.exportar_evaluacion_movimientos(
        movimientos, 
        archivo_csv=f'evaluacion_todas_opciones_{timestamp}.csv',
        solo_mejor_opcion=False
    )
    
    connection.close()

if __name__ == "__main__":
    probar_evaluador() 