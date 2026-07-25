# 芙清 CRM - 前端生产镜像
# 多阶段：Node 构建 + 非特权 Nginx 托管静态（禁止生产 vite preview）

# Stage 1: 构建
# 固定 minor；digest 锁定流程见 docs/operating/docker-ports-and-images.md
FROM node:22.17.0-alpine AS builder
WORKDIR /app

# 官方 registry（与 frontend-vue3/.npmrc 一致）
COPY package.json package-lock.json .npmrc ./
# 有 overrides 后尽量不用 --legacy-peer-deps；若 peer 仍冲突再回退
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: 静态托管（非 root nginx）
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
