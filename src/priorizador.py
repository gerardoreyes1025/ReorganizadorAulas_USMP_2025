from src.db.connection import create_connection
from src.db.queries import get_ocupaciones_aula
import csv

class Priorizador:
    def __init__(self, connection):
        self.connection = connection
        # Por defecto, todos los cursos son Tier 1 (máxima prioridad)
        self.tabla_priorizacion = {}
    
    def cargar_priorizacion_desde_csv(self, archivo_csv):
        """
        Carga la tabla de priorización desde un archivo CSV
        Formato esperado: codigo_curso, nombre_curso, tier
        """
        try:
            with open(archivo_csv, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    codigo_curso = row['codigo_curso']
                    tier = int(row['tier'])
                    self.tabla_priorizacion[codigo_curso] = {
                        'nombre_curso': row['nombre_curso'],
                        'tier': tier,
                        'peso': 5 - tier  # Tier 1 = peso 4, Tier 2 = peso 3, etc.
                    }
            print(f"Priorización cargada desde {archivo_csv}")
            return True
        except FileNotFoundError:
            print(f"Archivo {archivo_csv} no encontrado. Usando priorización por defecto.")
            return False
    
    def establecer_priorizacion_por_defecto(self, ocupaciones_aula):
        """
        Establece todos los cursos como Tier 1 por defecto
        """
        for ocupacion in ocupaciones_aula:
            codigo_curso = ocupacion.get('CODIGOCURSO', '')
            if codigo_curso and codigo_curso not in self.tabla_priorizacion:
                self.tabla_priorizacion[codigo_curso] = {
                    'nombre_curso': ocupacion.get('NOMBRE_CURSO', ''),
                    'tier': 1,
                    'peso': 4  # Máximo peso para Tier 1
                }
    
    def obtener_prioridad_curso(self, codigo_curso):
        """
        Retorna la prioridad de un curso específico
        """
        if codigo_curso in self.tabla_priorizacion:
            return self.tabla_priorizacion[codigo_curso]
        else:
            # Por defecto, Tier 1 si no está en la tabla
            return {'tier': 1, 'peso': 4, 'nombre_curso': codigo_curso}
    
    def ordenar_ocupaciones_por_prioridad(self, ocupaciones_aula):
        """
        Ordena las ocupaciones de un aula por prioridad (Tier 1 primero)
        """
        ocupaciones_con_prioridad = []
        
        for ocupacion in ocupaciones_aula:
            codigo_curso = ocupacion.get('CODIGOCURSO', '')
            prioridad = self.obtener_prioridad_curso(codigo_curso)
            
            ocupaciones_con_prioridad.append({
                'ocupacion': ocupacion,
                'prioridad': prioridad
            })
        
        # Ordenar por peso (mayor peso primero) y luego por hora de inicio
        ocupaciones_con_prioridad.sort(
            key=lambda x: (x['prioridad']['peso'], x['ocupacion']['HORAINICIO']),
            reverse=True
        )
        
        return ocupaciones_con_prioridad
    
    def exportar_priorizacion_actual(self, archivo_csv='priorizacion_actual.csv'):
        """
        Exporta la tabla de priorización actual a CSV
        """
        with open(archivo_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Codigo_Curso', 'Nombre_Curso', 'Tier', 'Peso'])
            for codigo, info in self.tabla_priorizacion.items():
                writer.writerow([codigo, info['nombre_curso'], info['tier'], info['peso']])
        print(f"Priorización exportada a {archivo_csv}")
    
    def mostrar_estadisticas_priorizacion(self):
        """
        Muestra estadísticas de la tabla de priorización
        """
        if not self.tabla_priorizacion:
            print("No hay cursos en la tabla de priorización.")
            return
        
        print("\n=== ESTADÍSTICAS DE PRIORIZACIÓN ===")
        tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        
        for codigo, info in self.tabla_priorizacion.items():
            tier = info['tier']
            if tier in tier_counts:
                tier_counts[tier] += 1
        
        for tier in sorted(tier_counts.keys()):
            print(f"Tier {tier}: {tier_counts[tier]} cursos")
        
        print(f"Total de cursos: {len(self.tabla_priorizacion)}")

# Función de prueba
def probar_priorizador():
    connection = create_connection()
    priorizador = Priorizador(connection)
    
    # Obtener ocupaciones de un aula de ejemplo
    ocupaciones = get_ocupaciones_aula(connection, '2101105', '2025', '2')
    
    # Establecer priorización por defecto
    priorizador.establecer_priorizacion_por_defecto(ocupaciones)
    
    # Ordenar por prioridad
    ocupaciones_ordenadas = priorizador.ordenar_ocupaciones_por_prioridad(ocupaciones)
    
    print("Ocupaciones ordenadas por prioridad:")
    for item in ocupaciones_ordenadas:
        ocupacion = item['ocupacion']
        prioridad = item['prioridad']
        print(f"Tier {prioridad['tier']} - {ocupacion['CODIGODIA']} {ocupacion['HORAINICIO']}-{ocupacion['HORAFIN']} | {ocupacion.get('NOMBRE_CURSO', '')}")
    
    # Mostrar estadísticas
    priorizador.mostrar_estadisticas_priorizacion()
    
    # Exportar priorización
    priorizador.exportar_priorizacion_actual()
    
    connection.close()

if __name__ == "__main__":
    probar_priorizador() 