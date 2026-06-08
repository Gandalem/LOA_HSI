FROM node:20-alpine AS build
WORKDIR /app/frontend

COPY package.json ./
RUN npm config set registry https://registry.npmjs.org/ \
    && npm install --no-audit --no-fund

COPY index.html ./index.html
COPY vite.config.js ./vite.config.js
COPY src ./src
RUN npm run build \
    && test -f /app/frontend/dist/index.html \
    && ls -la /app/frontend/dist

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --chown=101:101 --from=build /app/frontend/dist/ /usr/share/nginx/html/
COPY --chown=101:101 nginx.conf /etc/nginx/conf.d/default.conf
RUN test -f /usr/share/nginx/html/index.html \
    && ls -la /usr/share/nginx/html \
    && chmod -R a-w /usr/share/nginx/html /etc/nginx/conf.d/default.conf
USER 101
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
