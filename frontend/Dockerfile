# syntax=docker/dockerfile:1.7

FROM node:22-bookworm-slim AS dev

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

RUN chown node:node /app

USER node

COPY --chown=node:node package.json package-lock.json ./
RUN --mount=type=cache,target=/home/node/.npm,uid=1000,gid=1000 \
    npm ci

COPY --chown=node:node . .

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000').then(response => { if (!response.ok) process.exit(1) }).catch(() => process.exit(1))"]

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
