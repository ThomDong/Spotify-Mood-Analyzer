# app.py
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st
from collections import Counter
import pandas as pd
import kagglehub
from kagglehub import KaggleDatasetAdapter

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

@st.cache_data
def load_spotify_dataset():
    df = kagglehub.load_dataset(
        KaggleDatasetAdapter.PANDAS,
        "rodolfofigueroa/spotify-12m-songs",
        "tracks_features.csv",  # specify the CSV file name
    )
    
    # Check what columns exist
    print("Dataset columns:", df.columns.tolist())
    print("First 5 records:")
    print(df.head())
    
    # Convert to dict keyed by track ID for fast lookup
    # The column is likely 'id' or 'track_id' - we'll confirm from the output
    if 'id' in df.columns:
        df_dict = df.set_index("id").to_dict("index")
    elif 'track_id' in df.columns:
        df_dict = df.set_index("track_id").to_dict("index")
    else:
        raise ValueError(f"Could not find track ID column. Available columns: {df.columns.tolist()}")
    
    return df_dict


spotify_features = load_spotify_dataset()

# ---------- Mood from audio features ----------
def classify_mood(valence, energy):
    if valence is None or energy is None:
        return "unknown"
    if valence > 0.6 and energy > 0.6:
        return "happy"
    if valence < 0.4 and energy < 0.4:
        return "sad"
    if valence > 0.5 and energy < 0.4:
        return "calm"
    if valence < 0.5 and energy > 0.6:
        return "energetic"
    return "mixed"

def analyze_playlist(playlist_url: str):
    playlist_id = playlist_url.split("/")[-1].split("?")[0]
    
    tracks = []
    offset = 0
    limit = 100
    
    while True:
        results = sp.playlist_items(playlist_id, offset=offset, limit=limit)
        
        if not results["items"]:
            break
        
        for item in results["items"]:
            track = item["track"]
            if not track:
                continue
            
            if "artists" not in track or not track["artists"]:
                continue
            
            t_id = track["id"]
            t_name = track["name"]
            t_artists = ", ".join(a["name"] for a in track["artists"])
            
            # Try to find this track in the Kaggle dataset
            features = spotify_features.get(t_id, {})
            
            valence = features.get("valence", None)
            energy = features.get("energy", None)
            danceability = features.get("danceability", None)
            tempo = features.get("tempo", None)
            
            mood = classify_mood(valence, energy)
            
            tracks.append({
                "id": t_id,
                "name": t_name,
                "artists": t_artists,
                "valence": valence,
                "energy": energy,
                "danceability": danceability,
                "tempo": tempo,
                "mood": mood,
            })
        
        if results["next"] is None:
            break
        
        offset += limit
    
    # Compute mood distribution
    playlist_moods = [t["mood"] for t in tracks]
    mood_distribution = Counter(playlist_moods)
    
    # Compute averages
    valid_valences = [t["valence"] for t in tracks if t["valence"] is not None]
    valid_energies = [t["energy"] for t in tracks if t["energy"] is not None]
    
    avg_valence = sum(valid_valences) / len(valid_valences) if valid_valences else None
    avg_energy = sum(valid_energies) / len(valid_energies) if valid_energies else None
    
    summary = {
        "total_tracks": len(tracks),
        "tracks_with_features": sum(1 for t in tracks if t["valence"] is not None),
        "avg_valence": round(avg_valence, 3) if avg_valence else "N/A",
        "avg_energy": round(avg_energy, 3) if avg_energy else "N/A",
        "dominant_mood": mood_distribution.most_common(1)[0][0] if mood_distribution else "unknown",
    }
    
    return summary, tracks, mood_distribution

# ---------- Streamlit UI ----------
st.title("Spotify Playlist Mood Analyzer (Kaggle Dataset)")

playlist_url = st.text_input("Spotify playlist URL")

if st.button("Analyze") and playlist_url:
    with st.spinner("Analyzing playlist..."):
        summary, tracks, mood_dist = analyze_playlist(playlist_url)
    
    st.subheader("Summary")
    st.write(summary)
    
    st.subheader("Mood distribution")
    st.bar_chart({m: c for m, c in mood_dist.items()})
    
    st.subheader("Tracks")
    st.dataframe(
        [
            {
                "Name": t["name"],
                "Artists": t["artists"],
                "Mood": t["mood"],
                "Valence": t["valence"],
                "Energy": t["energy"],
                "Danceability": t["danceability"],
            }
            for t in tracks
        ]
    )
