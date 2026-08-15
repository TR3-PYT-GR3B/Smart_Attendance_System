# Hugging Face Docker Space image for the Django API and face verifier.
FROM python:3.14-slim AS wheels

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends build-essential g++ pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY backend/requirements.txt .
RUN pip wheel --wheel-dir /wheels --requirement requirements.txt


FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=7860

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 attendx

WORKDIR /app
COPY --from=wheels /wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

COPY backend/ /app/
COPY deploy/huggingface/start.sh /usr/local/bin/attendx-start

# Models and hashed admin assets are immutable image layers. Build failures are
# intentional here: a Space must not start without the verifier it promises.
RUN DJANGO_DEBUG=False \
    DJANGO_SECRET_KEY=build-only-not-used-at-runtime \
    DJANGO_ALLOWED_HOSTS=localhost \
    python download_models.py \
    && DJANGO_DEBUG=False \
       DJANGO_SECRET_KEY=build-only-not-used-at-runtime \
       DJANGO_ALLOWED_HOSTS=localhost \
       python manage.py collectstatic --noinput \
    && chmod 0755 /usr/local/bin/attendx-start \
    && chown -R attendx:attendx /app

USER attendx
EXPOSE 7860

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/usr/local/bin/attendx-start"]
