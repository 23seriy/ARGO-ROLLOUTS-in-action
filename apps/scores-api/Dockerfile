FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ARG APP_VERSION=v1
ENV APP_VERSION=${APP_VERSION}
EXPOSE 8080
CMD ["python", "app.py"]
