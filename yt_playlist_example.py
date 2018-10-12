import youtube, json, requests
from pprint import pprint

username = "8bitbanana.ec@gmail.com"

playlist_title = "Example Playlist Upload"
playlist_desc = """
This is an example playlist created using the Youtube Data API.
Here is a newline.

Here is another newline.
"""
playlist_videos = [
    "gtG-g03dmIk",
    "drCIj8Qgs4Y",
    "f-zdCoI3tv8",
    "JBoDWL_bayc"
]

t = youtube.token("youtube",username)

# headers for both API calls
headers = {
    "authorization":"Bearer "+t.token,
    'accept': 'application/json',
    'content-type': 'application/json'
}

# data for playlist creation call
data = {
    "kind":"youtube#playlist",
    "snippet": {
        "title": playlist_title,
        "description": playlist_desc,
    },
    "status": {
        "privacyStatus":"unlisted"
    },
}

# creating playlist
r = requests.post("https://www.googleapis.com/youtube/v3/playlists?part=snippet%2Cstatus",headers=headers,json=data)
ret = json.loads(r.content)
pprint(ret)

playlist_id = ret['id']

# adding videos
for video in playlist_videos:
    print("Adding " + video)
    # data for playlist addition call
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
    r = requests.post("https://www.googleapis.com/youtube/v3/playlistItems?part=snippet", headers=headers, json=data)
    pprint(json.loads(r.content))