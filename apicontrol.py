import spotify, youtube, requests, json, time, copy

TMR_DELAY = 5            # How long to wait for after an error 429 is received (too many requests)
ERR_DELAY = 1            # How long to wait before retrying on an error 5XX
RETRY_ATTEMPTS = 5       # How many times to retry after an error 5XX before giving up
DURATION_WARN = 0.2      # Decimal difference between two services duration differences to raise an error
PAGINATION_PAGES = 20    # How many pages to follow with a paging JSON object
SPOTIFY_IDS_CHUNKS = 100 # Size of the track id "chunks" that spotify_write_playlists sends

# Standardised track object to use throughout the program. Album optional
class Track:
    def __init__(self, title, artist, album=None):
        self.title = title
        self.artist = artist
        self.album = album
        self.services = {
            "spotify":{
                "id":None,
                "link":"https://open.spotify.com/track/{}",
                "duration":None
            },
            "youtube": {
                "id": None,
                "link": "https://www.youtube.com/watch?v={}",
                "duration": None
            },
            "local": {
                "id": None,
                "link": "",
                "duration": None
            }
        }

    def __repr__(self):
        return "Track Object - " + self.title + " by " + self.artist

    def __eq__(self, other):
        if type(other) == type(self):
            return self.title == other.title and self.artist == other.artist and self.album == other.album and self.services == other.services
        return False

    # Updates the specified service with the specified id
    def update_service(self, service, link):
        if service in self.services.keys():
            self.services[service]['id'] = link
        else:
            raise ValueError("Service must be one of "+str(list(self.services.keys()))+" not " + service)

    # Updates the specified service with the specified duration. Does not compleate if the specified duration
    # is too far removed from the currently saved durations (see DURATION_WARN)
    # If force if True, update the duration anyway, but still returning true/false
    def update_duration(self, service, duration, force=False):
        if service in self.services.keys():
            if duration == None:
                if force: self.services[service]['duration'] = None
                return False
            # Calculate average of all current durations
            total = 0
            amount = 0
            currentDuration = self.get_duration()
            if currentDuration:
                difference = abs(currentDuration - duration) / max(currentDuration, duration)
                if difference >= DURATION_WARN:
                    if force: self.services[service]['duration'] = duration
                    return False
                else:
                    self.services[service]['duration'] = duration
                    return True
            else:
                self.services[service]['duration'] = duration
                return True
        else:
            raise ValueError("Service must be one of "+str(list(self.services.keys()))+" not " + service)

    def get_link(self, service):
        if service in self.services.keys():
            return self.services[service]['link'].format(self.services[service]['id'])

    def get_duration(self):
        total = 0
        amount = 0
        for x in self.services:
            if self.services[x]['duration']:
                total += self.services[x]['duration']
                amount += 1
        if total: return total/amount
        else: return None

    # Returns a dictionary of the current track object
    def to_dict(self):
        d = {
            "title":self.title,
            "artist":self.artist,
            "album":self.album,
            "services":self.services
        }
        return d

# Converts a dict into a track object
def track_from_dict(track_dict):
    title = track_dict['title']
    artist = track_dict['artist']
    album = track_dict['album']
    services = track_dict['services']
    track = Track(title, artist, album)
    track.services = services
    return track

# A custom request, that handles API errors and 429: To Many Requests errors by waiting and retrying
def makeRequest(url, method="get", expectedCode=200, *args, **kwargs):
    retries = 0
    while True:
        try:
            r = requests.request(method, url, **kwargs)
        except requests.exceptions.ConnectionError as e:
            retries += 1
            if retries >= RETRY_ATTEMPTS:
                raise e
            time.sleep(ERR_DELAY)
            continue
        if r.status_code == 429:
            time.sleep(TMR_DELAY)
            continue
        elif r.status_code == expectedCode:
            return r
        elif str(r.status_code).startswith("5"): # To retry a bit rather than instantly erroring on a HTTP 5XX
            retries+=1
            if retries >= RETRY_ATTEMPTS:
                break
            time.sleep(ERR_DELAY)
            continue
        else:
            break
    if "spotify.com" in url:
        raise spotify.ApiError(r.status_code, expectedCode, r.content)
    else:
        raise youtube.ApiError(r.status_code, expectedCode, r.content)

# A wrapper around makeRequest that handles pagination. Returns a list of all returned items
def pagination(url, *args, **kwargs):
    items = []
    pageToken = None
    for page in range(PAGINATION_PAGES):
        if pageToken: params = {"pageToken":pageToken}
        else: params = {}
        r = makeRequest(url, params=params, *args, **kwargs)
        data = json.loads(r.content)
        items += data['items']
        if 'next' in data.keys() and data['next']: # If 'next' exists and is non-None
            url = data['next']
        elif 'nextPageToken' in data.keys() and data['nextPageToken']:
            pageToken = data['nextPageToken']
        else:
            break
    return items

# Deletes a playlist from spotify
def spotify_delete_playlist(auth, playlist_id):
    headers = {"authorization":"Bearer "+auth.token}
    r = makeRequest("https://api.spotify.com/v1/playlists/"+playlist_id+"/followers", "delete", headers=headers)

