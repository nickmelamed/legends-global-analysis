# Built from the repo root because the logo and fonts are read from ../brand
# (see web/vite.config.ts).
FROM node:20.18.1-alpine AS build

WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
COPY brand /src/brand
RUN npm run build

FROM nginx:1.27.3-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/web/dist /usr/share/nginx/html
