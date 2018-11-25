import requests, json, os
from urllib.parse import quote

creds_file = "api_creds.json"
with open(creds_file) as f:
    data = json.loads(f.read())
    client_id = data['spotify']['client_id']
    client_secret = data['spotify']['client_secret']

redirect_uri = "http://localhost/"
auth_filename = "data/spotify_auth.json"

head, tail = os.path.split(auth_filename)
if head and not os.path.isdir(head): os.makedirs(head)
if not os.path.isfile(auth_filename):
    with open(auth_filename, "w") as f:
        f.write("[]")

# All valid scopes allowed by Spotify
valid_scopes = [
    "playlist-read-collaborative",
    "playlist-modify-private",
    "playlist-read-private",
    "playlist-modify-public",
    "user-read-email",
    "user-read-private",
    "user-read-birthdate",
    "user-read-playback-state",
    "user-read-currently-playing",
    "user-modify-playback-state",
    "user-read-recently-played",
    "user-top-read",
    "user-follow-read",
    "user-follow-modify",
    "streaming",
    "user-library-read",
    "user-library-modify"
    ]

class Error(Exception):
    """
    Base class for custom exceptions
    """
    pass

class UsernameError(Error):
    """
    Raised when the user logs in to a different account that specified

    Args:
        tokenUsername: The owner of the token that the api returned
        expectedUsername: The username that the user called this library with
    """
    def __init__(self, tokenUsername, expectedUsername):
        Exception.__init__(self, "You signed in as "+tokenUsername+", not "+expectedUsername)

class ScopeError(Error):
    """
    Raised when the token class is called with a scope that doesn't exist or is formatted incorrectly
    The valid scopes are stored in the valid_scopes global list
    """
    def __init__(self):
        Exception.__init__(self, "Invalid scope")

class ApiError(Error):
    """
    Raised when the Spotify Web API returns a status code that isn't expected.

    Args:
        statusCode: The response code that the API returned (e.g 404)
        expectedCode: The response code that was expected (e.g 200)
        content: Optional. The content of whatever the API returned. This is so any error messages returned by the API can be shown
    """
    def __init__(self, statusCode, expectedCode, content=None):
        self.statusCode = statusCode
        self.expectedCode = expectedCode
        self.content = content
        try:
            content = json.loads(content)
            if "error_description" in content.keys(): # Spotify API errors either have "error_desc" or "message"
                err = content["error_description"]    # in the root of the returned json
            elif "message" in content.keys():
                err = content["message"]
            else:
                err = None
        except:
            err = None
        if err == None:
            Exception.__init__(self, "Response <" + str(expectedCode) + "> expected, <" + str(statusCode) + "> recived")
        else:
            Exception.__init__(self, "Response <" + str(expectedCode) + "> expected, <" + str(statusCode) + "> recived\nContent - " + err)

def wipe_cache():
    """
    Wipes auth.json, deleting any cached tokens. The user will need to log in again when creating a new token.
    """
    f = open(auth_filename,"w")
    f.write("[]")
    f.close()

def delete_account(username):
    """
    Deletes all cached tokens with the specified username
    """
    print("Deleting " + username)
    f = open(auth_filename, "r")
    tokens = json.loads(f.read())
    f.close()
    for i, token in enumerate(tokens):
        if token['username'] == username:
            tokens.pop(i)
    f = open(auth_filename, "w")
    f.write(json.dumps(tokens))
    f.close()

def master_token(username):
    """
    Creates and returns a token object with all valid scopes.
    Should only be used for development or debug purposes, as having a token with all API permissions is not a very good idea.
    
    Args:
        username: The username that the token should use
        
    Returns:
        A new token object with the specified username and all valid scopes from the global list valid_scopes
    """
    scopeStr = ""
    for x in valid_scopes:
        scopeStr += x
        scopeStr += " "
    scopeStr = scopeStr[:-1]
    return token(scopeStr, username)

