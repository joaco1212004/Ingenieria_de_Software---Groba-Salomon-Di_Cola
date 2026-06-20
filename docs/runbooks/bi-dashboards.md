# Runbook: Catálogo de dashboards de BI sobre el gold (Metabase)

## Propósito y disparador

Este runbook define **qué dashboards construir en Metabase** sobre el modelo
estrella del gold y **con qué campos exactos**, para que un usuario no técnico
explore producción de pozos no convencionales sin escribir SQL
([ADR-0017](../decisions/0017-bi-metabase.md)). Se usa al diseñar o rehacer un
tablero, al onboardear a un nuevo data analyst, o como insumo de la demo.

Es el catálogo de **diseño**. La validación de frescura y publicación de cada
tablero está en [`data-analyst.md`](./data-analyst.md).

## Rol, dueño y prerrequisitos

Dueño: data analyst (consumidor de BI). Para cambios en el modelo coordina con
el analytics engineer.

Prerrequisitos:

- Metabase accesible en `http://<EC2-2>:3000` con la base de datos `warehouse`
  (Postgres en EC2-1) ya registrada como data source.
- Los schemas `gold` y `audit` visibles/sincronizados en Metabase.
- Conocer la `fecha_extraccion` esperada para la entrega o demo.

> ⚠️ **Versión y MCP.** El Metabase desplegado es **v0.51.6**
> (`infra/metabase/docker-compose.metabase.yml`). El **MCP server** de Metabase
> (asistencia de un agente para armar tableros) requiere **v0.62+**, así que hoy
> NO está disponible sin actualizar. Estos dashboards se construyen con el
> **editor visual** point-and-click, que es lo que prioriza el ADR-0017.

## Modelo de datos (esquema gold/audit)

Base `warehouse`. Tablas (definidas en `dbt/models/marts/*.sql` y
`dbt/models/audit/quality_results.sql`):

| Tabla | Rol | Campos clave |
|---|---|---|
| `gold.fct_produccion_pozo_mes` | Fact mensual por pozo | medidas + flags + FKs `sk_*` |
| `gold.dim_pozo` | Dim pozo (SCD1) | `sk_pozo`, `sigla`, `clasificacion`, `tipo_reservorio`, `profundidad`, `latitud`, `longitud` |
| `gold.dim_empresa` | Dim operadora | `sk_empresa`, `empresa` |
| `gold.dim_area` | Dim área (aplanada) | `sk_area`, `cuenca`, `provincia`, `areayacimiento`, `areapermisoconcesion` |
| `gold.dim_tiempo` | Calendario mensual | `sk_tiempo`, `fecha_periodo`, `anio`, `mes`, `trimestre` |
| `audit.quality_results` | Resultados de tests dbt | `layer`, `table_name`, `check_name`, `dimension`, `severity`, `status`, `failed_rows`, `fecha_extraccion` |

**Medidas de la fact:** `prod_pet` [m³], `prod_gas` [10³ m³],
**`prod_gas_m3`** [m³, = `prod_gas*1000`, ya derivada], `prod_agua` [m³],
`iny_agua`, `iny_gas`, `iny_co2`, `iny_otro`, `tef` [días/mes].
**Atributos degenerados:** `tipoestado`, `tipoextraccion`, `tipopozo`,
`sub_tipo_recurso`, `rectificado`.
**Flags de calidad (boolean):** `flag_prod_negativa`, `flag_tef_fuera_rango`,
`flag_profundidad_fuera_rango`, `flag_coordenadas_fuera_rango`.

Los joins fact→dim se hacen por las surrogate keys `sk_pozo`, `sk_empresa`,
`sk_area`, `sk_tiempo`.

---

## Dashboard 1 — Producción (negocio)

**Audiencia:** usuario de negocio / admin. Es el tablero que pide la adenda.
**Fuente:** `gold.fct_produccion_pozo_mes` + dimensiones.

| Card | Visualización | Definición |
|---|---|---|
| Petróleo total | Scalar (number) | `SUM(prod_pet)` m³ del período filtrado |
| Gas total | Scalar | `SUM(prod_gas_m3)` m³ (¡no `prod_gas`!) |
| Agua total | Scalar | `SUM(prod_agua)` m³ |
| Evolución mensual | Line | `SUM(prod_pet)` y `SUM(prod_gas_m3)` por `dim_tiempo.fecha_periodo` |
| Top empresas | Bar (horizontal, top-N) | `SUM(prod_pet)` por `dim_empresa.empresa` |
| Producción por cuenca/provincia | Bar apilada o treemap | `SUM(prod_pet)` por `dim_area.cuenca` → `dim_area.provincia` |
| Mix por tipo | Bar | `SUM(prod_pet)` / `SUM(prod_gas_m3)` por `tipopozo` y `sub_tipo_recurso` |

