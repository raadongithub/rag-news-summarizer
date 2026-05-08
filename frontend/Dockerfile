FROM node:20-alpine AS base

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy source (bind mount in dev overrides this, but needed for build)
COPY . .

EXPOSE 3000

# In dev: hot reload via next dev
CMD ["npm", "run", "dev"]
