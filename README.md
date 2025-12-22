# Proyecto Web: Seguimiento de Cotizaciones de Criptomonedas

## Requisitos

- Docker y Docker Compose

## Inicio rapido

1. Copiar el archivo de variables de entorno:

   ```bash
   cp .env.example .env
   ```

2. Levantar los servicios:

   ```bash
   docker compose up --build
   ```

3. Abrir la app en el navegador:

   http://localhost:8000

## Notas

- La base de datos no expone puertos al host; solo esta disponible dentro de la red de Compose.
- Este repo inicia con un esqueleto de Flask y estructura de servicios y rutas.
- Configura `COINGECKO_VS_CURRENCY` si quieres usar otra moneda de referencia (default: usd).
- Puedes limitar la carga historica con `MAX_HISTORY_DAYS` (default: 365).
- Usa `COINGECKO_REQUEST_DELAY` para espaciar requests al API (default: 1.1s).

## API basica

- `GET /api/health`
- `GET /api/cryptos`
- `GET /api/cryptos/<id>/prices`
- `GET /api/cryptos/<id>/series?days=30&indicators=1`

## Backfill historico

En la vista de detalle puedes solicitar un backfill de X dias. El sistema calcula los dias faltantes y solo pide esos rangos a CoinGecko, pausando entre requests.

## Actualizacion manual

Los botones de actualizacion manual usan el dia anterior para evitar variaciones intradia.

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

## Tests

```bash
pip install -r web/requirements.txt -r requirements-dev.txt
PYTHONPATH=web pytest
```
