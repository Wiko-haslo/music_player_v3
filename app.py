import os
import json
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from flask import Flask, render_template, request, redirect, url_for, flash, session
from mutagen.opus import OpusFile  # Używamy mutagen.opus do obsługi plików .opus
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
        playlist_id = playlist_url.split("/")[-1].split("?")[0]
        results = sp.playlist_tracks(playlist_id)
        tracks = results["items"]

        for item in tracks:
            track = item["track"]
            track_name = track["name"]
            artist_name = track["artists"][0]["name"]
            album_cover_url = track["album"]["images"][0]["url"] if track["album"]["images"] else None
            filename = f"{artist_name} - {track_name}.opus"  # Zmieniamy na .opus

            # Pobierz okładkę, jeśli istnieje
            if album_cover_url:
                cover_filename = f"{artist_name} - {track_name}.jpg"
                download_cover(album_cover_url, cover_filename)

            # Pobierz utwór w formacie .opus
            os.system(f"spotdl '{track_name} {artist_name}' --format opus --output {MUSIC_FOLDER}/{filename}")
    except Exception as e:
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
    for filename in os.listdir(MUSIC_FOLDER):
        if filename.endswith(".opus"):  # Zmieniamy na .opus
            file_path = os.path.join(MUSIC_FOLDER, filename)
            try:
                audio = OpusFile(file_path)
                cover_path = os.path.join(COVERS_FOLDER, f"{filename[:-5]}.jpg")  # .opus ma 5 znaków
                if not os.path.exists(cover_path):
                    cover_path = None
                songs.append({
                    "filename": filename,
                    "title": filename[:-5],  # Usuwamy .opus z nazwy
                    "duration": audio.info.length,
                    "cover": cover_path
                })
            except Exception as e:
                print(f"Error loading {filename}: {str(e)}")
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
@app.route("/", methods=["GET", "POST"])
def index():
    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        playlist_url = request.form.get("playlist_url")
        if playlist_url:
            download_playlist(playlist_url)
            flash("Playlist downloaded successfully!", "success")
            return redirect(url_for("index"))

    # Wczytaj listę utworów
    songs = load_songs()
    return render_template("index.html", songs=songs)

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
        file_path = os.path.join(MUSIC_FOLDER, filename)
        if os.path.exists(file_path):
            try:
                audio = OpusFile(file_path)
                cover_path = os.path.join(COVERS_FOLDER, f"{filename[:-5]}.jpg")
                if not os.path.exists(cover_path):
                    cover_path = None
                songs.append({
                    "filename": filename,
                    "title": filename[:-5],
                    "duration": audio.info.length,
                    "cover": cover_path
                })
            except Exception as e:
                print(f"Error loading favorite {filename}: {str(e)}")

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

# Strona z ulubionymi (opcjonalna, jeśli masz osobny endpoint)
@app.route("/favorites_page")
def favorites_page():
    return redirect(url_for("favorites"))

# Uruchom aplikację tylko lokalnie
if __name__ == '__main__':
    app.run(debug=True)