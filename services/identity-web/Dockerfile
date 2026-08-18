FROM nginx:stable-alpine@sha256:97d490c12ba55b4946b01546d1c3ed324e8d41ab1c9fcb2a616aa470620e5b46

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY static/ /usr/share/nginx/html/
COPY 20-identity-web.sh /docker-entrypoint.d/20-identity-web.sh
RUN apk upgrade --no-cache \
    && chmod +x /docker-entrypoint.d/20-identity-web.sh \
    && sed -i 's#pid .*;#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /etc/nginx/conf.d

ENV IDENTITY_API_URL=http://localhost:8080

USER nginx

EXPOSE 8080
