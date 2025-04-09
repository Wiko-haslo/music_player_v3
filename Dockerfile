# Użyj oficjalnego obrazu Pythona jako bazy
FROM python:3.11

# Zainstaluj ffmpeg i inne zależności systemowe
RUN apt-get update && apt-get install -y ffmpeg

# Zaktualizuj pip, setuptools i wheel
RUN pip install --upgrade pip setuptools wheel

# Ustaw katalog roboczy
WORKDIR /app

# Skopiuj pliki projektu
COPY . .

# Zainstaluj spotdl bez zależności, aby uniknąć pykakasi
RUN pip install --no-cache-dir spotdl==4.2.6 --no-deps

# Zainstaluj pozostałe zależności z requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Uruchom aplikację za pomocą Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]