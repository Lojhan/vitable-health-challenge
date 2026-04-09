# Multi-stage Dockerfile for Vue.js frontend
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy application code
COPY . .

# Build the application
RUN npm run build

# Runtime stage
FROM node:22-alpine

WORKDIR /app

# Install serve to run the built app
RUN npm install -g serve

# Copy built application from builder
COPY --from=builder /app/dist ./dist

# Create a non-root user for security
RUN addgroup -g 1000 appgroup && adduser -D -u 1000 -G appgroup appuser
USER appuser

# Expose port for frontend server
EXPOSE 3000

# Serve the built application
CMD ["serve", "-s", "dist", "-l", "3000"]
