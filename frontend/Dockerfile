# Build de produção — serve os estáticos direto (nginx). VITE_BASE é o
# prefixo sob o qual o Core vai servir este módulo quando encaixado
# (ex. "/m/financeiro/"); default "/" funciona pra rodar o build
# standalone, fora do Core, sem precisar mudar nada.
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
ARG VITE_BASE=/
RUN npm run build -- --base=$VITE_BASE

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O - http://localhost:80/ || exit 1
