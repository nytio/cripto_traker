# Proyecto Web: Seguimiento de Cotizaciones de Criptomonedas

## 0) Objetivo (MVP) y alcance

Construir una plataforma web (dashboard) que permita:

1. **Registrar criptomonedas** para seguimiento (p. ej., Bitcoin, Ethereum) usando un identificador compatible con la API (idealmente `CoinGecko ID`).
2. **Actualizar cotizaciones diarias** desde una API pública (recomendado: CoinGecko) e **insertarlas** en una base de datos **PostgreSQL** como histórico.
3. **Visualizar series históricas** con **gráficas interactivas** en el navegador.
4. **Acelerar consultas/indicadores** en el backend con **DuckDB** (cálculos analíticos tipo OLAP), sin sobrecargar PostgreSQL.
5. Mantener una base sólida de **seguridad**, buenas prácticas y **extensibilidad** (p. ej., preparar el terreno para autenticación).

> Arquitectura objetiva: microservicios “ligeros” con Docker Compose (al menos `web` + `db`), red interna segura, y opción de componentes extra (scheduler / Nginx).

---

## 1) Plan de implementación (secuencial)

1. Crear estructura base del repo (`web/`, `docker-compose.yml`, `README.md`, `.gitignore`, `.env.example`).
2. Definir `docker-compose.yml` con servicios `db` (PostgreSQL) y `web` (Flask+Gunicorn) en red interna; volumen para datos de Postgres; puertos HTTP de `web`.
3. Implementar configuración por variables de entorno en Flask (incluye `DATABASE_URL`, `FLASK_SECRET_KEY`, `COINGECKO_BASE_URL`).
4. Diseñar e implementar el esquema en PostgreSQL: tablas de criptomonedas y precios, FK, índices, y restricción única `(crypto_id, date)`.
5. Implementar cliente CoinGecko (`requests`): validación de IDs, obtención de precio actual e histórico (si se usa carga inicial).
6. Implementar flujo “Agregar criptomoneda”: formulario → validación → insert en DB → (opcional) carga histórica inicial.
7. Implementar flujo “Actualizar cotizaciones”: acción manual (botón) que recorre criptos seguidas, consulta API, inserta/actualiza en DB, maneja errores y reintentos.
8. Implementar capa analítica DuckDB: consultar serie desde Postgres (DataFrame o `pg_scanner`) y calcular indicadores (SMA 7/30, Bollinger, etc.).
9. Implementar páginas Flask+Bootstrap: dashboard, agregar cripto, detalle con selector de rango e indicadores, mensajes de éxito/error.
10. Integrar gráfica interactiva (Plotly o Chart.js): datos embebidos o endpoint JSON; tooltips/zoom; activar/desactivar indicadores; refresco tras actualización.
11. Aplicar seguridad mínima: validación/sanitización, CSRF, cabeceras, secretos por env, consultas parametrizadas/ORM, contenedores sin root.
12. Añadir documentación y bases de calidad: `README.md` operativo, pinning de dependencias, y tests básicos (cliente API mockeado + analytics).

Es una política general que la cotización sea solo de ayer, para evitar consultas innecesarias. La base de datos solo guarda datos de ayer para mantener consistencia histórica. El precio de hoy no se utiliza.

---

## 2) Arquitectura en Docker (servicios, red y persistencia)

### 1.1 Servicios mínimos

1. **`db` (PostgreSQL)**  
   - Guarda criptomonedas seguidas y precios diarios históricos.  
   - Persistencia con **volumen** Docker (no perder datos al recrear contenedores).
   - **No exponer** el puerto de PostgreSQL a Internet (ni a host si no es necesario): solo accesible desde la red interna de Compose.

2. **`web` (Flask + Gunicorn)**  
   - Backend Flask (rutas HTML y opcionalmente API JSON).  
   - Conexión a PostgreSQL con `SQLAlchemy` o `psycopg2`.  
   - Cliente HTTP para CoinGecko (`requests`).  
   - Capa analítica con DuckDB para indicadores/consultas.
   - Servir HTTP en `http://localhost:8000` (o el puerto que se defina).

### 1.2 Opcionales recomendados (según fase)

