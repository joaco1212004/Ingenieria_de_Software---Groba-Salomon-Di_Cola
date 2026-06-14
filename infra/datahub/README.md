# Plataformas: Metabase (BI) + DataHub (gobierno) — EC2-2

Stream C de la Fase 2. Ambas plataformas corren en **EC2-2** (t2.large) separada
del stack de datos de EC2-1, y se conectan al warehouse Postgres de EC2-1.

- ADR-0017 (Metabase) · ADR-0016 (DataHub) · ADR-0014 (modelo gold consumido).

## Prerrequisitos

### EC2-1 (warehouse + ingestion)
1. Exponer Postgres a EC2-2: en el `.env` setear `POSTGRES_BIND=<ip-privada-EC2-1>`
   y recrear: `docker compose up -d postgres-dwh`.
2. Security group EC2-1: inbound `5432` **solo desde el SG/IP de EC2-2**.
3. Password real del warehouse (`POSTGRES_PASSWORD`), no el default `dwh`.
4. CLI de ingestion aislado: `pipx install 'acryl-datahub[postgres,dbt]==1.1.0'`.
   El pin importa: el CLI y el GMS tienen que ser la MISMA version (`1.1.0` ==
   server `v1.1.0`). Un CLI mas nuevo manda aspectos que un GMS viejo rechaza
   (p.ej. `/env` en ContainerProperties -> 0 records escritos).

### EC2-2 (plataformas)
1. Docker + Docker Compose, >= 8 GB RAM libres.
2. `pipx install 'acryl-datahub==1.1.0'` (para el quickstart; lanza el server
   `v1.1.0`). El CLI tiene que matchear `DATAHUB_VERSION`.
3. `.env` con las variables de `infra/platforms.env.example`.
4. Security group EC2-2: inbound `9002` y `3000` desde IPs del equipo; inbound
   `8080` (GMS) **solo desde EC2-1**; outbound a EC2-1:5432.

## Arranque

```bash
# --- EC2-2 ---
./scripts/datahub-up.sh                                              # DataHub :9002 / :8080
docker compose -f infra/metabase/docker-compose.metabase.yml --env-file .env up -d   # Metabase :3000

# --- EC2-1 ---  (publica metadata a DataHub)
set -a; . ./.env; set +a
./scripts/datahub-ingest.sh
```

En CI/CD esto lo hace `.github/workflows/deploy-platforms.yml` (push a `main`
que toque `infra/**` o por `workflow_dispatch`).

## Metabase — conexion al warehouse y dashboard

1. Primer login en `http://<EC2-2>:3000` (crea admin).
2. Admin → Databases → **Add database** → PostgreSQL:
   - Host: `<ip-privada-EC2-1>` · Port: `5432` · Database: `warehouse`
   - User/Pass: credenciales del warehouse · Schema: `gold`
3. Crear el dashboard **"Produccion por cuenca/empresa/periodo"**. Como Metabase
   OSS no versiona dashboards como codigo, la query base queda documentada aca:

```sql
-- Produccion mensual por cuenca y empresa (unidades normalizadas: gas a m3)
select
    t.anio,
    t.mes,
    a.cuenca,
    e.empresa,
    sum(f.prod_pet)     as prod_pet_m3,
    sum(f.prod_gas_m3)  as prod_gas_m3,
    sum(f.prod_agua)    as prod_agua_m3
from gold.fct_produccion_pozo_mes f
join gold.dim_tiempo  t on f.sk_tiempo  = t.sk_tiempo
join gold.dim_area    a on f.sk_area    = a.sk_area
join gold.dim_empresa e on f.sk_empresa = e.sk_empresa
group by t.anio, t.mes, a.cuenca, e.empresa
order by t.anio, t.mes;
```

Opcional: tablero de calidad sobre `audit.quality_results` (checks por
`dimension`/`severity`/`status`).

## DataHub — que cubre del MUST

- **Datos del warehouse + ultima actualizacion:** receta `recipes/postgres_warehouse.yml`
  cataloga `gold`/`silver`/`audit` con `last_modified` por tabla.
- **Lineage navegable a nivel tabla (MUST):** receta `recipes/dbt.yml` (necesita
  `catalog.json`, que `scripts/datahub-ingest.sh` genera con `dbt docs generate`).
- **Marca de calidad visible:** los resultados de los dbt tests entran como
  assertions por tabla.

## Notas

- **Ingestion fuera del contenedor Dagster a proposito:** `acryl-datahub` se
  aisla con pipx en EC2-1 para no mezclar sus dependencias con el entorno poetry.
  La ingestion corre en EC2-1 porque el warehouse y `dbt/target/` son locales ahi;
  solo el *sink* viaja a EC2-2:8080. Si se prefiere orquestarla con Dagster, se
  puede envolver `scripts/datahub-ingest.sh` en un `@op`/`@job` instalando el CLI
  en un venv aislado dentro de la imagen (`DATAHUB_EXECUTABLE`).
- **Costo:** EC2-2 queda always-on con el CD automatizado. Para ahorrar creditos
  se puede apagar fuera de demos; al reencender, re-correr arranque + ingestion
  (todo idempotente).
