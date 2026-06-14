{{ config(
    schema='silver',
    alias='listado_pozos',
    unique_key='idpozo',
    incremental_strategy='delete+insert',
    meta={'dagster': {'group': 'silver'}}
) }}

with raw_source as (
    select *
    from {{ source('raw', 'listado_pozos') }}
    where fecha_extraccion = '{{ var("fecha_extraccion") }}'::date
),

typed as (
    select
        {{ safe_bigint('idpozo') }} as idpozo,
        {{ nullable_text('sigla') }} as sigla,
        {{ nullable_text('formprod') }} as formprod,
        {{ nullable_text('idempresa') }} as idempresa,
        {{ nullable_text('idareapermisoconcesion') }} as idareapermisoconcesion,
        {{ nullable_text('idareayacimiento') }} as idareayacimiento,
        {{ nullable_text('idcuenca') }} as idcuenca,
        {{ nullable_text('idprovincia') }} as idprovincia,
        {{ nullable_text('codigopropio') }} as codigopropio,
        {{ nullable_text('nombrepropio') }} as nombrepropio,
        {{ safe_numeric('coordenadax') }} as longitud,
        {{ safe_numeric('coordenaday') }} as latitud,
        {{ safe_numeric('cota') }} as cota,
        {{ safe_numeric('profundidad') }} as profundidad,
        {{ safe_numeric('pet_inicial') }} as pet_inicial,
        {{ safe_numeric('gas_inicial') }} as gas_inicial,
        {{ safe_numeric('agua_inicial') }} as agua_inicial,
        {{ safe_numeric('iny_agua_inicial') }} as iny_agua_inicial,
        {{ safe_numeric('iny_gas_inicial') }} as iny_gas_inicial,
        {{ safe_numeric('iny_otros_inicial') }} as iny_otros_inicial,
        {{ safe_numeric('iny_co2_inicial') }} as iny_co2_inicial,
        {{ safe_numeric('vida_util_inicial') }} as vida_util_inicial,
        {{ nullable_text('areapermisoconcesion') }} as areapermisoconcesion,
        {{ nullable_text('areayacimiento') }} as areayacimiento,
        {{ clean_text('cuenca') }} as cuenca,
        {{ clean_text('provincia') }} as provincia,
        {{ clean_text('clasificacion') }} as clasificacion,
        {{ clean_text('subclasificacion') }} as subclasificacion,
        {{ clean_text('tipo_reservorio') }} as tipo_reservorio,
        {{ clean_text('subtipo_reservorio') }} as subtipo_reservorio,
        {{ nullable_text('comp_perf') }} as comp_perf,
        {{ safe_boolean('gasplus') }} as gasplus,
        fecha_extraccion,
        source_uri,
        loaded_at,
        raw_row_number,
        row_number() over (
            partition by {{ safe_bigint('idpozo') }}
            order by loaded_at desc, raw_row_number desc
        ) as rn
    from raw_source
),

deduped as (
    select *
    from typed
    where idpozo is not null
      and rn = 1
)

select
    idpozo,
    sigla,
    formprod,
    idempresa,
    idareapermisoconcesion,
    idareayacimiento,
    idcuenca,
    idprovincia,
    codigopropio,
    nombrepropio,
    longitud,
    latitud,
    cota,
    profundidad,
    pet_inicial,
    gas_inicial,
    agua_inicial,
    iny_agua_inicial,
    iny_gas_inicial,
    iny_otros_inicial,
    iny_co2_inicial,
    vida_util_inicial,
    areapermisoconcesion,
    areayacimiento,
    cuenca,
    provincia,
    clasificacion,
    subclasificacion,
    tipo_reservorio,
    subtipo_reservorio,
    comp_perf,
    gasplus,
    fecha_extraccion,
    source_uri,
    loaded_at
from deduped
