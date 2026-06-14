{{ config(severity='error', store_failures=true, schema='audit') }}

select *
from {{ ref('quality_results') }}
where fecha_extraccion = '{{ var("fecha_extraccion") }}'::date
  and severity = 'error'
  and status = 'fail'
