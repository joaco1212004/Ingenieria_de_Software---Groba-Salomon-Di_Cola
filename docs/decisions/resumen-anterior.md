# DEPRECATED

**Selección de Stack Tecnológico e Infraestructura para la API Mock (Fase 1)**  
**Contexto y Declaración del Problema**  
Para cumplir con la Fase 1 del proyecto "Plataforma Predictiva", debíamos desarrollar y desplegar una API RESTful (mock) que sirviera datos estáticos o simulados. Los requisitos de la adenda técnica incluían exposición de endpoints documentados (OpenAPI), validación de parámetros, empaquetado en contenedores Docker, un flujo automatizado de CI/CD, y despliegue utilizando los créditos de AWS otorgados por la cátedra. Teníamos que elegir las herramientas y lenguajes que nos permitieran hacer esto de la forma más rápida y robusta posible.  
**Factores de Decisión**  
- Conocimiento previo y curva de aprendizaje del equipo. Al ser estudiantes de una carrera muy ligada a datos e inteligencia artificial, nuestro fuerte es Python.  
- Velocidad para desarrollar APIs y generar documentación autogenerada según el estándar requerido.  
- Gestión predecible de dependencias para asegurar la portabilidad en Docker.  
- Restricción de direcciones IP dinámicas y efímeras en entornos de AWS Academy/Learner Labs, requiriendo una solución para tener un punto de acceso fijo para el corrector.  
**Opciones Consideradas**  
- **Lenguaje y Framework Web:** Python (FastAPI) vs Node.js (Express) vs Python (Flask/Django).  
- **Gestor de Dependencias:** Poetry vs Pip (requirements.txt).  
- **Infraestructura de Despliegue AWS:** Amazon EC2 (Docker directo) vs AWS App Runner / Elastic Beanstalk.  
- **Resolución DNS:** DuckDNS vs IP Elástica / AWS Route 53.  
**Resultado de la Decisión**  
**Opciones elegidas:** Python + FastAPI, Poetry, Docker, Amazon EC2, y DuckDNS.  
**Porque:**  
   
 Elegimos el ecosistema **Python** porque es nuestro lenguaje de mayor soltura por nuestra formación, y será fundamental más adelante cuando tengamos que implementar los modelos predictivos reales en fases posteriores. Dentro de Python, elegimos  **FastAPI** porque es moderno, excepcionalmente rápido y utiliza Pydantic para la validación nativa de tipos (por ejemplo, nos validó automáticamente el formato de fechas datetime.date devolviendo el error HTTP 422). Además, genera la documentación de Swagger/OpenAPI automáticamente de forma gratuita, cumpliendo directo con la adenda.  
Optamos por **Poetry** en lugar de requirements.txt tradicional para tener resolución estricta de dependencias (el poetry.lock) y evitar que la compilación en GitHub Actions falle por versiones rotas en bibliotecas transitivas.  
En cuanto a infraestructura, nos decantamos por **AWS EC2 (Ubuntu t2.micro)** por ser la opción más económica (Free Tier) y que nos da control absoluto sobre el servidor para correr nuestro contenedor Docker. Para mitigar el problema de que la IP de la instancia cambia si la apagamos (y no queremos pagar por una IP Elástica fija), introdujimos  **DuckDNS**. Esto nos dio un dominio gratuito (api-hidraulicos-tipazos.duckdns.org) actualizable mediante un script por cron en el servidor, permitiendo hacer entregas de CD automatizadas desde GitHub Actions sin tener que reconfigurar la IP en los secretos.  
**Consecuencias**  
- **Bueno, porque:** Pudimos desarrollar el mock en muy poco código, validando los datos de forma nativa sin escribir sentencias if/else complejas, y el entorno de AWS resulta sumamente económico e integrable por CI/CD (Appleboy SSH Action).  
- **Malo, porque:** EC2 requiere que manejemos el servidor, actualizaciones de SO y certificados manualmente en caso de querer agregar HTTPS en un futuro, sumando una pequeña carga de operaciones (DevOps). DuckDNS es un servicio de terceros externo a AWS que podría tener cortes imprevistos ajenos a nuestra infraestructura.  
**Confirmación**  
Se verificarán estas decisiones mediante la ejecución exitosa del pipeline de CI/CD en GitHub Actions y el acceso público ininterrumpido al endpoint /docs utilizando el dominio de DuckDNS.  
