from http.server import BaseHTTPRequestHandler
import requests
import os

from flask import Flask, request, redirect
#from dotenv import load_dotenv
from base64 import b64encode

from google.oauth2 import service_account
from apiclient import discovery
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SAMPLE_SPREADSHEET_ID = '1JOSHfmHUWOorpyoWBn0m0Zacrd3xxy5XZdFZFSUJVvs'
SAMPLE_RANGE_NAME = 'A:C'

from datetime import datetime, timedelta
current_date = datetime.now()
check_date = current_date - timedelta(days=7000)

app = Flask(__name__)
#load_dotenv()

@app.route("/")
def index():
    client_id = os.getenv("CLIENT_ID")
    redirect_uri = os.getenv("REDIRECT_URI")
    scope = "user-follow-read"  # Add any additional scopes you need

    authorize_url = f"https://accounts.spotify.com/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&scope={scope}"
    return redirect(authorize_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if code:
        access_token = get_access_token(code)
        # Use the access token to make requests to the Spotify API
        # Implement your logic here
        artists = getFollowedArtists(access_token)
        
        update = []
        for artist in artists:
            name = artist["name"].title()
            id = artist["id"]
            albums = getArtistAlbums(access_token, id)

            if albums:
                print("=====================\nFound new albums for", name)
                for idx, album in enumerate(albums):
                    update.append([name,album["name"],album["release_date"]])
            break
        
        updateGoogleSheet(update)

        #return "Authorization successful! You can close this page."
        return update
    else:
        error = request.args.get("error")
        # Handle the error case appropriately
        return f"Authorization failed: {error}"

def updateGoogleSheet(data):
    dict_me = dict(values=data)

    service_account_credentials = {
        "type": os.environ.get("type"),
        "project_id": os.environ.get("project_id"),
        "private_key_id": os.environ.get("private_key_id"),
        "private_key": os.environ.get("private_key"),
        "client_email": os.environ.get("client_email"),
        "client_id": os.environ.get("client_id"),
        "auth_uri": os.environ.get("auth_uri"),
        "token_uri": os.environ.get("token_uri"),
        "auth_provider_x509_cert_url": os.environ.get("auth_provider_x509_cert_url"),
        "client_x509_cert_url": os.environ.get("client_x509_cert_url")
    }

    print(service_account_credentials["private_key"])
    credentials = service_account.Credentials.from_service_account_info(
        service_account_credentials, scopes=SCOPES)
    
    # credentials = service_account.Credentials.from_service_account_file(
    #     "spotify-new-releases-388907-3a50d5a91da5.json", scopes=SCOPES)

    service = discovery.build('sheets', 'v4', credentials=credentials)

    service.spreadsheets().values().append(
        spreadsheetId=SAMPLE_SPREADSHEET_ID,
        valueInputOption='RAW',
        range=SAMPLE_RANGE_NAME,
        body=dict_me).execute()

    print('Sheet successfully Updated')
    return    

def getFollowedArtists(access_token):

    headers = { "Authorization": "Bearer {}".format(access_token)}
    response = requests.get("https://api.spotify.com/v1/me/following?type=artist&limit=50", headers=headers)
    result = response.json()['artists']

    artists = []
    artists.extend(result['items'])
    while result['next']:
        after = result['next'].split("&after=")[1]
        response = requests.get(f"https://api.spotify.com/v1/me/following?type=artist&limit=50&after={after}", headers=headers)
        result = response.json()['artists']
        artists.extend(result['items'])
        break

    return artists

def getArtistAlbums(access_token, id):
    headers = { "Authorization": "Bearer {}".format(access_token)}
    response = requests.get(f"https://api.spotify.com/v1/artists/{id}/albums?include_groups=album&market=DE&limit=50", headers=headers)
    result = response.json()

    albums = []
    for album in result["items"]:
        if album["release_date_precision"] == "day":
            release_date = datetime.strptime(album['release_date'], "%Y-%m-%d")
        else:
            continue

        if release_date >= check_date:
            albums.append(album)

    return albums
    
def getAuth():
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    return b64encode(f"{client_id}:{client_secret}".encode()).decode(
        "ascii"
    )

def get_access_token(code):
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    redirect_uri = os.getenv("REDIRECT_URI")

    headers = {"Authorization": "Basic {}".format(getAuth())}

    token_url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    response = requests.post(token_url, data=data, headers=headers)
    response_data = response.json()
    return response_data["access_token"]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        s = self.path
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

        # app.run(port=8000, debug=True)

        print('Sheet successfully updated')
        return
    
if __name__ == "__main__":
    print('Run Flask App')
    app.run(port=8000, debug=True)
