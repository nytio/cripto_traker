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
