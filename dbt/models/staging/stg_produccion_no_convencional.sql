{{ config(
    schema='silver',
    alias='produccion_no_convencional',
    unique_key=['idpozo', 'anio', 'mes'],
    incremental_strategy='delete+insert',
    meta={'dagster': {'group': 'silver'}}
) }}

with raw_source as (
    select *
    from {{ source('raw', 'produccion_no_convencional') }}
    where fecha_extraccion = '{{ var("fecha_extraccion") }}'::date
),

typed as (
    select
        {{ nullable_text('idempresa') }} as idempresa,
        {{ safe_bigint('anio') }} as anio,
        {{ safe_bigint('mes') }} as mes,
        {{ safe_bigint('idpozo') }} as idpozo,
        {{ safe_numeric('prod_pet') }} as prod_pet,
        {{ safe_numeric('prod_gas') }} as prod_gas,
        {{ safe_numeric('prod_agua') }} as prod_agua,
        {{ safe_numeric('iny_agua') }} as iny_agua,
        {{ safe_numeric('iny_gas') }} as iny_gas,
        {{ safe_numeric('iny_co2') }} as iny_co2,
        {{ safe_numeric('iny_otro') }} as iny_otro,
        {{ safe_numeric('tef') }} as tef,
        {{ clean_text('tipoextraccion') }} as tipoextraccion,
        {{ clean_text('tipoestado') }} as tipoestado,
        {{ clean_text('tipopozo') }} as tipopozo,
        {{ safe_timestamp('fechaingreso') }} as fechaingreso,
        {{ safe_timestamp('fecha_data') }} as fecha_data,
        {{ safe_boolean('rectificado') }} as rectificado,
        {{ safe_boolean('habilitado') }} as habilitado,
        {{ nullable_text('empresa') }} as empresa,
        {{ nullable_text('sigla') }} as sigla,
        {{ nullable_text('formprod') }} as formprod,
        {{ safe_numeric('profundidad') }} as profundidad,
        {{ nullable_text('formacion') }} as formacion,
        {{ nullable_text('idareapermisoconcesion') }} as idareapermisoconcesion,
        {{ nullable_text('areapermisoconcesion') }} as areapermisoconcesion,
        {{ nullable_text('idareayacimiento') }} as idareayacimiento,
        {{ nullable_text('areayacimiento') }} as areayacimiento,
        {{ nullable_text('idcuenca') }} as idcuenca,
        {{ clean_text('cuenca') }} as cuenca,
        {{ nullable_text('idprovincia') }} as idprovincia,
        {{ clean_text('provincia') }} as provincia,
        {{ nullable_text('proyecto') }} as proyecto,
        {{ clean_text('clasificacion') }} as clasificacion,
        {{ clean_text('subclasificacion') }} as subclasificacion,
        {{ clean_text('sub_tipo_recurso') }} as sub_tipo_recurso,
        {{ safe_numeric('coordenadax') }} as longitud,
        {{ safe_numeric('coordenaday') }} as latitud,
        fecha_extraccion,
        source_uri,
        loaded_at,
        raw_row_number
    from raw_source
),

enriched as (
    select
        *,
        coalesce(
            fecha_data::date,
            case
                when anio is not null and mes between 1 and 12
                    then (make_date(anio::int, mes::int, 1)
                        + interval '1 month - 1 day')::date
                else null
            end
        ) as fecha_periodo,
        (prod_pet < 0 or prod_gas < 0) as flag_prod_negativa,
        (tef < 0 or tef > 31) as flag_tef_fuera_rango,
        (profundidad < 0 or profundidad > 10000) as flag_profundidad_fuera_rango,
        not (
            latitud between -56 and -21
            and longitud between -74 and -53
        ) as flag_coordenadas_fuera_rango,
        md5(concat_ws('|', idpozo::text, anio::text, mes::text))
            as grain_produccion_pozo_mes,
        row_number() over (
            partition by idpozo, anio, mes
            order by loaded_at desc, raw_row_number desc
        ) as rn
    from typed
),

deduped as (
    select *
    from enriched
    where idpozo is not null
      and anio is not null
      and mes is not null
      and rn = 1
)

select
    idempresa,
    anio,
    mes,
    idpozo,
    prod_pet,
    prod_gas,
    prod_agua,
    iny_agua,
    iny_gas,
    iny_co2,
    iny_otro,
    tef,
    tipoextraccion,
    tipoestado,
    tipopozo,
    fechaingreso,
    fecha_data,
    rectificado,
    habilitado,
    empresa,
    sigla,
    formprod,
    profundidad,
    formacion,
    idareapermisoconcesion,
    areapermisoconcesion,
    idareayacimiento,
    areayacimiento,
    idcuenca,
    cuenca,
    idprovincia,
    provincia,
    proyecto,
    clasificacion,
    subclasificacion,
    sub_tipo_recurso,
    longitud,
    latitud,
    fecha_periodo,
    flag_prod_negativa,
    flag_tef_fuera_rango,
    flag_profundidad_fuera_rango,
    flag_coordenadas_fuera_rango,
    grain_produccion_pozo_mes,
    fecha_extraccion,
    source_uri,
    loaded_at
from deduped
