import os
import json
import logging
from datetime import datetime
import google.oauth2.credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
import database

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly'
]

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

CLIENT_SECRETS_FILE = os.path.join(database.BASE_DIR, 'client_secrets.json')

def get_client_config():
    db_config_str = database.get_app_setting('youtube_oauth_client')
    if db_config_str:
        try:
            return json.loads(db_config_str)
        except Exception as e:
            logger.error(f"Error parsing youtube_oauth_client setting: {e}")

    if os.path.exists(CLIENT_SECRETS_FILE):
        try:
            with open(CLIENT_SECRETS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading {CLIENT_SECRETS_FILE}: {e}")

    return None

def save_client_config(config_dict_or_json):
    if isinstance(config_dict_or_json, dict):
        config_str = json.dumps(config_dict_or_json, ensure_ascii=False)
    else:
        config_str = str(config_dict_or_json).strip()
        json.loads(config_str)

    database.set_app_setting('youtube_oauth_client', config_str)
    try:
        with open(CLIENT_SECRETS_FILE, 'w', encoding='utf-8') as f:
            f.write(config_str)
    except Exception as e:
        logger.warning(f"Could not write {CLIENT_SECRETS_FILE}: {e}")

def create_oauth_flow(redirect_uri: str):
    client_config = get_client_config()
    if not client_config:
        raise ValueError("Google OAuth credentials are not configured yet. Please provide Client ID and Client Secret.")

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    return flow

def get_authenticated_credentials():
    token_json_str = database.get_app_setting('youtube_oauth_tokens')
    if not token_json_str:
        return None

    try:
        token_info = json.loads(token_json_str)
        client_config = get_client_config()
        client_info = client_config.get('web') or client_config.get('installed') or {}

        creds = google.oauth2.credentials.Credentials(
            token=token_info.get('token'),
            refresh_token=token_info.get('refresh_token'),
            token_uri=token_info.get('token_uri') or 'https://oauth2.googleapis.com/token',
            client_id=token_info.get('client_id') or client_info.get('client_id'),
            client_secret=token_info.get('client_secret') or client_info.get('client_secret'),
            scopes=token_info.get('scopes') or SCOPES
        )

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_credentials(creds)

        return creds
    except Exception as e:
        logger.error(f"Error restoring credentials: {e}")
        return None

def save_credentials(credentials, channel_info=None):
    token_data = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
        'expiry': credentials.expiry.isoformat() if credentials.expiry else None
    }
    database.set_app_setting('youtube_oauth_tokens', json.dumps(token_data))

    if channel_info:
        database.set_app_setting('youtube_channel_info', json.dumps(channel_info, ensure_ascii=False))

def disconnect_youtube():
    database.delete_app_setting('youtube_oauth_tokens')
    database.delete_app_setting('youtube_channel_info')

def get_youtube_status():
    has_client_config = get_client_config() is not None
    creds = get_authenticated_credentials()
    channel_info = None

    if creds:
        raw_info = database.get_app_setting('youtube_channel_info')
        if raw_info:
            try:
                channel_info = json.loads(raw_info)
            except Exception:
                pass
        
        if not channel_info:
            try:
                channel_info = fetch_channel_info(creds)
                if channel_info:
                    database.set_app_setting('youtube_channel_info', json.dumps(channel_info, ensure_ascii=False))
            except Exception as e:
                logger.error(f"Failed to fetch channel info: {e}")

    return {
        "configured": has_client_config,
        "authenticated": creds is not None and creds.valid,
        "channel": channel_info
    }

def fetch_channel_info(credentials):
    youtube = build('youtube', 'v3', credentials=credentials)
    response = youtube.channels().list(
        part='snippet,contentDetails,statistics',
        mine=True
    ).execute()

    items = response.get('items', [])
    if items:
        item = items[0]
        snippet = item.get('snippet', {})
        stats = item.get('statistics', {})
        thumbnails = snippet.get('thumbnails', {})
        thumb_url = (thumbnails.get('default') or thumbnails.get('medium') or {}).get('url')

        return {
            'id': item.get('id'),
            'title': snippet.get('title'),
            'custom_url': snippet.get('customUrl'),
            'thumbnail': thumb_url,
            'subscribers': stats.get('subscriberCount'),
            'video_count': stats.get('videoCount')
        }
    return None

def upload_video_to_youtube(video_path: str, title: str, description: str, privacy: str = 'private', tags: list = None, category_id: str = "22"):
    creds = get_authenticated_credentials()
    if not creds:
        raise PermissionError("YouTube account is not connected. Please authenticate first via OAuth.")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found at: {video_path}")

    youtube = build('youtube', 'v3', credentials=creds)

    body = {
        'snippet': {
            'title': title or 'Untitled LiveEdits Video',
            'description': description or 'Uploaded via LiveEdits Studio',
            'tags': tags or ['LiveEdits', 'Streaming', 'Highlights'],
            'categoryId': category_id
        },
        'status': {
            'privacyStatus': privacy if privacy in ['public', 'private', 'unlisted'] else 'private',
            'selfDeclaredMadeForKids': False
        }
    }

    media = MediaFileUpload(
        video_path,
        mimetype='video/mp4',
        chunksize=1024*1024*4,
        resumable=True
    )

    insert_request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = insert_request.next_chunk()
        if status:
            logger.info(f"Uploading to YouTube: {int(status.progress() * 100)}%")

    video_id = response.get('id')
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"

    return {
        'video_id': video_id,
        'url': youtube_url,
        'title': response.get('snippet', {}).get('title'),
        'privacy': response.get('status', {}).get('privacyStatus'),
        'uploaded_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
