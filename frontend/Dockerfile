FROM node:22-slim AS base

WORKDIR /app
COPY package.json ./
RUN npm install

COPY . .

FROM base AS dev
CMD ["npm", "run", "dev", "--", "--host"]

FROM base AS build
RUN npm run build

FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
