FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:stable-alpine@sha256:97d490c12ba55b4946b01546d1c3ed324e8d41ab1c9fcb2a616aa470620e5b46

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY 20-web-negocio.sh /docker-entrypoint.d/20-web-negocio.sh
COPY --from=build /app/dist /usr/share/nginx/html/
RUN apk upgrade --no-cache \
    && chmod +x /docker-entrypoint.d/20-web-negocio.sh \
    && sed -i 's#pid .*;#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /etc/nginx/conf.d

ENV NEGOCIO_API_URL=http://localhost:8082

USER nginx

EXPOSE 8080