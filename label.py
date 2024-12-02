import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime
from tqdm import tqdm
import time

# Spotify API scopes
SCOPES = "playlist-modify-public playlist-modify-private playlist-read-private"

# Initialize Spotipy client
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
#    client_id=SPOTIFY_CLIENT_ID,
#    client_secret=SPOTIFY_CLIENT_SECRET,
#    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope=SCOPES
))

existing_tracks = []

def get_existing_playlist(user_id, playlist_name):
    """
    Check if the playlist exists and return its ID.
    """
    playlists = sp.user_playlists(user_id)
    for playlist in playlists['items']:
        if playlist is not None and 'name' in playlist and playlist['name'] == playlist_name:
            return playlist['id']
    return None

def get_tracks_in_playlist(playlist_id):
    """
    Retrieve all tracks from a playlist.
    """
    tracks = []
    results = sp.playlist_items(playlist_id)
    while results:
        tracks.extend(results['items'])
        results = sp.next(results) if results['next'] else None

    # Extract relevant track details
    return [{
        'track_id': item['track']['id'],
        'artist': item['track']['artists'][0]['name'],
        'title': item['track']['name'],
        'album_id': item['track']['album']['id']
    } for item in tracks if item['track']]

def search_albums_by_label(label_name, year, limit=50):
    """
    Search for albums released by a label in a given year.
    """
    query = f'label:"{label_name}" year:{year}'
    results = {"albums":{"total":1}}
    ret = []
    offset = 0
    while len(ret) < results["albums"]['total']:
        results = sp.search(q=query, type='album', limit=limit, offset=offset)
        ret += [{
            'album_id': album['id'],
            'release_date': album['release_date'],
            'name': album['name'],
            'artist': album['artists'][0]['name']
        } for album in results['albums']['items']]
        print(f"Got {results['albums']['total']}/{len(ret)} albums...")
        offset += 50
    return ret    

def get_tracks_from_album(album_id):
    """
    Get all tracks from a specific album.
    """
    results = sp.album_tracks(album_id)
    return [{'track_id': track['id'], 'artist': track['artists'][0]['name'], 'title': track['name']} for track in results['items']]

def filter_new_albums(existing_tracks, albums):
    existing_album_ids = {track['album_id'] for track in existing_tracks}
    new_albums = [album for album in albums if album['album_id'] not in existing_album_ids]
    return new_albums

def filter_new_tracks(existing_tracks, albums, all_tracks):
    """
    Filter out tracks and albums that are already in the playlist.
    """
    existing_album_ids = {track['album_id'] for track in existing_tracks}
    existing_track_keys = {(track['artist'], track['title']) for track in existing_tracks}

    # Exclude albums that are already seen
    new_albums = [album for album in albums if album['album_id'] not in existing_album_ids]

    # Filter tracks by excluding re-releases and duplicates
    new_tracks = []
    for track in all_tracks:
        key = (track['artist'], track['title'])
        if key not in existing_track_keys and track['artist'] != 'Spring Offensive':
            new_tracks.append(track)

    return new_tracks

def add_tracks_to_playlist_sorted(playlist_id, tracks):
    """
    Add tracks to a playlist, sorted by release date.
    """
    sorted_tracks = sorted(tracks, key=lambda t: t.get('release_date', '9999-99-99'))
    sorted_tracks_2 = []
    existing_keys = set()
    for track in sorted_tracks:
        key = (track['artist'], track['title'])
        if key in existing_keys: continue
        existing_keys.add(key)
        sorted_tracks_2.append(track)
    track_ids = [track['track_id'] for track in sorted_tracks_2]
    print("Actual tracks: "+str(len(track_ids)))
    for track_id in tqdm(track_ids):
        sp.playlist_add_items(playlist_id, [track_id])
        time.sleep(1.01)

def main():
    # Input record label and playlist details
    label_name = "This Never Happened" #input("Enter the record label name: ")
    current_year = datetime.now().year
    playlist_name = f"{label_name} in {current_year}"

    # Get user ID and existing playlist
    user_id = sp.current_user()['id']
    playlist_id = get_existing_playlist(user_id, playlist_name)

    for last_year in range(2016, current_year):
        last_playlist_name = f"{label_name} in {last_year}"
        last_playlist_id = get_existing_playlist(user_id, last_playlist_name)
        if last_playlist_id:
            print(f"Fetching existing tracks in {last_year} playlist...")
            existing_tracks.extend(get_tracks_in_playlist(last_playlist_id))
            print(f"{len(existing_tracks)} existing so far")

    # Create a new playlist if it doesn't exist
    if not playlist_id:
        print("Creating playlist")
        playlist_id = sp.user_playlist_create(user=user_id, name=playlist_name, public=False)['id']
    else:
        print(f"Playlist exists: {playlist_id}")

    print(f"Got {len(existing_tracks)} old tracks, fetching existing tracks in the playlist...")
    existing_tracks.extend(get_tracks_in_playlist(playlist_id))
    print(f"Got {len(existing_tracks)} total")

    # Search for albums released by the record label this year
    print(f"Searching for albums released by {label_name} in {current_year}...")
    albums = search_albums_by_label(label_name, current_year)

    print(f"Got {len(albums)}, filtering...")
    albums = filter_new_albums(existing_tracks, albums)

    # Get all tracks from the new albums
    print(f"Fetching tracks from {len(albums)} albums...")
    all_tracks = []
    for album in tqdm(albums):
        tries = 0
        while tries < 10:
            try:
                tracks = get_tracks_from_album(album['album_id'])
                break
            except:
                tries += 1
                time.sleep(tries)
        for track in tracks:
            track['release_date'] = album['release_date']  # Include release date for sorting
        all_tracks.extend(tracks)

    # Filter new tracks to exclude already added ones
    print(f"Filtering out already added tracks from {len(all_tracks)}...")
    new_tracks = filter_new_tracks(existing_tracks, albums, all_tracks)

    # Add new tracks to the playlist
    if new_tracks:
        print(f"Adding {len(new_tracks)} new tracks to the playlist...")
        add_tracks_to_playlist_sorted(playlist_id, new_tracks)
        print(f"Playlist '{playlist_name}' updated successfully!")
    else:
        print("No new tracks to add.")

if __name__ == "__main__":
    main()