# Deletes a plsylist from youtube
def youtube_delete_playlist(auth, playlist_id):
    headers = {"authorization":"Bearer "+auth.token}
    r = makeRequest("https://www.googleapis.com/youtube/v3/playlists?id="+playlist_id, "delete", headers=headers, expectedCode=204)

# Gets an item from spotify, track, album or playlist
def spotify_get_item(auth, track_id, itemType="track"):
    types_dict = {
        "track":"tracks", # how the type is formatted in the request URL
        "album":"albums",
        "playlist":"playlists"
    }
    try:
        itemType = types_dict[itemType]
    except KeyError:
        raise ValueError("Invalid itemType for spotify_get_item - " + itemType)
    headers = {"authorization":"Bearer "+auth.token}
    try:
        r = makeRequest("https://api.spotify.com/v1/"+itemType+"/"+track_id, "get", headers=headers)
    except spotify.ApiError as e:
        if e.statusCode == 404:
            return None
        else:
            raise e
    data = json.loads(r.content)
    return data

# Gets an item from youtube, video or playlist
def youtube_get_item(auth, video_id, itemType="video"):
    types_dict = {
        "video":"videos",
        "playlist":"playlists"
    }
    try:
        itemType = types_dict[itemType]
    except KeyError:
        raise ValueError("Invalid itemType for youtube_get_item - " + itemType)

    headers = {"authorization": "Bearer " + auth.token}
    r = makeRequest("https://www.googleapis.com/youtube/v3/videos?part=snippet%2CcontentDetails&id=" + video_id, "get", headers=headers)
    data = json.loads(r.content)['items']
    if data:
        return data[0]
    else:
        return None

# Reads all loaded spotify playlists
def spotify_read_playlists(auth, ids=False):
    playlists = {}
    marked_items = set()
    headers = {"authorization":"Bearer "+auth.token}
    items = pagination("https://api.spotify.com/v1/me/playlists", "get", headers=headers)
    if ids:
        for item in items:
            if item['name'] in playlists.keys():
                marked_items.add(item['name'])
                playlists[item['name'] + " (" + item['id'] + ")"] = item['id']
            else:
                playlists[item['name']] = item['id']
        for marked_name in marked_items:
            marked_id = playlists.pop(marked_name)
            playlists[marked_name + " (" + marked_id + ")"] = marked_id
    else:
        for item in items:
            if 'id' in item['tracks']:
                playlist_id = item['tracks']['id']
            elif 'href' in item['tracks']:
                url = item['tracks']['href']
                playlist_id = url.split("/")[-2]
            playlists[item['name']] = spotify_read_playlist(auth, playlist_id)
    return playlists

# Reads a single spotify playlist
def spotify_read_playlist(auth, playlist_id, album=False):
    tracks = []
    headers = {
        "authorization": "Bearer " + auth.token,
    }
    if album:
        items = pagination("https://api.spotify.com/v1/albums/"+playlist_id+"/tracks", "get", headers=headers)
    else:
        items = pagination("https://api.spotify.com/v1/playlists/" + playlist_id + "/tracks", "get", headers=headers)
    for track in items:
        if album:
            track['album'] = {"name":None} # When getting the tracks from an album, the album name itself is not in the track object.
        else:                              # As the Qt GUI doesn't display albums, they aren't needed, so this line is to prevent errors.
            track = track['track']         # If albums are needed, the album name will need to be passes, probably into this function in the album parameter
        new_track = Track(
            track['name'],
            track['artists'][0]['name'],
            track['album']['name']
        )
        if track['is_local']:
            print(new_track.title + " is local media and therefore has no Spotify link")
        else:
            new_track.update_service("spotify", track['href'].replace("https://api.spotify.com/v1/tracks/",""))
            new_track.update_duration("spotify", track['duration_ms']/1000)
        tracks.append(new_track)
    return tracks

# Creates a spotify playlist
def spotify_write_playlist(auth, name, desc, tracks, public=True):
    ids = []
    for track in tracks:
        track_id = track.services['spotify']['id']
        if track_id: ids.append("spotify:track:"+track_id)
    headers = {
        "authorization":"Bearer " + auth.token,
        "content-type":"application/json"
    }
    data = {
        "name":name,
        "description":desc,
        "public":public
    }
    r = makeRequest("https://api.spotify.com/v1/users/" + auth.username + "/playlists", "post", 201, json=data, headers=headers)
    playlist_id = json.loads(r.content)['id']
    data_chunks = [{"uris":ids[i:i + SPOTIFY_IDS_CHUNKS]} for i in range(0, len(ids), SPOTIFY_IDS_CHUNKS)]
    for chunk in data_chunks:
        r = makeRequest("https://api.spotify.com/v1/users/" + auth.username + "/playlists/" + playlist_id + "/tracks", "post", 201, json=chunk, headers=headers)
    return playlist_id

