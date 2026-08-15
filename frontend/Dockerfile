FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Baked in at build time — Next.js inlines NEXT_PUBLIC_* into the client bundle.
ARG NEXT_PUBLIC_API_URL=https://contractor-ai-api.fly.dev
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

FROM node:20-slim AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public

ENV PORT=3000
EXPOSE 3000
CMD ["node", "server.js"]
