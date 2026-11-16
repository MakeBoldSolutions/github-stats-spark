# Docker Deployment (self-hosted)

Runs the existing dashboard as a Docker stack: `web` (nginx serving the built React app) and `worker`
(the `spark` CLI, run once on demand). GitHub Pages and the CLI are unchanged.

## Quick start (local)

```bash
cp docker/env.example .env      # set SPARK_USER and a token (see below)
docker compose up -d --build web
docker compose up worker        # collect data once (needs a token)
sh docker/smoke.sh              # http://127.0.0.1:8086
```

Open <http://127.0.0.1:8086>. The page shows data once the worker has written it to the `spark-data`
volume; reload after a run.

## Storage

| Volume | Holds | Notes |
| --- | --- | --- |
| `spark-data`, `spark-output` | generated JSON, reports, screenshots | rebuildable; mounted read-only in `web` |
| `spark-cache` | GitHub API cache | rebuildable |
| `spark-config` | `config/spark.yml`, themes | seeded from the image on first creation; edit here to change settings (the seeded copy then wins over later image updates) |

## GitHub token

Public data needs a token with default public read access (no private repository scopes; the constitution
keeps private data out of this release). Prefer a secret file over `GITHUB_TOKEN`, which is visible via
`docker inspect`: put the token in `./secrets/github_token`, add a bind mount of it to the worker
(for example `./secrets/github_token:/run/secrets/github_token:ro`) and set
`GITHUB_TOKEN_FILE=/run/secrets/github_token`. `secrets/` is excluded from images.

## Home server (Ubuntu, Portainer)

1. In Portainer: Stacks → Add stack → Repository (this repo, branch with these files) or paste
   `docker-compose.yml`.
2. Stack variables: `SPARK_USER`, `GITHUB_TOKEN` (or the secret-file approach), `BIND_ADDRESS=192.168.1.197`,
   `WEB_PORT=8086`.
3. Deploy. The `web` container becomes healthy; the `worker` runs once and exits (`restart: "no"`).
4. Refresh data: start the `worker` container again in Portainer. Scheduled refresh is a later roadmap item.
5. Browse to `http://192.168.1.197:8086` from the LAN.

The default bind is `127.0.0.1`; the app has no authentication yet, so keep it on the trusted LAN and do
not forward the port. Do not enable private repositories until the private-data boundary item ships.

## Troubleshooting

- Dashboard says data failed to load: run the worker, check `docker compose logs worker`.
- `no GitHub token` error: set `GITHUB_TOKEN` or `GITHUB_TOKEN_FILE`.
- Reset collected data only: `docker compose down` then `docker volume rm github-stats-spark_spark-data
  github-stats-spark_spark-output github-stats-spark_spark-cache`. Keep `spark-config`.
