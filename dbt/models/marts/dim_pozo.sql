{{ config(
    schema='gold',
    alias='dim_pozo',
    unique_key='sk_pozo',
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

pozos as (
    select distinct on (idpozo)
        md5(idpozo::text) as sk_pozo,
        idpozo,
        sigla,
        formprod,
        clasificacion,
        subclasificacion,
        tipo_reservorio,
        subtipo_reservorio,
        profundidad,
        gasplus,
        latitud,
        longitud,
        pet_inicial,
        gas_inicial,
        agua_inicial,
        fecha_extraccion
    from {{ ref('stg_listado_pozos') }}
    where idpozo is not null
    order by idpozo, fecha_extraccion desc, loaded_at desc
),

unknown_row as (
    select
        md5('__unknown__') as sk_pozo,
        -1::bigint as idpozo,
        'DESCONOCIDO'::text as sigla,
        'DESCONOCIDO'::text as formprod,
        'SIN DATO'::text as clasificacion,
        'SIN DATO'::text as subclasificacion,
        'SIN DATO'::text as tipo_reservorio,
        'SIN DATO'::text as subtipo_reservorio,
        null::double precision as profundidad,
        null::boolean as gasplus,
        null::double precision as latitud,
        null::double precision as longitud,
        null::double precision as pet_inicial,
        null::double precision as gas_inicial,
        null::double precision as agua_inicial,
        null::date as fecha_extraccion
)

select p.*
from pozos p
cross join quality_gate q
where q.blocking_failures = 0

union all

select u.*
from unknown_row u
cross join quality_gate q
where q.blocking_failures = 0
