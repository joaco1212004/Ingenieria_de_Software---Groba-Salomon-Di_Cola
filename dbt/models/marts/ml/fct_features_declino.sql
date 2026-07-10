{{ config(
    schema='gold',
    alias='fct_features_declino',
    materialized='table',
    tags=['ml'],
    meta={'dagster': {'group': 'ml'}}
) }}

-- Feature mart del entrenamiento de declino (ADR-0022, nodo build_features).
--
-- Senal: tasa diaria = prod_pet / tef, que separa el declino fisico del
-- downtime operativo (un mes parado colapsa el volumen mensual pero no la
-- tasa). tef <= 0 es un mes sin operar: la tasa queda NULL, nunca 0 (un 0 se
-- confundiria con un pozo que declino a cero).
--
-- Materializado como tabla completa (no incremental): es una proyeccion del
-- fact acumulativo y el entrenamiento siempre lee la historia entera de cada
-- pozo; el rebuild es barato e idempotente.

with produccion as (
    select
        idpozo_natural as idpozo,
        anio,
        mes,
        fecha_periodo,
        prod_pet,
        tef,
        case when tef > 0 then prod_pet / tef end as tasa_diaria_pet,
        fecha_extraccion
    from {{ ref('fct_produccion_pozo_mes') }}
),

-- Filtros de cohorte del benchmark: sin historia minima no hay curva que
-- ajustar (mismos umbrales que re-chequea pipeline/ml/datos.py).
pozos_con_senal as (
    select idpozo
    from produccion
    group by idpozo
    having count(*) >= 12
       and count(*) filter (where tasa_diaria_pet > 0) >= 6
)

select p.*
from produccion p
join pozos_con_senal s on p.idpozo = s.idpozo
