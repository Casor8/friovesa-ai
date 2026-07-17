# Arquitectura

## Límites del sistema

- `scraper/`: Proyecto 1. Descubre tiendas y paginación, consulta sitemap, verifica URLs y convierte HTML oficial en modelos.
- `models/`: contrato estable del producto y sus variantes.
- `output/`: serialización reproducible a CSV, JSON y Markdown; versionado de ejecuciones.
- `knowledge_builder/`: Proyecto 2. Solo consume modelos ya extraídos; no rastrea fichas ni contiene datos manuales.
- `knowledge/`: artefactos regenerables para IA. Nunca contiene código fuente.
- `utils/`: comparación de versiones, normalización y logging.
- `config/brands/`: configuración externa por marca y tienda.

## Flujo

1. Cargar configuración YAML de marca.
2. Leer sitemap de productos y sus fechas `lastmod`.
3. Recorrer todas las páginas de cada tienda siguiendo `next`.
4. Validar descubierto = total anunciado.
5. Comparar huella de listado y `lastmod` con la versión previa.
6. Descargar fichas nuevas/modificadas; reutilizar las intactas y verificar sus URLs con `HEAD`.
7. Comparar modelos mediante identidad estable `tienda + product_id`.
8. Archivar versión previa, publicar salidas de forma conjunta y guardar snapshot fechado.
9. Regenerar la base IA y el reporte de cambios.

## Invariantes

- La web es la única fuente de verdad; un CSV antiguo nunca alimenta modelos.
- Quito y Guayaquil usan espacios de identidad separados.
- Una ejecución oficial nunca publica una sola ciudad.
- Una discrepancia de paginación detiene la publicación.
- Un campo ausente permanece vacío o se muestra como “No publicado”.
- `knowledge/` puede borrarse y reconstruirse completamente desde `output/catalogo.json`.
- Los cambios de URL se detectan como modificación cuando el ID de WooCommerce permanece estable.

## Evolución

Los parsers actuales implementan WooCommerce/Dokan. Una marca compatible se incorpora con otro YAML. Si una futura marca usa otra plataforma, se añade un adaptador que produzca el mismo modelo `Product`; generadores, comparación, versionado y documentos no necesitan cambiar.
