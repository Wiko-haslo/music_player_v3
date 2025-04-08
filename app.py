import os
import json
import re
import subprocess
import io
import requests
from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, session
from mutagen import File
from PIL import Image
import mutagen.opus
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

app = Flask(__name__)
app.secret_key = 'super_secret_key'  # Klucz do sesji użytkownika

# Ścieżki do folderów
MUSIC_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), 'music'))
COVERS_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), 'static', 'covers'))
DATA_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
USERS_FILE = os.path.join(DATA_FOLDER, 'users.json')
FAVORITES_FILE = os.path.join(DATA_FOLDER, 'favorites.json')

# Utwórz foldery, jeśli nie istnieją
os.makedirs(MUSIC_FOLDER, exist_ok=True)
os.makedirs(COVERS_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

# Inicjalizuj pliki JSON, jeśli nie istnieją lub są puste
def initialize_json_file(file_path):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        with open(file_path, 'w') as f:
            json.dump({}, f)

initialize_json_file(USERS_FILE)
initialize_json_file(FAVORITES_FILE)

# Ustawienia Spotify API
SPOTIFY_CLIENT_ID = 'TWOJ_CLIENT_ID'  # Wstaw swój Client ID
SPOTIFY_CLIENT_SECRET = 'TWOJ_CLIENT_SECRET'  # Wstaw swój Client Secret
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))

# Stały limit pobierania
DOWNLOAD_LIMIT = 100  # Możesz zmienić tę wartość na inną, np. 50

# Funkcja do pobierania okładki z URL-a
def download_cover(url, cover_path):
    response = requests.get(url)
    if response.status_code == 200:
        img = Image.open(io.BytesIO(response.content))
        img = img.resize((300, 300), Image.Resampling.LANCZOS)
        img.save(cover_path, 'JPEG')

# Funkcja do pobierania listy utworów
def get_music_files():
    music_files = []
    for file in os.listdir(MUSIC_FOLDER):
        if file.endswith(('.opus', '.mp3', '.flac')):
            file_path = os.path.join(MUSIC_FOLDER, file)
            try:
                audio = File(file_path)
                title = audio.get('title', [file])[0] if audio else file
                artist = audio.get('artist', ['Unknown'])[0] if audio else 'Unknown'
                
                # Wyciąganie okładki albumu z metadanych
                cover_filename = None
                if audio and 'APIC:' in audio.tags:
                    cover_data = audio.tags['APIC:'].data
                    cover_filename = f"{file}.jpg"
                    cover_path = os.path.join(COVERS_FOLDER, cover_filename)
                    if not os.path.exists(cover_path):
                        img = Image.open(io.BytesIO(cover_data))
                        img = img.resize((300, 300), Image.Resampling.LANCZOS)
                        img.save(cover_path, 'JPEG')
                
                # Sprawdzenie, czy istnieje ręcznie dodana okładka
                if not cover_filename:
                    # Szukaj okładki z pełną nazwą pliku (np. "C418 - Minecraft.opus.jpg")
                    possible_cover = f"{file}.jpg"
                    possible_cover_path = os.path.join(COVERS_FOLDER, possible_cover)
                    if os.path.exists(possible_cover_path):
                        cover_filename = possible_cover
                    else:
                        # Jeśli nie znaleziono, spróbuj z nazwą bez rozszerzenia (np. "C418 - Minecraft.jpg")
                        base_filename = os.path.splitext(file)[0]
                        possible_cover = f"{base_filename}.jpg"
                        possible_cover_path = os.path.join(COVERS_FOLDER, possible_cover)
                        if os.path.exists(possible_cover_path):
                            cover_filename = possible_cover
                        else:
                            cover_filename = 'default_cover.jpg'
                
                music_files.append({
                    'filename': file,
                    'title': title,
                    'artist': artist,
                    'cover': cover_filename
                })
            except Exception as e:
                print(f"Error reading {file}: {e}")
                music_files.append({
                    'filename': file,
                    'title': file,
                    'artist': 'Unknown',
                    'cover': 'default_cover.jpg'
                })
    return music_files

