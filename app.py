import os
import json
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from PIL import Image
import requests
from io import BytesIO

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Zmień na bezpieczny klucz w produkcji

# Ścieżki do folderów
MUSIC_FOLDER = "music"
COVERS_FOLDER = "static/covers"
DATA_FOLDER = "data"

# Upewnij się, że foldery istnieją
if not os.path.exists(MUSIC_FOLDER):
    os.makedirs(MUSIC_FOLDER)
if not os.path.exists(COVERS_FOLDER):
    os.makedirs(COVERS_FOLDER)
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# Konfiguracja Spotify API
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))

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

# Funkcja do pobierania okładki albumu
def download_cover(url, filename):
    try:
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        img = img.resize((300, 300))  # Zmiana rozmiaru okładki
        img.save(os.path.join(COVERS_FOLDER, filename))
    except Exception as e:
        print(f"Error downloading cover for {filename}: {str(e)}")

# Funkcja do pobierania playlisty Spotify w formacie .opus
def download_playlist(playlist_url):
    try:
        print(f"Starting playlist download: {playlist_url}")  # Debug
        playlist_id = playlist_url.split("/")[-1].split("?")[0]
        print(f"Extracted playlist ID: {playlist_id}")  # Debug
        results = sp.playlist_tracks(playlist_id)
        tracks = results["items"]
        print(f"Found {len(tracks)} tracks in playlist")  # Debug

        for item in tracks:
            track = item["track"]
            track_name = track["name"]
            artist_name = track["artists"][0]["name"]
            album_cover_url = track["album"]["images"][0]["url"] if track["album"]["images"] else None
            filename = f"{artist_name} - {track_name}.opus"
            print(f"Processing track: {filename}")  # Debug

            # Pobierz okładkę, jeśli istnieje
            if album_cover_url:
                cover_filename = f"{artist_name} - {track_name}.jpg"
                print(f"Downloading cover: {cover_filename}")  # Debug
                download_cover(album_cover_url, cover_filename)
            else:
                print("No album cover available")  # Debug

            # Pobierz utwór w formacie .opus
            command = f"spotdl '{track_name} {artist_name}' --format opus --output \"{MUSIC_FOLDER}/{filename}\""
            print(f"Running command: {command}")  # Debug
            result = os.system(command)
            if result == 0:
                print(f"Successfully downloaded: {filename}")  # Debug
            else:
                print(f"Failed to download: {filename}, spotdl exit code: {result}")  # Debug
                flash(f"Failed to download {filename}", "error")
    except Exception as e:
        print(f"Error downloading playlist: {str(e)}")  # Debug
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

# Funkcja do wczytywania utworów (bez mutagen.opus)
def load_songs():
    songs = []
    print(f"Looking for songs in folder: {MUSIC_FOLDER}")  # Debug
    if not os.path.exists(MUSIC_FOLDER):
        print(f"Music folder {MUSIC_FOLDER} does not exist!")
        return songs

    for filename in os.listdir(MUSIC_FOLDER):
        print(f"Found file: {filename}")  # Debug
        if filename.endswith(".opus"):
            # Rozdziel nazwę pliku na artystę i tytuł
            base_name = filename[:-5]  # Usuń ".opus"
            parts = base_name.split(" - ")
            artist = parts[0] if len(parts) > 1 else "Unknown Artist"
            song_title = parts[1] if len(parts) > 1 else base_name

            # Sprawdź, czy istnieje okładka
            cover_filename = f"{base_name}.jpg"
            cover_path = cover_filename if os.path.exists(os.path.join(COVERS_FOLDER, cover_filename)) else None

            songs.append({
                "filename": filename,
                "title": song_title,
                "artist": artist,
                "duration": 0,  # Pomijamy duration, bo nie używamy mutagen
                "cover": cover_filename  # Zwracamy nazwę pliku okładki (bez ścieżki)
            })
            print(f"Loaded song: {filename}, Artist: {artist}, Title: {song_title}, Cover: {cover_filename}")  # Debug
    print(f"Total songs loaded: {len(songs)}")  # Debug
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
        print(f"User favorites for {session['username']}: {user_favorites}")  # Debug
    except (FileNotFoundError, json.JSONDecodeError):
        user_favorites = []
        print("Favorites file not found or empty")  # Debug

    songs = []
    for filename in user_favorites:
        file_path = os.path.join(MUSIC_FOLDER, filename)
        print(f"Checking favorite file: {file_path}")  # Debug
        if os.path.exists(file_path):
            # Rozdziel nazwę pliku na artystę i tytuł
            base_name = filename[:-5]  # Usuń ".opus"
            parts = base_name.split(" - ")
            artist = parts[0] if len(parts) > 1 else "Unknown Artist"
            song_title = parts[1] if len(parts) > 1 else base_name

            # Sprawdź, czy istnieje okładka
            cover_filename = f"{base_name}.jpg"
            cover_path = cover_filename if os.path.exists(os.path.join(COVERS_FOLDER, cover_filename)) else None

            songs.append({
                "filename": filename,
                "title": song_title,
                "artist": artist,
                "duration": 0,  # Pomijamy duration
                "cover": cover_filename
            })
            print(f"Loaded favorite song: {filename}, Artist: {artist}, Title: {song_title}, Cover: {cover_filename}")  # Debug

    print(f"Total favorite songs loaded: {len(songs)}")  # Debug
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

    download_playlist(playlist_url)
    return jsonify({"status": "success", "message": "Playlist downloaded successfully!"})

# Endpoint do pobierania utworu
@app.route("/download_track/<filename>")
def download_track(filename):
    return send_from_directory(MUSIC_FOLDER, filename, as_attachment=True)

# Uruchom aplikację tylko lokalnie
if __name__ == '__main__':
    app.run(debug=True)