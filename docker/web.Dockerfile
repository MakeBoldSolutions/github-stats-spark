# Web image: builds the existing React dashboard and serves it with nginx.
# Repository data (/data) and screenshots (/output) are NOT baked in; they are
# mounted as read-only volumes written by the worker, so data refreshes never
# require an image rebuild.

FROM node:24-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json frontend/
RUN cd frontend && npm ci
COPY frontend frontend
# The Vite config writes to <repo>/docs (the Pages target) inside this build stage only.
RUN cd frontend && npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
ARG SPARK_REVISION=unknown
LABEL org.opencontainers.image.revision=$SPARK_REVISION \
      org.opencontainers.image.title="github-stats-spark web"
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/docs /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null || exit 1
