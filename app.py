import os
import io
import json
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from PIL import Image
import requests
from io import BytesIO
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
import time
import threading

# Utwórz plik service-account.json z zmiennej środowiskowej
SERVICE_ACCOUNT_JSON = os.getenv("SERVICE_ACCOUNT_JSON")
if SERVICE_ACCOUNT_JSON:
    with open("service-account.json", "w") as f:
        f.write(SERVICE_ACCOUNT_JSON)
else:
    if not os.path.exists("service-account.json"):
        raise FileNotFoundError("SERVICE_ACCOUNT_JSON not set and service-account.json not found")

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Ścieżki do folderów (lokalne, tymczasowe)
MUSIC_FOLDER = "music"
COVERS_FOLDER = "static/covers"
DATA_FOLDER = "data"

# Upewnij się, że foldery istnieją lokalnie
for folder in [MUSIC_FOLDER, COVERS_FOLDER, DATA_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Konfiguracja Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'service-account.json'
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

# ID folderu na Google Drive (zastąp swoim ID folderu)
GOOGLE_DRIVE_FOLDER_ID = '1xLshqBxIQeGFZoYp44h50HDV-3Hylg-_'  # Wstaw ID folderu MusicPlayerFiles

# Funkcja do przesyłania pliku na Google Drive z ponawianiem
def upload_to_drive(file_path, file_name, folder_id, retries=3):
    for attempt in range(retries):
        try:
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            media = MediaFileUpload(file_path)
            file = drive_service.files().create(
                body=file_metadata, media_body=media, fields='id').execute()
            print(f"Uploaded {file_name} to Google Drive with ID: {file.get('id')}")
            return file.get('id')
        except HttpError as e:
            if e.resp.status in [429, 503]:
                print(f"Rate limit exceeded, retrying {attempt + 1}/{retries}...")
                time.sleep(2 ** attempt)
            else:
                raise e
    raise Exception(f"Failed to upload {file_name} after {retries} retries")

# Funkcja do przesyłania pliku z bufora w pamięci na Google Drive
def upload_to_drive_from_buffer(buffer, file_name, folder_id, retries=3):
    for attempt in range(retries):
        try:
            buffer.seek(0)  # Upewnij się, że bufor jest na początku
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            media = MediaFileUpload(buffer, mimetype='image/jpeg')
            file = drive_service.files().create(
                body=file_metadata, media_body=media, fields='id').execute()
            print(f"Uploaded {file_name} to Google Drive with ID: {file.get('id')}")
            return file.get('id')
        except HttpError as e:
            if e.resp.status in [429, 503]:
                print(f"Rate limit exceeded, retrying {attempt + 1}/{retries}...")
                time.sleep(2 ** attempt)
            else:
                raise e
    raise Exception(f"Failed to upload {file_name} after {retries} retries")

# Funkcja do wyszukiwania pliku na Google Drive
def find_file_on_drive(filename, folder_id):
    escaped_filename = filename.replace("'", "\\'")
    query = f"'{folder_id}' in parents and name = '{escaped_filename}' and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    return files[0]['id'] if files else None

# Konfiguracja Spotify API
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SERVICE_ACCOUNT_JSON = os.getenv("SERVICE_ACCOUNT_JSON")

if not all([SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SERVICE_ACCOUNT_JSON]):
    raise ValueError("Missing required environment variables: SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, or SERVICE_ACCOUNT_JSON")

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET
))

# Funkcja do zapisu danych użytkownika
def save_user(username, password):
    users_file = os.path.join(DATA_FOLDER, "users.json")
    try:
        with open(users_file, "r") as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users = {}
    
    users[username] = password
    with open(users_file, "w") as f:
        json.dump(users, f)

# Funkcja do sprawdzania użytkownika
def check_user(username, password):
    users_file = os.path.join(DATA_FOLDER, "users.json")
    try:
        with open(users_file, "r") as f:
            users = json.load(f)
        return users.get(username) == password
    except (FileNotFoundError, json.JSONDecodeError):
        return False

# Funkcja do zapisywania metadanych piosenki
def save_song_metadata(artist, title, song_file_id, cover_file_id):
    songs_file = os.path.join(DATA_FOLDER, "songs.json")
    try:
        with open(songs_file, "r") as f:
            songs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        songs = []

    songs.append({
        "artist": artist,
        "title": title,
        "filename": f"{artist} - {title}.opus",
        "song_file_id": song_file_id,
        "cover_file_id": cover_file_id
    })

    with open(songs_file, "w") as f:
        json.dump(songs, f)
    print(f"Saved metadata for {artist} - {title}, Song ID: {song_file_id}, Cover ID: {cover_file_id}")

