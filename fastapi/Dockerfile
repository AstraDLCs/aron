FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Las dependencias se instalan primero (capa cacheable); el paquete `app` es un
# esqueleto temporal que luego se reemplaza por el código real.
COPY pyproject.toml ./
RUN mkdir app && touch app/__init__.py && pip install -e ".[dev]"

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
