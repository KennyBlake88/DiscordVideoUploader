import google
import google_auth_oauthlib
import google_auth_httplib2
import os
import discord
import googleapiclient
from Discord.DiscordClient import DiscordClient
"""
The main driver code for the Discord Video Uploader.
If you're reading this, hello! I hope you enjoy looking at my code!

Author: Kenny Blake
Version: 1.0.0
"""





def main():
    
    discordClient = DiscordClient()
    discordClient.run(os.getenv("DISCORDTOKEN"))

def createAzureComputerVisionInstance():
    pass

def createYoutubeDataInstance():
    pass




if __name__ == "__main__":
    main()