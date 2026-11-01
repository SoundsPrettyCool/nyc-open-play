# Test and dev environment for soccer-open-play.
#
#   docker build -t soccer-open-play .
#   docker run --rm soccer-open-play                 # run the test suite (default)
#
# Where Docker Hub is rate-limited, pass a mirror:
#   docker build --build-arg BASE_IMAGE=mirror.gcr.io/library/python:3.12-slim -t soccer-open-play .
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /repo

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Run as a non-root user; data the build writes goes to a writable directory.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p app/site/data validation/out \
    && chown -R app:app /repo
USER app

CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "app/tests", "validation/tests"]
