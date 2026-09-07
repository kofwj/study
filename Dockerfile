# 阶段1：构建前端
FROM node:20-alpine AS build
ARG APP_REVISION=dev
ENV APP_REVISION=$APP_REVISION
WORKDIR /app
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
COPY VERSION ./VERSION
RUN printf '%s\n' "$APP_REVISION" > ./REVISION
RUN npm run build

# 阶段2：运行后端 + 托管前端产物
FROM python:3.11-slim
ARG APP_REVISION=dev
ENV APP_REVISION=$APP_REVISION
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY data/ ./data/
COPY VERSION ./VERSION
RUN printf '%s\n' "$APP_REVISION" > ./REVISION
COPY --from=build /app/dist ./frontend/dist
ENV SUNSHINE_DB=/data/sunshine.db
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]