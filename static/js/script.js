let trackList = [];
let currentTrackIndex = -1;
let audioContext, source, filters;
let isShuffling = false;
let isRepeating = false;
let shuffledIndices = [];

// Inicjalizacja Web Audio API
function initAudioContext() {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const audioPlayer = document.getElementById('audio-player');
    source = audioContext.createMediaElementSource(audioPlayer);

    // Tworzenie filtrów equalizera (Bass, Mid, Treble)
    filters = [
        { freq: 60, gain: 0, type: 'lowshelf' },   // Bass
        { freq: 1000, gain: 0, type: 'peaking' },  // Mid
        { freq: 4000, gain: 0, type: 'highshelf' } // Treble
    ].map(filter => {
        const biquad = audioContext.createBiquadFilter();
        biquad.type = filter.type;
        biquad.frequency.value = filter.freq;
        biquad.gain.value = filter.gain;
        biquad.Q.value = 1;
        return biquad;
    });

    // Połączenie filtrów w łańcuch
    source.connect(filters[0]);
    for (let i = 0; i < filters.length - 1; i++) {
        filters[i].connect(filters[i + 1]);
    }
    filters[filters.length - 1].connect(audioContext.destination);
}

// Formatowanie czasu (mm:ss)
function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}:${secs < 10 ? '0' : ''}${secs}`;
}

function playTrack(index) {
    if (index < 0 || index >= trackList.length) return;

    currentTrackIndex = index;
    const track = trackList[currentTrackIndex];
    const audioPlayer = document.getElementById('audio-player');
    const playerCover = document.getElementById('player-cover');
    const playerTitle = document.getElementById('player-title');
    const playerArtist = document.getElementById('player-artist');
    const activity = document.getElementById('activity');
    const playPauseBtn = document.getElementById('play-pause-btn');
    const seekSlider = document.getElementById('seek-slider');
    const currentTime = document.getElementById('current-time');
    const duration = document.getElementById('duration');

    audioPlayer.src = `/music/${track.file_id}`;
    playerCover.src = track.cover ? `/cover/${track.cover}` : `/static/covers/default_cover.jpg`;
    playerTitle.textContent = track.title;
    playerArtist.textContent = track.artist;
    audioPlayer.play();

    activity.innerHTML = `
        <div class="playing">
            <div class="bar"></div>
            <div class="bar"></div>
            <div class="bar"></div>
            <div class="bar"></div>
            <p class="text-light mb-0 ms-2">Listening to: ${track.title} by ${track.artist}</p>
        </div>
    `;

    playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
    audioPlayer.onpause = () => {
        activity.innerHTML = '<p class="text-muted">Not playing</p>';
        playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
    };
    audioPlayer.onplay = () => {
        activity.innerHTML = `
            <div class="playing">
                <div class="bar"></div>
                <div class="bar"></div>
                <div class="bar"></div>
                <div class="bar"></div>
                <p class="text-light mb-0 ms-2">Listening to: ${track.title} by ${track.artist}</p>
            </div>
        `;
        playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
    };

    audioPlayer.onloadedmetadata = () => {
        seekSlider.max = audioPlayer.duration;
        duration.textContent = formatTime(audioPlayer.duration);
    };

    audioPlayer.ontimeupdate = () => {
        seekSlider.value = audioPlayer.currentTime;
        currentTime.textContent = formatTime(audioPlayer.currentTime);
        const progressPercent = (audioPlayer.currentTime / audioPlayer.duration) * 100;
        seekSlider.style.background = `linear-gradient(to right, #1db954 ${progressPercent}%, #2a2a3e ${progressPercent}%)`;
    };

    audioPlayer.onended = () => {
        if (isRepeating) {
            playTrack(currentTrackIndex);
        } else {
            playNextTrack();
        }
    };

    seekSlider.oninput = () => {
        audioPlayer.currentTime = seekSlider.value;
    };
}

function playNextTrack() {
    let nextIndex;
    if (isShuffling) {
        const remainingIndices = shuffledIndices.filter(i => i > currentTrackIndex);
        nextIndex = remainingIndices.length > 0 ? remainingIndices[0] : shuffledIndices[0];
    } else {
        nextIndex = (currentTrackIndex + 1) % trackList.length;
    }
    playTrack(nextIndex);
}

function playPrevTrack() {
    let prevIndex;
    if (isShuffling) {
        const previousIndices = shuffledIndices.filter(i => i < currentTrackIndex);
        prevIndex = previousIndices.length > 0 ? previousIndices[previousIndices.length - 1] : shuffledIndices[shuffledIndices.length - 1];
    } else {
        prevIndex = (currentTrackIndex - 1 + trackList.length) % trackList.length;
    }
    playTrack(prevIndex);
}

function shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

function downloadPlaylist() {
    const playlistUrl = document.getElementById('playlist-url').value;
    const downloadMessage = document.getElementById('download-message');
    downloadMessage.textContent = 'Downloading playlist in background...';
    downloadMessage.style.display = 'block';

    fetch('/download_playlist', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ url: playlistUrl })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            downloadMessage.textContent = data.message;
            downloadMessage.style.color = '#1db954';
            // Odśwież listę utworów po kilku sekundach
            setTimeout(() => {
                fetch('/get_music')
                    .then(response => response.json())
                    .then(newTrackList => {
                        trackList = newTrackList;
                        shuffledIndices = shuffleArray([...Array(trackList.length).keys()]);
                        renderTrackList();
                    });
            }, 5000);
        } else {
            downloadMessage.textContent = data.message;
            downloadMessage.style.color = '#dc3545';
        }
    })
    .catch(error => {
        downloadMessage.textContent = 'Error downloading playlist: ' + error;
        downloadMessage.style.color = '#dc3545';
    });
}

