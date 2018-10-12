import spotify, time, requests, json


spotify_username = "8bitbanana"
#spotify_scope = ""

auth = spotify.master_token("8bitbanana")

headers = {"authorization":"Bearer "+auth.token}

def main():
    r = requests.get("https://api.spotify.com/v1/me/player/currently-playing",headers=headers)
    data = json.loads(r.content)
    timestamp = data['timestamp']
    progress = data['progress_ms'] / 1000
    track_id = data['item']['id']

    print(data['item']['name'])

    r = requests.get("https://api.spotify.com/v1/audio-analysis/"+track_id, headers=headers)
    audio_analysis = json.loads(r.content)
    beats = [x['start'] for x in audio_analysis['beats']]
    bars = [x['start'] for x in audio_analysis['bars']]
    time_sig = audio_analysis['track']['time_signature']
    start_time = time.time()
    beatCount = 0
    while True:
        running_time = time.time() - start_time
        position = progress + running_time
        try:
            if position >= bars[0]:
                beatCount = 0
            if position >= beats[0]:
                beat = beats.pop(0)
                beatCount += 1
                print(beatCount)
        except IndexError:
            break

if __name__ == '__main__':
    while True: main()