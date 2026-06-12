# EDA del Bronze — Hallazgos para el diseño Silver/Gold

> Análisis exploratorio de los datos **crudos** que la capa bronze descarga de
> datos.gob.ar (`pipeline/assets/bronze.py`). Objetivo: fundamentar las
> transformaciones de **silver (staging dbt)**, el **modelo estrella (gold)** y
> los **chequeos de calidad** que exige la Adenda 2 (ADRs 0013-0015).
>
> - **Fuente del análisis:** snapshots locales en `data/` (mismos bytes que el bronze).
> - **Reproducir:** `notebooks/01_eda_bronze.ipynb` (env `notebooks/environment.yml`).
> - **Alcance:** los **2 datasets que ingesta el bronze**. El convencional
>   `produccin-...-2026.csv` NO es parte del bronze → fuera de scope.
> - **Snapshot perfilado:** descargado el 2026-05-30.

---

## Resumen ejecutivo

| Dataset | Filas | Cols | Grano | PK limpia | Duplicados de grano |
|---|---:|---:|---|---|---:|
| `listado_pozos` | 84.242 | 51 | `idpozo` (well) | ✅ `idpozo` único, sin nulos | 0 |
| `produccion_no_convencional` | 405.996 | 40 | `idpozo, anio, mes` (mensual) | ✅ combinación única | 0 |

Hallazgos que condicionan el diseño:

1. **BOM en el header** (`﻿idpozo`): la primera columna llega contaminada → leer con `utf-8-sig` / limpiar en staging.
2. **`rectificado` es un flag, no un versionado**: solo 694/405.996 filas en `t` y **cero duplicados de grano**. El source ya entrega un único registro por `(idpozo,anio,mes)` con la corrección aplicada → justifica **merge/upsert por grano, último snapshot gana** (ADR-0013), no SCD de la fact.
3. **Columnas constantes / casi vacías**: `habilitado` = `t` siempre, `tipo_de_recurso` = `NO CONVENCIONAL` siempre, `vida_util` 97,9 % nulo, `observaciones` 94,3 % nulo → drop o no promover a gold.
4. **296 `idpozo` huérfanos** (2.704 filas) en producción sin match en `listado_pozos` → el test de integridad referencial debe ser `warn`, no `error`, y `dim_pozo` necesita un miembro "desconocido".
5. **Outliers físicos**: `profundidad` máx 378.939 (imposible en metros), `prod_pet`/`prod_gas` con valores negativos, `coordenadax` con un valor positivo (resto longitudes negativas).

---

## 1. `listado_pozos` (84.242 filas × 51 col)

**Grano:** un registro por pozo. `idpozo` es **único, sin nulos, sin duplicados** → surrogate/natural key confiable para `dim_pozo`.

### Nulos relevantes (% sobre 84.242)

| Columna | % nulo | Lectura |
|---|---:|---|
| `adjiv_fecha_abandono` | 95,1 | Casi vacía → drop |
| `subtipo_reservorio` / `adjiv_subtipo_reservorio` | 94,5 / 94,4 | Casi vacía |
| `fechadeingreso`, `fecha_data` | 81,6 | Mayormente vacías; cuidado al usar como fecha de validez |
| `adjiv_fecha_*_term`, `adjiv_capacidad_perf`, `comp_perf` | ~40 | Atributos de terminación, parciales |
| `tipo_reservorio`, `clasificacion`, `subclasificacion` | 21-25 | Útiles pero con nulos → categoría "SIN DATO" |

### Redundancia de columnas `adjiv_*`
Hay pares casi duplicados: `clasificacion`↔`adjiv_clasificacion`, `tipo_reservorio`↔`adjiv_tipo_reservorio`, `subclasificacion`↔`adjiv_subclasificacion`, `comp_perf`↔`adjiv_comp_perf`. **Silver debe quedarse con una sola versión** (la no prefijada, más poblada) y descartar la `adjiv_*` para no arrastrar columnas espejo a gold.