# Funkcja do pobierania polubionych utworów użytkownika
def get_favorites(username):
    with open(FAVORITES_FILE, 'r') as f:
        if os.path.getsize(FAVORITES_FILE) == 0:
            return []
        favorites_data = json.load(f)
    return favorites_data.get(username, [])

# Endpoint logowania
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        with open(USERS_FILE, 'r') as f:
            if os.path.getsize(USERS_FILE) == 0:
                users = {}
            else:
                users = json.load(f)

        if username in users and users[username] == password:
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')

# Endpoint rejestracji
@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')

    with open(USERS_FILE, 'r') as f:
        if os.path.getsize(USERS_FILE) == 0:
            users = {}
        else:
            users = json.load(f)

    if username in users:
        return render_template('login.html', error='Username already exists')

    users[username] = password
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

    session['username'] = username
    return redirect(url_for('index'))

# Endpoint wylogowania
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# Główna strona
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    music_files = get_music_files()
    username = session['username']
    favorites = get_favorites(username)
    return render_template('index.html', music_files=music_files, username=username, favorites=favorites)

# Strona z polubionymi utworami
@app.route('/favorites')
def favorites():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    favorites = get_favorites(username)
    music_files = get_music_files()
    favorite_files = [track for track in music_files if track['filename'] in favorites]
    return render_template('favorites.html', music_files=favorite_files, username=username)

# Endpoint do pobierania listy utworów
@app.route('/get_music')
def get_music():
    music_files = get_music_files()
    return jsonify(music_files)