3. **Scheduler (tareas programadas)**  
   - Para actualizar precios cada 24 h:
     - Opción A: `APScheduler` dentro de `web`.
     - Opción B: `cron` en el contenedor `web`.
     - Opción C: trigger externo (p. ej. cron del host/servicio) que llame a un endpoint.
   - En el MVP, se puede dejar como **botón manual** “Actualizar cotizaciones” y sumar automatización después.

4. **`nginx` (reverse proxy + HTTPS en producción)**  
   - En producción, poner Nginx delante: terminación TLS (HTTPS) y reverse proxy a Gunicorn.

### 1.3 Red interna segura

- Definir una red por defecto en Compose; `web` se conecta a `db` usando el hostname del servicio (p. ej. `db:5432`).
- Mantener credenciales y configuración **solo en variables de entorno** (`docker-compose.yml` + `.env`), nunca hardcodeadas.
- (Opcional recomendado) Definir límites de recursos en Compose (memoria/CPU) para mitigar DoS simples y evitar que un contenedor monopolice el host.

---

## 3) Estructura sugerida del repositorio

Crear una estructura clara y extendible:

- `docker-compose.yml`
- `.env` (no commitear; añadir a `.gitignore`)
- `web/`
  - `Dockerfile`
  - `requirements.txt` (versiones “pinneadas”)
  - `wsgi.py` (entrada Gunicorn)
  - `app/`
    - `__init__.py` (app factory `create_app`)
    - `config.py` (carga de env)
    - `db.py` (SQLAlchemy engine/session)
    - `models.py` (tablas: criptomonedas, precios, opcional usuarios)
    - `services/`
      - `coingecko.py` (cliente API)
      - `price_updater.py` (actualización + deduplicación + retries)
      - `analytics.py` (DuckDB: indicadores y consultas)
    - `routes/` (blueprints)
      - `dashboard.py`
      - `cryptos.py` (agregar/listar)
      - `prices.py` (actualizar)
      - `charts.py` (detalle/serie)
      - `api.py` (opcional: JSON)
    - `templates/` (Jinja2)
    - `static/` (Bootstrap/JS/CSS, assets)
- `README.md` (cómo levantar, configurar, operar, extender)
- `tests/` (opcional MVP, recomendado para base futura)

---

## 4) Configuración por variables de entorno (seguridad y despliegue)

### 3.1 Variables mínimas (ejemplo)

- PostgreSQL:
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`
  - `POSTGRES_DB`
  - `DATABASE_URL=postgresql://user:pass@db:5432/dbname`
- API CoinGecko:
  - `COINGECKO_BASE_URL=https://api.coingecko.com/api/v3`
  - (si en el futuro hay proveedor con API key) `CRYPTO_API_KEY`
- App:
  - `FLASK_SECRET_KEY` (obligatoria si hay sesiones/CSRF)
  - `LOG_LEVEL`

### 3.2 Reglas

1. **No hardcodear** secretos ni credenciales.  
2. Guardar `.env` fuera de control de versiones.  
3. En producción, considerar gestor de secretos (si aplica).

---

## 5) Diseño de Base de Datos (PostgreSQL)

### 4.1 Tablas mínimas

1. **`cryptocurrencies` (o `cryptos`)**
   - `id` (PK)
   - `name` (opcional)
   - `symbol` (opcional, útil para UI)
   - `coingecko_id` (texto, **único** recomendado)
   - `created_at`

2. **`prices`**
   - `id` (PK)
   - `crypto_id` (FK a `cryptocurrencies.id`)
   - `date` (DATE, día de la cotización)
   - `price` (NUMERIC/DECIMAL)
   - (opcionales futuros) `volume`, `market_cap`

### 4.2 Restricciones e índices

1. **Evitar duplicados**: constraint única por `(crypto_id, date)`.  
2. Índice recomendado para series: `(crypto_id, date)` (si no queda cubierto por la unique).  
3. Integridad referencial con FK y `ON DELETE` según decisión (p. ej. cascade o restrict).

### 4.3 Carga histórica inicial (opcional)

- Al agregar una cripto, opcionalmente poblar el último año (u otro rango) usando endpoint histórico (CoinGecko `market_chart`), para que el usuario tenga gráfico desde el inicio.
- Si se omite, comenzar a registrar desde el día actual.

---

## 6) Backend Flask (rutas, capas y flujo de datos)

### 5.1 Patrones de organización

1. Separar en **blueprints** por dominio (dashboard, criptos, precios, charts, api).  
2. Encapsular lógica en **servicios**:
   - cliente CoinGecko
   - actualización de precios
   - capa analítica DuckDB
