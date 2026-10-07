# =============================================================================
# Frontend Dockerfile — Multi-stage production build
# =============================================================================

# ---- Base: Node.js 20 -------------------------------------------------------
FROM node:20-alpine AS base
WORKDIR /app

# ---- Dependencies -----------------------------------------------------------
FROM base AS dependencies
COPY package*.json ./
RUN npm ci --silent

# ---- Development: hot-reload via Vite ---------------------------------------
FROM dependencies AS development
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---- Build: compile for production ------------------------------------------
FROM dependencies AS builder
COPY . .
RUN npm run build

# ---- Production: serve with nginx -------------------------------------------
FROM nginx:1.27-alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80/healthz || exit 1

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
