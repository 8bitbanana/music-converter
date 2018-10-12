import spotify, requests, json, android

droid = android.Android()

mode_dict = {
    0:'minor',
    1:'major'
}

key_dict = {
    0:'c',
    1:'c#',
    2:'d',
    3:'d#',
    4:'e',
    5:'f',
    6:'f#',
    7:'g',
    8:'g#',
    9:'a',
    10:'a#',
    11:'b'
}

username = "8bitbanana"
scope = "user-read-playback-state"

def getKey():
    auth = spotify.token(scope, username)
    headers = {"authorization":"Bearer "+auth.token}
    current_track = json.loads(requests.get("https://api.spotify.com/v1/me/player", headers=headers).content)['item']['id']
    data = json.loads(requests.get("https://api.spotify.com/v1/audio-features/" + current_track, headers=headers).content)
    mode = mode_dict[data['mode']]
    key = key_dict[data['key']]
    return key.upper() + " " + mode.capitalize()

if __name__ == '__main__':
    key = getKey()
    droid.makeToast(key)