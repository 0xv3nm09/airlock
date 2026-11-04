FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# server-mode build (no AIRLOCK_STATIC_BUILD): rewrites proxy /api/* to the backend
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