function addFavorite(filename) {
    window.location.href = `/favorite/add/${filename}`;
}

function removeFavorite(filename) {
    window.location.href = `/favorite/remove/${filename}`;
}

function renderTrackList() {
    const trackListDiv = document.getElementById('track-list');
    trackListDiv.innerHTML = '';
    trackList.forEach((track, index) => {
        const coverSrc = track.cover ? `/cover/${track.cover}` : `/static/covers/default_cover.jpg`;
        console.log(`Rendering track: ${track.title}, Cover: ${coverSrc}`);
        const trackCard = `
            <div class="col-md-4 col-lg-3 mb-4 track-item" data-title="${track.title.toLowerCase()}" data-artist="${track.artist.toLowerCase()}">
                <div class="card track-card">
                    <img src="${coverSrc}" class="card-img-top rounded-top" alt="Album Cover" onerror="this.src='/static/covers/default_cover.jpg'">
                    <div class="card-body">
                        <h5 class="card-title text-light">${track.title}</h5>
                        <p class="card-text text-muted">${track.artist}</p>
                        <div class="d-flex justify-content-between flex-wrap">
                            <button class="btn btn-primary btn-sm me-1 mb-1" onclick="playTrack(${index})"><i class="fas fa-play me-1"></i>Play</button>
                            <button class="btn btn-success btn-sm me-1 mb-1" onclick="addFavorite('${track.filename}')"><i class="fas fa-heart me-1"></i>Add</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        trackListDiv.innerHTML += trackCard;
    });
}

// Wyszukiwanie i obsługa odtwarzacza
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            const query = searchInput.value.toLowerCase();
            const tracks = document.querySelectorAll('.track-item');
            tracks.forEach(track => {
                const title = track.dataset.title;
                const artist = track.dataset.artist;
                if (title.includes(query) || artist.includes(query)) {
                    track.style.display = 'block';
                } else {
                    track.style.display = 'none';
                }
            });
        });
    }

    // Inicjalizacja listy utworów
    fetch('/get_music')
        .then(response => response.json())
        .then(data => {
            trackList = data;
            shuffledIndices = shuffleArray([...Array(trackList.length).keys()]);
            renderTrackList();
        });

    // Inicjalizacja Web Audio API
    initAudioContext();

    // Obsługa przycisku play/pause
    const playPauseBtn = document.getElementById('play-pause-btn');
    const audioPlayer = document.getElementById('audio-player');
    playPauseBtn.addEventListener('click', () => {
        if (audioPlayer.paused) {
            audioPlayer.play();
        } else {
            audioPlayer.pause();
        }
    });

    // Obsługa regulacji głośności
    const volumeSlider = document.getElementById('volume-slider');
    const volumeIcon = document.getElementById('volume-icon');
    volumeSlider.addEventListener('input', () => {
        audioPlayer.volume = volumeSlider.value / 100;
        const progressPercent = volumeSlider.value;
        volumeSlider.style.background = `linear-gradient(to right, #1db954 ${progressPercent}%, #2a2a3e ${progressPercent}%)`;
        if (audioPlayer.volume === 0) {
            volumeIcon.className = 'fas fa-volume-mute text-light me-2';
        } else if (audioPlayer.volume < 0.5) {
            volumeIcon.className = 'fas fa-volume-down text-light me-2';
        } else {
            volumeIcon.className = 'fas fa-volume-up text-light me-2';
        }
    });

    // Obsługa przycisków odtwarzania
    const shuffleBtn = document.getElementById('shuffle-btn');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const repeatBtn = document.getElementById('repeat-btn');

    shuffleBtn.addEventListener('click', () => {
        isShuffling = !isShuffling;
        shuffleBtn.classList.toggle('active', isShuffling);
        if (isShuffling) {
            shuffledIndices = shuffleArray([...Array(trackList.length).keys()]);
        }
    });

    prevBtn.addEventListener('click', () => {
        playPrevTrack();
    });

    nextBtn.addEventListener('click', () => {
        playNextTrack();
    });

    repeatBtn.addEventListener('click', () => {
        isRepeating = !isRepeating;
        repeatBtn.classList.toggle('active', isRepeating);
    });

    // Obsługa equalizera
    const presetSelect = document.getElementById('preset-select');
    const sliders = {
        bass: document.getElementById('eq-bass'),
        mid: document.getElementById('eq-mid'),
        treble: document.getElementById('eq-treble')
    };

    const presets = {
        flat: [0, 0, 0],
        pop: [4, 2, 4],
        rock: [4, -2, 4],
        bass: [6, 0, -2],
        classical: [2, 4, 6]
    };

    presetSelect.addEventListener('change', () => {
        const preset = presets[presetSelect.value];
        filters.forEach((filter, index) => {
            filter.gain.value = preset[index];
            sliders[Object.keys(sliders)[index]].value = preset[index];
        });
    });

    Object.keys(sliders).forEach((key, index) => {
        sliders[key].addEventListener('input', () => {
            filters[index].gain.value = sliders[key].value;
            presetSelect.value = 'custom';
        });
    });
});