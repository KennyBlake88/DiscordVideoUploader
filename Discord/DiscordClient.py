import asyncio
from typing import List
import discord
from discord.ext import commands
from discord.ext.commands.core import command
from discord.message import Attachment
from time import sleep
from datetime import datetime
from datetime import timedelta
import math
import os
from google.cloud import storage
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from google.cloud import videointelligence
import cv2
from YoutubeUploader import YoutubeUploader

 
"""
The DiscordClient class represents the communication with discord's servers.


It also acts as the main tether to Google Cloud's servers/my database. 

WHAT IT DOES:
-Gathers Videos
-Sends the terms and conditions
-Sends user acceptance data/video id's to the database

It also has all the functionality of the VideoAnalyzer class because I am tired of that not working!




Author: Kenny Blake
Version: 1.2.0
"""
class DiscordClient(discord.Client):

    """
    Runs whenever a new instance of this class is created. 

    Author: Kenny Blake
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.video_client = videointelligence.VideoIntelligenceServiceClient()
        self.words = []
        self.currentVideos = {}
        self.lockedMessage: discord.Message
        self.active = False
        self.productionChannel: discord.TextChannel
        self.testChannel: discord.TextChannel
        self.production = False
        self.counter = 0
        self.firstTime = True
        self.firstVideos = {}
        self.stillProcessing = []
        self.waitingForAcceptance = {}
        self.storageClient = storage.Client()
        self.bucket = self.storageClient.bucket("discord-video-uploader")
        self.cred = credentials.Certificate("auth/discordvideouploader-96a038698ad2.json")
        firebase_admin.initialize_app(self.cred)
        self.db = firestore.client()
        self.users_ref = self.db.collection(u'users')
        self.ytu = YoutubeUploader()
        self.currentVideosTemp = {}

        self.features = [videointelligence.Feature.EXPLICIT_CONTENT_DETECTION,
        videointelligence.Feature.SPEECH_TRANSCRIPTION,
        videointelligence.Feature.TEXT_DETECTION]
        self.config = videointelligence.SpeechTranscriptionConfig(
            language_code="en-US", enable_automatic_punctuation=False
        )

        self.context = videointelligence.VideoContext(speech_transcription_config=self.config)


        with open ('extra/badwords.txt') as f:
            for word in f.readlines():
                self.words.append(word.strip().strip('\n').lower())



    """
    Activates when the bot is ready to go, and a connection to discord has been established.

    Author: Kenny Blake
    """
    async def on_ready(self):
        print("Discord Client is ready!")
        self.productionChannel = self.get_channel(873307149621686362)
        self.testChannel = self.get_channel(827543130017759244)

    """
    Whenever a message gets sent, it makes sure that it's in the right channel, carries on
    with the rest of the program.

    Author: Kenny Blake
    """
    async def on_message(self, message: discord.Message):
        
        #if the person who sent the message isn't a person and is, in fact, a bot. 
        if (type(message.author) == discord.user.User):
            return
        
        #the roles of the user who just send the message. 
        roleids = []
        for role in message.author.roles:
            roleids.append(role.id)

    
        #commands for nipsey & i
        if 778848428980436994 in roleids:

            #Get the current videos in the set.
            if message.clean_content == ";get_current_videos":
                if (len(self.currentVideos.keys()) > 0):
                    for i in self.currentVideos.keys():
                        await message.channel.send(f"{i}, {self.currentVideos.get(i)}")
                else:
                    await message.channel.send("No videos in this set!")
            
            #shuts down the entire bot
            elif message.clean_content == ";terminate":
                await message.channel.send("I really hope you meant to do this cause I can't be fucked to write interactivity to this bot. Shutting the whole bot down.")
                exit()

            #ping command
            elif message.clean_content == ";ping":
                await message.channel.send(f"Latency is {math.floor(self.latency * 100)}ms.")

            #STOP command
            elif message.clean_content == ";stop":
                if self.production and self.active:
                    overwrite = self.productionChannel.overwrites_for(message.guild.default_role)
                    overwrite.send_messages = False
                    await self.productionChannel.set_permissions(self.get_guild(756025919063326752).default_role, overwrite=overwrite)
                    await self.productionChannel.send("Sorry, this channel is locked while the bot is stopped!")
                elif self.active:
                    await self.testChannel.send("Sorry, this channel is locked while the bot is stopped!")

                self.active = False


            if message.clean_content == ";prod end":
                self.production = False


            #####
            # START COMMAND
            #####
            #prod
            elif message.clean_content == ";start prod":
                self.production = True
                overwrite = self.productionChannel.overwrites_for(self.get_guild(756025919063326752).default_role)
                overwrite.send_messages = True
                await self.productionChannel.set_permissions(self.get_guild(756025919063326752).default_role, overwrite=overwrite)
                deleteMsg = await self.productionChannel.history(limit=10).flatten()
                for i in deleteMsg:
                    if(i.clean_content == "Sorry, this channel is locked while the bot is stopped!"):
                        await i.delete()
                        
                self.active = True
                self.loop.create_task(self.hourChecker())

            #test
            elif message.clean_content == ";start":
                overwrite = self.testChannel.overwrites_for(self.get_guild(756025919063326752).default_role)
                overwrite.send_messages = True
                await self.testChannel.set_permissions(self.get_guild(756025919063326752).default_role, overwrite=overwrite)
                deleteMsg = await self.testChannel.history(limit=10).flatten()
                for i in deleteMsg:
                    if(i.clean_content == "Sorry, this channel is locked while the bot is stopped!"):
                        await i.delete()
                        
                self.active = True
                self.loop.create_task(self.hourChecker())
                    
                    


        #commands for helpers/mods/admins
        if 756027716087840888 in roleids:

            #reset timer command
            if message.clean_content == ";reset timer":
                self.counter = 0


            #deletes all the videos from the videos folder to conserve space. 
            elif message.clean_content == ";purge":
                dir = 'Videos'
                counter = 0 
                for f in os.listdir(dir):
                    if int(f) in self.currentVideos.keys():
                        await message.channel.send(f"I can't delete {f}, it is in this set's videos!")
                    else:
                        os.remove(os.path.join(dir, f))
                        counter += 1

                if(self.production):
                    await self.productionChannel.send(f"Removed {counter} videos!")
                else:
                    await self.testChannel.send(f"Removed {counter} videos!")

        #commands for everyone (fun ones)
        if message.clean_content == ";ym" or message.clean_content == ";give_me_image_perms":
            await message.channel.send("ya motha")

        if message.clean_content == ";forget_i_ever_existed":
            self.loop.create_task(self.deleteAllData(message.author.id, message))


        #The main thing. 
        if(message.channel == self.productionChannel or message.channel == self.testChannel) and self.active:
            self.loop.create_task(self.validateVideo(message))


    """
    If a message gets deleted, it checks if it had a video in the currentVideos dictionary.
    If it did, it deletes it from that dictionary.

    Author: Kenny Blake
    """
    async def on_message_delete(self, message: discord.Message):
        if message.id in self.currentVideos.keys():
            self.currentVideos.pop(message.id)
    
    """
    Whenever a reaction gets added to a message, it checks the channel it is in,
    and if it is apart of this set of images, it adds 1 to it's score.

    Author: Kenny Blake
    """
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if(payload.guild_id == None):
            if(payload.user_id in self.waitingForAcceptance):
                  if(str(payload.emoji) == '✅'):
                      self.loop.create_task(self.userAccepted(payload.user_id, self.waitingForAcceptance.get(payload.user_id)))
                  elif(str(payload.emoji) == "❌"):
                      self.loop.create_task(self.userDenied(payload.user_id, self.waitingForAcceptance.get(payload.user_id)))
        else:
            if(str(payload.emoji) == '✅'):
                if(self.currentVideos.get(payload.message_id, None) != None):
                    self.currentVideos[payload.message_id] += 1

    """
    Whenever a reaction gets removed from a message, it checks the channel it is in,
    and if it is apart of this set of images, it subtracts 1 from it's score.

    Author: Kenny Blake
    """
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if(payload.message_id in self.currentVideos.keys()):
            self.currentVideos[payload.message_id] -= 1


    async def removeVideo(self, videoID):
        message = None
        authorID = None
        found = False
        if self.production:
            try:
                message = await self.productionChannel.fetch_message(videoID)
                authorID = message.author.id
                await message.delete()
                await self.productionChannel.send(f"{message.author.mention} I've detected your video with the messageid {videoID} as profane. This has been logged.")
                found = True
            except discord.errors.NotFound:
                print(f"A video was found to be nsfw but was deleted before this method could run. It's id was {videoID}.")
        else:
            try:
                message = await self.testChannel.fetch_message(videoID)
                authorID = message.author.id
                await message.delete()
                await self.testChannel.send(f"{message.author.mention} I've detected your video with the messageid {videoID} as profane. This has been logged.")
                found = True
            except discord.errors.NotFound:
                print(f"A video was found to be nsfw but was deleted before this method could run. It's id was {videoID}.")
        
        if self.currentVideos.get(videoID) != None:
            del self.currentVideos[videoID]
           
        if found:
            doc_ref = self.users_ref.document(str(authorID))

            data = doc_ref.get().to_dict()
            data.get('videos')[str(videoID)] = True

            doc_ref.update(
                data
            )




    """
    Ensures that the message supplied has a single MP4 file in it. 
    If it doesn't, it deletes the message and sends a little thing saying "hey you can't do that".
    
    Author: Kenny Blake
    """
    async def validateVideo(self, message: discord.Message):
        channel = message.channel
        attachments: List[discord.Attachment] = message.attachments
        if(self.active):
            if(len(attachments) == 1):
                print(attachments[0].content_type)
                if (attachments[0].content_type == "video/mp4" or attachments[0].content_type == "video/quicktime"):
                    if(self.currentVideos.get(message.id, None) == None):
                        fileName = f"Videos/{message.id}.mp4"
                        await attachments[0].save(fileName)
                        duration = await self.getVideoLength(fileName)
                        if int(duration[0]) > 0 or int(duration[1]) > 15:
                            await channel.send(f"{message.author.mention}, your video:{attachments[0].filename} was too long! 15 Seconds max!")
                            await message.delete()
                        else:
                            await message.add_reaction("✅")
                            self.currentVideos[message.id] = 0
                            dmChannel = await message.author.create_dm()
                            self.loop.create_task(self.sendTerms(dmChannel, message, fileName))
                            
                else:
                    await message.delete()
                    await channel.send(f"{message.author.mention}, you can only send .mp4 files!")
            
            elif (len(attachments) > 1 ):
                await self.amountError(message)
            else:
                return


        else:
            return
    

    async def upload_blob(self, sourceFile, destination, userId):
        blob = self.bucket.blob(str(destination))

        blob.upload_from_filename(sourceFile)

        print(f"{userId} sent {destination}")

        self.loop.create_task(self.analyzeVideo(destination))
        self.stillProcessing.append(destination)
        print(type(destination))

        doc_ref = self.users_ref.document(str(userId))

        doc_ref.set({
            'videos': {
                str(destination): False
            }
        }, merge=True)


    async def userAccepted(self, userId, videoid):
        fileName = self.firstVideos.get(videoid)

        self.loop.create_task(self.upload_blob(fileName, videoid, userId))

        data = {
            u'accepted': True
        }
        

        doc_ref = self.users_ref.document(u'' + str(userId))
        doc_ref.set(data)

        del self.waitingForAcceptance[userId]

    async def userDenied(self, userId, videoID):
        print("got here")
        if self.production:
            message = await self.productionChannel.fetch_message(videoID)
            await message.delete()
        else:
            message = await self.testChannel.fetch_message(videoID)
            await message.delete()

        data = {
            u'accepted': False
        }

        doc_ref = self.users_ref.document(u''+ str(userId))
        doc_ref.set(data)

    async def deleteAllData(self,userId, message):
        doc_ref = self.users_ref.document(str(userId))
        bucket = self.storageClient.bucket('discord-video-uploader')
        data = doc_ref.get().to_dict()
        if data != None:
            if data.get('videos') != None:
                videos = data.get('videos')
                for i in videos.keys():
                    if videos[i] == False:
                        blob = bucket.blob(i)
                        if blob.exists():
                            blob.delete()
                        if self.production:
                            try:
                                message = await self.productionChannel.fetch_message(i)
                                await message.delete()
                            except discord.errors.NotFound:
                                print(f"Message {i} not found")
                        else:
                            try:
                                message = await self.testChannel.fetch_message(i)
                                await message.delete()
                            except discord.errors.NotFound:
                                print(f"Message {i} not found")
            doc_ref.delete()
        await message.author.send("Any data associated with you for this project has been deleted.")

        
    """
    The timer, aka hour glass. It's actually 20 minutes but I named it hour checker and don't feel like changing it. 
    Checks every 20 minutes what the most "upvoted" video is, and makes a video object of it. It then checks it, and if it passes all the checks, uploads it. 

    Author: Kenny Blake
    """      
    async def hourChecker(self):
        if (self.firstTime):
            self.firstTime = False
        else:
            minutes = math.floor((1200 - self.counter) / 60)
            seconds = (1200 - self.counter) % 60
            if self.production:
                await self.productionChannel.send(f"{minutes} Minutes, {seconds} seconds until the next video is chosen! Good Luck!")
            else:
                await self.testChannel.send(f"{minutes} Minutes, {seconds} seconds until the next video is chosen! Good Luck!")

        #While the program is running
        while self.active:
            #Just Started
            if self.counter == 0:
                if(self.production):
                    await self.productionChannel.send("20 Minutes until the video is chosen. Good luck!")
                else:
                    await self.testChannel.send("20 Minutes until the video is chosen. Good luck!")
                self.counter+= 1


            #5 Minutes
            elif self.counter == 300:
                if(self.production):
                    await self.productionChannel.send("15 Minutes until the video is chosen. Good luck!")
                else:
                    await self.testChannel.send("15 Minutes until the video is chosen. Good luck!")
                self.counter+= 1


            #10 Minutes    
            elif self.counter == 600:
                if(self.production):
                    await self.productionChannel.send("10 Minutes until the video is chosen. Halfway there!")
                else:
                    await self.testChannel.send("10 Minutes until the video is chosen. Halfway there!")
                self.counter+= 1


            #15 Minutes
            elif self.counter == 900: 
                if(self.production):
                    await self.productionChannel.send("5 Minutes until the video is chosen. Now would be a good time to review what you want uploaded!")
                else:
                    await self.testChannel.send("5 Minutes until the video is chosen. Now would be a good time to review what you want uploaded!")
                self.counter+= 1

            #19.5 Minutes
            elif self.counter == 1170:
                if(self.production):
                    await self.productionChannel.send("30 seconds until the video is chosen. Get those last votes in!")
                else:
                    await self.testChannel.send("30 seconds until the video is chosen. Get those last votes in!")
                self.counter+= 1
            
            #20 Minutes
            elif self.counter == 1200:
                mostVoted = await self.getMostVoted()
                if mostVoted == None:
                    if (self.production):
                        await self.productionChannel.send("""No videos were in this set, OR they are still being analyzed by Google.