# Funkcja do pobierania okładki albumu
def download_cover(url, filename):
    try:
        print(f"Starting download of cover from URL: {url}")
        # Krok 1: Pobierz obraz
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        print(f"Response status code: {response.status_code}")
        response.raise_for_status()
        print(f"Cover downloaded successfully, size: {len(response.content)} bytes")

        # Krok 2: Otwórz i przetwórz obraz
        img = Image.open(BytesIO(response.content))
        print(f"Image opened successfully, format: {img.format}, size: {img.size}")
        img = img.resize((300, 300))
        print("Image resized to 300x300")

        # Krok 3: Zapisz obraz do pamięci (zamiast na dysk)
        img_buffer = io.BytesIO()
        img.save(img_buffer, "JPEG", quality=95)
        print(f"Image saved to memory buffer, size: {img_buffer.getbuffer().nbytes} bytes")

        # Krok 4: Prześlij na Google Drive
        print(f"Uploading cover to Google Drive: {filename}")
        file_id = upload_to_drive_from_buffer(img_buffer, filename, GOOGLE_DRIVE_FOLDER_ID)
        print(f"Cover uploaded to Google Drive with ID: {file_id}")
        return file_id
    except requests.exceptions.RequestException as e:
        print(f"Error downloading cover from URL {url}: {str(e)}")
        return None
    except IOError as e:
        print(f"Error processing image for {filename}: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error in download_cover for {filename}: {str(e)}")
        return None

# Funkcja do pobierania playlisty w tle
def download_playlist_async(playlist_url):
    try:
        print(f"Starting playlist download in background: {playlist_url}")
        playlist_id = playlist_url.split("/")[-1].split("?")[0]
        print(f"Extracted playlist ID: {playlist_id}")
        results = sp.playlist_tracks(playlist_id)
        tracks = results["items"]
        print(f"Found {len(tracks)} tracks in playlist")

        for item in tracks:
            track = item["track"]
            track_name = track["name"]
            artist_name = track["artists"][0]["name"]
            album_cover_url = track["album"]["images"][0]["url"] if track["album"]["images"] else None
            filename = f"{artist_name} - {track_name}.opus"

            # Pobierz okładkę, jeśli istnieje
            cover_file_id = None
            if album_cover_url:
                cover_filename = f"{artist_name} - {track_name}.jpg"
                cover_file_id = download_cover(album_cover_url, cover_filename)
            else:
                print("No album cover available")

            # Pobierz utwór w formacie .opus
            command = f"spotdl '{track_name} {artist_name}' --format opus --output \"{MUSIC_FOLDER}/{filename}\""
            print(f"Running command: {command}")
            result = os.system(command)
            if result == 0:
                print(f"Successfully downloaded: {filename}")
                # Prześlij utwór na Google Drive
                song_file_id = upload_to_drive(os.path.join(MUSIC_FOLDER, filename), filename, GOOGLE_DRIVE_FOLDER_ID)
                # Zapisz metadane piosenki
                save_song_metadata(artist_name, track_name, song_file_id, cover_file_id)
            else:
                print(f"Failed to download: {filename}, spotdl exit code: {result}")
                flash(f"Failed to download {filename}", "error")
        flash("Playlist downloaded successfully!", "success")
    except Exception as e:
        print(f"Error downloading playlist: {str(e)}")
        flash(f"Error downloading playlist: {str(e)}", "error")

# Funkcja do zarządzania ulubionymi
def manage_favorite(username, filename, action):
    favorites_file = os.path.join(DATA_FOLDER, "favorites.json")
    try:
        with open(favorites_file, "r") as f:
            favorites = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        favorites = {}

    if username not in favorites:
        favorites[username] = []

    if action == "add" and filename not in favorites[username]:
        favorites[username].append(filename)
    elif action == "remove":
        favorites[username] = [f for f in favorites[username] if f != filename]

    with open(favorites_file, "w") as f:
        json.dump(favorites, f)

# Funkcja do wczytywania utworów
def load_songs():
    songs = []
    songs_file = os.path.join(DATA_FOLDER, "songs.json")
    try:
        with open(songs_file, "r") as f:
            song_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("No songs.json found, loading songs from Google Drive as fallback")
        # Fallback: Wczytaj piosenki z Google Drive, jeśli songs.json nie istnieje
        query = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed = false"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        for file in files:
            filename = file['name']
            if filename.endswith(".opus"):
                base_name = filename[:-5]
                parts = base_name.split(" - ")
                artist = parts[0] if len(parts) > 1 else "Unknown Artist"
                song_title = parts[1] if len(parts) > 1 else base_name
                cover_filename = f"{base_name}.jpg"
                cover_file_id = find_file_on_drive(cover_filename, GOOGLE_DRIVE_FOLDER_ID)
                songs.append({
                    "filename": filename,
                    "file_id": file['id'],
                    "title": song_title,
                    "artist": artist,
                    "duration": 0,
                    "cover": cover_file_id
                })
                print(f"Loaded song: {filename}, Artist: {artist}, Title: {song_title}, Cover ID: {cover_file_id}")
    else:
        for song in song_data:
            songs.append({
                "filename": song["filename"],
                "file_id": song["song_file_id"],
                "title": song["title"],
                "artist": song["artist"],
                "duration": 0,
                "cover": song["cover_file_id"]
            })
            print(f"Loaded song: {song['filename']}, Artist: {song['artist']}, Title: {song['title']}, Cover ID: {song['cover_file_id']}")
    print(f"Total songs loaded: {len(songs)}")
    return songs