# Endpoint do pobierania playlisty
@app.route('/download_playlist', methods=['POST'])
def download_playlist():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401

    data = request.get_json()
    playlist_url = data.get('url')

    if not playlist_url or not re.match(r'https://open\.spotify\.com/playlist/[\w\d]+', playlist_url):
        return jsonify({'status': 'error', 'message': 'Invalid Spotify playlist URL'}), 400

    try:
        # Krok 1: Pobierz metadane playlisty z Spotify API
        playlist_id = playlist_url.split('/')[-1].split('?')[0]
        playlist = sp.playlist(playlist_id)
        tracks = playlist['tracks']['items']
        
        # Ogranicz liczbę utworów do pobrania do stałego limitu
        tracks_to_download = tracks[:DOWNLOAD_LIMIT]
        
        # Mapa tytuł -> URL okładki
        cover_urls = {}
        for item in tracks_to_download:
            track = item['track']
            title = track['name']
            artist = track['artists'][0]['name']
            album = track['album']
            cover_url = album['images'][0]['url'] if album['images'] else None
            if cover_url:
                track_key = f"{artist} - {title}".lower()
                cover_urls[track_key] = cover_url

        # Krok 2: Utwórz tymczasowy plik z listą utworów do pobrania
        temp_playlist_file = os.path.join(DATA_FOLDER, 'temp_playlist.txt')
        with open(temp_playlist_file, 'w', encoding='utf-8') as f:
            for item in tracks_to_download:
                track = item['track']
                title = track['name']
                artist = track['artists'][0]['name']
                f.write(f"{artist} - {title}\n")

        # Krok 3: Pobierz utwory za pomocą spotdl
        result = subprocess.run(
            ['spotdl', 'download', temp_playlist_file, '--output', MUSIC_FOLDER, '--format', 'opus', '--threads', '1', '--max-retries', '5'],
            capture_output=True,
            text=True
        )

        # Usuń tymczasowy plik
        os.remove(temp_playlist_file)

        if result.returncode != 0:
            print(f"spotdl stderr: {result.stderr}")
            print(f"spotdl stdout: {result.stdout}")
            return jsonify({'status': 'error', 'message': 'Failed to download playlist: ' + result.stderr}), 500

        # Krok 4: Pobierz okładki dla pobranych utworów
        downloaded_files = []
        for file in os.listdir(MUSIC_FOLDER):
            if file.endswith(('.opus', '.mp3', '.flac')):
                file_path = os.path.join(MUSIC_FOLDER, file)
                try:
                    audio = File(file_path)
                    title = audio.get('title', [file])[0] if audio else file
                    artist = audio.get('artist', ['Unknown'])[0] if audio else 'Unknown'
                    track_key = f"{artist} - {title}".lower()

                    # Sprawdź, czy mamy URL okładki z Spotify
                    if track_key in cover_urls:
                        cover_filename = f"{file}.jpg"
                        cover_path = os.path.join(COVERS_FOLDER, cover_filename)
                        if not os.path.exists(cover_path):
                            download_cover(cover_urls[track_key], cover_path)
                    downloaded_files.append(file)
                except Exception as e:
                    print(f"Error processing cover for {file}: {e}")

        # Krok 5: Unikanie duplikatów
        unique_tracks = set()
        final_files = []
        skipped_files = 0

        for file in downloaded_files:
            file_path = os.path.join(MUSIC_FOLDER, file)
            try:
                audio = File(file_path)
                title = audio.get('title', [file])[0] if audio else file
                artist = audio.get('artist', ['Unknown'])[0] if audio else 'Unknown'
                track_id = f"{title.lower()} - {artist.lower()}"  # Unikalny identyfikator

                if track_id in unique_tracks:
                    # Jeśli utwór już istnieje (na podstawie tytułu i artysty), usuń go
                    os.remove(file_path)
                    skipped_files += 1
                    continue

                unique_tracks.add(track_id)
                final_files.append(file)
            except Exception as e:
                print(f"Error reading {file}: {e}")
                if file in final_files:
                    os.remove(file_path)
                    skipped_files += 1
                else:
                    final_files.append(file)

        # Krok 6: Policz wszystkie utwory w folderze music/
        total_files = len([f for f in os.listdir(MUSIC_FOLDER) if f.endswith(('.opus', '.mp3', '.flac'))])

        return jsonify({
            'status': 'success',
            'message': f'Downloaded {len(final_files)} tracks, skipped {skipped_files} duplicates. Total tracks in library: {total_files}'
        })
    except Exception as e:
        print(f"Exception in download_playlist: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Endpoint do dodawania do polubionych
@app.route('/add_favorite', methods=['POST'])
def add_favorite():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401

    data = request.get_json()
    filename = data.get('filename')
    username = session['username']

    with open(FAVORITES_FILE, 'r') as f:
        if os.path.getsize(FAVORITES_FILE) == 0:
            favorites_data = {}
        else:
            favorites_data = json.load(f)

    if username not in favorites_data:
        favorites_data[username] = []

    if filename not in favorites_data[username]:
        favorites_data[username].append(filename)
        with open(FAVORITES_FILE, 'w') as f:
            json.dump(favorites_data, f)
        return jsonify({'status': 'success', 'message': 'Added to favorites'})
    else:
        return jsonify({'status': 'error', 'message': 'Already in favorites'})

# Endpoint do usuwania z polubionych
@app.route('/remove_favorite', methods=['POST'])
def remove_favorite():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401

    data = request.get_json()
    filename = data.get('filename')
    username = session['username']

    with open(FAVORITES_FILE, 'r') as f:
        if os.path.getsize(FAVORITES_FILE) == 0:
            favorites_data = {}
        else:
            favorites_data = json.load(f)

    if username in favorites_data and filename in favorites_data[username]:
        favorites_data[username].remove(filename)
        with open(FAVORITES_FILE, 'w') as f:
            json.dump(favorites_data, f)
        return jsonify({'status': 'success', 'message': 'Removed from favorites'})
    else:
        return jsonify({'status': 'error', 'message': 'Not in favorites'})

# Endpoint do serwowania plików muzycznych
@app.route('/music/<filename>')
def serve_music(filename):
    file_path = os.path.join(MUSIC_FOLDER, filename)
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return jsonify({'status': 'error', 'message': 'File not found'}), 404
    print(f"Serving file: {file_path}")
    return send_from_directory(MUSIC_FOLDER, filename)

# Uruchomienie aplikacji
if __name__ == '__main__':
    # Dla lokalnego uruchamiania
    app.run(debug=True)
else:
    # Dla Render
    import os
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)