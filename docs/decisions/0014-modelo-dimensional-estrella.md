# Diseño del modelo estrella: grano, dimensiones y SCD tipo 1

## Contexto y Declaración del Problema

La adenda impone que el warehouse use **modelo estrella** y exige
documentar: **grano de la fact table, dimensiones, surrogate keys donde
aplique, y decisión de SCD** si las dimensiones cambian. El esquema
estrella en sí no es negociable; las decisiones de diseño que sí están
abiertas — y que este ADR compara — son el **grano de la fact** y la
**estrategia de SCD** para las dimensiones que cambian.

La fuente de producción trae una fila por (idpozo, anio, mes) con medidas
de producción e inyección, más atributos denormalizados del pozo, la
empresa y el área. El listado de pozos trae los atributos maestros por
pozo. Atributos del pozo **sí cambian en el tiempo** (estado, tipo de
extracción, clasificación), así que la decisión de SCD es real.

## Diseño del Modelo

- **Fact `fct_produccion_pozo_mes`** — **grano: un pozo × un mes
  calendario**. Medidas: `prod_pet`, `prod_gas`, `prod_agua`, `iny_agua`,
  `iny_gas`, `tef` (tiempo efectivo). FKs surrogate a las dimensiones.
  El estado operativo del pozo en ese período (`tipoestado`,
  `tipoextraccion`), que es un hecho del período y no un atributo lento
  del pozo, se modela en la fact (dimensión degenerada/junk), no en
  `dim_pozo`.
- **`dim_pozo`** — sigla, tipo de pozo, clasificación, profundidad,
  formación, coordenadas.
- **`dim_empresa`** — operadora.
- **`dim_area`** — área de concesión / yacimiento / cuenca / provincia,
  **jerarquía aplanada en una sola dimensión** (evitamos copo de nieve:
  Metabase y los usuarios de BI joinean una sola tabla).
- **`dim_tiempo`** — generada, grano mes, con año/trimestre/mes.
- **Surrogate keys:** hash determinístico vía
  `dbt_utils.generate_surrogate_key` sobre la clave natural; la clave
  natural (`idpozo`, `idempresa`, …) se conserva como atributo. El hash
  determinístico (vs secuencias) mantiene la idempotencia del merge
  ([ADR-0013](0013-tipo-de-carga-incremental-merge.md)): re-procesar no
  cambia las claves.

## Factores de Decisión (SCD)

- Casos de uso reales: BI de producción por período/cuenca/empresa y la
  API de pronóstico — ambos preguntan por el **estado actual** del pozo.
- Complejidad de consulta para usuarios no técnicos en Metabase.
- Idempotencia y simplicidad del merge en cada corrida.
- Posibilidad de reconstruir historia si mañana hiciera falta.

## Opciones Consideradas

- **Opción A — SCD tipo 1 (sobrescribir).** El upsert pisa los atributos
  del pozo con el último valor conocido.
- **Opción B — SCD tipo 2 (versionado con vigencias).** Cada cambio de
  atributo crea una fila nueva con `valid_from`/`valid_to`.
- **Opción C — Snapshots dimensionales (dbt snapshots).** dbt captura
  periódicamente el estado de la dimensión; intermedio entre A y B.

## Resultado de la Decisión

**Opción elegida: A (SCD tipo 1) para `dim_pozo`, `dim_empresa` y
`dim_area`.**

**Por qué:**

- **Ningún caso de uso actual paga el costo de SCD2:** los dashboards y
  la API preguntan "cuánto produjo el pozo X en el período Y" y "qué
  pozos hay hoy". La parte de la historia que sí importa por período —
  el estado operativo del pozo en cada mes — **ya viene en la fact
  fuente y se modela en la fact**, no como SCD: queda historizada sin
  vigencias ni joins por rango.
- **Simplicidad para BI:** SCD2 obliga a cada consulta a filtrar por
  vigencia (`valid_to is null` o join por rango de fechas). Para
  usuarios no técnicos en Metabase eso es una trampa de duplicados;
  SCD1 mantiene 1 fila = 1 pozo.
- **Idempotencia natural:** el upsert por clave natural de SCD1 es
  exactamente el merge del [ADR-0013](0013-tipo-de-carga-incremental-merge.md).
  SCD2 complica el reprocesamiento histórico: re-correr una fecha vieja
  puede fabricar versiones espurias.
- **La historia no se pierde, se difiere:** bronze conserva todos los
  snapshots completos ([ADR-0010](0010-datalake-bronze-s3.md)), así que
  si gobierno o un caso de uso futuro exige SCD2, se reconstruye con un
  backfill (o se activa la opción C, dbt snapshots, de bajo costo de
  adopción). Elegir SCD2 hoy sería pagar complejidad permanente por una
  necesidad hipotética.

### Consecuencias

- **Bueno, porque:** el modelo es el más simple que cumple los casos de
  uso; la doc exigida (grano, dimensiones, SKs, SCD) queda en este ADR y
  en los YAML de dbt (`dbt docs`).
- **Bueno, porque:** merge idempotente y claves estables entre corridas.
- **Malo, porque:** se pierde la trayectoria de los atributos lentos del
  pozo (p. ej. reclasificaciones) en el warehouse; mitigado por los
  snapshots de bronze que permiten reconstruirla.
- **Malo, porque:** si se activara SCD2 más adelante, los dashboards
  existentes deberán revisarse (filtros de vigencia).

### Confirmación

Se verifica con: los modelos `marts/` de dbt con la fact y las cuatro
dimensiones descritas; tests `unique`/`not_null` sobre claves naturales y
surrogate; relaciones fact→dim validadas con tests `relationships`
([ADR-0015](0015-calidad-de-datos-dbt-tests.md)); y `dbt docs` publicando
grano y descripciones de columnas.
