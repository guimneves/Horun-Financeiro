# Build de produção — serve os estáticos direto (nginx). VITE_BASE é o
# prefixo sob o qual o Core vai servir este módulo quando encaixado
# (ex. "/m/financeiro/"); default "/" funciona pra rodar o build
# standalone, fora do Core, sem precisar mudar nada.
FROM node:22-slim AS build
WORKDIR /app
# vendor/ (cópia do design-system do Core) precisa estar no contexto antes
# do npm ci — a dependência é "file:./vendor/horun-design-system"
COPY package.json package-lock.json ./
COPY vendor ./vendor
RUN npm ci
COPY . .
ARG VITE_BASE=/
RUN npm run build -- --base=$VITE_BASE

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
# 127.0.0.1, não "localhost": no Alpine, localhost resolve primeiro pra ::1
# e o nginx.conf só escuta IPv4 — o container ficava "(unhealthy)" mesmo
# servindo normalmente (mesmo sintoma do RE7S).
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:80/ || exit 1
