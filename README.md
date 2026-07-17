# Base de Conocimiento Inteligente de Friovesa

Sistema profesional dividido en dos proyectos internos:

1. **Crawler:** descubre automáticamente las páginas de las tiendas Quito y Guayaquil, sigue toda la paginación y extrae cada ficha pública de WooCommerce.
2. **Generador de conocimiento (`knowledge_builder/`):** toma solamente el catálogo obtenido por el crawler y regenera los documentos Markdown en `knowledge/` para el asistente de IA.

La web es siempre la fuente oficial. Un CSV antiguo es opcional y solo se usa para producir una comparación separada.

Las decisiones de diseño, límites e invariantes están documentados en `ARCHITECTURE.md`.

## Actualización automática en GitHub

El workflow `.github/workflows/actualizar_catalogo.yml` ejecuta pruebas y actualiza el catálogo todos los días a las 03:15 en la zona `America/Guayaquil`. También puede iniciarse manualmente desde **GitHub → Actions → Actualizar catálogo Friovesa → Run workflow**. Si hay cambios, el bot actualiza `output/`, `knowledge/` y `reports/`; los logs de cada ejecución se conservan durante 30 días como artefactos.

## Instalación

Requiere Python 3.10 o posterior.

```powershell
cd C:\Users\dcaso\Downloads\friovesa_catalogo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Actualización completa

```powershell
python actualizar_catalogo.py
```

La actualización normal es incremental. Siempre recorre las páginas de índice de ambas tiendas para detectar altas y bajas, consulta el sitemap oficial para saber qué fichas cambiaron y reutiliza las fichas intactas. Todas las URLs se verifican, incluso cuando se reutiliza la ficha.

Para una auditoría completa:

```powershell
python actualizar_catalogo.py --full
```

Para regenerar solamente los documentos de IA desde el último catálogo:

```powershell
python generar_base_ia.py
```

Opcionalmente:

```powershell
python actualizar_catalogo.py --csv-antiguo "C:\ruta\catalogo_viejo.csv"
```

El CSV no alimenta el catálogo. Solo genera `output/comparacion_csv_antiguo.csv` y exige una columna SKU o código.

## Salidas

- `output/catalogo_quito.csv`
- `output/catalogo_guayaquil.csv`
- `output/catalogo_completo.csv`
- `output/catalogo.json`
- `output/catalogo.md`
- `output/ULTIMO_REPORTE_CAMBIOS.md`
- `output/reportes/cambios_*.md`
- `output/versiones/<fecha_hora>/` con cada ejecución publicada
- `output/historico/<fecha_hora>/` con respaldo previo al reemplazo
- `knowledge/INDICE_GENERAL.md` y documentos por ciudad/categoría
- `logs/actualizacion_*.log`
- `reports/cambios_*.md` y `reports/ULTIMO_REPORTE_CAMBIOS.md`

## Garantías operativas

- No existe una lista fija de categorías ni productos.
- La paginación se sigue por el enlace `next` hasta agotarse.
- El total descubierto se valida contra el total anunciado por la tienda; si no coincide, la ejecución se detiene.
- Las dos ciudades se rastrean y publican por separado.
- Cada ficha conserva su estado HTTP, URL final, errores y campos no publicados como valores vacíos.
- Las variantes se leen desde el JSON oficial embebido por WooCommerce.
- Los cambios usan el ID estable de WooCommerce por ciudad; así una URL modificada se reconoce como modificación.
- Antes de reemplazar salidas se archiva la versión anterior.
- Si falla el descubrimiento, no se reemplaza el catálogo vigente.

## Configuración externa y nuevas marcas

La marca, tiendas, sitemap y parámetros viven en `config/brands/friovesa.yaml`. Para Runpetz, Barfy, KOFI u otra tienda compatible, copie `config/brands/EJEMPLO_NUEVA_MARCA.yaml`, complete sus URLs públicas y seleccione el archivo:

```powershell
$env:CATALOG_CONFIG = "C:\ruta\runpetz.yaml"
python actualizar_catalogo.py
```

Las opciones también admiten variables de entorno: `CATALOG_TIMEOUT`, `CATALOG_RETRIES`, `CATALOG_WORKERS`, `CATALOG_DELAY`, `CATALOG_INCREMENTAL`, `CATALOG_FULL_REFRESH_DAYS` y `CATALOG_USER_AGENT`.

Para diagnóstico existe `--solo-ciudad uio|gye`; no debe utilizarse para publicar una ejecución oficial completa.

## Pruebas automáticas

```powershell
python -m unittest discover -s tests -v
```

Ejecutarlas después de modificar selectores, modelos o lógica de comparación. Una ejecución real también valida que la cantidad descubierta coincida exactamente con la cantidad anunciada en cada tienda.

## Solución de problemas

- **No se reconoce `python`:** instalar Python 3.10+ y marcar “Add Python to PATH”, o invocar la ruta completa del ejecutable.
- **Error de dependencias:** activar `.venv` y ejecutar `python -m pip install -r requirements.txt`.
- **Total descubierto distinto al anunciado:** la estructura o la paginación cambió; revisar el log. El sistema no publica una salida parcial.
- **HTTP 429/5xx:** aumentar `delay_seconds`, reducir `workers` o volver a ejecutar; hay reintentos automáticos.
- **Cambio grande inesperado:** revisar `reports/ULTIMO_REPORTE_CAMBIOS.md` y comparar con `output/versiones/` antes de usar la versión.
- **Cambió el HTML de WooCommerce:** ejecutar las pruebas, revisar `scraper/product_parser.py` y luego hacer una auditoría con `--full`.
