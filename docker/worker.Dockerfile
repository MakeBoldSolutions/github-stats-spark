# Worker image: the existing `spark` CLI. Playwright/browsers are intentionally
# excluded (screenshot capture is optional and not part of this image).

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SPARK_CACHE_DIR=/app/.cache
WORKDIR /app

COPY requirements.txt ./
RUN grep -viE '^\s*playwright' requirements.txt > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt

COPY setup.py pyproject.toml README.md ./
COPY src ./src
COPY config ./config
# --no-deps: dependencies were installed above (minus Playwright).
RUN pip install --no-deps -e .

COPY docker/worker-entrypoint.sh /usr/local/bin/worker-entrypoint.sh

# Non-root user. Named volumes mounted at these paths inherit this ownership.
RUN useradd --uid 10001 --create-home app \
    && chmod +x /usr/local/bin/worker-entrypoint.sh \
    && mkdir -p /app/data /app/output /app/.cache \
    && chown -R app:app /app/data /app/output /app/.cache /app/config
USER app

ENTRYPOINT ["worker-entrypoint.sh"]
# One-shot run; the user is supplied by the compose file.
CMD ["spark", "--help"]
