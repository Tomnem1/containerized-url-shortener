FROM python:3.12-slim
WORKDIR /containerized-url-shortener
COPY ./requirements.txt /containerized-url-shortener/
RUN pip install --no-cache-dir -r requirements.txt
COPY ./app /containerized-url-shortener/app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
