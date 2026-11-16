# Docker Deployment (self-hosted)

Runs the existing dashboard as a Docker stack: `web` (nginx serving the built React app) and `worker`
(a scheduler that runs the `spark` CLI on an interval). GitHub Pages and the CLI are unchanged.

## Quick start (local)

```bash
cp docker/env.example .env      # set SPARK_USER and a token (see below)
docker compose up -d --build    # web + scheduled worker (collects on start)
sh docker/smoke.sh              # http://127.0.0.1:8086
```

Open <http://127.0.0.1:8086>. The page shows data once the first collection finishes.

## Scheduled collection

| Variable | Default | Meaning |
| --- | --- | --- |
| `SPARK_USER` | required | GitHub user(s), comma separated. **Seeds the source registry on first start only**; after that the registry is authoritative. |
| `SPARK_REFRESH_INTERVAL` | `6h` | time between runs (minimum `60s`) |
| `SPARK_RUN_ON_START` | `true` | collect immediately when the worker starts |
| `SPARK_RUN_TIMEOUT` | `2h` | a run longer than this is stopped and reported failed |
| `SPARK_RETRY_DELAY` | `30m` | wait before retrying after a failed run |
| `SPARK_MIN_RATE_REMAINING` | `300` | skip a run while GitHub quota is below this; resumes after reset |
| `SPARK_EXTRA_ARGS` | empty | extra `spark unified` flags, e.g. `--include-ai-summaries` |

How a run works: the worker runs `spark unified` in a staging directory, checks that repository data was
produced, and only then swaps it into the served volumes with an atomic symlink rename. A failed or
interrupted run publishes nothing, so the dashboard keeps the last good data. Each run updates
`/data/status.json`, which the dashboard header shows as **up to date**, **refreshed with errors**,
**refresh paused** (rate limit), or **last refresh failed**. To force a run now, restart the `worker`
container. `docker compose ps` shows the worker as unhealthy if its loop stops.

The first run after upgrading from the one-shot setup moves the existing `users` directory into
`.releases/legacy-*` and replaces it with a link (a brief one-time gap). Only the two newest releases are kept.

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
3. Deploy. Both containers become healthy; the worker collects on start and then every interval.
4. Refresh now: restart the `worker` container in Portainer.
5. Browse to `http://192.168.1.197:8086` from the LAN.

The default bind is `127.0.0.1`; the app has no authentication yet, so keep it on the trusted LAN and do
not forward the port. Do not enable private repositories until the private-data boundary item ships.

## Troubleshooting

- Dashboard says data failed to load: check `docker compose logs worker` and the status line in the header.
- `no GitHub token` error: set `GITHUB_TOKEN` or `GITHUB_TOKEN_FILE`.
- Reset collected data only: `docker compose down` then `docker volume rm github-stats-spark_spark-data
  github-stats-spark_spark-output github-stats-spark_spark-cache`. Keep `spark-config`.


## Managing sources (organizations, repositories, users)

Sources live in a SQLite registry (`/app/config/registry.db`, in the `spark-config` volume, so it
survives container recreation). Manage them from the worker container (uses its `GITHUB_TOKEN`):

```sh
docker compose exec worker python -m spark.registry add org MyOrg --client "Acme"
docker compose exec worker python -m spark.registry add repo owner/name
docker compose exec worker python -m spark.registry list
docker compose exec worker python -m spark.registry exclude owner/name
docker compose exec worker python -m spark.registry disable 3
```

- Each cycle the worker re-discovers every enabled source (all pages), de-duplicates repositories by
  case-insensitive full name, and publishes `data/portfolio.json` with per-source status. A source
  that fails (`not_found`, `no_access`, `sso_required`, `rate_limited`) is reported there and makes the
  run `partial`; other sources are unaffected.
- Removing a source never deletes repositories (or collected data). Delete orphans explicitly with
  `python -m spark.registry prune`.
- Full per-repository analytics (`data/users/<name>/...`, the dashboard) still run for `user` sources.
  Organization and explicit-repository sources currently appear in `portfolio.json` only.
- Back up `registry.db` (stop the worker, or use `sqlite3 registry.db ".backup out.db"`).

## Admin UI (sign-in, sources, tokens)

A third service, `api`, serves the admin API. It has no host port; the web container proxies `/api`
to it, so it is exactly as reachable as the dashboard (keep `BIND_ADDRESS` on the LAN). The
dashboard shows a **Sources** page only when the API answers; on GitHub Pages it never appears.

**First start**
1. Generate an encryption key once and keep it outside the database:
   `docker compose run --rm api python -m spark.api generate-key` -> set it as `SPARK_SECRET_KEY`
   (or point `SPARK_SECRET_KEY_FILE` at a secret file). Set it on the stack so both `api` and
   `worker` see it. Losing or changing it makes saved tokens unreadable (re-enter them).
2. Set `SPARK_ADMIN_USER` and `SPARK_ADMIN_PASSWORD` (12+ characters). The administrator is created
   on first start and the variables are ignored afterwards; **remove the password from the stack
   once you can sign in**. Alternatively run `docker compose exec api python -m spark.api create-admin`.
3. Open the dashboard, choose **Sources**, and sign in.

**What it does**
- **Sources:** add an organization, user or repository. Access is validated against GitHub first;
  a source that cannot be read is not saved and the error says what to fix. Disable, re-enable or
  remove sources; removing never deletes collected repositories.
- **Repositories:** include/exclude and assign to a client, project and application.
- **Tokens:** save fine-grained personal access tokens (read-only; one per user or organization),
  encrypted at rest. A token's expiry is tracked: the page warns when one is within 14 days, and a
  source whose token has expired reports `connection_unusable` instead of silently using another.
  Sources without a token use the stack's `GITHUB_TOKEN`.
- **Refresh now:** asks the worker to collect; it starts within seconds.

**Security notes**
- Passwords are stored as Argon2id hashes; session cookies are `HttpOnly`, `SameSite=Strict`, and only
  a hash of the session token is stored. Writes require a CSRF token and a matching `Origin`.
  Five failed sign-ins lock that username for 15 minutes. Changing the password signs everyone out.
- The API is plain HTTP on the LAN. Set `SPARK_COOKIE_SECURE=true` only behind HTTPS.
- Tokens are never returned by the API or written to logs. Back up `registry.db` and the key
  separately: the database alone cannot be used to recover saved tokens.
- `docker/smoke.sh` now also checks that the API refuses unauthenticated reads.
