# app.py
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st
from collections import Counter

# ---------- Spotify setup ----------
# 실제 배포할 땐 client_id/secret은 환경변수나 별도 config에서 읽는 게 좋음
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id="315a0b8d76314d19b3b2de3f13f8d2b8",
        client_secret="14d51a4c5ce7407eb4657a62239d0981",
        redirect_uri="http://127.0.0.1:8888/callback",
        scope="playlist-read-private",
    )
)

# ---------- Mood from genres ----------
def mood_from_genres(genres):
    if not genres:
        return "unknown"
    g = " ".join(genres).lower()
    if any(x in g for x in ["lo-fi", "lofi", "chill", "ambient", "study"]):
        return "chill"
    if any(x in g for x in ["hip hop", "rap", "trap", "drill"]):
        return "hype"
    if any(x in g for x in ["r&b", "soul", "ballad"]):
        return "emotional"
    if any(x in g for x in ["edm", "house", "techno", "dance"]):
        return "dance"
    if any(x in g for x in ["jazz", "jazz ballads", "cool jazz"]):
        return "smooth"
    if any(x in g for x in ["metal", "hardcore"]):
        return "intense"
    return "mixed"

def analyze_playlist(playlist_url: str):
    playlist_id = playlist_url.split("/")[-1].split("?")[0]
    
    # Collect ALL tracks using pagination
    tracks = []
    artist_ids = set()
    offset = 0
    limit = 100  # max per request
    
    while True:
        results = sp.playlist_items(playlist_id, offset=offset, limit=limit)
        
        if not results["items"]:
            break  # no more items
        
        for item in results["items"]:
            track = item["track"]
            if not track:
                continue
            
            # Skip tracks without artists (local files, podcasts, unavailable tracks)
            if "artists" not in track or not track["artists"]:
                continue
            
            t_artists = track["artists"]
            tracks.append(
                {
                    "id": track["id"],
                    "name": track["name"],
                    "artists": ", ".join(a["name"] for a in t_artists),
                    "artist_ids": [a["id"] for a in t_artists if a.get("id")],
                }
            )
            for a in t_artists:
                if a.get("id"):
                    artist_ids.add(a["id"])
        
        # Check if there are more pages
        if results["next"] is None:
            break  # we got all items
        
        offset += limit  # move to next batch
    
    # Get artist info in batches of 50
    artist_ids = list(artist_ids)
    artists_info = {}
    for i in range(0, len(artist_ids), 50):
        chunk = artist_ids[i:i+50]
        resp = sp.artists(chunk)
        for art in resp["artists"]:
            artists_info[art["id"]] = {
                "name": art["name"],
                "genres": art["genres"],
                "popularity": art["popularity"],
            }

    # Attach mood/genre/popularity to each track
    playlist_moods = []
    genre_counter = Counter()

    for t in tracks:
        artist_id = t["artist_ids"][0] if t["artist_ids"] else None
        artist_data = artists_info.get(artist_id, {})
        genres = artist_data.get("genres", [])
        popularity = artist_data.get("popularity", None)
        mood = mood_from_genres(genres)

        t["genres"] = genres
        t["artist_popularity"] = popularity
        t["mood"] = mood

        if genres:
            genre_counter.update(genres)
        playlist_moods.append(mood)

    mood_distribution = Counter(playlist_moods)

    summary = {
        "total_tracks": len(tracks),
        "dominant_mood": mood_distribution.most_common(1)[0][0] if mood_distribution else "unknown",
        "top_genre": genre_counter.most_common(1)[0][0] if genre_counter else "unknown",
    }

    return summary, tracks, mood_distribution, genre_counter


# ---------- Streamlit UI ----------
st.title("Spotify Playlist Mood (Genre-based)")

playlist_url = st.text_input("Spotify playlist URL")

if st.button("Analyze") and playlist_url:
    with st.spinner("Analyzing playlist..."):
        summary, tracks, mood_dist, genre_counter = analyze_playlist(playlist_url)

    st.subheader("Summary")
    st.write(summary)

    st.subheader("Mood distribution")
    st.bar_chart({m: c for m, c in mood_dist.items()})

    st.subheader("Top genres")
    st.bar_chart(dict(genre_counter.most_common(10)))

    st.subheader("Tracks")
    st.dataframe(
        [
            {
                "Name": t["name"],
                "Artists": t["artists"],
                "Mood": t["mood"],
                "Genres": ", ".join(t["genres"][:3]),
                "Artist popularity": t["artist_popularity"],
            }
            for t in tracks
        ]
    )
