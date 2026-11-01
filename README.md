# nyc-open-play

Find out whether an NYC park soccer field has a permit on it at a given date and time, or is likely free for open play.

- Plan: [docs/PLAN.md](docs/PLAN.md)
- Data-source validation scripts: [validation/](validation/README.md)

## Configuration

The data build needs one required setting. **It isn't hard-coded in the repo.**

| Name | Where | Required | What |
|---|---|---|---|
| `NYC_PARKS_SLOTS_API_URL` | GitHub **repository secret** (Settings → Secrets and variables → Actions → **Secrets**) | **Yes** | Base URL of the NYC Parks athletic-field slots API, without a query string. See `docs/VALIDATION_FINDINGS.md` §7. |
| `SOCRATA_APP_TOKEN` | GitHub **secret** | No | Raises NYC Open Data rate limits |

Locally, copy `.env.example` to `.env` (gitignored) and fill it in; Docker Compose reads it.
If it's missing, the build and the CI data jobs stop with an error that names it. It's a secret, not a variable,
so GitHub masks it as `***` in workflow logs and doesn't pass it to pull requests from forks.

## Development & testing

Everything runs in Docker, so local runs and CI use the same environment.

```bash
make test         # build the image and run all unit tests (no network needed)
make build-data   # download NYC Open Data into app/site/data (needs network)
make serve        # serve app/site at http://localhost:8000
make shell        # bash inside the container
```

Without `make`: `docker compose run --rm test`, `docker compose run --rm build-data`, `docker compose up web`.

If Docker Hub rate-limits you, use Google's mirror of the same image:
`make test BASE_IMAGE=mirror.gcr.io/library/python:3.12-slim`.

CI (`.github/workflows/ci.yml`) builds the image and runs the tests on every push and PR, on
GitHub's runners. The live-data jobs (the twice-daily refresh and the CI smoke test) run on a
**self-hosted Raspberry Pi runner**, because NYC Parks' CDN challenges GitHub's runners. Setup:
[`docs/RASPBERRY_PI.md`](docs/RASPBERRY_PI.md).
A second job builds the site data from the live APIs on `main` or on manual runs. To raise
the API rate limits, set an optional `SOCRATA_APP_TOKEN` repository secret.