### Categóricas (buenas para dimensiones)
- `cuenca`: GOLFO SAN JORGE (44.045), NEUQUINA (32.366), CUYANA, AUSTRAL, NOROESTE… + **3 nulos** y categorías de 1-2 filas (ÑIRIHUAU, ARGENTINA NORTE).
- `provincia`: Santa Cruz, Chubut, Neuquén, Mendoza, Rio Negro… (8 con volumen + colas chicas como "Estado Nacional").
- `tipo_reservorio`: CONVENCIONAL (57.690), NO CONVENCIONAL (4.633), SIN RESERVORIO, + 21.518 nulos.
- `gasplus`: `no` (83.136) / `si` (1.106) → booleano.

### Numéricas / outliers
| Columna | min | max | mean | Observación |
|---|---:|---:|---:|---|
| `profundidad` | 0 | **378.939** | 1.698 | Máx imposible en m; hay ceros → outlier/centinela |
| `coordenadax` (long) | -72,11 | **55,38** | -68,40 | 1 valor positivo fuera de Argentina (resto < 0) |
| `coordenaday` (lat) | -69,42 | -22,00 | -42,36 | Coherente (todo negativo) |
| `pet_inicial` | 0 | 1.912.394 | 16.967 | Cola larga |
| `gas_inicial` | 0 | 7.901.910 | 11.531 | Cola larga |

---

## 2. `produccion_no_convencional` (405.996 filas × 40 col)

**Grano:** `(idpozo, anio, mes)` → **405.996 combinaciones únicas, 0 duplicados**. Es la **fact table candidata** (producción mensual por pozo).

- `anio`: 2006–2026. `mes`: 1–12, distribución pareja (~32-36k c/u).

### `rectificado` — clave para el tipo de carga (ADR-0013)
```
rectificado:  f = 405.302   t = 694      (filas en grano duplicado = 0)
```
La fuente **ya consolida** un único registro por grano; `rectificado=t` solo marca el 0,17 % corregido retroactivamente. **Implicancia:** la fact se carga con **MERGE/upsert sobre `(idpozo,anio,mes)`**, donde el último snapshot bronze sobrescribe el registro previo. No hace falta versionar la fact (no es SCD); basta con idempotencia por grano. `rectificado` se conserva como atributo de la fact para auditoría.

### Columnas constantes / vacías → no promover a gold
| Columna | Valor | Acción |
|---|---|---|
| `habilitado` | `t` en el 100 % | Drop (sin varianza hoy) o filtro implícito |
| `tipo_de_recurso` | `NO CONVENCIONAL` 100 % | Drop (redundante con el dataset) |
| `vida_util` | 97,9 % nulo | Drop |
| `observaciones` | 94,3 % nulo | Drop (texto libre) |

### Categóricas (dimensiones / atributos)
- `tipoestado` (12+ valores): Extracción Efectiva (335.603), Parado Transitoriamente, En Estudio, Abandonado… → `dim_estado_pozo` o atributo de la fact.
- `tipopozo`: Gasífero (221.257), Petrolífero (156.071), Otro tipo… + 605 nulos.
- `tipoextraccion`: Surgencia Natural (261.982), Plunger Lift, Bombeo Mecánico… + 605 nulos.
- `sub_tipo_recurso`: SHALE (213.916) / TIGHT (191.640) + 440 nulos.
- `cuenca`/`provincia`: dominadas por NEUQUINA / Neuquén (esperable en no convencional).

### Numéricas / outliers (medidas de la fact)
| Columna | min | max | mean | p99 | Ceros | Negativos |
|---|---:|---:|---:|---:|---:|---:|
| `prod_pet` | **-0,001** | 26.593 | 323 | 4.805 | 144.047 | 1 |
| `prod_gas` | **-12,267** | 29.130 | 628 | 8.709 | 83.800 | 2 |
| `prod_agua` | 0 | 34.793 | 182 | 2.991 | 122.426 | 0 |
| `iny_agua` | 0 | 70.279 | 25 | 0 | 405.430 | 0 |
| `iny_gas` | 0 | 3.569.000 | 37 | 0 | 405.459 | 0 |
| `tef` | 0 | 79,34 | 21,9 | 31 | 79.171 | 0 |
| `profundidad` | 0 | **378.939** | 3.744 | 6.625 | 5.275 | 0 |

Notas: las inyecciones (`iny_*`) son ~99,9 % ceros (poca señal). Los **negativos** en producción y el **máx de profundidad** son errores de fuente a marcar.

