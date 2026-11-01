# Shortcuts for the Docker test environment. Override the base image where Docker Hub
# is rate-limited:  make test BASE_IMAGE=mirror.gcr.io/library/python:3.12-slim
BASE_IMAGE ?= python:3.12-slim
export BASE_IMAGE

.PHONY: image test build-data serve shell

image:
	docker compose build test

test: image
	docker compose run --rm test

build-data: image
	mkdir -p app/site/data
	docker compose run --rm --user "$$(id -u):$$(id -g)" build-data

serve: image
	docker compose up web

shell: image
	docker compose run --rm test bash
