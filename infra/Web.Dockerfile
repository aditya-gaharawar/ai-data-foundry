# syntax=docker/dockerfile:1
FROM node:24-alpine@sha256:4eefa1bfce4197942661ef9148247d779ddf1bb0ee006d3294a467609de60724 AS build
WORKDIR /app
RUN --mount=type=secret,id=system_ca \
    NODE_EXTRA_CA_CERTS=/run/secrets/system_ca npm install -g pnpm@11.25.0
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/sdk-ts/package.json packages/sdk-ts/package.json
RUN --mount=type=secret,id=system_ca \
    NODE_EXTRA_CA_CERTS=/run/secrets/system_ca pnpm install --frozen-lockfile
COPY apps/web apps/web
COPY packages/sdk-ts packages/sdk-ts
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build
FROM node:24-alpine@sha256:4eefa1bfce4197942661ef9148247d779ddf1bb0ee006d3294a467609de60724
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0
COPY --from=build /app/apps/web/.next/standalone ./
COPY --from=build /app/apps/web/.next/static ./apps/web/.next/static
USER node
CMD ["node", "apps/web/server.js"]
