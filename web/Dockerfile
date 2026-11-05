FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# rewrite destinations are baked into the build manifest — the backend URL must be
# set at BUILD time (the compose `environment` value alone does nothing for rewrites)
ENV AIRLOCK_API_URL=http://api:8000

COPY . .
# server-mode build (no AIRLOCK_STATIC_BUILD): rewrites proxy /api/* to the backend
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