class token:
    """
    An class that handles the Spotify Web API authentication process, including user login and token refreshing.
    
    Args:
        scope: A string of all scopes that the token should use, seperated by spaces. See the Spotify Web API documentation for what scopes are needed for what.
        (e.g. playlist-read-collaborative playlist-modify-private user-read-email")
        username: Optional. The username that the token should use. If no username is specified all cached usernames are ignored and a new token is generated.
        returnUrl: Optional. If set to True, the token object stops at the point where a browser should be opened, and instead sets the url attribute. If set to a string, that url is used as the callback url to complete the sign in process.
        request: Optional. If set to True, the object does not request any new tokens, but stores current cached tokens matching the scope in the auths variable. Therefore the username parameter would be ignored

    Attributes:
        scope: The all scopes of the token, as a string sperated by spaces
        token: The access token that the user logged in with.
        refresh: The refresh token. Spotify Web API tokens expire after an hour. Use the refresh_token function rather than manually refreshing the token.
        username: The username that the token belongs to.
        auths: If request if True, all stored tokens matching the specified scope
        url: The url to enter into a browser if the returnUrl paramter is set to True
    
    Raises:
        ScopeError: The scope is invalid, or formatted incorrectly
        UsernameError: The username that the token belongs to does not match the username that this object was called with. This means that the user logged in with a different username than expected.
        ApiError: The API errored in some way. The returned error will be displayed if it exists.
    """
    def __init__(self, scope, username=None, returnUrl=False, request=False):
        for x in scope.split(" "):
            if not x in valid_scopes:
                raise ScopeError
        if request:
            auths = self.load_json(auth_filename)
            current_auths = self.find_scope(auths, scope)
            self.auths = current_auths
        else:
            self.scope = scope
            self.auth_file = auth_filename
            self.auth = None
            self.token = None
            self.refresh = None
            self.auths = self.load_json(self.auth_file)
            self.username = username
            self.returnUrl = returnUrl
            if returnUrl == False:
                cacheAuth = self.find_scope(self.auths, self.scope, self.username)
            else:
                cacheAuth = None
            if cacheAuth == None:
                self.auth = self.browser_auth()
                if self.auth: # stop browser_auth returns None
                    tokens = self.get_token(self.auth)
                    self.token = tokens['access_token']
                    self.refresh = tokens['refresh_token']
                    token_username = self.token_username(self.token)
                    if self.username == None: # If a username was specified, we need to check if it is correct
                        self.username = token_username # otherwise, the detected username is the new username
                    else:
                        if token_username != self.username:
                            raise UsernameError(token_username, self.username)
                    tokens['username']=self.username
                    self.auths.append(tokens)
                    self.save_json(self.auth_file, self.auths)
            else:
                tokens = cacheAuth
                self.token = tokens['access_token']
                self.refresh = tokens['refresh_token']
                self.refresh_token()

    def load_json(self, auth_file):
        f = open(auth_file,"r")
        data=json.loads(f.read())
        f.close()
        return data

    def token_username(self, testToken):
        headers = {
	        'authorization': 'Bearer '+testToken
        }
        r = requests.get("https://api.spotify.com/v1/me",headers=headers)
        if r.status_code != 200:
            raise ApiError(r.status_code, 200, r.text)
        data = json.loads(r.text)
        return data['id']
    
    def save_json(self, auth_file, data):
        f=open(auth_file,"w")
        f.write(json.dumps(data))
        f.close()

    def sort_scope(self, scope):
        scopeList = scope.split(" ")
        scopeList.sort()
        scopeStr = ""
        for x in scopeList:
            scopeStr+=x
        return scopeStr
    
    def find_scope(self, auths, scope, username=None):
        scopeList = scope.strip().split(" ")
        scopes = []
        for x in auths:
            newScope = x['scope'].strip().split(" ")
            good = True
            for perm in scopeList:
                try:
                    i = newScope.index(perm)
                except ValueError:
                    good = False
                    break
            if good and (x['username']==username or username==None):
                if username == None:
                    scopes.append(x)
                else:
                    return x
        if username == None:
            return scopes
        else:
            return None
    
    def browser_auth(self):
        if self.returnUrl == False:
            url = "https://accounts.spotify.com/authorize/?client_id="+client_id+"&response_type=code&redirect_uri="+quote(redirect_uri)+"&scope="+quote(self.scope)
            print("Use this URL in your browser to log in to Spotify")
            print()
            print(url)
            print()
            callback = input("PASTE CALLBACK URL HERE - ")
            auth_code = callback[callback.find("?code=")+6:]
            return auth_code
        elif self.returnUrl == True:
            self.url = "https://accounts.spotify.com/authorize/?client_id="+client_id+"&response_type=code&redirect_uri="+quote(redirect_uri)+"&scope="+quote(self.scope)
            return None
        elif type(self.returnUrl) == str:
            callback = self.returnUrl
            auth_code = callback[callback.find("?code=") + 6:]
            return auth_code
        else:
            raise TypeError("Invalid parameter for returnUrl")

    def get_token(self, auth_code):
        data = {
            'grant_type':'authorization_code',
            'code':auth_code,
            'redirect_uri':redirect_uri,
            'client_id':client_id,
            'client_secret':client_secret
            }
        headers = {
            'accept':'application/json',
            'content-type':'application/x-www-form-urlencoded'
            }
        r = requests.post("https://accounts.spotify.com/api/token",data=data,headers=headers)
        if r.status_code != 200:
            raise ApiError(r.status_code, 200, r.text)
        tokens = json.loads(r.text)
        return tokens

    def pop_token(self, auths, token):
        for index in range(0,len(auths)-1):
            if auths[index]['access_token']==token:
                auths.pop(index)
        return auths
    
    def refresh_token(self):
        """
        Refreshes the access token using the refresh token.
        
        Raises:
            ApiError: The API errored in some way. The returned error will be displayed if it exists.
        """
        refresh_token = self.refresh
        data = {
            'grant_type':'refresh_token',
            'refresh_token':refresh_token,
            'redirect_uri':redirect_uri,
            'client_id':client_id,
            'client_secret':client_secret
            }
        headers = {
            'accept':'application/json',
            'content-type':'application/x-www-form-urlencoded'
            }
        r = requests.post("https://accounts.spotify.com/api/token",headers=headers,data=data)
        if r.status_code != 200:
            raise ApiError(r.status_code, 200, r.text)
        self.auths = self.pop_token(self.auths, self.token)
        tokens = json.loads(r.text)
        self.token = tokens["access_token"]
        tokens['username']=self.username
        tokens['refresh_token']=self.refresh
        self.auths.append(tokens)
        self.save_json(self.auth_file, self.auths)
        self.token = tokens['access_token']
        return tokens

def main():
    pass

if __name__=="__main__":
    main()
