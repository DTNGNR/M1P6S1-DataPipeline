from http.server import BaseHTTPRequestHandler
import spotipy
import os

# https://stackoverflow.com/questions/75869291/cache-errors-using-spotify-api-in-python-program
cache_dir = '.cache'
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

#os.chmod(cache_dir, 0o700)

from google.oauth2 import service_account
from apiclient import discovery
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SAMPLE_SPREADSHEET_ID = '1JOSHfmHUWOorpyoWBn0m0Zacrd3xxy5XZdFZFSUJVvs'
SAMPLE_RANGE_NAME = 'A:C'


from datetime import datetime, timedelta
current_date = datetime.now()
check_date = current_date - timedelta(days=7)

from spotipy.oauth2 import SpotifyOAuth
print("CUSTOMER_ID", os.environ.get("CUSTOMER_ID"))
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.environ.get("CUSTOMER_ID"), client_secret=os.environ.get("SECRET_ID"),redirect_uri="http://localhost/",scope="user-follow-read,user-read-recently-played"))

def getArtistAlbums(uuid):
    albums = []
    results = sp.artist_albums(uuid, album_type='album')
    albums.extend(results['items'])
    while results['next']:
        results = sp.next(results)
        albums.extend(results['items'])

    unique = {}
    for album in albums:
        name = album['name'].title()

        if album["release_date_precision"] == "day":
            release_date = datetime.strptime(album['release_date'], "%Y-%m-%d")
        else:
            continue

        if ( name not in unique ) & (release_date >= check_date):
            unique[name] = album['release_date']
    return unique


def getFollowedArtists():
    artists = []
    results = sp.current_user_followed_artists()
    artists.extend(results['artists']['items'])
    while results['artists']['next']:
        after = results['artists']['next'].split("&after=")[1]
        results = sp.current_user_followed_artists(after=after)
        artists.extend(results['artists']['items'])
    print(f"Added {len(artists)} artists")

    unique = {}
    for artist in artists:
        name = artist['name'].title()
        if name not in unique:
            unique[name] = artist["id"]
        # break
    return unique

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        s = self.path
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
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
        service = discovery.build('sheets', 'v4', credentials=credentials)

        artists = getFollowedArtists()

        update = []
        for idx, artist in enumerate(artists):
            albums = getArtistAlbums(artists[artist])
            if albums:
                print("=====================\nNew albums for", artist, artists[artist])
                for idx, album in enumerate(albums):
                    update.append([artist,album,albums[album]])

        dict_me = dict(values=update)

        service.spreadsheets().values().append(
            spreadsheetId=SAMPLE_SPREADSHEET_ID,
            valueInputOption='RAW',
            range=SAMPLE_RANGE_NAME,
            body=dict_me).execute()

        print('Sheet successfully Updated')
        return




