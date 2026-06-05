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

FROM nginx:1.27-alpine
RUN rm -rf /usr/share/nginx/html/* /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN test -f /usr/share/nginx/html/index.html \
    && ls -la /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
