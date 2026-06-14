{{ config(
    schema='gold',
    alias='dim_empresa',
    unique_key='sk_empresa',
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

empresas as (
    select distinct on (idempresa)
        md5(idempresa::text) as sk_empresa,
        idempresa,
        empresa,
        fecha_extraccion
    from {{ ref('stg_produccion_no_convencional') }}
    where idempresa is not null
    order by idempresa, fecha_extraccion desc, loaded_at desc
),

unknown_row as (
    select
        md5('__unknown__') as sk_empresa,
        'DESCONOCIDO'::text as idempresa,
        'DESCONOCIDO'::text as empresa,
        null::date as fecha_extraccion
)

select e.*
from empresas e
cross join quality_gate q
where q.blocking_failures = 0

union all

select u.*
from unknown_row u
cross join quality_gate q
where q.blocking_failures = 0