### Integridad referencial `produccion.idpozo → listado_pozos.idpozo`
```
idpozo distintos en produccion : 4.929
idpozo distintos en listado    : 84.242
huérfanos (en prod, sin listado): 296   →  2.704 filas
```
Producción no convencional es un **subconjunto** de pozos, pero **296 pozos no aparecen** en el listado (probable desfase temporal entre snapshots). El test `relationships` debe configurarse como **`warn`** y `dim_pozo` debe incluir un **miembro "DESCONOCIDO"** para no perder esas 2.704 filas de la fact.

---

## 3. Transformaciones propuestas para Silver (staging dbt)

1. **Limpiar BOM** del header (`﻿`) y normalizar nombres a snake_case.
2. **Castear tipos**: `anio`/`mes` → int; `prod_*`/`iny_*`/`tef`/`profundidad` → numeric; `rectificado`/`habilitado`/`gasplus` `t`/`f`/`si`/`no` → boolean; fechas (`fecha_data`, `fechaingreso`) → date.
3. **Descartar columnas espejo** `adjiv_*` en listado y **constantes/vacías** (`habilitado`, `tipo_de_recurso`, `vida_util`, `observaciones`).
4. **Normalizar categóricas** nulas a `'SIN DATO'` (cuenca, provincia, tipo_reservorio, tipopozo, tipoextraccion, sub_tipo_recurso).
5. **Sanear outliers**: marcar (no borrar) `prod_pet/prod_gas < 0` y `profundidad` fuera de rango plausible vía columna de flag de calidad.
6. **Dedupe defensivo** por grano (aunque hoy sea 0) para garantizar idempotencia del MERGE.

## 4. Modelo estrella propuesto para Gold (insumo ADR-0014)

- **`fct_produccion_mensual`** — grano `(idpozo, anio, mes)`. Medidas: `prod_pet`, `prod_gas`, `prod_agua`, `iny_agua`, `iny_gas`, `tef`. Degenerate/atributos: `rectificado`, `tipoestado`. FKs a las dimensiones.
- **`dim_pozo`** (SK desde `idpozo`) — atributos de `listado_pozos`: sigla, formprod, clasificacion, tipo_reservorio, profundidad, gasplus, coordenadas. Incluir miembro **"DESCONOCIDO"** (huérfanos).
- **`dim_empresa`** (SK desde `idempresa`) — `empresa`.
- **`dim_area`** (SK desde `idareayacimiento`/`idareapermisoconcesion`) — yacimiento, concesión.
- **`dim_geografia`** — `cuenca`, `provincia`.
- **`dim_tiempo`** — derivada de `anio`/`mes`.
- **SCD:** la **fact NO necesita versionado** (MERGE por grano, último gana). Para `dim_pozo`, los atributos del pozo (estado, clasificación) pueden cambiar → evaluar **SCD2 solo si** el negocio necesita histórico; por defecto **SCD1 (overwrite)**, dado que el grano de análisis es la producción mensual y el listado es metadata de referencia.

## 5. Chequeos de calidad propuestos (insumo ADR-0015)

| Test dbt | Tabla.columna | Dimensión de calidad | Severidad |
|---|---|---|---|
| `unique` + `not_null` | `dim_pozo.idpozo` | Unicidad / completitud | error |
| `unique` (combo) | `fct_produccion_mensual (idpozo,anio,mes)` | Unicidad / grano | error |
| `not_null` | `fct.*` claves y `prod_*` | Completitud | error |
| `accepted_values` | `mes` ∈ 1..12; `rectificado`,`habilitado` ∈ {t,f} | Validez | error |
| `accepted_values` | `tipopozo`, `tipoestado`, `sub_tipo_recurso` | Validez / conformidad | warn |
| `relationships` | `fct.idpozo → dim_pozo.idpozo` | Integridad / linaje | **warn** (296 huérfanos) |
| rango (`dbt_utils`/custom) | `prod_pet >= 0`, `prod_gas >= 0` | Exactitud | warn |
| rango | `profundidad` plausible (p. ej. ≤ 10.000 m) | Exactitud | warn |
| frescura (`source freshness`) | `fecha_data` / partición bronze | Actualidad | warn |

Cubre ≥ 3 dimensiones (unicidad, completitud, validez, integridad/linaje, exactitud, actualidad) y los resultados deben **persistirse** (no solo asserts en runtime), con consecuencia operativa (bloqueo de promoción o marca de calidad visible), según la Adenda.
