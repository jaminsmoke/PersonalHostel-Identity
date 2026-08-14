FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY static/ /usr/share/nginx/html/
COPY 20-identity-web.sh /docker-entrypoint.d/20-identity-web.sh
RUN chmod +x /docker-entrypoint.d/20-identity-web.sh

ENV IDENTITY_API_URL=http://localhost:8080

EXPOSE 80