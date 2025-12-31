# Proyecto Web: Seguimiento de Cotizaciones de Criptomonedas

## Requisitos

- Docker y Docker Compose

## Inicio rápido

1. Copiar el archivo de variables de entorno:

   ```bash
   cp .env.example .env
   ```

2. Levantar los servicios:

   ```bash
   docker compose up --build
   ```

3. Abrir la app en el navegador:

   http://localhost:8080

## Notas

- La base de datos no expone puertos al host; solo está disponible dentro de la red de Compose.
- Este repo inicia con un esqueleto de Flask y estructura de servicios y rutas.
- Configura `COINGECKO_VS_CURRENCY` si quieres usar otra moneda de referencia (default: usd).
- Puedes limitar la carga historica con `MAX_HISTORY_DAYS` (default: 365).
- Usa `COINGECKO_REQUEST_DELAY` para espaciar requests al API (default: 1.1s).
- Reintentos configurables: `COINGECKO_RETRY_COUNT` y `COINGECKO_RETRY_DELAY`.

## API basica

- `GET /api/health`
- `GET /api/cryptos`
- `GET /api/cryptos/<id>/prices`
- `GET /api/cryptos/<id>/series?days=30&indicators=1`

## Backfill historico

En la vista de detalle puedes solicitar un backfill de X dias. El sistema calcula los días faltantes y solo pide esos rangos a CoinGecko, pausando entre requests.

## Actualizacion manual

Los botones de actualización manual usan el día anterior para evitar variaciones intradía.

## Auth (placeholder)

Se incluyen rutas `/login` y `/logout` y un modelo `users` como base para autenticacion.

## Scheduler opcional

Para ejecutar la actualizacion diaria en un contenedor separado:

```bash
docker compose --profile scheduler up --build
```

Variables:
- `SCHEDULER_TIMEZONE` (default: UTC)
- `SCHEDULE_HOUR` (0-23)
- `SCHEDULE_MINUTE` (0-59)
- `SCHEDULE_RUN_ON_START` (1 para ejecutar al iniciar)
- `SCHEDULE_OFFSET_DAYS` (default: 1, para actualizar el dia anterior)

## Nginx (opcional, HTTPS)

Agrega certificados en `nginx/certs/fullchain.pem` y `nginx/certs/privkey.pem`, luego levanta:

```bash
docker compose --profile nginx up --build
```

## Tests

```bash
pip install -r requirements-dev.txt
PYTHONPATH=web pytest
```
