# soccer-open-play

Find out whether an NYC park soccer field has a permit on it at a given date and time, or is likely free for open play.

- Plan: [docs/PLAN.md](docs/PLAN.md)
- Data-source validation scripts: [validation/](validation/README.md)

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

CI (`.github/workflows/ci.yml`) builds the image and runs the tests on every push and PR.
A second job builds the site data from the live APIs on `main` or on manual runs. To raise
the API rate limits, set an optional `SOCRATA_APP_TOKEN` repository secret.