# Updates a spotify playlist
def spotify_update_playlist(auth, playlist_object, name, desc, public=True):
    headers = {
        "authorization": "Bearer " + auth.token,
        "content-type": "application/json"
    }
    data = {
        "name": name,
        "description": desc,
        "public": public
    }
    playlist_id = playlist_object['id']
    r = makeRequest("https://api.spotify.com/v1/playlists/"+playlist_id, "put", headers=headers, data=data)

# Gets spotify playlist info
def spotify_get_playlist_info(auth, playlist_id, album=False):
    headers = {
        "authorization": "Bearer " + auth.token,
    }
    if album:
        r = makeRequest("https://api.spotify.com/v1/albums/" + playlist_id, "get", headers=headers)
    else:
        r = makeRequest("https://api.spotify.com/v1/playlists/"+playlist_id, "get", headers=headers)
    data = json.loads(r.content)
    return data

# Updates a youtube playlist
def youtube_update_playlist(auth, playlist_object, name, desc, public=True):
    if public:
        privacy = "public"
    else:
        privacy = "unlisted"
    headers = {
        "authorization": "Bearer " + auth.token,
    }
    data = copy.deepcopy(playlist_object)
    data['snippet']['title'] = name
    data['snippet']['description'] = desc
    data['status']['privacyStatus'] = privacy
    if data == playlist_object:
        return # Values are unchanged, quit
    if playlist_object['status']['privacyStatus'] == privacy:
        part = "snippet"
        data.pop('status')
    else:
        part = "snippet%2Cstatus"
    r = makeRequest("https://www.googleapis.com/youtube/v3/playlists?part="+part, "put", headers=headers, json=data)

# Gets info from a youtube playlist
def youtube_get_playlist_info(auth, playlist_id):
    headers = {
        "authorization": "Bearer " + auth.token,
    }
    r = makeRequest("https://www.googleapis.com/youtube/v3/playlists?part=snippet%2CcontentDetails%2Cstatus&id="+playlist_id, "get", headers=headers)
    data = json.loads(r.content)
    return data['items'][0]

# Creates a youtube playlist
def youtube_write_playlist(auth, name, desc, tracks, public=True):
    if public:
        privacy = "public"
    else:
        privacy = "unlisted"
    ids = []
    for track in tracks:
        track_id = track.services['youtube']['id']
        if track_id: ids.append(track_id)
    headers = {
        "authorization": "Bearer " + auth.token,
        'accept': 'application/json',
        'content-type': 'application/json'
    }
    data = {
        "kind": "youtube#playlist",
        "snippet": {
            "title": name,
            "description":desc
        },
        "status": {
            "privacyStatus": privacy
        },
    }
    r = makeRequest("https://www.googleapis.com/youtube/v3/playlists?part=snippet%2Cstatus", "post", 200, headers=headers, json=data)
    playlist_id = json.loads(r.content)['id']
    for video in ids:
        data = {
            "kind": "youtube#playlistItem",
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video
                }
            }
        }
        r = makeRequest("https://www.googleapis.com/youtube/v3/playlistItems?part=snippet", "post", 200, headers=headers, json=data)
    return playlist_id

# Reads all loaded youtube playlists
def youtube_read_playlists(auth, ids=False):
    playlists = {}
    marked_items = set()
    headers = {
        "authorization": "Bearer " + auth.token
    }
    items = pagination("https://www.googleapis.com/youtube/v3/playlists?part=snippet&mine=true&maxResults=50", "get", headers=headers)
    if ids:
        for item in items:
            if item['snippet']['title'] in playlists.keys():
                marked_items.add(item['snippet']['title'])
                playlists[item['snippet']['title'] + " (" + item['id'] + ")"] = item['id']
            else:
                playlists[item['snippet']['title']] = item['id']
        for marked_name in marked_items:
            marked_id = playlists.pop(marked_name)
            playlists[marked_name + " (" + marked_id + ")"] = marked_id
    else:
        for item in items:
            playlists[item['snippet']['title']] = youtube_read_playlist(auth, item['id'])
    return playlists

# Reads a single youtube playlist
def youtube_read_playlist(auth, playlist_id):
    ids_request_limit = 40
    playlist = []
    headers = {
        "authorization": "Bearer " + auth.token
    }
    items = pagination("https://www.googleapis.com/youtube/v3/playlistItems?part=snippet%2CcontentDetails&maxResults=50&playlistId=" + playlist_id, "get", headers=headers)
    ids_str_list = []
    ids_str = ""
    index = 0
    for item in items:
        ids_str += item['contentDetails']['videoId'] + "%2C"
        index += 1
        if index >= ids_request_limit:
            ids_str_list.append(ids_str)
            ids_str = ""
    ids_str_list.append(ids_str)
    for ids_str in ids_str_list:
        r = makeRequest("https://www.googleapis.com/youtube/v3/videos?part=snippet&id=" + ids_str, "get", headers=headers)
        videoData = json.loads(r.content)
        for item in videoData['items']:
            track = Track(
                item['snippet']['title'],
                item['snippet']['channelTitle'],
                None
            )
            track.update_service("youtube",item['id'])
            playlist.append(track)
    return playlist

if __name__ == "__main__":
    pass