**Filtros del dashboard:** año/mes (`dim_tiempo.anio`, `dim_tiempo.mes`),
empresa (`dim_empresa.empresa`), cuenca/provincia (`dim_area`), tipo de producto
(petróleo / gas).

---

## Dashboard 2 — Calidad de datos

**Audiencia:** data analyst / analytics engineer. Tablero de calidad visible
(ADR-0017). **Fuente:** `audit.quality_results`.

| Card | Visualización | Definición |
|---|---|---|
| % checks OK (gold) | Scalar / gauge | `% status='pass'` con `layer='gold'` en la última `fecha_extraccion` |
| Fails por dimensión | Bar | `COUNT(*)` con `status='fail'` por `dimension` (completitud, unicidad, validez, integridad_referencial, exactitud) |
| Detalle de fallas | Table | filas `status='fail'`: `table_name`, `check_name`, `severity`, `failed_rows` |
| Tendencia de calidad | Line | `SUM(failed_rows)` por `fecha_extraccion` |

**Filtros:** `layer`, `severity` (error/warn), `dimension`, `fecha_extraccion`.

> Separar `severity='error'` (bloquea promoción) de `warn` (marca de calidad):
> p. ej. los 296 pozos huérfanos viven como `warn` de integridad referencial.

---

## Dashboard 3 — Pozos / performance

**Audiencia:** analista técnico de producción.
**Fuente:** `gold.fct_produccion_pozo_mes` + `gold.dim_pozo`.

| Card | Visualización | Definición |
|---|---|---|
| Ranking de pozos | Table | top pozos por `SUM(prod_pet)` con `dim_pozo.sigla`, `clasificacion`, `tipo_reservorio` |
| TEF promedio | Scalar / line | `AVG(tef)` (días efectivos) por período y por `tipoextraccion` |
| GOR (gas/petróleo) | Bar / line | `SUM(prod_gas_m3) / NULLIF(SUM(prod_pet),0)` por cuenca o por pozo |
| Producción por día efectivo | Bar | `SUM(prod_pet) / NULLIF(SUM(tef),0)` |
| Profundidad vs producción | Scatter | `dim_pozo.profundidad` vs `SUM(prod_pet)` por pozo |

**Filtros:** `dim_pozo.clasificacion`, `tipo_reservorio`, `tipopozo`, empresa,
período.

---

## Dashboard 4 — Geográfico / mapa

**Audiencia:** negocio / exploración espacial.
**Fuente:** `gold.dim_pozo` (+ fact agregada por pozo).

| Card | Visualización | Definición |
|---|---|---|
| Mapa de pozos | Pin / scatter map | pozos por `dim_pozo.latitud` / `longitud`, color por `cuenca`, tamaño por `SUM(prod_pet)`. **Filtrar `flag_coordenadas_fuera_rango = false`** |
| Producción por provincia | Region map o bar | `SUM(prod_pet)` y `SUM(prod_gas_m3)` por `dim_area.provincia` |

**Filtros:** provincia, cuenca, período, tipo de producto.

> Las coordenadas ya vienen corregidas en silver (`latitud`/`longitud`); el
> readme oficial las nombra invertidas, no usar `coordenadax/y` crudas.

---

## Métricas y unidades (reglas de oro)

Documentar y aplicar en **todas** las cards:

1. **Nunca sumar `prod_pet + prod_gas` crudo** — gas viene en 10³ m³, da error de
   1000×. Para mezclar o comparar gas con líquidos usar **`prod_gas_m3`**.
2. **GOR (razón gas/petróleo)** = `SUM(prod_gas_m3) / NULLIF(SUM(prod_pet), 0)`.
3. **Producción por día efectivo** = `SUM(prod_pet) / NULLIF(SUM(tef), 0)`.
4. **Outliers** — ofrecer un filtro que excluya `flag_prod_negativa = true`
   (o mostrarlo aparte); el mapa filtra `flag_coordenadas_fuera_rango = false`.
5. **Huérfanos** — `dim_pozo` incluye un miembro `"DESCONOCIDO"` (296 pozos sin
   match en el listado). No filtrarlo en silencio: distorsiona los totales.

## Métricas nativas de Metabase recomendadas

Definir una sola vez como **Metrics** reutilizables (Admin → Data model) para que
los no técnicos las arrastren sin reescribir fórmulas:

- **Producción Petróleo** = `SUM(prod_pet)` [m³]
- **Producción Gas** = `SUM(prod_gas_m3)` [m³]
- **GOR** = `SUM(prod_gas_m3) / NULLIF(SUM(prod_pet), 0)`
- **TEF promedio** = `AVG(tef)` [días/mes]

## Gobernanza

Una métrica sin definición documentada **no es oficial**: puede usarse para
exploración, pero no para demo o decisión de negocio (alineado con
[`data-analyst.md`](./data-analyst.md)). Como Metabase OSS no versiona los
dashboards como código, este runbook es la fuente de verdad del diseño; la
metadata de Metabase se persiste en Postgres con backup.