3. Acceso a datos por **ORM/consultas parametrizadas** (nunca concatenar SQL con entradas).

### 5.2 Flujo: “Agregar criptomoneda”

1. UI: formulario (input `coingecko_id` o dropdown).  
2. Backend valida:
   - formato (alfanumérico/guiones, longitud razonable)
   - que no exista ya en DB
   - (ideal) que exista en CoinGecko (consulta de validación)
3. Insertar en `cryptocurrencies`.
4. (Opcional) cargar histórico inicial y poblar `prices`.
5. Redirigir al dashboard o al detalle.

### 5.3 Flujo: “Actualizar cotizaciones”

1. Acción desde dashboard (botón “Actualizar cotizaciones”).  
2. Para cada cripto seguida:
   - pedir precio actual (endpoint `simple/price`) o precio histórico del día (si se requiere “cierre diario” consistente)
   - parsear JSON
   - insertar registro en `prices`
   - respetar límites de la API (CoinGecko: plan gratuito con límite mensual y ~30 req/min; para 1 actualización diaria suele ser suficiente)
3. Manejar errores:
   - timeouts, status no-200, rate limits
   - log + reintentos simples (por ser 1 vez/día)
4. Asegurar no duplicar (constraint única o “upsert”).

### 5.4 Rutas HTML mínimas (MVP)

- `GET /` Dashboard: lista criptos + precio más reciente + acción “Actualizar”.
- `GET /cryptos/new` + `POST /cryptos` Agregar cripto.
- `POST /prices/update` Actualizar todas (o por cripto).
- `GET /cryptos/<id>` Detalle: gráfico + controles (rango, indicadores).

### 5.5 API JSON (opcional, para futura extensibilidad)

- `GET /api/prices/<coingecko_id>` o `GET /api/cryptos/<id>/prices` para devolver series como JSON.

---

## 7) DuckDB (capa analítica para indicadores y consultas rápidas)

### 6.1 Objetivo

- Ejecutar consultas analíticas (medias móviles, RSI, correlaciones, bandas, regresión/tendencia) con SQL rápido tipo OLAP, sin cargar a PostgreSQL con cálculos pesados.

### 6.2 Estrategias de integración (elegir 1)

**Estrategia A: DataFrame → DuckDB (simple y efectiva)**  
1. Consultar en PostgreSQL la serie necesaria (rango y cripto).  
2. Convertir a DataFrame (si se usa Pandas) o estructura equivalente.  
3. Registrar el DataFrame en DuckDB y ejecutar SQL con window functions (p. ej. `AVG(...) OVER (...)`).

**Estrategia B: DuckDB `pg_scanner` (consulta directa a Postgres)**  
1. Levantar DuckDB embebido en la app.  
2. Usar extensión `pg_scanner` para leer directo desde Postgres con SQL.  
3. Ejecutar consultas analíticas directamente en DuckDB.

> Mantener este módulo aislado (`services/analytics.py`) para poder cambiar estrategia sin tocar rutas.

---

## 8) Frontend (Flask + Jinja2 + Bootstrap 5)

### 7.1 Principios

- UI estilo dashboard, moderna, responsiva (Bootstrap grid + componentes).
- Separar presentación:
  - `templates/` para HTML
  - `static/` para JS/CSS
- UX mínimo:
  - mensajes de éxito/error (flash)
  - estados de carga al actualizar precios
  - validaciones visibles en formularios

### 7.2 Páginas/secciones (según el PDF)

1. **Dashboard**: resumen + lista de criptos seguidas + precios recientes + botón actualizar.  
2. **Agregar criptomoneda**: formulario; validación; redirección.  
3. **Actualizar cotizaciones**: acción global (y opcional por cripto).  
4. **Detalle/Serie histórica**: gráfico + selección de rango + selección de indicadores.

### 7.3 Iconos/estilo

- Opcional: Font Awesome (o similar) para iconos (agregar, refresh).
- Puede usarse un tema estándar Bootstrap, dejando abierta personalización futura.

---

## 9) Gráficas interactivas (Chart.js o Plotly; D3 opcional)

### 8.1 Elección recomendada para MVP

- **Plotly** (zoom/hover/leyendas “out-of-the-box”) o **Chart.js** (simple e integrable).
- D3 solo si se requiere alta personalización (mayor curva de aprendizaje).

