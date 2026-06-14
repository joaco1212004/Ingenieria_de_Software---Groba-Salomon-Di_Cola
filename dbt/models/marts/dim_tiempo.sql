{{ config(
    schema='gold',
    alias='dim_tiempo',
    unique_key='sk_tiempo',
    incremental_strategy='delete+insert',
    meta={'dagster': {'group': 'gold'}}
) }}

with quality_gate as (
    select count(*) as blocking_failures
    from {{ ref('quality_results') }}
    where fecha_extraccion = '{{ var("fecha_extraccion") }}'::date
      and severity = 'error'
      and status = 'fail'
),

tiempos as (
    select distinct
        to_char(fecha_periodo::date, 'YYYYMMDD')::integer as sk_tiempo,
        fecha_periodo::date as fecha_periodo,
        anio,
        mes,
        extract(quarter from fecha_periodo::date)::integer as trimestre
    from {{ ref('stg_produccion_no_convencional') }}
    where fecha_periodo is not null
)

select t.*
from tiempos t
cross join quality_gate q
where q.blocking_failures = 0
