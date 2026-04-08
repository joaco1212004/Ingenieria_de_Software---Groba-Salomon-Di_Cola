# Plataforma Predictiva - API Mock (Fase 1)

Este repositorio contiene la implementación inicial de la **Plataforma Predictiva** de producción de hidrocarburos desarrollada para la materia Ingeniería de Software (Groba, Salomon, Di Cola).

## Descripción

El objetivo de este servicio es proveer una API RESTful (Mock) que permite:
- Obtener un listado de pozos.
- Consultar pronósticos de producción para un horizonte de tiempo determinado.

Actualmente, los resultados provistos por la API son estáticos o generados con lógicas simples a modo de maqueta (Mock) para que los sistemas y equipos externos puedan comenzar a integrarse de forma temprana.

## Acceso y Uso

- La documentación interactiva de la API (Swagger UI) está disponible en la ruta `/docs` cuando el servicio se encuentra en ejecución.
- **Autenticación:** La API está protegida por un mecanismo de API Key. Todos los requests deben incluir el header HTTP `X-API-Key` con la clave correspondiente (provista por la administración/cátedra).

## Tecnologías Utilizadas

- **Framework:** FastAPI (Python)
- **Gestión de dependencias:** Poetry
- **CI/CD:** GitHub Actions (Pytest, Black, automatización de Docker y despliegue a AWS)
- **Contenedores:** Docker

## Ejecución Local

Para levantar el servicio de forma local utilizando Docker:

```bash
docker build -t predictiva-api .
docker run -p 8000:8000 predictiva-api
```
Luego, accede a `http://localhost:8000/docs` en tu navegador.