### 8.2 Requisitos funcionales de la gráfica

1. **Interactividad**: hover con valores, leyenda clara, zoom/pan (especialmente con Plotly).  
2. **Indicadores**: permitir activar/desactivar (p. ej. SMA 7 y SMA 30, bandas de Bollinger).  
3. **Tendencias/anotaciones**:
   - MVP: mostrar líneas calculadas (p. ej. tendencia lineal) si se decide.
   - Futuro: dibujo por usuario (si se adopta librería especializada/D3).
4. **Actualización**: al insertar nuevos datos (precio del día), el gráfico debe reflejarlo (recarga o AJAX).

### 8.3 Flujo de datos a la gráfica

- Backend prepara series (precio + indicadores) y las entrega:
  - embebidas en el HTML como JSON, o
  - via endpoint JSON consumido por fetch/AJAX.

---

## 10) Seguridad (desde el diseño)

Implementar desde el inicio:

1. **Validación y sanitización de entradas** (p. ej. `coingecko_id`, rangos de fechas).  
2. **Consultas parametrizadas/ORM** (SQLAlchemy recomendado).  
3. **CSRF** en formularios que modifican datos (Flask-WTF).  
4. **Gestión de secretos** por env (`.env`), nunca en repo.  
5. **Cabeceras de seguridad** (CSP, X-Frame-Options, etc.), idealmente con `Flask-Talisman`.  
6. **HTTPS en producción** (Nginx + TLS).  
7. **Docker hardening básico**:
   - imágenes oficiales y actualizadas (`postgres:15-alpine`, `python:3.11-slim` o similar)
   - ejecutar como **usuario no-root** en el contenedor `web`
   - exponer solo puertos necesarios
8. **Dependencias seguras**:
   - pinning en `requirements.txt`
   - mantener librerías actualizadas
   - (si aplica) escaneo SCA en CI

---

## 11) Extensibilidad y mantenibilidad

1. **Modularidad** (blueprints + servicios) y separación tipo MVC (modelos/servicios/rutas).  
2. **Documentación**:
   - `README.md` con despliegue, configuración, estructura, operación (actualización manual/diaria)
3. **Preparación para autenticación**:
   - planificar rutas `/login`, `/logout`
   - considerar modelo `users` desde el principio (aunque no se use aún)
4. **Facilidad de evolución**:
   - cambiar proveedor de precios encapsulando cliente API
   - portafolios por usuario, alertas, más indicadores, IA/predicción
5. **API REST futura**:
   - estructurar para poder exponer endpoints JSON junto con HTML
6. **Pruebas** (recomendado):
   - tests para cliente API (mock)
   - tests para cálculos DuckDB
   - tests básicos de rutas (Flask test client)

---

## 12) Checklist final (para no omitir nada del PDF)

- [ ] Docker Compose con `web` (Flask+Gunicorn) y `db` (PostgreSQL) + volumen de persistencia.
- [ ] Red interna segura: Postgres no expuesto públicamente; `web` conecta por hostname `db`.
- [ ] Variables de entorno para credenciales/URLs; ningún secreto hardcodeado.
- [ ] PostgreSQL con tablas `cryptos` y `prices`, FK, índices, y unique `(crypto_id, date)`.
- [ ] Integración CoinGecko:
  - [ ] alta de cripto guarda `coingecko_id`
  - [ ] carga histórica inicial (opcional)
  - [ ] actualización diaria (manual y/o programada) con manejo de errores + reintentos
- [ ] DuckDB para consultas analíticas/indicadores (vía DataFrame o `pg_scanner`).
- [ ] Frontend Flask+Jinja2+Bootstrap:
  - [ ] Dashboard + formulario agregar + acción actualizar + página detalle
- [ ] Gráficas interactivas:
  - [ ] Plotly o Chart.js
  - [ ] zoom/hover/leyendas
  - [ ] selección de indicadores y (opcional) tendencias
  - [ ] actualización al ingresar nuevos datos (recarga o AJAX)
- [ ] Seguridad:
  - [ ] validación de entradas, ORM/param queries, CSRF, headers, secrets por env
  - [ ] imágenes actualizadas, usuario no-root, puertos mínimos
  - [ ] HTTPS con Nginx (producción)
- [ ] Extensibilidad:
  - [ ] estructura modular, documentación, preparación para auth, API REST futura, pruebas base
