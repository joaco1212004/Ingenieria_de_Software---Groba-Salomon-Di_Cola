{% macro clean_text(expr, default="'SIN DATO'") -%}
    coalesce(nullif(trim({{ expr }}::text), ''), {{ default }})
{%- endmacro %}

{% macro nullable_text(expr) -%}
    nullif(trim({{ expr }}::text), '')
{%- endmacro %}

{% macro safe_numeric(expr) -%}
    case
        when nullif(trim({{ expr }}::text), '') is null then null
        when replace(trim({{ expr }}::text), ',', '.') ~ '^-?[0-9]+(\.[0-9]+)?$'
            then replace(trim({{ expr }}::text), ',', '.')::double precision
        else null
    end
{%- endmacro %}

{% macro safe_bigint(expr) -%}
    case
        when nullif(trim({{ expr }}::text), '') is null then null
        when replace(trim({{ expr }}::text), ',', '.') ~ '^-?[0-9]+(\.0+)?$'
            then replace(trim({{ expr }}::text), ',', '.')::numeric::bigint
        else null
    end
{%- endmacro %}

{% macro safe_boolean(expr) -%}
    case
        when lower(trim({{ expr }}::text)) in ('t', 'true', '1', 'si', 's') then true
        when lower(trim({{ expr }}::text)) in ('f', 'false', '0', 'no', 'n') then false
        else null
    end
{%- endmacro %}

{% macro safe_timestamp(expr) -%}
    case
        when nullif(trim({{ expr }}::text), '') is null then null
        when trim({{ expr }}::text) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
            then trim({{ expr }}::text)::timestamp
        else null
    end
{%- endmacro %}
