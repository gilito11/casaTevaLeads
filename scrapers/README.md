# Scrapers - Sistema de Captación de Leads

Este directorio contiene los scrapers para portales inmobiliarios y utilidades de filtrado.

## 🚨 Componente Crítico: Filtrado de Particulares

El archivo más importante de este módulo es `utils/particular_filter.py`, que implementa la lógica para **NUNCA scrapear**:

- ❌ Anuncios de inmobiliarias/agencias
- ❌ Particulares que rechacen contacto de inmobiliarias
- ❌ Profesionales del sector inmobiliario

### Uso del Filtro

```python
from scrapers.utils.particular_filter import debe_scrapear

# Ejemplo: anuncio de Fotocasa
anuncio = {
    'nombre': 'Juan Pérez',
    'titulo': 'Piso en venta Lleida centro',
    'descripcion': 'Vendo piso 3 habitaciones por traslado',
    'num_anuncios_activos': 1,
    'badges': []
}

if debe_scrapear(anuncio):
    # ✅ Scrapear este anuncio
    print("Lead válido - scrapear")
else:
    # ❌ Ignorar este anuncio
    print("Lead no válido - ignorar")
```

### Funciones Disponibles

#### `es_profesional(data: dict) -> bool`
Detecta si el anunciante es una inmobiliaria o profesional.

**Criterios:**
- Nombre contiene palabras como: inmobiliaria, agencia, real estate, API, promotora
- Badges: "profesional verificado", "agencia verificada", "pro"
- Más de 3 anuncios activos

#### `permite_inmobiliarias(data: dict) -> bool`
Detecta si el particular rechaza contacto de inmobiliarias.

**Frases de rechazo detectadas:**
- "no inmobiliarias"
- "no agencias"
- "solo particulares"
- "particular a particular"
- "abstenerse inmobiliarias"
- "no intermediarios"
- "solo comprador directo"
- "sin agencias"

#### `debe_scrapear(data: dict) -> bool`
Función principal que decide si scrapear el anuncio.

Retorna `True` solo si:
1. NO es profesional/inmobiliaria
2. El particular SÍ permite contacto

#### `get_razon_rechazo(data: dict) -> Optional[str]`
Útil para logging. Retorna la razón por la que se rechazó un anuncio.

## 🧪 Tests

Los tests están en `tests/test_scrapers/test_particular_filter.py`

Ejecutar tests:
```bash
# Todos los tests
pytest tests/test_scrapers/test_particular_filter.py -v

# Solo tests de es_profesional
pytest tests/test_scrapers/test_particular_filter.py::TestEsProfesional -v

# Con cobertura
pytest tests/test_scrapers/test_particular_filter.py --cov=scrapers.utils.particular_filter
```

**Cobertura de tests:**
- ✅ 20+ tests para `es_profesional()`
- ✅ 20+ tests para `permite_inmobiliarias()`
- ✅ 10+ tests para `debe_scrapear()`
- ✅ Tests de casos edge (campos vacíos, None, tipos incorrectos)
- ✅ Tests de casos reales

## 📋 Estructura de Datos Esperada

```python
{
    # Información del anunciante
    'nombre': str,                    # Nombre del vendedor
    'badges': list[str],              # Badges del usuario
    'num_anuncios_activos': int,      # Cuántos anuncios tiene activos

    # Información del anuncio
    'titulo': str,                    # Título del anuncio
    'descripcion': str,               # Descripción completa

    # Campos adicionales (no usados en filtrado)
    'precio': float,
    'direccion': str,
    'habitaciones': int,
    # ... etc
}
```

## 🎯 Ejemplos Prácticos

### ✅ Casos que SÍ se deben scrapear

```python
# Particular normal
{
    'nombre': 'María García',
    'titulo': 'Piso 3 hab Lleida',
    'descripcion': 'Vendo piso por traslado',
    'num_anuncios_activos': 1
}

# Particular con pocos anuncios
{
    'nombre': 'Juan López',
    'num_anuncios_activos': 2
}
```

### ❌ Casos que NO se deben scrapear

```python
# Inmobiliaria
{
    'nombre': 'Inmobiliaria Casa Bonita',
    'badges': ['agencia verificada']
}

# Particular que rechaza
{
    'nombre': 'Pedro Martínez',
    'descripcion': 'Piso en venta. NO INMOBILIARIAS'
}

# Profesional con muchos anuncios
{
    'nombre': 'Carlos',
    'num_anuncios_activos': 15
}
```

## 🔧 Mantenimiento

Si necesitas añadir nuevas palabras clave o frases de rechazo, edita las constantes en `particular_filter.py`:

- `PALABRAS_PROFESIONAL`: Lista de palabras que identifican profesionales
- `BADGES_PROFESIONAL`: Badges que identifican cuentas profesionales
- `FRASES_RECHAZO`: Frases que indican rechazo de inmobiliarias
- `UMBRAL_ANUNCIOS_PROFESIONAL`: Número de anuncios para considerar profesional (actualmente 3)

## 📊 Métricas Recomendadas

Al integrar en el scraper, recomendamos trackear:

- Total de anuncios procesados
- Anuncios rechazados por ser profesionales
- Anuncios rechazados por rechazo explícito
- Anuncios aceptados y scrapeados
- Tasa de filtrado (% rechazados vs aceptados)
