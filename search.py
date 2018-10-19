import itertools, apicontrol, json, traceback, isodate
from urllib.parse import quote

# Creates a list of all possible combinations of string of words
# https://stackoverflow.com/questions/464864/how-to-get-all-possible-combinations-of-a-list-s-elements
# I edited this function to remove the empty tuple and the full tuple
def powerset(iterable):
    s = list(iterable)
    pow = itertools.chain.from_iterable(itertools.combinations(s, r) for r in range(len(s)+1))
    pow = (x for x in pow if x != () and x != s)
    return pow

# Converts a tuple of strings to a single string, seperated by spaces
def tuple_to_str(terms):
    str_terms = []
    for x in terms:
        if type(x) != tuple and type(x) != list and type(x) != set:
            str_terms.append(x)
            continue
        new_str = ""
        for y in x:
            new_str += y + " "
        str_terms.append(new_str[:-1])
    return str_terms

# Runs a search through spotify's api
def spotify_search(keywords, content_type, auth, amount=1):
    valid_types = ["artist","album","track"]
    if not content_type in valid_types: raise ValueError("Invalid Type - "+content_type)
    headers = {"Authorization":"Bearer "+auth.token}
    keywords = quote(keywords)
    r = apicontrol.makeRequest("https://api.spotify.com/v1/search?q=" + keywords + "&type=" + content_type + "&limit=" + str(amount), "get", headers=headers)
    data = json.loads(r.text)[content_type+"s"]['items']
    if len(data) == 0:
        return []
    else:
        return data

# Runs a search through YouTube's api. offset specifies the result number to return, default 0 (the first result)
def youtube_search(keywords, content_type, auth, amount=1):
    valid_types = ["video","channel","playlist"]
    if not content_type in valid_types: raise ValueError("Invalid Type - " + content_type)
    headers = {"Authorization": "Bearer " + auth.token}
    keywords = quote(keywords)
    r = apicontrol.makeRequest("https://www.googleapis.com/youtube/v3/search?q=" + keywords + "&part=snippet&maxResults=" + str(amount) + "&type=" + content_type, "get", headers=headers)
    data = json.loads(r.text)['items']
    return data

# Runs through a list of tracks until it hits one that is in youtube_str
def match_tracks(youtube_str, spotify_tracks):
    matching_tracks = []
    for track in spotify_tracks:
        trackTitle = track.title.lower()
        youtubeTitle = youtube_str.lower()
        if trackTitle in youtubeTitle:
            # We need to check if the match is not just a substring, to reduce incorrect matches.
            # E.g. WIN in ElectrosWINg throws the algorithm into an incorrect artist that makes it match
            # incorrectly. The below code checks to see if the values either side of the match are
            # not letters to make sure it is a full word
            start = youtubeTitle.index(trackTitle)
            end = start + len(trackTitle)
            if start > 0:
                startCheck = not youtubeTitle[start-1].isalpha()
            else:
                startCheck = True
            try:
                endCheck = not youtubeTitle[end].isalpha()
            except IndexError:
                endCheck = True
            # ---
            if startCheck and endCheck:
                matching_tracks.append(track)
    if len(matching_tracks) == 0:
        return None
    elif len(matching_tracks) == 1:
        return matching_tracks[0]
    max_len = 0
    matched_track = None
    for track in matching_tracks: # If there are multiple matching tracks, return the longest match
        if len(track.title) > max_len:
            max_len = len(track.title)
            matched_track = track
    return matched_track

# Returns all tracks from a specified artists id
def spotify_all_tracks(artist_id, auth):
    all_tracks = []
    headers = {"Authorization":"Bearer "+auth.token}
    albums = apicontrol.pagination("https://api.spotify.com/v1/artists/" + artist_id + "/albums", "get", headers=headers)
    for album in albums:
        tracks = apicontrol.pagination("https://api.spotify.com/v1/albums/" + album['id'] + "/tracks?limit=50", "get", headers=headers)
        for track in tracks:
            track_obj = apicontrol.Track(
                    track['name'],
                    track['artists'][0]['name'],
                    album['name']
                )
            track_obj.update_service("spotify",track['id'])
            track_obj.update_duration("spotify", track['duration_ms']/1000) # Convert ms to s
            all_tracks.append(track_obj)
    return all_tracks

# Searching in Spotify is a total pain, as you have to specify the keywords exactly or it will return nothing.
# The algorithm this uses is outlines in search_notes.txt
def youtube_to_spotify(track, auth):
    search_terms = [track.artist]
    if len(track.artist.split(" ")) > 0:
        search_terms += tuple_to_str(powerset(track.artist.split(" ")))
    if len(track.title.split(" ")) > 0:
        search_terms += tuple_to_str(powerset(track.title.split(" ")))
    for term in search_terms:
        try:
            artist = spotify_search(term,"artist", auth, amount=1)[0]
        except IndexError:
            continue
        except Exception as e:
            print("Error with search term '" + term + "'")
            traceback.print_exc() # If the search raises an ApiError or something, we want to just move onto the next term, not give up completly
            artist = None
        if artist == None: # No artist returned, continue to next serach term
            continue
        tracks = spotify_all_tracks(artist['id'],auth)
        matched_track = match_tracks(track.title, tracks)
        if matched_track != None: # A track has been matched, add the spotify link to the original track and return it.
            track.title = matched_track.title # Spotify is the most reliable, update all values to the matched track
            track.artist = matched_track.artist
            track.album = matched_track.album
            track.update_service("spotify",matched_track.services['spotify']['id'])
            return track
    return None

# Searching using YouTube is much simpler, as Google (believe it or not) is good at searching
def spotify_to_youtube(track, auth):
    search_term = track.artist + " " + track.title
    results = youtube_search(search_term, "video", auth, 5)
    videoId = None
    firstDuration = None # Remember the first results duration to use later if none of the results match
    for result in results:
        id = result['id']['videoId']
        headers = {
            "authorization":"Bearer " + auth.token
        }
        r = apicontrol.makeRequest("https://www.googleapis.com/youtube/v3/videos?part=contentDetails&id="+id, headers=headers)
        duration = json.loads(r.text)['items'][0]['contentDetails']['duration'] # get the ISO 8601 duration string
        duration = isodate.parse_duration(duration).total_seconds() # parse into seconds
        if not firstDuration: firstDuration = duration # Gets set on the first loop, but none of the others
        valid = track.update_duration("youtube", duration)
        if valid:
            videoId = id
            break
        else:
            print("Skipping " + id + " - duration too different from other links")
    if results == []: return None
    if videoId:
        track.update_service("youtube",videoId) # Add the video id
    else:
        print("No videos with a close enough duration were found. Defaulting to the first returned")
        track.update_service("youtube", results[0]['id']['videoId'])
        track.update_duration("youtube", firstDuration, force=True) # force=True, as the update_duration will fail, force the duration to update anyway
    return track