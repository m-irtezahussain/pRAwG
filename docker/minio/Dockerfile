# syntax=docker/dockerfile:1.7

FROM golang:1.24-bookworm AS build

ARG MINIO_COMMIT
RUN test -n "$MINIO_COMMIT" \
    && CGO_ENABLED=0 GOBIN=/out go install "github.com/minio/minio@${MINIO_COMMIT}"

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home --home-dir /home/minio minio \
    && mkdir -p /data \
    && chown 10001:10001 /data

COPY --from=build /out/minio /usr/local/bin/minio

USER 10001
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
