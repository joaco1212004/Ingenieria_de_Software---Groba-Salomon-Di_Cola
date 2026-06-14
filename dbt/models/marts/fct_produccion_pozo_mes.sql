{{ config(
    schema='gold',
    alias='fct_produccion_pozo_mes',
    unique_key='sk_produccion_pozo_mes',
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

produccion as (
    select *
    from {{ ref('stg_produccion_no_convencional') }}
),

fact as (
    select
        md5(concat_ws('|', p.idpozo::text, p.anio::text, p.mes::text))
            as sk_produccion_pozo_mes,
        coalesce(dp.sk_pozo, md5('__unknown__')) as sk_pozo,
        coalesce(de.sk_empresa, md5('__unknown__')) as sk_empresa,
        coalesce(da.sk_area, md5('__unknown__')) as sk_area,
        dt.sk_tiempo,
        p.idpozo as idpozo_natural,
        p.anio,
        p.mes,
        p.fecha_periodo::date as fecha_periodo,
        p.prod_pet,
        p.prod_gas,
        p.prod_gas * 1000 as prod_gas_m3,
        p.prod_agua,
        p.iny_agua,
        p.iny_gas,
        p.iny_co2,
        p.iny_otro,
        p.tef,
        p.rectificado,
        p.tipoestado,
        p.tipoextraccion,
        p.tipopozo,
        p.sub_tipo_recurso,
        p.flag_prod_negativa,
        p.flag_tef_fuera_rango,
        p.flag_profundidad_fuera_rango,
        p.flag_coordenadas_fuera_rango,
        p.fecha_extraccion
    from produccion p
    left join {{ ref('dim_pozo') }} dp on p.idpozo = dp.idpozo
    left join {{ ref('dim_empresa') }} de on p.idempresa = de.idempresa
    left join {{ ref('dim_area') }} da
        on coalesce(p.idareapermisoconcesion, '') = coalesce(da.idareapermisoconcesion, '')
       and coalesce(p.idareayacimiento, '') = coalesce(da.idareayacimiento, '')
       and coalesce(p.idcuenca, '') = coalesce(da.idcuenca, '')
       and coalesce(p.idprovincia, '') = coalesce(da.idprovincia, '')
    left join {{ ref('dim_tiempo') }} dt on p.fecha_periodo::date = dt.fecha_periodo
)

select f.*
from fact f
cross join quality_gate q
where q.blocking_failures = 0
