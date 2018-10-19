import string

def id_matching(service, text):
    requirements = {
        "spotify": {
            "length": 22,
            "chars": string.ascii_letters + string.digits
        },
        "youtube": {
            "length": 11,
            "chars": string.ascii_letters + string.digits + "_-"
        }
    }
    if not service in requirements:
        raise ValueError("Invalid service for id_matching")
    substrings = []
    current_substring = ""
    for x in text:
        if x in requirements[service]['chars']:
            current_substring += x
        else:
            if current_substring:
                substrings.append(current_substring)
                current_substring = ""
    if current_substring:
        substrings.append(current_substring)
    return [x for x in substrings if len(x) == requirements[service]['length']]


spotify_tracks = [
    "spotify:track:6rqhFgbbKwnb9MLmUQDhG6",
    "6rqhFgbbKwnb9MLmUQDhG6",
    "6rqhFgbbKwnb9MLmUQDhG62",
    "http://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6"
]
youtube_tracks = [
    "http://youtu.be/-wtIMTCHWuI",
    "http://www.youtube.com/watch?v=-wtIMTCHWuI",
    "youtu.be/-wtIMTCHWuI"
]

for track in spotify_tracks: print(track, id_matching("spotify",track))
for track in youtube_tracks: print(track, id_matching("youtube",track))