# Strona logowania
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if check_user(username, password):
            session["username"] = username
            flash("Logged in successfully!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "error")
    return render_template("login.html")

# Strona rejestracji
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        save_user(username, password)
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("login.html")

# Strona główna
@app.route("/", methods=["GET"])
def index():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("index.html")

# Strona ulubionych
@app.route("/favorites")
def favorites():
    if "username" not in session:
        return redirect(url_for("login"))

    favorites_file = os.path.join(DATA_FOLDER, "favorites.json")
    try:
        with open(favorites_file, "r") as f:
            favorites = json.load(f)
        user_favorites = favorites.get(session["username"], [])
    except (FileNotFoundError, json.JSONDecodeError):
        user_favorites = []

    songs = []
    for filename in user_favorites:
        file_id = find_file_on_drive(filename, GOOGLE_DRIVE_FOLDER_ID)
        if file_id:
            base_name = filename[:-5]
            parts = base_name.split(" - ")
            artist = parts[0] if len(parts) > 1 else "Unknown Artist"
            song_title = parts[1] if len(parts) > 1 else base_name
            cover_filename = f"{base_name}.jpg"
            cover_file_id = find_file_on_drive(cover_filename, GOOGLE_DRIVE_FOLDER_ID)

            songs.append({
                "filename": filename,
                "file_id": file_id,
                "title": song_title,
                "artist": artist,
                "duration": 0,
                "cover": cover_file_id
            })

    return render_template("favorites.html", songs=songs)

# Dodaj/usuń z ulubionych
@app.route("/favorite/<action>/<filename>")
def favorite(action, filename):
    if "username" not in session:
        return redirect(url_for("login"))

    manage_favorite(session["username"], filename, action)
    if action == "add":
        flash("Added to favorites!", "success")
    else:
        flash("Removed from favorites!", "success")
    return redirect(request.referrer or url_for("index"))

# Wylogowanie
@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))

# Endpoint do pobierania listy utworów w formacie JSON
@app.route("/get_music", methods=["GET"])
def get_music():
    if "username" not in session:
        return redirect(url_for("login"))
    songs = load_songs()
    return jsonify(songs)

# Endpoint do pobierania playlisty
@app.route("/download_playlist", methods=["POST"])
def download_playlist_endpoint():
    if "username" not in session:
        return redirect(url_for("login"))

    data = request.get_json()
    playlist_url = data.get("url") if data else None
    if not playlist_url:
        return jsonify({"status": "error", "message": "Please provide a playlist URL"}), 400

    # Uruchom pobieranie w tle
    thread = threading.Thread(target=download_playlist_async, args=(playlist_url,))
    thread.start()
    return jsonify({"status": "success", "message": "Playlist download started in the background!"})

# Endpoint do serwowania plików muzycznych (ze strumieniowaniem)
@app.route("/music/<file_id>")
def serve_music(file_id):
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Downloaded {int(status.progress() * 100)}%")

        fh.seek(0)
        return Response(
            fh,
            mimetype="audio/ogg",
            headers={"Content-Disposition": f"inline; filename={file_id}.opus"}
        )
    except Exception as e:
        print(f"Error serving music file {file_id}: {str(e)}")
        return jsonify({"status": "error", "message": f"File {file_id} not found"}), 404

# Endpoint do serwowania okładek
@app.route("/cover/<file_id>")
def serve_cover(file_id):
    if not file_id or file_id == "None":
        return jsonify({"status": "error", "message": "No cover file ID provided"}), 404

    try:
        file_metadata = drive_service.files().get(fileId=file_id, fields="name").execute()
        filename = file_metadata.get("name", "cover.jpg")
        request = drive_service.files().get_media(fileId=file_id)
        file_content = request.execute()
        return Response(
            file_content,
            mimetype="image/jpeg",
            headers={"Content-Disposition": f"inline; filename={filename}"}
        )
    except Exception as e:
        print(f"Error serving cover file {file_id}: {str(e)}")
        return jsonify({"status": "error", "message": f"File {file_id} not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)