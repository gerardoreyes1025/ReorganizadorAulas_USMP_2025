from src.db.connection import create_connection
from src.db.queries import get_aula_libre
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
        
        # 1. Generar TODAS las opciones posibles (COMPLETO)
        todas_las_opciones = self._generar_todas_las_opciones(codigo_aula, configuracion)
        
        if todas_las_opciones is None:
                    print("❌ Error al consultar las ocupaciones del aula.")
                    return None

        if not todas_las_opciones:
            print(f"⚠️  El aula {codigo_aula} no tiene cursos ni actividades asignadas para el periodo seleccionado.")
            self._exportar_catalogo_sin_opciones(codigo_aula, f"catalogo_{codigo_aula}_sin_opciones.csv")
            return None
        
        # 2. Generar TODOS los archivos automáticamente
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        prefijo_archivo = f"reorganizacion_{codigo_aula}_{timestamp}"
        
        # Exportar catálogo COMPLETO (todas las opciones)
        self._exportar_catalogo_completo(todas_las_opciones, f"{prefijo_archivo}_completo.csv")
        
        # Generar solución AUTOMÁTICA (selección inteligente sin cruces)
        solucion_automatica = self._generar_solucion_automatica(todas_las_opciones, codigo_aula, configuracion)
        
        if solucion_automatica:
            # Mostrar resultados
            self._mostrar_solucion_automatica(solucion_automatica)
            
            # Exportar solución automática
            self._exportar_solucion_automatica_csv(solucion_automatica, f"{prefijo_archivo}_automatico.csv")
            self._exportar_solucion_json(solucion_automatica, f"{prefijo_archivo}.json")
            
            print(f"\n✅ Proceso completado. Archivos generados:")
            print(f"   📋 {prefijo_archivo}_completo.csv (TODAS las opciones)")
            print(f"   🤖 {prefijo_archivo}_automatico.csv (Solución automática)")
            print(f"   📄 {prefijo_archivo}.json (Solución completa en JSON)")
        
        return solucion_automatica
    
    def _generar_todas_las_opciones(self, codigo_aula, configuracion):
        # """
        # Genera TODAS las opciones posibles para cada curso de un aula (basado en consulta_aulas.py)
        # """
        print(f"🔍 Generando TODAS las opciones para aula {codigo_aula}...")
        
        # Obtener ocupaciones del aula
        try:
            ocupaciones = get_aula_libre(
                self.connection,
                codigo_aula,
                configuracion['ano'],
                configuracion['semestre']
            )
        except Exception as e:
            print(f"❌ Error consultando ocupaciones: {e}")
            return None

        if not ocupaciones:
            print("❌ No se encontraron ocupaciones en esta aula.")
            return []
        
        # Obtener todas las aulas libres
        aulas_libres = self.evaluador.aula_logic.fetch_libres(
            configuracion['campus_code'], 
            configuracion['pabellon_codes'], 
            configuracion['ano'], 
            configuracion['semestre']
        )
        
        todas_las_opciones = []
        
        for ocupacion in ocupaciones:
            curso_opciones = {
                'ocupacion': ocupacion,
                'prioridad': self.priorizador.obtener_prioridad_curso(ocupacion.get('CODIGOCURSO', '')),
                'aulas_candidatas': []
            }
            
            # Buscar aulas candidatas para este curso específico
            dia = ocupacion['CODIGODIA']
            hora_inicio = ocupacion['HORAINICIO']
            hora_fin = ocupacion['HORAFIN']
            capacidad_requerida = int(ocupacion.get('CAPACIDADMAXIMA', 0)) if ocupacion.get('CAPACIDADMAXIMA') else 0
            
            for (aula_codigo, aula_nombre, aula_capacidad), bloques in aulas_libres.items():
                # Filtrar por capacidad
                if capacidad_requerida > 0 and aula_capacidad < capacidad_requerida:
                    continue
                
                # Buscar bloques que cubran completamente el horario del curso
                for bloque in bloques:
                    if (bloque['dia'] == dia and 
                        bloque['inicio'] <= hora_inicio and 
                        bloque['fin'] >= hora_fin):
                        
                        # Calcular score de compatibilidad
                        score = self._calcular_score_compatibilidad(aula_capacidad, capacidad_requerida)
                        
                        curso_opciones['aulas_candidatas'].append({
                            'codigo': aula_codigo,
                            'nombre': aula_nombre,
                            'capacidad': aula_capacidad,
                            'pabellon': aula_codigo[:2] if len(aula_codigo) >= 2 else 'N/A',
                            'score': score,
                            'bloque_libre': {
                                'inicio': bloque['inicio'],
                                'fin': bloque['fin']
                            }
                        })
                        break  # Solo necesitamos un bloque que cubra el horario
            
            # Ordenar por score (mejor primero)
            curso_opciones['aulas_candidatas'].sort(key=lambda x: x['score'], reverse=True)
            
            todas_las_opciones.append(curso_opciones)
        
        print(f"✅ Generadas {len(todas_las_opciones)} opciones de cursos")
        return todas_las_opciones
    
    def _calcular_score_compatibilidad(self, capacidad_aula, capacidad_requerida):
        """
        Calcula el score de compatibilidad entre aula y curso
        """
        if capacidad_requerida == 0:
            return 100  # Si no hay requerimiento específico, score perfecto
        
        diferencia = abs(capacidad_aula - capacidad_requerida)
        if diferencia == 0:
            return 100  # Capacidad exacta
        elif diferencia <= 5:
            return 90   # Muy buena compatibilidad
        elif diferencia <= 10:
            return 80   # Buena compatibilidad
        elif diferencia <= 20:
            return 70   # Compatibilidad aceptable
        else:
            return max(50, 100 - diferencia)  # Penalizar grandes diferencias
    
    def _exportar_catalogo_completo(self, todas_las_opciones, archivo_csv):
        """
        Exporta el catálogo COMPLETO con TODAS las opciones (basado en consulta_aulas.py)
        """
        with open(archivo_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Curso', 'Programa', 'Docente', 'Dia', 'Hora_Inicio', 'Hora_Fin', 'Capacidad_Requerida',
                'Tier', 'Aula_Destino', 'Nombre_Aula', 'Capacidad_Aula', 'Pabellon', 'Score_Compatibilidad',
                'Bloque_Libre_Inicio', 'Bloque_Libre_Fin', 'Estado', 'Ranking'
            ])
            
            for curso_opciones in todas_las_opciones:
                ocupacion = curso_opciones['ocupacion']
                prioridad = curso_opciones['prioridad']
                aulas_candidatas = curso_opciones['aulas_candidatas']
                
                if aulas_candidatas:
                    for i, aula_candidata in enumerate(aulas_candidatas, 1):
                        writer.writerow([
                            ocupacion.get('NOMBRE_CURSO', ''),
                            ocupacion.get('NOMBRE_PROGRAMA', ''),
                            ocupacion.get('NOMBRE_DOCENTE', ''),
                            ocupacion['CODIGODIA'],
                            ocupacion['HORAINICIO'],
                            ocupacion['HORAFIN'],
                            ocupacion.get('CAPACIDADMAXIMA', ''),
                            prioridad['tier'],
                            aula_candidata['codigo'],
                            aula_candidata['nombre'],
                            aula_candidata['capacidad'],
                            aula_candidata['pabellon'],
                            aula_candidata['score'],
                            aula_candidata['bloque_libre']['inicio'],
                            aula_candidata['bloque_libre']['fin'],
                            'DISPONIBLE',
                            f"Opción {i} de {len(aulas_candidatas)}"
                        ])
                else:
                    writer.writerow([
                        ocupacion.get('NOMBRE_CURSO', ''),
                        ocupacion.get('NOMBRE_PROGRAMA', ''),
                        ocupacion.get('NOMBRE_DOCENTE', ''),
                        ocupacion['CODIGODIA'],
                        ocupacion['HORAINICIO'],
                        ocupacion['HORAFIN'],
                        ocupacion.get('CAPACIDADMAXIMA', ''),
                        prioridad['tier'],
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ NO HAY AULAS DISPONIBLES',
                        '❌ SIN_OPCIONES_DISPONIBLES',
                        '❌ 0 OPCIONES'
                    ])
        
        print(f"📋 Catálogo COMPLETO exportado: {archivo_csv}")
    
    def _generar_solucion_automatica(self, todas_las_opciones, codigo_aula, configuracion):
        """
        Genera una solución automática seleccionando la mejor opción para cada curso sin cruces
        """
        print(f"🤖 Generando solución automática para aula {codigo_aula}...")
        
        solucion = {
            'aula_origen': codigo_aula,
            'fecha_generacion': datetime.now().isoformat(),
            'configuracion': configuracion,
            'plan_movimientos': {
                'movimientos': [],
                'conflictos': [],
                'aulas_utilizadas': []
            },
            'estadisticas': {},
            'es_valida': True
        }
        
        # Almacenar horarios ya utilizados para evitar cruces
        horarios_utilizados = set()
        
        # Procesar cada curso en orden de prioridad
        for curso_opciones in todas_las_opciones:
            ocupacion = curso_opciones['ocupacion']
            prioridad = curso_opciones['prioridad']
            aulas_candidatas = curso_opciones['aulas_candidatas']
            
            if aulas_candidatas:
                # Buscar la mejor aula disponible (sin cruces)
                mejor_aula = None
                for aula_candidata in aulas_candidatas:
                    # Crear clave única para el horario
                    horario_key = f"{aula_candidata['codigo']}_{ocupacion['CODIGODIA']}_{ocupacion['HORAINICIO']}_{ocupacion['HORAFIN']}"
                    
                    if horario_key not in horarios_utilizados:
                        mejor_aula = aula_candidata
                        horarios_utilizados.add(horario_key)
                        break
                
                if mejor_aula:
                    # Agregar movimiento exitoso
                    solucion['plan_movimientos']['movimientos'].append({
                        'ocupacion': ocupacion,
                        'prioridad': prioridad,
                        'aula_destino': mejor_aula,
                        'score': mejor_aula['score']
                    })
                    
                    if mejor_aula['codigo'] not in solucion['plan_movimientos']['aulas_utilizadas']:
                        solucion['plan_movimientos']['aulas_utilizadas'].append(mejor_aula['codigo'])
                else:
                    # Agregar como conflicto
                    solucion['plan_movimientos']['conflictos'].append({
                        'ocupacion': ocupacion,
                        'prioridad': prioridad,
                        'tipo': 'TODAS_LAS_AULAS_OCUPADAS'
                    })
            else:
                # Agregar como conflicto
                solucion['plan_movimientos']['conflictos'].append({
                    'ocupacion': ocupacion,
                    'prioridad': prioridad,
                    'tipo': 'SIN_AULAS_DISPONIBLES'
                })
        
        # Calcular estadísticas
        solucion['estadisticas'] = self._calcular_estadisticas_solucion(solucion['plan_movimientos'])
        solucion['es_valida'] = len(solucion['plan_movimientos']['conflictos']) == 0
        
        return solucion
    
    def _calcular_estadisticas_solucion(self, plan_movimientos):
        """
        Calcula estadísticas de la solución
        """
        movimientos = plan_movimientos['movimientos']
        conflictos = plan_movimientos['conflictos']
        
        if not movimientos:
            return {
                'total_movimientos': 0,
                'total_conflictos': len(conflictos),
                'aulas_utilizadas': len(plan_movimientos['aulas_utilizadas']),
                'score_promedio': 0,
                'porcentaje_exito': 0
            }
        
        scores = [mov['score'] for mov in movimientos]
        
        return {
            'total_movimientos': len(movimientos),
            'total_conflictos': len(conflictos),
            'aulas_utilizadas': len(plan_movimientos['aulas_utilizadas']),
            'score_promedio': sum(scores) / len(scores),
            'porcentaje_exito': (len(movimientos) / (len(movimientos) + len(conflictos))) * 100
        }
    
    def _mostrar_solucion_automatica(self, solucion):
        """
        Muestra la solución automática en consola
        """
        print(f"\n{'='*60}")
        print(f"SOLUCIÓN AUTOMÁTICA - AULA {solucion['aula_origen']}")
        print(f"{'='*60}")
        
        stats = solucion['estadisticas']
        print(f"📊 Estadísticas:")
        print(f"   • Movimientos exitosos: {stats['total_movimientos']}")
        print(f"   • Conflictos: {stats['total_conflictos']}")
        print(f"   • Aulas utilizadas: {stats['aulas_utilizadas']}")
        print(f"   • Score promedio: {stats['score_promedio']:.1f}")
        print(f"   • Porcentaje de éxito: {stats['porcentaje_exito']:.1f}%")
        print(f"   • Solución válida: {'SÍ' if solucion['es_valida'] else 'NO'}")
        
        if solucion['plan_movimientos']['movimientos']:
            print(f"\n🔄 Movimientos exitosos:")
            for i, movimiento in enumerate(solucion['plan_movimientos']['movimientos'], 1):
                ocupacion = movimiento['ocupacion']
                aula_destino = movimiento['aula_destino']
                print(f"   {i:2d}. {ocupacion.get('NOMBRE_CURSO', '')[:30]}...")
                print(f"       {ocupacion['CODIGODIA']} {ocupacion['HORAINICIO']}-{ocupacion['HORAFIN']}")
                print(f"       → {aula_destino['codigo']} (Cap: {aula_destino['capacidad']}, Score: {movimiento['score']})")
        
        if solucion['plan_movimientos']['conflictos']:
            print(f"\n⚠️  Conflictos:")
            for i, conflicto in enumerate(solucion['plan_movimientos']['conflictos'], 1):
                ocupacion = conflicto['ocupacion']
                print(f"   {i:2d}. {ocupacion.get('NOMBRE_CURSO', '')[:30]}...")
                print(f"       {ocupacion['CODIGODIA']} {ocupacion['HORAINICIO']}-{ocupacion['HORAFIN']}")
                print(f"       → {conflicto['tipo']}")
    
    def _exportar_solucion_automatica_csv(self, solucion, archivo_csv):
        """
        Exporta la solución automática a CSV
        """
        with open(archivo_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Aula_Origen', 'Aula_Destino', 'Tier', 'Dia', 'Hora_Inicio', 'Hora_Fin',
                'Curso', 'Programa', 'Docente', 'Capacidad_Requerida', 'Capacidad_Destino',
                'Score_Compatibilidad', 'Estado'
            ])
            
            # Exportar movimientos exitosos
            for movimiento in solucion['plan_movimientos']['movimientos']:
                ocupacion = movimiento['ocupacion']
                prioridad = movimiento['prioridad']
                aula_destino = movimiento['aula_destino']
                
                writer.writerow([
                    solucion['aula_origen'],
                    aula_destino['codigo'],
                    prioridad['tier'],
                    ocupacion['CODIGODIA'],
                    ocupacion['HORAINICIO'],
                    ocupacion['HORAFIN'],
                    ocupacion.get('NOMBRE_CURSO', ''),
                    ocupacion.get('NOMBRE_PROGRAMA', ''),
                    ocupacion.get('NOMBRE_DOCENTE', ''),
                    ocupacion.get('CAPACIDADMAXIMA', ''),
                    aula_destino['capacidad'],
                    movimiento['score'],
                    'MOVIMIENTO_EXITOSO'
                ])
            
            # Exportar conflictos
            for conflicto in solucion['plan_movimientos']['conflictos']:
                ocupacion = conflicto['ocupacion']
                prioridad = conflicto['prioridad']
                
                writer.writerow([
                    solucion['aula_origen'],
                    '',
                    prioridad['tier'],
                    ocupacion['CODIGODIA'],
                    ocupacion['HORAINICIO'],
                    ocupacion['HORAFIN'],
                    ocupacion.get('NOMBRE_CURSO', ''),
                    ocupacion.get('NOMBRE_PROGRAMA', ''),
                    ocupacion.get('NOMBRE_DOCENTE', ''),
                    ocupacion.get('CAPACIDADMAXIMA', ''),
                    '',
                    '',
                    f"CONFLICTO_{conflicto['tipo']}"
                ])
        
        print(f"🤖 Solución automática exportada: {archivo_csv}")
    
    def _exportar_solucion_json(self, solucion, archivo_json):
        """
        Exporta la solución a JSON (formato estandarizado)
        """
        # Convertir set a list para serialización JSON
        if 'aulas_utilizadas' in solucion['plan_movimientos']:
            solucion['plan_movimientos']['aulas_utilizadas'] = list(solucion['plan_movimientos']['aulas_utilizadas'])
        
        with open(archivo_json, 'w', encoding='utf-8') as jsonfile:
            json.dump(solucion, jsonfile, indent=2, ensure_ascii=False)
        
        print(f"📄 Solución JSON exportada: {archivo_json}")
    
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
        print(f"⚠️  El sistema evitará cruces entre las aulas procesadas")
        
        resultados = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        prefijo_archivo = f"consolidado_{timestamp}"
        
        # Almacenar movimientos ya generados para evitar cruces
        movimientos_ya_generados = []
        
        for i, codigo_aula in enumerate(codigos_aulas, 1):
            print(f"\n--- Procesando aula {i}/{len(codigos_aulas)}: {codigo_aula} ---")
            
            try:
                # Generar solución normalmente
                solucion = self.generador.generar_solucion_completa(
                    codigo_aula,
                    campus_code=configuracion['campus_code'],
                    pabellon_codes=configuracion['pabellon_codes'],
                    ano=configuracion['ano'],
                    semestre=configuracion['semestre']
                )
                
                if solucion:
                    # Verificar cruces con movimientos ya generados
                    movimientos_sin_cruces = self._verificar_y_filtrar_cruces(solucion, movimientos_ya_generados)
                    
                    if movimientos_sin_cruces:
                        # Actualizar la solución con movimientos sin cruces
                        solucion['plan_movimientos']['movimientos'] = movimientos_sin_cruces
                        solucion['estadisticas'] = self.generador._calcular_estadisticas_solucion(solucion['plan_movimientos'])
                        
                        # Agregar movimientos exitosos a la lista de movimientos ya generados
                        for movimiento in movimientos_sin_cruces:
                            movimientos_ya_generados.append({
                                'aula_origen': codigo_aula,
                                'aula_destino': movimiento['aula_destino']['codigo'],
                                'dia': movimiento['ocupacion']['CODIGODIA'],
                                'hora_inicio': movimiento['ocupacion']['HORAINICIO'],
                                'hora_fin': movimiento['ocupacion']['HORAFIN'],
                                'curso': movimiento['ocupacion'].get('NOMBRE_CURSO', ''),
                                'docente': movimiento['ocupacion'].get('NOMBRE_DOCENTE', '')
                            })
                        
                        resultados.append({
                            'aula': codigo_aula,
                            'exito': True,
                            'solucion': solucion
                        })
                        
                        print(f"✅ Aula {codigo_aula} procesada exitosamente")
                        print(f"   📊 Movimientos exitosos: {len(movimientos_sin_cruces)}")
                        print(f"   ⚠️  Conflictos: {len(solucion['plan_movimientos']['conflictos'])}")
                    else:
                        resultados.append({
                            'aula': codigo_aula,
                            'exito': False,
                            'error': 'Todos los movimientos generan cruces con aulas anteriores',
                            'solucion': None
                        })
                        print(f"❌ Todos los movimientos de aula {codigo_aula} generan cruces")
                else:
                    resultados.append({
                        'aula': codigo_aula,
                        'exito': False,
                        'error': 'No se pudo generar solución',
                        'solucion': None
                    })
                    print(f"❌ No se pudo generar solución para aula {codigo_aula}")
                    
            except Exception as e:
                print(f"❌ Error procesando aula {codigo_aula}: {str(e)}")
                resultados.append({
                    'aula': codigo_aula,
                    'exito': False,
                    'error': str(e),
                    'solucion': None
                })
        
        # Generar archivos consolidados
        self._generar_archivos_consolidados(resultados, prefijo_archivo, configuracion)
        
        # Mostrar resumen final
        self._mostrar_resumen_final(resultados, movimientos_ya_generados)
        
        return resultados
    
    def _verificar_y_filtrar_cruces(self, solucion, movimientos_ya_generados):
        """
        Verifica y filtra los movimientos de una solución para evitar cruces con movimientos ya generados
        """
        movimientos_sin_cruces = []
        
        for movimiento in solucion['plan_movimientos']['movimientos']:
            tiene_cruce = False
            
            # Verificar si este movimiento cruza con algún movimiento ya generado
            for movimiento_existente in movimientos_ya_generados:
                if (movimiento['aula_destino']['codigo'] == movimiento_existente['aula_destino'] and
                    movimiento['ocupacion']['CODIGODIA'] == movimiento_existente['dia'] and
                    self._horarios_se_superponen(
                        movimiento['ocupacion']['HORAINICIO'],
                        movimiento['ocupacion']['HORAFIN'],
                        movimiento_existente['hora_inicio'],
                        movimiento_existente['hora_fin']
                    )):
                    tiene_cruce = True
                    break
            
            if not tiene_cruce:
                movimientos_sin_cruces.append(movimiento)
            else:
                # Agregar como conflicto
                solucion['plan_movimientos']['conflictos'].append({
                    'ocupacion': movimiento['ocupacion'],
                    'prioridad': movimiento['prioridad'],
                    'tipo': 'CRUCE_CON_AULA_ANTERIOR'
                })
        
        return movimientos_sin_cruces
    
    def _mostrar_resumen_final(self, resultados, movimientos_ya_generados):
        """
        Muestra un resumen final del proceso de reorganización múltiple
        """
        print(f"\n{'='*60}")
        print(f"RESUMEN FINAL - REORGANIZACIÓN MÚLTIPLE")
        print(f"{'='*60}")
        
        exitosos = sum(1 for r in resultados if r['exito'])
        fallidos = len(resultados) - exitosos
        total_movimientos = len(movimientos_ya_generados)
        
        print(f"📊 Estadísticas generales:")
        print(f"   • Aulas procesadas: {len(resultados)}")
        print(f"   • Aulas exitosas: {exitosos}")
        print(f"   • Aulas fallidas: {fallidos}")
        print(f"   • Total de movimientos generados: {total_movimientos}")
        
        if total_movimientos > 0:
            print(f"\n🔄 Movimientos generados (sin cruces):")
            for i, movimiento in enumerate(movimientos_ya_generados, 1):
                print(f"   {i:2d}. {movimiento['aula_origen']} → {movimiento['aula_destino']} | {movimiento['dia']} {movimiento['hora_inicio']}-{movimiento['hora_fin']} | {movimiento['curso'][:30]}...")
        
        print(f"\n✅ Proceso completado sin cruces entre aulas")
        print(f"⚠️  Todos los movimientos respetan los horarios y aulas ya asignadas")
    

    
    def _generar_archivos_consolidados(self, resultados, prefijo_archivo, configuracion):
        """
        Genera los 3 archivos consolidados: completo, automático y JSON
        """
        # 1. Archivo completo con todas las opciones
        self._exportar_consolidado_completo(resultados, f"{prefijo_archivo}_completo.csv")
        
        # 2. Archivo automático con solo las mejores opciones
        self._exportar_consolidado_automatico(resultados, f"{prefijo_archivo}_automatico.csv")
        
        # 3. Archivo JSON consolidado
        self._exportar_consolidado_json(resultados, f"{prefijo_archivo}.json", configuracion)
        
        print(f"\n✅ Archivos consolidados generados:")
        print(f"   📋 {prefijo_archivo}_completo.csv (TODAS las opciones)")
        print(f"   🤖 {prefijo_archivo}_automatico.csv (Solución automática)")
        print(f"   📄 {prefijo_archivo}.json (Solución completa en JSON)")
    
    def _exportar_consolidado_completo(self, resultados, archivo_csv):
        """
        Exporta el catálogo completo consolidado
        """
        with open(archivo_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Aula_Origen', 'Aula_Destino', 'Tier', 'Dia', 'Hora_Inicio', 'Hora_Fin',
                'Curso', 'Programa', 'Docente', 'Capacidad_Requerida', 'Capacidad_Destino',
                'Score_Compatibilidad', 'Estado'
            ])
            
            for resultado in resultados:
                aula_origen = resultado['aula']
                
                if resultado['exito'] and resultado['solucion']:
                    # Exportar movimientos exitosos
                    for movimiento in resultado['solucion']['plan_movimientos']['movimientos']:
                        ocupacion = movimiento['ocupacion']
                        prioridad = movimiento['prioridad']
                        aula_destino = movimiento['aula_destino']
                        
                        writer.writerow([
                            aula_origen,
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
                    
                    # Exportar conflictos
                    for conflicto in resultado['solucion']['plan_movimientos']['conflictos']:
                        ocupacion = conflicto['ocupacion']
                        prioridad = conflicto['prioridad']
                        
                        writer.writerow([
                            aula_origen,
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
                else:
                    # Exportar error
                    writer.writerow([
                        aula_origen,
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        f"ERROR: {resultado.get('error', 'Error desconocido')}"
                    ])
    
    def _exportar_consolidado_automatico(self, resultados, archivo_csv):
        """
        Exporta la solución automática consolidada
        """
        with open(archivo_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Aula_Origen', 'Aula_Destino', 'Tier', 'Dia', 'Hora_Inicio', 'Hora_Fin',
                'Curso', 'Programa', 'Docente', 'Capacidad_Requerida', 'Capacidad_Destino',
                'Score_Compatibilidad', 'Estado'
            ])
            
            for resultado in resultados:
                aula_origen = resultado['aula']
                
                if resultado['exito'] and resultado['solucion']:
                    for movimiento in resultado['solucion']['plan_movimientos']['movimientos']:
                        ocupacion = movimiento['ocupacion']
                        prioridad = movimiento['prioridad']
                        aula_destino = movimiento['aula_destino']
                        
                        writer.writerow([
                            aula_origen,
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
                    
                    for conflicto in resultado['solucion']['plan_movimientos']['conflictos']:
                        ocupacion = conflicto['ocupacion']
                        prioridad = conflicto['prioridad']
                        
                        writer.writerow([
                            aula_origen,
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
                else:
                    writer.writerow([
                        aula_origen,
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        f"ERROR: {resultado.get('error', 'Error desconocido')}"
                    ])
    
    def _exportar_consolidado_json(self, resultados, archivo_json, configuracion):
        """
        Exporta la solución consolidada en JSON
        """
        solucion_consolidada = {
            'tipo': 'reorganizacion_multiple',
            'fecha_generacion': datetime.now().isoformat(),
            'configuracion': configuracion,
            'aulas_procesadas': len(resultados),
            'resultados': []
        }
        
        for resultado in resultados:
            resultado_json = {
                'aula_origen': resultado['aula'],
                'exito': resultado['exito'],
                'error': resultado.get('error', ''),
                'solucion': resultado.get('solucion', None)
            }
            solucion_consolidada['resultados'].append(resultado_json)
        
        with open(archivo_json, 'w', encoding='utf-8') as jsonfile:
            json.dump(solucion_consolidada, jsonfile, indent=2, ensure_ascii=False)
    
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
    
    def continuar_desde_json(self, archivo_json, codigo_aula, configuracion=None):
        """
        Continúa la reorganización basándose en un JSON existente, actualizando el mismo archivo
        """
        if configuracion is None:
            configuracion = {
                'campus_code': 14,
                'pabellon_codes': [3, 4],
                'ano': '2025',
                'semestre': '2'
            }
        
        print(f"\n{'='*60}")
        print(f"CONTINUAR DESDE JSON - AULA {codigo_aula}")
        print(f"{'='*60}")
        print(f"Archivo JSON: {archivo_json}")
        
        # Cargar JSON existente
        solucion_existente, movimientos_existentes = cargar_json_existente(archivo_json)
        if not solucion_existente:
            return None
        
        print(f"⚠️  Evitando cruces con {len(movimientos_existentes)} movimientos existentes")
        
        # Evaluar movimientos para la nueva aula
        movimientos_posibles = self.evaluador.evaluar_movimientos_aula(
            codigo_aula,
            campus_code=configuracion['campus_code'],
            pabellon_codes=configuracion['pabellon_codes'],
            ano=configuracion['ano'],
            semestre=configuracion['semestre']
        )
        
        if not movimientos_posibles:
            print("❌ No se encontraron movimientos posibles para esta aula.")
            return None
        
        # Filtrar movimientos para evitar cruces con los existentes
        movimientos_filtrados = self._filtrar_cruces_con_existentes(movimientos_posibles, movimientos_existentes)
        
        # Generar solución para la nueva aula
        solucion_nueva = self.generador.generar_solucion_completa(
            codigo_aula,
            campus_code=configuracion['campus_code'],
            pabellon_codes=configuracion['pabellon_codes'],
            ano=configuracion['ano'],
            semestre=configuracion['semestre']
        )
        
        if solucion_nueva:
            # Actualizar el JSON existente con la nueva solución
            self._actualizar_json_existente(archivo_json, solucion_nueva, movimientos_existentes)
            
            print(f"\n✅ JSON actualizado exitosamente:")
            print(f"   📄 {archivo_json} (actualizado con nueva aula)")
            print(f"   🆕 Aula agregada: {codigo_aula}")
            print(f"   📊 Total de movimientos: {len(movimientos_existentes) + len(solucion_nueva['plan_movimientos']['movimientos'])}")
            
            return solucion_nueva
        else:
            print("❌ No se pudo generar solución para la nueva aula.")
            return None
    
    def _filtrar_cruces_con_existentes(self, movimientos_posibles, movimientos_existentes):
        """
        Filtra los movimientos posibles para evitar cruces con movimientos existentes
        """
        movimientos_filtrados = []
        
        for movimiento in movimientos_posibles:
            aulas_candidatas_filtradas = []
            
            for aula_candidata in movimiento['aulas_candidatas']:
                # Verificar si hay cruces con movimientos existentes
                tiene_cruce = False
                
                for movimiento_existente in movimientos_existentes:
                    if (aula_candidata['codigo'] == movimiento_existente['aula_destino'] and
                        movimiento['ocupacion']['CODIGODIA'] == movimiento_existente['dia'] and
                        self._horarios_se_superponen(
                            movimiento['ocupacion']['HORAINICIO'],
                            movimiento['ocupacion']['HORAFIN'],
                            movimiento_existente['hora_inicio'],
                            movimiento_existente['hora_fin']
                        )):
                        tiene_cruce = True
                        break
                
                if not tiene_cruce:
                    aulas_candidatas_filtradas.append(aula_candidata)
            
            if aulas_candidatas_filtradas:
                movimiento_filtrado = movimiento.copy()
                movimiento_filtrado['aulas_candidatas'] = aulas_candidatas_filtradas
                movimiento_filtrado['mejor_opcion'] = aulas_candidatas_filtradas[0] if aulas_candidatas_filtradas else None
                movimientos_filtrados.append(movimiento_filtrado)
            else:
                # Mantener el movimiento pero sin opciones
                movimiento_filtrado = movimiento.copy()
                movimiento_filtrado['aulas_candidatas'] = []
                movimiento_filtrado['mejor_opcion'] = None
                movimientos_filtrados.append(movimiento_filtrado)
        
        return movimientos_filtrados
    
    def _horarios_se_superponen(self, inicio1, fin1, inicio2, fin2):
        """
        Verifica si dos horarios se superponen
        """
        # Convertir a minutos para comparar
        def hora_a_minutos(hora_str):
            h, m = map(int, hora_str.split(':'))
            return h * 60 + m
        
        inicio1_min = hora_a_minutos(inicio1)
        fin1_min = hora_a_minutos(fin1)
        inicio2_min = hora_a_minutos(inicio2)
        fin2_min = hora_a_minutos(fin2)
        
        # Dos horarios se superponen si uno empieza antes de que termine el otro
        return inicio1_min < fin2_min and inicio2_min < fin1_min
    
    def _actualizar_json_existente(self, archivo_json, solucion_nueva, movimientos_existentes):
        """
        Actualiza el JSON existente agregando la nueva solución
        """
        try:
            # Cargar JSON existente
            with open(archivo_json, 'r', encoding='utf-8') as jsonfile:
                json_existente = json.load(jsonfile)
            
            # Agregar la nueva solución
            if 'aulas_adicionales' not in json_existente:
                json_existente['aulas_adicionales'] = []
            
            json_existente['aulas_adicionales'].append({
                'aula_origen': solucion_nueva['aula_origen'],
                'fecha_agregada': datetime.now().isoformat(),
                'solucion': solucion_nueva
            })
            
            # Actualizar estadísticas
            if 'estadisticas_consolidadas' not in json_existente:
                json_existente['estadisticas_consolidadas'] = {
                    'total_aulas_procesadas': 0,
                    'total_movimientos_exitosos': 0,
                    'total_conflictos': 0
                }
            
            json_existente['estadisticas_consolidadas']['total_aulas_procesadas'] += 1
            json_existente['estadisticas_consolidadas']['total_movimientos_exitosos'] += len(solucion_nueva['plan_movimientos']['movimientos'])
            json_existente['estadisticas_consolidadas']['total_conflictos'] += len(solucion_nueva['plan_movimientos']['conflictos'])
            
            # Actualizar fecha de modificación
            json_existente['fecha_ultima_modificacion'] = datetime.now().isoformat()
            
            # Guardar JSON actualizado
            with open(archivo_json, 'w', encoding='utf-8') as jsonfile:
                json.dump(json_existente, jsonfile, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"❌ Error actualizando JSON: {str(e)}")

def solicitar_configuracion():
    """
    Solicita parámetros de configuración con valores por defecto
    """
    print("\n=== CONFIGURACIÓN ===")
    
    # Año
    ano = input("Año académico (default: 2025): ").strip()
    if not ano:
        ano = '2025'
    
    # Semestre
    semestre = input("Semestre (default: 2): ").strip()
    if not semestre:
        semestre = '2'
    
    # Pabellones
    pabellones_input = input("Códigos de pabellones separados por coma (default: 3,4): ").strip()
    if not pabellones_input:
        pabellon_codes = [3, 4]
    else:
        try:
            pabellon_codes = [int(p.strip()) for p in pabellones_input.split(',')]
        except ValueError:
            print("⚠️  Formato inválido, usando pabellones por defecto: 3,4")
            pabellon_codes = [3, 4]
    
    # Campus
    campus_input = input("Código de campus (default: 14): ").strip()
    if not campus_input:
        campus_code = 14
    else:
        try:
            campus_code = int(campus_input)
        except ValueError:
            print("⚠️  Formato inválido, usando campus por defecto: 14")
            campus_code = 14
    
    configuracion = {
        'campus_code': campus_code,
        'pabellon_codes': pabellon_codes,
        'ano': ano,
        'semestre': semestre,
        'archivo_priorizacion': None
    }
    
    print(f"\n✅ Configuración establecida:")
    print(f"   📅 Año: {ano}, Semestre: {semestre}")
    print(f"   🏢 Campus: {campus_code}, Pabellones: {pabellon_codes}")
    
    return configuracion

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

def cargar_json_existente(archivo_json):
    """
    Carga un JSON existente con movimientos ya realizados
    """
    try:
        with open(archivo_json, 'r', encoding='utf-8') as jsonfile:
            solucion_existente = json.load(jsonfile)
        
        print(f"✅ JSON cargado: {archivo_json}")
        print(f"   📋 Aula origen: {solucion_existente.get('aula_origen', 'N/A')}")
        print(f"   📅 Fecha: {solucion_existente.get('fecha_generacion', 'N/A')}")
        
        # Extraer movimientos existentes
        movimientos_existentes = []
        if 'plan_movimientos' in solucion_existente:
            for movimiento in solucion_existente['plan_movimientos'].get('movimientos', []):
                ocupacion = movimiento['ocupacion']
                aula_destino = movimiento['aula_destino']
                
                movimientos_existentes.append({
                    'aula_destino': aula_destino['codigo'],
                    'dia': ocupacion['CODIGODIA'],
                    'hora_inicio': ocupacion['HORAINICIO'],
                    'hora_fin': ocupacion['HORAFIN'],
                    'curso': ocupacion.get('NOMBRE_CURSO', ''),
                    'aula_origen': ocupacion.get('CODIGOAULA', '')
                })
        
        print(f"   📊 Movimientos existentes: {len(movimientos_existentes)}")
        return solucion_existente, movimientos_existentes
        
    except FileNotFoundError:
        print(f"❌ Archivo {archivo_json} no encontrado.")
        return None, []
    except json.JSONDecodeError:
        print(f"❌ Error al leer el archivo JSON {archivo_json}.")
        return None, []
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")
        return None, []



def main():
    """
    Función principal con interfaz de línea de comandos
    """
    parser = argparse.ArgumentParser(description='Reorganizador Automático de Aulas')
    parser.add_argument('--aula', type=str, help='Código de aula específica a reorganizar')
    parser.add_argument('--aulas-csv', type=str, help='Archivo CSV con códigos de aulas a reorganizar')
    parser.add_argument('--solo-catalogos', action='store_true', help='Generar solo catálogos de opciones (sin solución automática)')
    parser.add_argument('--campus', type=int, default=14, help='Código de campus (default: 14)')
    parser.add_argument('--pabellones', type=str, help='Códigos de pabellones separados por coma (default: 3,4)')
    parser.add_argument('--ano', type=str, default='2025', help='Año académico (default: 2025)')
    parser.add_argument('--semestre', type=str, default='2', help='Semestre (default: 2)')
    parser.add_argument('--priorizacion', type=str, help='Archivo CSV con tabla de priorización')
    
    args = parser.parse_args()
    
    # Configurar pabellones (por defecto 3,4)
    if args.pabellones:
        pabellon_codes = [int(p.strip()) for p in args.pabellones.split(',')]
    else:
        pabellon_codes = [3, 4]  # Valores por defecto
    
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
            print("2. Reorganizar múltiples aulas (sin cruces entre aulas)")
            print("3. Continuar en base a un JSON (evitando cruces con movimientos existentes)")
            print("4. Generar solo catálogos de opciones (sin solución automática)")
            
            opcion = input("\nSeleccione una opción (1, 2, 3 o 4): ").strip()
            
            # Solicitar configuración para modo interactivo
            configuracion = solicitar_configuracion()
            
            if opcion == "1":
                aula = input("Ingrese el código de aula: ").strip()
                if aula:
                    reorganizador.reorganizar_aula(aula, configuracion)
                else:
                    print("Código de aula no válido.")
            
            elif opcion == "2":
                print("\n--- REORGANIZACIÓN MÚLTIPLE SIN CRUCES ---")
                aulas_input = input("Ingrese códigos de aulas separados por coma: ").strip()
                if aulas_input:
                    aulas = [a.strip() for a in aulas_input.split(',') if a.strip()]
                    if aulas:
                        print(f"📋 Aulas a procesar: {', '.join(aulas)}")
                        print("⚠️  El sistema evitará cruces entre las aulas procesadas")
                        reorganizador.reorganizar_multiples_aulas(aulas, configuracion)
                    else:
                        print("No se ingresaron aulas válidas.")
                else:
                    print("No se ingresaron aulas.")
            
            elif opcion == "3":
                print("\n--- CONTINUAR DESDE JSON ---")
                archivo_json = input("Ingrese el nombre del archivo JSON: ").strip()
                if archivo_json:
                    aula = input("Ingrese el código de aula a reorganizar: ").strip()
                    if aula:
                        reorganizador.continuar_desde_json(archivo_json, aula, configuracion)
                    else:
                        print("Código de aula no válido.")
                else:
                    print("Nombre de archivo no válido.")
            
            elif opcion == "4":
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