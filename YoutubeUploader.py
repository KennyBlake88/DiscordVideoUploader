import asyncio 
import random
import json
import google 
import googleapiclient.discovery
import httplib2
from google_auth_oauthlib.flow import InstalledAppFlow
import os
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

class YoutubeUploader():

    def __init__(self):
        self.api_service_name = "youtube"
        self.api_version = "v3"
        self.developer_key = os.getenv("YOUTUBE_KEY")
        self.flow = InstalledAppFlow.from_client_secrets_file(
            "auth/client_secret_620611828215-s4dhhe6rhnmkasuoar81p4m0ce80apeo.apps.googleusercontent.com.json",
            scopes=["https://www.googleapis.com/auth/youtube.force-ssl"]
        )
        self.db = firestore.client()
        self.users_ref = self.db.collection(u'users')
        self.flow.run_console()
        self.credentials = self.flow.credentials
        self.cjson = json.loads(self.credentials.to_json())
        self.acces_token = self.cjson.get('token')
        self.refresh_token = self.cjson.get('refresh_token')
        self.cid = self.cjson.get('client_id')
        self.csecret = self.cjson.get('client_secret')
        self.token_uri = self.cjson.get('token_uri')

        self.youtube = googleapiclient.discovery.build(self.api_service_name, self.api_version, developerKey = self.developer_key, credentials=self.credentials)

    async def checkDatabaseForNSFWValue(self, videoID, authorID, username):
        doc_ref = self.users_ref.document(str(authorID))

        data = doc_ref.get().to_dict()

        if (data.get('videos').get('videoID')):
            return True
        else:
            #print(f"The video {videoID} would have just uploaded!")
            print(
f"""===========================
{username}: A.K.A {authorID}, is uploading a video! The video id is {videoID}
===========================
            """)
            #self.uploadVideo(username, videoID, authorID)



    async def uploadVideo(self, username, videoID):
            creds = google.oauth2.credentials.Credentials(self.access_token, refresh_token=self.refresh_token, token_uri=self.token_uri, client_id = self.cid, client_secret = self.csecret, scopes=["https://www.googleapis.com/auth/youtube.force-ssl"])
            if creds.valid == False:
                request = google.auth.transport.requests.Request()
                creds.refresh(request)

                youtube = googleapiclient.discovery.build(self.api_service_name, self.api_version, developerKey = self.DEVELOPER_KEY, credentials=creds)
            else:
                youtube = googleapiclient.discovery.build(self.api_service_name, self.api_version, developerKey = self.DEVELOPER_KEY, credentials=creds)

            request = youtube.videos().insert(
                part="snippet",
                body={
                    "title": f"{username} from discord uploaded this to here!",
                    "description": "Check out my main youtube channel",
                    "tags": ["michael reeves", "programming"],
                    "category_id": "28"
                },
                media_body = MediaFileUpload(options)
            )
            response = request.execute()

            items = response["items"]
