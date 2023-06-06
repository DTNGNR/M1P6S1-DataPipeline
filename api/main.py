import requests
import os
import concurrent.futures
import logging

from flask import Flask, request, redirect
from base64 import b64encode

from google.oauth2 import service_account
from apiclient import discovery
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SAMPLE_SPREADSHEET_ID = '1JOSHfmHUWOorpyoWBn0m0Zacrd3xxy5XZdFZFSUJVvs'
SAMPLE_RANGE_NAME = 'A:C'

# Set up logging
logging.basicConfig(level=logging.INFO)

from datetime import datetime, timedelta
current_date = datetime.now()
check_date = current_date - timedelta(days=8)

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

    credentials = service_account.Credentials.from_service_account_info(
        service_account_credentials, scopes=SCOPES)
    
    service = discovery.build('sheets', 'v4', credentials=credentials)

    service.spreadsheets().values().append(
        spreadsheetId=SAMPLE_SPREADSHEET_ID,
        valueInputOption='RAW',
        range=SAMPLE_RANGE_NAME,
        body=dict_me).execute()

    print('Sheet successfully Updated')
    return    

LAST_ARTIST_ID_FILE = "api/last_artist_id.txt"

def read_last_artist_id():
    with open(LAST_ARTIST_ID_FILE, "r") as file:
        return file.read().strip()

def write_last_artist_id(artist_id):
    with open(LAST_ARTIST_ID_FILE, "w") as file:
        file.write(artist_id)


def getFollowedArtists(access_token):

    last_artist_id = read_last_artist_id()
    if len(last_artist_id) > 10:
        logging.debug(f"Last artist ID from file: {last_artist_id}")
        url = "https://api.spotify.com/v1/me/following?type=artist&limit=50&after={after}"
    else:
        url = "https://api.spotify.com/v1/me/following?type=artist&limit=50"


    headers = { "Authorization": "Bearer {}".format(access_token)}
    response = requests.get(url, headers=headers)
    result = response.json()['artists']

    artists = []
    artists.extend(result['items'])
    # while result['next']:
    #     after = result['next'].split("&after=")[1]
    #     response = requests.get(f"https://api.spotify.com/v1/me/following?type=artist&limit=50&after={after}", headers=headers)
    #     result = response.json()['artists']
    #     artists.extend(result['items'])

    # Store the last artist's ID in the file
    if len(artists) > 1:
        last_artist_id = artists[-1]['id']
    else:
        last_artist_id = ""
    write_last_artist_id(last_artist_id)

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

app = Flask(__name__)

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
        logging.debug("=====================\nGot acces token")

        artists = getFollowedArtists(access_token)
        logging.debug(f"=====================\Found {len(artists)} artists to check")

        update = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            artist_albums = [(access_token, artist) for artist in artists]
            futures = [executor.submit(process_artist, *args) for args in artist_albums]
            for future in concurrent.futures.as_completed(futures):
                try:
                    album_updates = future.result()
                    if album_updates:
                        update.extend(album_updates)
                except Exception as e:
                    logging.error(f"Exception occurred: {e}")

        updateGoogleSheet(update)

        return str(update)
    else:
        error = request.args.get("error")
        return f"Authorization failed: {error}"

def process_artist(access_token, artist):
    name = artist["name"].title()
    id = artist["id"]
    albums = getArtistAlbums(access_token, id)

    if albums:
        logging.debug("=====================\nFound new albums for %s", name)
        album_updates = [[name, album["name"], album["release_date"]] for album in albums]
        return album_updates
    return []

# @app.route("/callback")
# def callback():
#     code = request.args.get("code")
#     if code:
#         access_token = get_access_token(code)

#         artists = getFollowedArtists(access_token)
        
#         update = []
#         for artist in artists:
#             name = artist["name"].title()
#             id = artist["id"]
#             albums = getArtistAlbums(access_token, id)

#             if albums:
#                 print("=====================\nFound new albums for", name)
#                 for idx, album in enumerate(albums):
#                     update.append([name,album["name"],album["release_date"]])
        
#         updateGoogleSheet(update)

#         return update
#     else:
#         error = request.args.get("error")
#         return f"Authorization failed: {error}"