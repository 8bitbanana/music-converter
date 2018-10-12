import requests, json, random
import spotify

scope = "playlist-modify-private playlist-read-private playlist-modify-public user-read-playback-state"

#username = input("Enter Username - ")
username = "8bitbanana"

# Authorisation!
tokenObj = spotify.token(scope, username)
token = tokenObj.token

headers = {
	'accept': 'application/json',
	'content-type': 'application/json',
        # americans
	'authorization': 'Bearer ' + token
        }

# TODO - The api splits the requests content into pages, with a maximum page
#        size of 50/100. Is there a module that can handle this, or will I
#        need to write one myself?
#        https://stackoverflow.com/questions/17777845/python-requests-arguments-dealing-with-api-pagination?utm_medium=organic&utm_source=google_rich_qa&utm_campaign=google_rich_qa
playlists_url = "https://api.spotify.com/v1/users/"+username+"/playlists?limit=50"
playlist_url = "https://api.spotify.com/v1/users/"+username+"/playlists/{}/tracks?limit=100"
move_url = "https://api.spotify.com/v1/users/"+username+"/playlists/{}/tracks"
playback_url = "https://api.spotify.com/v1/me/player"

def main():
    # Get the list of playlists
    r = requests.get(playlists_url, headers=headers)
    data = json.loads(r.content)
    playlists = data['items']
    # Get the currently playling playlist
    r = requests.get(playback_url, headers=headers)
    # If nothing is playing, the response is empty
    if len(r.content) < 5 or r.status_code != 200:
        currentID = None
        currentName = None
    else:
        data = json.loads(r.content)['context']
        # If they are not playing a playlist, type != playlist
        if data['type'] != "playlist":
            currentID = None
            currentName = None
        else:
            # Get the playlist id from the spotify uri
            currentID = data['uri'][data['uri'].index(":playlist:")+10:]
            currentName = None
            # Search for a playlist with that ID
            for playlist in playlists:
                if playlist['id'] == currentID:
                    currentName = playlist['name']
    # List all the options. "0" is set aside for the currently playing playlist,
    # and is only shown if it exists
    # This means the displayed indexes are shifted up by 1
    if currentID and currentName:
        print("[0] - [PLAYING] - {}".format(currentName))
    for index, playlist in enumerate(playlists):
        print("[{}] - {} ".format(index+1, playlist['name']))
    user_input = int(input("> "))
    if user_input == 0:
        playlist_id = currentID
    else:
        playlist_id = playlists[user_input-1]['id']
    print()
    # Get the playlists current list of tracks, in order
    r = requests.get(playlist_url.format(playlist_id), headers=headers)
    data = json.loads(r.content)
    tracks = data['items']
    for v,x in enumerate(tracks):
        track = x['track']
        print(v,track['name'])
    input()
    playlist_len = len(tracks)
    # Shuffle by shifting random tracks to the start of the playlist
    # 2*playlist_len for extra shuffleness
    for x in range(2*playlist_len):
        rn = random.randint(1,playlist_len-1)
        data = "{\"range_start\":RAND,\"range_length\":1,\"insert_before\":0}".replace("RAND", str(rn))
        requests.put(move_url.format(playlist_id),headers=headers,data=data)
        print(str(rn)+" ",end="")
    print("\n")
    # Get and print the playlist again to show the new shuffled order
    r = requests.get(playlist_url.format(playlist_id), headers=headers)
    data = json.loads(r.content)
    tracks = data['items']
    for v,x in enumerate(tracks):
        track = x['track']
        print(v,track['name'])
    input()
if __name__ == "__main__":
    main()
