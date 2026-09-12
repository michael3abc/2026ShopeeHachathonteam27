FROM node:24.21.0-bookworm-slim AS build
WORKDIR /app
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web ./
ENV NEXT_TELEMETRY_DISABLED=1 API_BASE_URL=http://api:8000
RUN npm run build
FROM node:24.21.0-bookworm-slim
WORKDIR /app
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
ENV HOSTNAME=0.0.0.0 PORT=3000 NODE_ENV=production
CMD ["node", "server.js"]
