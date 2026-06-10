# Frontend Dockerfile — multi-stage build
# Stage 1: Build React app
FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm install --production=false
COPY . .
RUN npm run build

# Stage 2: Serve with nginx (includes API proxy to gateway)
FROM nginx:alpine

# Copy built React app to nginx html dir
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx config with API proxy
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]