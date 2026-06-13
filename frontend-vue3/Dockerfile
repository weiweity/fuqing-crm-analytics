# Sample CRM - 前端 Dockerfile
# 多阶段构建：Node构建 + nginx托管（非特权，安全增强）

# Stage 1: 构建
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: 托管（非特权 nginx，以 nginx 用户运行）
FROM nginxinc/nginx-unprivileged:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
