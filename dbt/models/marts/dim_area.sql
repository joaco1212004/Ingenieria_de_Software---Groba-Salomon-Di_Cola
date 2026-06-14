{{ config(
    schema='gold',
    alias='dim_area',
    unique_key='sk_area',
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

areas as (
    select distinct on (
        idareapermisoconcesion,
        idareayacimiento,
        idcuenca,
        idprovincia
    )
        md5(concat_ws(
            '|',
            coalesce(idareapermisoconcesion, ''),
            coalesce(idareayacimiento, ''),
            coalesce(idcuenca, ''),
            coalesce(idprovincia, '')
        )) as sk_area,
        idareapermisoconcesion,
        areapermisoconcesion,
        idareayacimiento,
        areayacimiento,
        idcuenca,
        cuenca,
        idprovincia,
        provincia,
        fecha_extraccion
    from {{ ref('stg_produccion_no_convencional') }}
    order by
        idareapermisoconcesion,
        idareayacimiento,
        idcuenca,
        idprovincia,
        fecha_extraccion desc,
        loaded_at desc
),

unknown_row as (
    select
        md5('__unknown__') as sk_area,
        'DESCONOCIDO'::text as idareapermisoconcesion,
        'DESCONOCIDO'::text as areapermisoconcesion,
        'DESCONOCIDO'::text as idareayacimiento,
        'DESCONOCIDO'::text as areayacimiento,
        'DESCONOCIDO'::text as idcuenca,
        'DESCONOCIDO'::text as cuenca,
        'DESCONOCIDO'::text as idprovincia,
        'DESCONOCIDO'::text as provincia,
        null::date as fecha_extraccion
)

select a.*
from areas a
cross join quality_gate q
where q.blocking_failures = 0

union all

select u.*
from unknown_row u
cross join quality_gate q
where q.blocking_failures = 0
