import requests, json, os
from urllib.parse import quote, unquote

client_id = "251705760801-5o6ihfj26i59d171n81koolor0d6i6al.apps.googleusercontent.com"
client_secret = "AVccUHwJF81bmINoVXbIBCj-"
redirect_uri = "https://localhost/"
auth_filename = "data/youtube_auth.json"

head, tail = os.path.split(auth_filename)
if head and not os.path.isdir(head): os.makedirs(head)
if not os.path.isfile(auth_filename):
    with open(auth_filename, "w") as f:
        f.write("[]")

# All valid Google scopes that pertain to YouTube
valid_scopes = [
    "youtube",
    "youtube.force-ssl",
    "youtube.readonly",
    "youtube.upload",
    "youtubepartner",
    "youtubepartner-channel-audit",
    "userinfo.profile",
    "userinfo.email"
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
    Raised when the Youtube API returns a status code that isn't expected.

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
            err = str(content['error']) # This is how Google APIs seem to format their error messages
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


class token:
    def __init__(self, scope, username=None, returnUrl=False, request=False):
        for x in scope.split(" "):
            if not x.replace("https://www.googleapis.com/auth/", "") in valid_scopes:
                raise ScopeError
        if scope.find("userinfo.profile") == -1:
            scope += " userinfo.profile"  # added scopes required to get the email
        if scope.find("userinfo.email") == -1:
            scope += " userinfo.email"
        # Adds the scope urls that google scopes have
        newScope = ""
        for x in scope.split(" "):
            if not "https://www.googleapis.com/auth/" in x:
                newScope += "https://www.googleapis.com/auth/" + x + " "
            else:
                newScope += x
        if request:
            if username != None:
                raise Warning("Request Mode - username parameter is ignored")
            auths = self.load_json(auth_filename)
            current_auths = self.find_scope(auths, newScope)
            self.auths = current_auths
        else:
            self.scope = newScope[:-1]
            self.auth_file = auth_filename
            self.auth = None
            self.token = None
            self.refresh = None
            self.auths = self.load_json(auth_filename)
            self.username = username
            self.returnUrl = returnUrl
            if returnUrl == False:
                cacheAuth = self.find_scope(self.auths, self.scope, self.username)
            else:
                cacheAuth = None
            if cacheAuth == None:
                self.auth = self.browser_auth(self.username)
                if self.auth:
                    tokens = self.get_token(self.auth)
                    self.token = tokens['access_token']
                    self.refresh = tokens['refresh_token']
                    token_username = self.token_username(self.token) # uses email as unique username
                    if self.username == None: # If a username was specified, we need to check if it is correct
                        self.username = token_username
                    else:
                        if token_username != self.username:
                            raise UsernameError(token_username, self.username)
                    tokens['username']=self.username
                    tokens['scope']=self.scope
                    self.auths.append(tokens)
                    self.save_json(self.auths)
            else:
                tokens = cacheAuth
                self.token = tokens['access_token']
                self.refresh = tokens['refresh_token']
                self.refresh_token()

    def load_json(self, auth_filename):
        f = open(auth_filename,"r")
        data=json.loads(f.read())
        f.close()
        return data

    def token_username(self, testToken): # Uses the Google+ API to get the account email
        headers = {
            "authorization": "Bearer " + testToken
        }
        r = requests.get("https://www.googleapis.com/plus/v1/people/me", headers=headers)
        if r.status_code != 200:
            raise ApiError(r.status_code, 200, r.text)
        data = json.loads(r.text)
        email = None
        for e in data['emails']:
            if e['type'] == 'account':
                email = e['value']
        if email == None:
            raise Error("This account appears to not have an account email linked")
        return email

    def save_json(self, data):
        f=open(self.auth_file,"w")
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
            if good and (x['username'] == username or username == None):
                if username == None:
                    scopes.append(x)
                else:
                    return x
        if username == None:
            return scopes
        else:
            return None

    def browser_auth(self, username=None):
        if self.returnUrl == False:
            url = "https://accounts.google.com/o/oauth2/v2/auth?scope=" + quote(self.scope) + "&response_type=code&redirect_uri=" + quote(redirect_uri) + "&client_id=" + client_id + "&access_type=offline&prompt=consent"
            print("Use this URL in your browser to log in to YouTube")
            print()
            print(url)
            print()
            callback = input("PASTE CALLBACK URL HERE - ")
            auth_code = callback[callback.find("?code=")+6:]
            return auth_code
        elif self.returnUrl == True:
            self.url = "https://accounts.google.com/o/oauth2/v2/auth?scope=" + quote(self.scope) + "&response_type=code&redirect_uri=" + quote(redirect_uri) + "&client_id=" + client_id + "&access_type=offline&prompt=consent"
            return None
        elif type(self.returnUrl) == str:
            callback = self.returnUrl
            auth_code = callback[callback.find("?code=") + 6:]
            return unquote(auth_code)
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
        r = requests.post("https://www.googleapis.com/oauth2/v4/token",data=data,headers=headers)
        if r.status_code != 200:
            raise ApiError(r.status_code, 200, r.text)
        tokens = json.loads(r.text)
        return tokens

    def pop_token(self, auths, token):
        for index in range(0,len(auths)-1):
            if auths[index]['access_token']==token:
                auths.pop(index)
        return auths

    # Beats me why the code doubles up tokens. It works, I'm not fixing it
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
            'client_id':client_id,
            'client_secret':client_secret
            }
        headers = {
            'accept':'application/json',
            'content-type':'application/x-www-form-urlencoded'
            }
        r = requests.post("https://www.googleapis.com/oauth2/v4/token",headers=headers,data=data)
        if r.status_code != 200:
            raise ApiError(r.status_code, 200, r.text)
        self.auths = self.pop_token(self.auths, self.token)
        tokens = json.loads(r.text)
        self.token = tokens["access_token"]
        tokens['username']=self.username
        tokens['scope'] = self.scope
        tokens['refresh_token']=self.refresh
        self.auths.append(tokens)
        self.save_json(self.auths)
        self.token = tokens['access_token']
        return tokens

def main():
    pass

if __name__=="__main__":
    main()
