# Reorganizador Automático de Aulas

Este sistema permite reorganizar automáticamente las aulas buscando espacios libres y moviendo cursos según una tabla de priorización.

## Estructura del Sistema

### Archivos Principales

1. **`src/priorizador.py`** - Maneja la tabla de priorización (Tier 1, 2, 3, 4)
2. **`src/evaluador_movimientos.py`** - Evalúa qué cursos se pueden mover a qué aulas
3. **`src/generador_soluciones.py`** - Genera las soluciones de reorganización
4. **`src/reorganizador_automatico.py`** - Orquesta todo el proceso (archivo principal)

### Archivos de Soporte

- **`src/db/connection.py`** - Conexión a la base de datos
- **`src/db/queries.py`** - Consultas SQL
- **`src/logic/aula_logic.py`** - Lógica de aulas

## Cómo Usar

### 1. Reorganizar una Aula Específica

```bash
python src/reorganizador_automatico.py --aula 2101105
```

### 2. Reorganizar Múltiples Aulas desde CSV

```bash
python src/reorganizador_automatico.py --aulas-csv aulas_a_reorganizar.csv
```

### 3. Con Configuración Personalizada

```bash
python src/reorganizador_automatico.py --aula 2101105 --campus 14 --pabellones "3,4" --ano 2025 --semestre 2
```

### 4. Con Tabla de Priorización Personalizada

```bash
python src/reorganizador_automatico.py --aula 2101105 --priorizacion ejemplo_priorizacion.csv
```

### 5. Modo Interactivo

```bash
python src/reorganizador_automatico.py
```

## Tabla de Priorización

### Formato del CSV

```csv
codigo_curso,nombre_curso,tier
2101104,Matemáticas I,1
2101105,Matemáticas II,1
2101107,Química I,2
2101110,Estadística,3
2101118,Compiladores,4
```

### Tiers de Prioridad

- **Tier 1**: Máxima prioridad (peso 4) - Cursos fundamentales
- **Tier 2**: Alta prioridad (peso 3) - Cursos importantes
- **Tier 3**: Media prioridad (peso 2) - Cursos regulares
- **Tier 4**: Baja prioridad (peso 1) - Cursos opcionales

## Archivos de Salida

### Para una Aula Individual

- `reorganizacion_[AULA]_[TIMESTAMP].csv` - Movimientos planificados
- `reorganizacion_[AULA]_[TIMESTAMP].json` - Solución completa en JSON
- `reorganizacion_[AULA]_[TIMESTAMP]_priorizacion.csv` - Tabla de priorización usada

### Para Múltiples Aulas

- `reporte_consolidado_[TIMESTAMP].csv` - Resumen de todas las reorganizaciones

## Ejemplo de Uso Completo

```python
from src.reorganizador_automatico import ReorganizadorAutomatico
from src.db.connection import create_connection

# Conectar a la base de datos
connection = create_connection()

# Crear reorganizador
reorganizador = ReorganizadorAutomatico(connection)

# Configuración
config = {
    'campus_code': 14,
    'pabellon_codes': [3, 4],
    'ano': '2025',
    'semestre': '2'
}

# Reorganizar una aula
solucion = reorganizador.reorganizar_aula('2101105', config)

# Reorganizar múltiples aulas
aulas = ['2101105', '2101104', '2101106']
resultados = reorganizador.reorganizar_multiples_aulas(aulas, config)

connection.close()
```

## Flujo del Sistema

1. **Análisis del Aula Origen**: Obtiene todas las ocupaciones del aula
2. **Priorización**: Ordena los cursos según la tabla de priorización
3. **Búsqueda de Espacios**: Encuentra aulas libres que puedan recibir los cursos
4. **Evaluación de Movimientos**: Calcula scores de compatibilidad
5. **Generación de Solución**: Crea un plan optimizado de movimientos
6. **Validación**: Verifica que la solución sea factible
7. **Exportación**: Genera archivos CSV y JSON con los resultados

## Criterios de Evaluación

### Score de Compatibilidad

- **Capacidad**: Penaliza aulas mucho más grandes que la requerida
- **Pabellón**: Considera proximidad (se puede personalizar)
- **Disponibilidad**: Verifica que el aula esté libre en el horario requerido

### Validación de Solución

- Una solución es válida si al menos el 50% de los movimientos son posibles
- Se consideran conflictos críticos (sin destino) vs. conflictos menores

## Personalización

### Modificar Criterios de Evaluación

Edita `src/evaluador_movimientos.py` en la función `_calcular_score_compatibilidad()`:

```python
def _calcular_score_compatibilidad(self, capacidad_aula, capacidad_requerida, codigo_aula):
    score = 100
    
    # Personalizar criterios aquí
    if capacidad_requerida > 0:
        ratio = capacidad_aula / capacidad_requerida
        if ratio > 2.0:
            score -= 20  # Penalizar aulas muy grandes
        elif ratio < 0.8:
            score -= 30  # Penalizar aulas muy pequeñas
    
    return score
```

### Modificar Validación

Edita `src/generador_soluciones.py` en la función `_validar_solucion()`:

```python
def _validar_solucion(self, plan_movimientos):
    # Personalizar criterios de validación aquí
    conflictos_criticos = sum(1 for c in plan_movimientos['conflictos'] if c['tipo'] == 'SIN_DESTINO')
    total_movimientos = len(plan_movimientos['movimientos'])
    
    # Cambiar el umbral de 0.5 según necesidades
    ratio_exitoso = total_movimientos / (total_movimientos + conflictos_criticos)
    return ratio_exitoso >= 0.7  # 70% de éxito mínimo
```

## Troubleshooting

### Error de Conexión
- Verificar configuración en `src/db/connection.py`
- Asegurar que la base de datos esté disponible

### No Se Encuentran Aulas Libres
- Verificar códigos de pabellones
- Revisar año y semestre
- Comprobar que existan aulas libres en el rango especificado

### Errores en Priorización
- Verificar formato del CSV de priorización
- Asegurar que los códigos de curso existan en la base de datos

## Próximas Mejoras

- [ ] Interfaz gráfica web
- [ ] Algoritmos de optimización más avanzados
- [ ] Consideración de preferencias de docentes
- [ ] Integración con sistemas de gestión académica
- [ ] Análisis de impacto en otros cursos 