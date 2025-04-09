# Użyj oficjalnego obrazu Pythona jako bazy
FROM python:3.11

# Zainstaluj ffmpeg i inne zależności systemowe
RUN apt-get update && apt-get install -y ffmpeg

# Ustaw katalog roboczy
WORKDIR /app

# Skopiuj pliki projektu
COPY . .

# Zainstaluj zależności Pythona
RUN pip install --no-cache-dir -r requirements.txt

# Ustaw zmienne środowiskowe (opcjonalnie, można ustawić w Render)
ENV SPOTIPY_CLIENT_ID="twój_client_id"
ENV SPOTIPY_CLIENT_SECRET="twój_client_secret"
ENV SERVICE_ACCOUNT_JSON='{"type": "service_account", "project_id": "...", ...}'

# Uruchom aplikację za pomocą Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]