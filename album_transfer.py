# Seamlessly (ish) transfers the users playback from a track on a playlist (or similar) to the same track on an album

import spotify, requests, json, sys
username = "8bitbanana"
scope = "user-read-playback-state user-modify-playback-state"
auth = spotify.token(scope, username)
headers = {
    "Authorization":"Bearer "+auth.token
}
r = requests.get("https://api.spotify.com/v1/me/player/currently-playing", headers=headers)
currently_playing = json.loads(r.content)
if currently_playing['context']['type'] == "album":
    print("An album is already playing")
    sys.exit()
album_id = currently_playing['item']['album']['id']
track_id = currently_playing['item']['id']
position_ms = currently_playing['progress_ms']
data = {
    "context_uri":"spotify:album:"+album_id,
    "offset": {"uri":"spotify:track:"+track_id}
}
requests.put("https://api.spotify.com/v1/me/player/play", headers=headers, json=data)
requests.put("https://api.spotify.com/v1/me/player/seek?position_ms="+str(position_ms), headers=headers)