Don't worry, any videos from this set still being analyzed will be automatically brought back over to the next one!""")
                    else:
                        await self.testChannel.send("""No videos were in this set, OR they are still being analyzed by Google.
Don't worry, any videos from this set still being analyzed will be automatically brought back over to the next one!""")
                
                self.counter = 0

                for i in self.currentVideos.keys():
                    if i in self.stillProcessing:
                        self.currentVideosTemp[i] = self.currentVideosTemp.get(i)
                self.currentVideos = self.currentVideosTemp
                self.currentVideosTemp = {}

            else:
                self.counter += 1
            
            await asyncio.sleep(.05)


    async def getMostVoted(self):
        stillLooking = True
        tempVideos = {}
        mostVoted = None
        maximum = 0
        while stillLooking:
            if len(self.currentVideos.keys()) != len(self.stillProcessing):
                    itsMessage = None
                    for i in self.currentVideos.keys():
                        if str(i) in self.stillProcessing:
                            tempVideos[i] = self.currentVideos.get(i)
                            del self.currentVideos[i]
                            break
                        else:
                            thisVal = self.currentVideos.get(i, -10000)
                            if thisVal > maximum:
                                maximum = thisVal
                                mostVoted = i
                        if(self.production):
                            itsMessage = await self.productionChannel.fetch_message(i)
                        else:
                            itsMessage = await self.testChannel.fetch_message(i)
                    nsfw = await self.ytu.checkDatabaseForNSFWValue(i, itsMessage.author.id, itsMessage.author.display_name)
                    if(nsfw):
                        del self.currentVideos[i]
                    elif nsfw == "Nope":
                        if self.production:
                            await self.productionChannel.send(f"{itsMessage.author.mention}, I attempted to upload your video, but I couldn't find your video on my database. Did you do ;forget_i_ever_existed?")
                        else:
                            await self.testChannel.send(f"{itsMessage.author.mention}, I attempted to upload your video, but I couldn't find your video on my database. Did you do ;forget_i_ever_existed?")
                    else:
                        stillLooking = False
                        
                        if(self.production):
                            await self.productionChannel.send(f"{itsMessage.author.mention}, your video has won! It's now uploading, you'll see it soon!")
                        else:
                            await self.testChannel.send(f"{itsMessage.author.mention}, your video has won! It's now uploading, you'll see it soon!")
            else:
                for i in tempVideos:
                    self.currentVideos[i] = tempVideos.get(i)
                return mostVoted
                        


    async def checkForAcceptAndUploadOrNot(self, doc, message, fileName):
        data = doc.to_dict()

        if data.get('accepted'):
            self.loop.create_task(self.upload_blob(fileName, message.id, message.author.id))
        else:
            await message.delete()
            await message.author.send("""Hey, sorry, you have to accept the terms of service to use the bot!
If you declined the terms, and now want to accept them, type ;forget_i_ever_existed into #bot-talk""")
        
        
    async def sendTerms(self, dmChannel, message, fileName):
        
        theMessage: discord.Message

        doc = self.users_ref.document(str(dmChannel.recipient.id))
        doc = doc.get()

        if doc.exists:
            self.loop.create_task(self.checkForAcceptAndUploadOrNot(doc, message, fileName))
        else:
            self.waitingForAcceptance[dmChannel.recipient.id] = message.id
            await message.author.send("""
                                Hey there! It looks like this is your first time sending a video, just some things you need to accept before you continue:
                                
    1. All videos are sent to Google for analysis. 
            Basically, it just tells me what it thinks it sees in the video, what words it hears being said in the video, and what text appears on the screen during the video.
            You can learn more about this here:
            https://cloud.google.com/video-intelligence/
            
    2. You also accept that you have received consent from everyone in any videos you send (if applicable), that they will appear in a video that will be sent into this bot, and analyzed. 
            If someone doesn't want you to send a video of them into this bot, then don't.
                                    
    3. Your discord ID will be placed in a database stating whether you accept or deny these terms. 
            To delete any data associated with you from the servers/databases running this bot, use the command ;forget_i_ever_existed
                                
    Please select ✅ to accept or ❌ to deny these terms.
                                
                                """)

            self.firstVideos[message.id] = fileName
            messages = await dmChannel.history(before=datetime.now() - timedelta(seconds=1)).flatten()
            if len(messages) > 1:
                for i in range(0, len(messages) -1):
                    if messages[i].author.id == 872945917471375380:
                        await messages[i].delete()
            messages = await dmChannel.history().flatten()

            for m in messages:
                if m.author.id == 872945917471375380:
                    theMessage = m
                    break
                    
            await theMessage.add_reaction("✅")
            await theMessage.add_reaction("❌")


    async def analyzeVideo(self, videoID):
        operation = self.video_client.annotate_video(
            request={
                "features": self.features, 
                "input_uri":f"gs://discord-video-uploader/{videoID}",
                "video_context": self.context}
        )

        operation.add_done_callback(self.callback)

        print(f"Now processing video {videoID}")

            
    def callback(self, operation_future):
        result = operation_future.result()
        videoID = (result.annotation_results[0].input_uri.strip("/discord-video-uploader/"))
        
        print(f"Finished processing {videoID}")
        self.stillProcessing.remove(int(videoID))
        for frame in result.annotation_results[0].explicit_annotation.frames:
            if videointelligence.Likelihood(frame.pornography_likelihood) > 3:
                self.loop.create_task(self.removeVideo(videoID))
                return

        for speech_transcription in result.annotation_results[1].speech_transcriptions:
            for alternative in speech_transcription.alternatives:
                for word_info in alternative.words:
                    word = word_info.word.lower()
                    if word in self.words:
                        self.loop.create_task(self.removeVideo(videoID))
                        return

        for text in result.annotation_results[0].text_annotations:
            print(text.text)
            if text.text in self.words:
                self.loop.create_task(self.removeVideo(videoID))
                return

    """
    Returns the length of the video.
    """
    async def getVideoLength(self, video):
        cap = cv2.VideoCapture(video)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frameCount = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frameCount / fps
        cap.release()
        return (duration / 60, duration % 60)    

"""
i hope u like my code❤️
"""