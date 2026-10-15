# Containerized URL Shortener

[![CI](https://github.com/Tomnem1/containerized-url-shortener/actions/workflows/pipeline.yaml/badge.svg)](https://github.com/Tomnem1/containerized-url-shortener/actions/workflows/pipeline.yaml)

A URL shortener REST API (FastAPI + PostgreSQL) with a production-style CI/CD and container workflow. The app is intentionally small; the focus is on how it is tested, packaged, published and run. Every pull request runs a GitHub Actions pipeline that lints the code, tests it against a real PostgreSQL database and builds the Docker image, and only changes that pass can be merged into the protected `main` branch. Each merge and each version tag publishes the image to [Docker Hub](https://hub.docker.com/r/sejrank/url-shortener), tagged with the commit ID it was built from. The whole stack (the app and PostgreSQL with a persistent volume) starts with one Docker Compose command, with health checks and automatic restarts. Configuration comes from environment variables; credentials live in a local `.env` file and in GitHub Secrets, never in the code.

**Tech stack**

- **CI/CD:** GitHub Actions
- **Containers:** Docker, Docker Compose
- **Registry:** Docker Hub
- **Database:** PostgreSQL 17
- **Application:** Python 3.12, FastAPI, Uvicorn, psycopg 3
- **Testing and linting:** pytest, ruff

## Architecture

```mermaid
flowchart LR
    dev[Developer] -- "pull request / merge" --> gh[GitHub]
    gh --> ci["GitHub Actions<br/>lint · tests · build"]
    ci -. "tests use" .-> cidb[("PostgreSQL 17<br/>service container")]
    ci -- "push image" --> hub[("Docker Hub<br/>sejrank/url-shortener")]

    subgraph compose["Docker Compose"]
        app["app<br/>FastAPI + Uvicorn<br/>:8000"] -- "DATABASE_URL<br/>db:5432" --> db[("db<br/>PostgreSQL 17")]
        db --- vol[("volume<br/>database-data")]
    end

    client[Client] -- "localhost:8000" --> app
```

- The **app** is stateless: every short link is stored in PostgreSQL, so the app container can be stopped, replaced or restarted without losing data.
- The **db** is reachable only inside the Compose network (no host port). The app finds it by its service name, `db`.
- The data survives container restarts, removals and rebuilds because it lives in the named volume `database-data`; it is lost only when the volume itself is deleted.
- Compose builds the app image from source. The image published by CI can be pulled separately with `docker pull sejrank/url-shortener`.

## Project layout

```
app/main.py            FastAPI app: endpoints, database access, startup (creates the table)
tests/test_main.py     pytest tests, run against a real PostgreSQL
Dockerfile             app image (python:3.12-slim, runtime dependencies only)
compose.yaml           app + db, health check, restart policies, volume
.github/workflows/     CI/CD pipeline
requirements.txt       pinned runtime dependencies
requirements-dev.txt   runtime + test and lint tools
.env.example           template for .env (placeholder values only)
```

## Quick start

Requires Docker with Docker Compose.

```bash
git clone https://github.com/Tomnem1/containerized-url-shortener.git
cd containerized-url-shortener
cp .env.example .env        # then set your own POSTGRES_PASSWORD (letters and digits only)
docker compose up -d --build
```

`db` starts first; `app` starts once `db` reports healthy. Check the status:

```bash
docker compose ps     # wait until db shows "(healthy)" and app is "Up"
```

Then try the API:

```bash
curl -s http://localhost:8000/health   # {"status":"ok"} once the app is ready
curl -s -X POST http://localhost:8000/shorten -H "Content-Type: application/json" -d '{"url": "https://example.com"}'
curl -i http://localhost:8000/<code>   # use the code from the previous response
```

Stop the stack with `docker compose down` (the data is kept). `docker compose down -v` also deletes the volume and all stored links.

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/shorten` | Body `{"url": "https://example.com"}`. Returns `{"short_url": "http://localhost:8000/<code>"}` (422 if the body is invalid). |
| `GET` | `/{code}` | Redirects (HTTP 307) to the original URL, or returns 404 if the code is unknown. |
| `GET` | `/health` | Runs `SELECT 1` against the database. Returns `{"status": "ok"}`, or HTTP 503 `{"status": "error", "database": "unreachable"}`. |

Interactive API docs are served at <http://localhost:8000/docs>.

## CI/CD pipeline

One workflow, [`.github/workflows/pipeline.yaml`](.github/workflows/pipeline.yaml), runs on every pull request into `main`, every merge to `main` and every version tag (`v*.*.*`):

```mermaid
flowchart LR
    pg[("start PostgreSQL 17<br/>service container")] --> lint[ruff check] --> test["pytest<br/>against PostgreSQL"] --> build[docker build]
    build -- "pull request" --> stop([image discarded])
    build -- "merge to main / tag" --> push["log in with GitHub Secrets<br/>push to Docker Hub"]
```

| Event | What runs | Published tags |
|---|---|---|
| Pull request into `main` | lint, tests, build | none |
| Merge into `main` | lint, tests, build, push | short commit ID (e.g. `581019b`) and `latest` |
| Git tag `vX.Y.Z` | lint, tests, build, push | `X.Y.Z` (e.g. `1.0.0`) and the short commit ID |

- The tests run against a PostgreSQL 17 **service container**: GitHub Actions starts it on the runner before the first step and removes it when the job ends, so every run starts with an empty database. The tests reach it at `localhost:5432` through `DATABASE_URL`, set on the "run tests" step. A broken SQL query fails the `ci` check, so the pull request cannot be merged.
- Every image is tagged with the commit ID it was built from, so a running image can be traced back to its exact code and rolled back to it.
- The Docker Hub token is stored in **GitHub Secrets**; the workflow file contains no credentials.

Images: [`sejrank/url-shortener`](https://hub.docker.com/r/sejrank/url-shortener). To publish a release, tag a commit on `main` and push the tag:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

## Branch protection

`main` is protected by a repository ruleset (`protect-main`):

- changes reach `main` only through a **pull request**
- the **`ci` check must pass** before merging
- **force pushes** and **deleting** the branch are blocked

No approving review is required, since this is a single-maintainer repository. On a team, this would be at least one.

Together with the pipeline this means that every commit on `main`, and every image on Docker Hub, has passed lint and the tests.

## Reliability

| Mechanism | Where | What it prevents |
|---|---|---|
| Database health check (`pg_isready`) | `compose.yaml`, `db` | Treating PostgreSQL as ready while it is still starting |
| `depends_on: condition: service_healthy` | `compose.yaml`, `app` | The app connecting too early and crashing at startup |
| `restart: unless-stopped` | both services | A crashed container staying down until someone notices |
| `/health` checks the database | `app/main.py` | Reporting "ok" while the database is down; returns 503 instead |

## Configuration

| Variable | Used by | Meaning |
|---|---|---|
| `POSTGRES_USER` | `db` | Database user created on first start |
| `POSTGRES_PASSWORD` | `db` | Password for that user (required) |
| `POSTGRES_DB` | `db` | Database created on first start |
| `DATABASE_URL` | `app` | `postgresql://USER:PASSWORD@HOST:PORT/DBNAME`. Compose builds it from the three values above with host `db` |

- The first three live in `.env` (template: [`.env.example`](.env.example)).
- `.env` is excluded from Git and from the Docker image.
- They are applied only when the volume is empty (first start); changing them later does not change an existing database.

The same code runs in every environment; only `DATABASE_URL` changes:

| Environment | Where `DATABASE_URL` is set | Host |
|---|---|---|
| Docker Compose | `compose.yaml` | `db` |
| CI | step "run tests" in `pipeline.yaml` | `localhost` (service container) |
| Local development | command line | `localhost` (test container) |

## Development

Requires Python 3.12, [uv](https://docs.astral.sh/uv/) and Docker. Set up the environment:

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements-dev.txt
```

The tests need a PostgreSQL. Start a throw-away test database (deleted when stopped, separate from the Compose data) and wait until it accepts connections:

```bash
docker run -d --rm --name test-db -e POSTGRES_PASSWORD=test -p 5432:5432 postgres:17
until docker exec test-db pg_isready -h localhost -U postgres; do sleep 1; done
```

Then lint and test:

```bash
ruff check .
DATABASE_URL=postgresql://postgres:test@localhost:5432/postgres pytest -v
```

Stop the test database with `docker stop test-db`. The password `test` only protects this temporary database.

## Design decisions

| Decision | Choice | Instead of | Why |
|---|---|---|---|
| Database access | psycopg 3 driver, plain SQL | SQLAlchemy (ORM) | A few queries on one table do not need an ORM; the exact SQL sent to PostgreSQL is readable in `app/main.py` |
| Database configuration | one `DATABASE_URL` | separate `DB_HOST`, `DB_USER`, ... variables | Industry convention; one variable to set in Compose and in CI |
| Passing `.env` to containers | `environment:` with `${VAR}` placeholders | `env_file: .env` | Only the listed variables reach the container, not the entire `.env` file |
| Tests' database | a PostgreSQL container (locally and as a service container in CI) | reusing the Compose database | Same engine as production; test data never touches real data |
| Pipeline triggers | pull requests into `main`, merges to `main`, version tags | a run on every push to any branch | No duplicate runs; every merge is verified again on `main` |
| Image tags | commit ID + `latest` on merge, `X.Y.Z` on release | `latest` only, or version tags only | Every image is traceable to a commit; releases get readable versions |
| Registry | Docker Hub, token in GitHub Secrets | GitHub Container Registry (GHCR) | The default public registry; credentials never in the repository |
| Base image | `python:3.12-slim` | full `python:3.12`, Alpine | Small and fast to pull, without the build issues of Alpine |
| Dependencies | everything pinned; test tools in `requirements-dev.txt` | only direct packages pinned; one requirements file | Reproducible builds; the image carries no test tooling |
| Restart policy | `unless-stopped` for both services | `always`, `on-failure` | Recovers from crashes, but respects a manual stop |
| `/health` | checks the database, 503 if unreachable | always "ok" while the process runs | Reports whether the service can actually do its job |

## Next steps

- **Readiness probe:** split `/health` into liveness (`/health`) and readiness (`/ready`, checks the database), the way Kubernetes liveness and readiness probes use them.
- **Container security:** run the app as a non-root user and scan the image with Trivy in CI.
- **Database migrations:** manage schema changes with Alembic instead of creating the table at startup.
- **Observability and deployment:** Prometheus metrics, and deployment to a server or Kubernetes.

## License

MIT, see [LICENSE](LICENSE).
