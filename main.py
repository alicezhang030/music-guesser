import asyncio

import discord
import random
import youtube_dl
import time

import kpop_list
import taylor_swift_list

from discord.ext import commands

from dotenv import load_dotenv
import os

client = commands.Bot(command_prefix="!")

#---------GLOBAL VARIABLES---------
play_for_secs = "5" #how many seconds the song plays for before players need to guess
guess_for_secs = "15" #how many seconds the players have to guess
players = {} #dictionary where the players are the keys and their scores are the values
in_game = False #True if the user is in a game already, False if not
song_key = {} #the selected playlist of songs
possible_categories = ['k-pop', 'taylor swift']

#---------COMMANDS---------
@client.command(name = "newGame", help = "!newGame [category] Starts a new music guessing game session. Categories: 'K-Pop,' 'TS' (Taylor Swift). Default K-Pop.")
async def newGame(ctx, category="k-pop"):
    global in_game, song_key

    if ctx.message.author.voice is None:  # the author of the msg isn't in a VC
        await ctx.send("You're not in a voice channel yet. Join a voice channel for me to work!")
        return
    else:
        voice_channel = ctx.message.author.voice.channel

    if ctx.voice_client is None: #if the bot isn't already in a VC
        await voice_channel.connect()
    else: #if the bot is in a VC already
        if ctx.voice_client.channel is not voice_channel:
            await ctx.send("I am switching voice channels now...")
            await ctx.voice_client.move_to(voice_channel)

    if in_game:
        time.sleep(0.5)
        await ctx.send("A game is already in progress! Please end this one before starting a new game.")
    else:
        #initialize all of the players
        players_list = [ctx.message.author]
        if ctx.message.mentions is not None:  # if it is multiplayer
            players_list = players_list + ctx.message.mentions

        for player in players_list:
            players[player] = 0

        #initialize songs
        if category.lower() == "k-pop":
            song_key = kpop_list.song_key
            time.sleep(0.5)
        elif category.lower() == 'ts':
            song_key = taylor_swift_list.song_key
            time.sleep(0.5)

        for key in song_key:
            song_key[key].played_before = False

        await round(ctx)


@client.command(name = "round", help = "Starts a new round in the game.")
async def round(ctx):
    global players, in_game

    if len(song_key) == 0: #if the user used !round before setting up a category
        await newGame(ctx)
        return

    in_game = True

    ydl_opts = {
        'format': 'bestaudio/best',
    }

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    vc = ctx.voice_client

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        selected_song_url = random_song_selection()
        info = ydl.extract_info(selected_song_url, download=False)
        plain_audio_url = info['formats'][0]['url']
        source = await discord.FFmpegOpusAudio.from_probe(plain_audio_url, **FFMPEG_OPTIONS)
        vc.play(source)

    time.sleep(int(play_for_secs))

    vc.stop()

    await ctx.send("What is the title of this song?")

    def check(message): #check if the message was sent by one of the players and if their guess is the right answer
        if message.author in players and message.content.lower() == song_key[selected_song_url].title.lower():
            return True
        return False

    try:
        guess = await client.wait_for('message', check=check, timeout=int(guess_for_secs))
    except asyncio.TimeoutError:
        await ctx.send("Time is up and no one got it right :( The correct answer is " + song_key[selected_song_url].title)
    else:
        time.sleep(0.4)
        players[guess.author] = players[guess.author] + 1
        await ctx.send("Woo hoo! {.author} got it correct.".format(guess))
        time.sleep(1)
        if all_songs_played():
            time.sleep(1)
            await ctx.send("All of the songs in the playlist has been played.")
            time.sleep(0.6)
            await endGame(ctx)
        else:
            await ctx.send("Here's the scoreboard so far...")
            time.sleep(1)
            for key in players:
                await ctx.send(key.name + "#" + key.discriminator + "'s score is currently: " + str(players[key]))
                time.sleep(0.8)

@client.command(name = "endGame", help = "Ends the game.")
async def endGame(ctx):
    global in_game, song_key

    if ctx.voice_client is not None:
        in_game = False
        song_key = {} #reset the song key

        winning_player = None
        winning_score = 0

        for key in players:
            if(players[key] > winning_score):
                winning_player = key.name + "#" + key.discriminator
                winning_score = players[key]

        if winning_player is not None:
            time.sleep(0.4)
            await ctx.send("That was a good game :D")
            time.sleep(1)
            await ctx.send("The winner is...")
            time.sleep(1.5)
            await ctx.send(winning_player + "!")
            time.sleep(1.5)
            await ctx.send("Here's the final scoreboard...")
            time.sleep(1)
            for key in players:
                await ctx.send(key.name + "#" + key.discriminator + "'s final score: " + str(players[key]))
                time.sleep(0.8)

        await ctx.voice_client.disconnect()
    else:
        await ctx.send("Uh...I am not connected to a voice channel. There's no game going on.")

@client.command(name = "playFor", help = "Set the number of seconds each song play for.")
async def playFor(ctx, new_secs):
    global play_for_secs
    if not new_secs.isdigit():
        await ctx.send("Seconds are numbers...")
        return
    else:
        play_for_secs = new_secs
        await ctx.send("Got it. The songs will now play for " + play_for_secs + " seconds.")

@client.command(name = "guessFor", help = "Set the number of seconds players have to guess.")
async def guessFor(ctx, new_secs):
    global guess_for_secs
    if not new_secs.isdigit():
        await ctx.send("Seconds are numbers...")
        return
    else:
        guess_for_secs= new_secs
        await ctx.send("Got it. The guessing time limit is now set to " + guess_for_secs + " seconds.")

#---------EVENTS---------
@client.event
async def on_ready():
    print('Bot is ready!')

#---------HELPER METHODS---------

def all_songs_played():
    for key in song_key:
        if song_key[key].played_before is False: #there is a song that hasn't been played yet
            return False
    return True

def random_song_selection():
    random_number = random.randint(0, len(song_key) - 1)

    while song_key[list(song_key.keys())[random_number]].played_before is True:
        random_number = random.randint(0, len(song_key) - 1)

    song_key[list(song_key.keys())[random_number]].played_before = True

    return list(song_key.keys())[random_number]

load_dotenv('.env')
client.run(os.getenv('BOT_TOKEN'))
