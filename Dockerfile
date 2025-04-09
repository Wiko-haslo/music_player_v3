# Użyj oficjalnego obrazu Pythona jako bazy
FROM python:3.11

# Zainstaluj ffmpeg i inne zależności systemowe
RUN apt-get update && apt-get install -y ffmpeg

# Zaktualizuj pip i zainstaluj wheel
RUN pip install --upgrade pip && pip install wheel

# Ustaw katalog roboczy
WORKDIR /app

# Skopiuj pliki projektu
COPY . .

# Zainstaluj zależności Pythona
RUN pip install --no-cache-dir -r requirements.txt

# Uruchom aplikację za pomocą Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]