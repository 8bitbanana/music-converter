# Disables shuffle if the users playback is from an album

import spotify, requests, json

def main():
    username = "8bitbanana"
    scope = "user-read-playback-state user-modify-playback-state user-read-recently-played"
    auth = spotify.token(scope, username)
    headers = {
        "Authorization":"Bearer "+auth.token
    }
    r = requests.get("https://api.spotify.com/v1/me/player", headers=headers)
    playback_state = json.loads(r.content)
    if not playback_state['shuffle']: return
    if playback_state['context']['type'] == "album": return
    r = requests.get("https://api.spotify.com/v1/me/player/recently-played?limit=2",headers=headers)
    recent_tracks = json.loads(r.content)['items']
    if recent_tracks[0]['context']['uri'] != recent_tracks[1]['context']['uri']: return
    requests.put("https://api.spotify.com/v1/me/player/shuffle?state=false", headers=headers)

main()