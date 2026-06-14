{{ config(
    schema='audit',
    alias='quality_results',
    unique_key=['fecha_extraccion', 'layer', 'table_name', 'check_name'],
    incremental_strategy='delete+insert',
    meta={'dagster': {'group': 'audit'}}
) }}

with checks as (
    select
        '{{ var("fecha_extraccion") }}'::date as fecha_extraccion,
        'silver' as layer,
        'listado_pozos' as table_name,
        'idpozo_not_null' as check_name,
        'completitud' as dimension,
        'error' as severity,
        count(*)::bigint as failed_rows
    from {{ ref('stg_listado_pozos') }}
    where idpozo is null

    union all

    select
        '{{ var("fecha_extraccion") }}'::date,
        'silver',
        'listado_pozos',
        'idpozo_unique',
        'unicidad',
        'error',
        coalesce(sum(n - 1), 0)::bigint
    from (
        select idpozo, count(*) as n
        from {{ ref('stg_listado_pozos') }}
        where idpozo is not null
        group by idpozo
        having count(*) > 1
    ) duplicados

    union all

    select
        '{{ var("fecha_extraccion") }}'::date,
        'silver',
        'produccion_no_convencional',
        'grain_keys_not_null',
        'completitud',
        'error',
        count(*)::bigint
    from {{ ref('stg_produccion_no_convencional') }}
    where idpozo is null or anio is null or mes is null

    union all

    select
        '{{ var("fecha_extraccion") }}'::date,
        'silver',
        'produccion_no_convencional',
        'grain_idpozo_anio_mes_unique',
        'unicidad',
        'error',
        coalesce(sum(n - 1), 0)::bigint
    from (
        select idpozo, anio, mes, count(*) as n
        from {{ ref('stg_produccion_no_convencional') }}
        where idpozo is not null and anio is not null and mes is not null
        group by idpozo, anio, mes
        having count(*) > 1
    ) duplicados

    union all

    select
        '{{ var("fecha_extraccion") }}'::date,
        'silver',
        'produccion_no_convencional',
        'mes_valid',
        'validez',
        'error',
        count(*)::bigint
    from {{ ref('stg_produccion_no_convencional') }}
    where mes is null or mes < 1 or mes > 12

    union all

    select
        '{{ var("fecha_extraccion") }}'::date,
        'silver',
        'produccion_no_convencional',
        'measures_not_null',
        'completitud',
        'error',
        count(*)::bigint
    from {{ ref('stg_produccion_no_convencional') }}
    where prod_pet is null or prod_gas is null or prod_agua is null

    union all

    select
        '{{ var("fecha_extraccion") }}'::date,
        'silver',
        'produccion_no_convencional',
        'idpozo_relationship_listado',
        'integridad_referencial',
        'warn',
        count(*)::bigint
    from {{ ref('stg_produccion_no_convencional') }} p
    left join {{ ref('stg_listado_pozos') }} l on p.idpozo = l.idpozo
    where p.idpozo is not null and l.idpozo is null

    union all

    select
        '{{ var("fecha_extraccion") }}'::date,
        'silver',
        'produccion_no_convencional',
        'produccion_no_negativa',
        'exactitud',
        'warn',
        count(*)::bigint
    from {{ ref('stg_produccion_no_convencional') }}
    where prod_pet < 0 or prod_gas < 0

    union all

    select
        '{{ var("fecha_extraccion") }}'::date,
        'silver',
        'produccion_no_convencional',
        'tef_0_31',
        'validez',
        'warn',
        count(*)::bigint
    from {{ ref('stg_produccion_no_convencional') }}
    where tef < 0 or tef > 31

    union all

    select
        '{{ var("fecha_extraccion") }}'::date,
        'silver',
        'produccion_no_convencional',
        'coordenadas_argentina',
        'exactitud',
        'warn',
        count(*)::bigint
    from {{ ref('stg_produccion_no_convencional') }}
    where latitud not between -56 and -21
       or longitud not between -74 and -53
)

select
    fecha_extraccion,
    layer,
    table_name,
    check_name,
    dimension,
    severity,
    case when failed_rows = 0 then 'pass' else 'fail' end as status,
    failed_rows,
    current_timestamp as checked_at
from checks
