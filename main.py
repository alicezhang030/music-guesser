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

client = commands.Bot(command_prefix="!", help_command=None)

# ---------GLOBAL VARIABLES---------
play_for_secs = 10  # how many seconds the song plays for before players need to guess
guess_for_secs = 15  # how many seconds the players have to guess
players = {}  # dictionary where the players are the keys and their scores are the values
in_game = False  # True if the bot is in a game already, False if not
song_key = {}  # the selected playlist of songs
category = ""
possible_categories = ['k-pop', 'taylor swift']


# ---------COMMANDS--------
@client.command()
async def newGame(ctx):
    global in_game, song_key

    if in_game:
        await ctx.send("I'm facilitating someone else's game right now! Please wait for me :D")
        return
    elif ctx.message.author.voice is None:  # the author of the msg isn't in a VC
        await ctx.send("You're not in a voice channel yet. Join a voice channel for me to work!")
        return
    else:
        voice_channel = ctx.message.author.voice.channel

        if ctx.voice_client is None:  # if the bot isn't already in a VC
            await voice_channel.connect()
        else:  # if the bot is in a VC already
            if ctx.voice_client.channel is not voice_channel:
                await ctx.send("I am switching to your voice channel now...")
                await ctx.voice_client.move_to(voice_channel)

        # initialize all of the players
        players_list = [ctx.message.author]
        if ctx.message.mentions is not None:  # if it is multiplayer
            players_list = players_list + ctx.message.mentions

        for player in players_list:
            players[player] = 0

        await ctx.send("You have started a game with " + ", ".join(str(x) for x in players.keys()))
        time.sleep(0.5)
        category_msg = "Which category would you like to play? Your possible options are k-pop and taylor swift"
        await ctx.send(category_msg)

        def check(message):
            return message.author in players and message.content.lower() in possible_categories

        try:
            category = await client.wait_for('message', check=check, timeout=None)
        except asyncio.TimeoutError:
            await ctx.send("Yawn...I have fallen asleep waiting for your reply. Goodbye.")
        else:
            category = category.content
            await ctx.send("Sounds good! You have selected the category " + category)
            if category.lower() == "k-pop" or category.lower() == "k pop" or category.lower() == "kpop":
                song_key = kpop_list.song_key
                time.sleep(0.5)
            elif category.lower() == 'taylor swift' or category.lower() == 'taylorswift':
                song_key = taylor_swift_list.song_key
                time.sleep(0.5)

            for key in song_key:
                song_key[key].played_before = False

        await ctx.send("You may now start a new round with the !round command")
        time.sleep(0.5)
        await round(ctx)  # calls on the help! embed for !round


@client.command()
async def round(ctx):
    global players, in_game

    in_game = True
    await ctx.send("New round has begun!")

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

    time.sleep(play_for_secs)

    vc.stop()

    await ctx.send("What is the title of this song?")
    print("The title of the song is " + song_key[selected_song_url].title)

    def check(message):  # check if the message was sent by one of the players and if their guess is the right answer
        if message.author in players and message.content.lower() == song_key[selected_song_url].title.lower():
            return True
        return False

    try:
        guess = await client.wait_for('message', check=check, timeout=guess_for_secs)
    except asyncio.TimeoutError:
        await ctx.send(
            "Time is up and no one got it right :( The correct answer is " + song_key[selected_song_url].title)
    else:
        time.sleep(0.4)
        players[guess.author] = players[guess.author] + 1
        await ctx.send("Woo hoo! {.author} got it correct.".format(guess))
        time.sleep(1)
        await ctx.send("Here's the scoreboard so far...")
        time.sleep(1)
        for key in players:
            await ctx.send(key.name + "#" + key.discriminator + "'s score is currently: " + str(players[key]))
            time.sleep(0.8)


@client.command()
async def endGame(ctx):
    global in_game, song_key, players

    if ctx.voice_client is not None:
        winning_players = []
        winning_score = 0

        for key in players:
            if players[key] > winning_score:
                username = key.name + "#" + key.discriminator
                winning_players = [username]
                winning_score = players[key]
            elif players[key] == winning_score:
                username = key.name + "#" + key.discriminator
                winning_players.append(username)

        if len(winning_players) != 0:
            time.sleep(0.4)
            await ctx.send("That was a good game :D")
            time.sleep(1)
            await ctx.send("The winner(s) is...")
            time.sleep(1.5)
            await ctx.send(", ".join(str(x) for x in winning_players))
            time.sleep(1.5)
            await ctx.send("Here's the final scoreboard...")
            time.sleep(1)
            for key in players:
                await ctx.send(key.name + "#" + key.discriminator + "'s final score: " + str(players[key]))
                time.sleep(0.8)

        default_settings()
        await ctx.voice_client.disconnect()
    else:
        await ctx.send("Uh...I am not connected to a voice channel. There's no game going on.")


@client.command()
async def playFor(ctx, new_secs):
    global play_for_secs
    if not new_secs.isdigit():
        await ctx.send("Seconds are numbers...")
        return
    else:
        play_for_secs = int(new_secs)
        await ctx.send("Got it. The songs will now play for " + new_secs + " seconds.")


@client.command()
async def guessFor(ctx, new_secs):
    global guess_for_secs
    if not new_secs.isdigit():
        await ctx.send("Seconds are numbers...")
        return
    else:
        guess_for_secs = int(new_secs)
        await ctx.send("Got it. The guessing time limit is now set to " + new_secs + " seconds.")


@client.group(invoke_without_command=True)
async def help(ctx):
    em = discord.Embed(title="Help", description="Use !help <command> for more info on a command.")
    em.add_field(name="Start/End Game", value="newGame, round, endGame")
    em.add_field(name="Game Settings", value="playFor, guessFor")

    await ctx.send(embed=em)


@help.command()
async def newGame(ctx):
    em = discord.Embed(title="newGame",
                       description="Starts a new music guessing game.\nAvailable categories: K-Pop, TS (for Taylor Swift). The default category is K-Pop.\n@ mention other users to add them as players.")
    em.add_field(name="**Syntax**", value="!newGame <category> <@ mentions>")

    await ctx.send(embed=em)


@help.command()
async def round(ctx):
    em = discord.Embed(title="round",
                       description="Plays a song for players to guess, aka start a round.\nDO NOT use when no game is in progress.")
    em.add_field(name="**Syntax**", value="!round")

    await ctx.send(embed=em)


@help.command()
async def endGame(ctx):
    em = discord.Embed(title="endGame", description="Ends the current music guessing game and announces the winner.")
    em.add_field(name="**Syntax**", value="!endGame")

    await ctx.send(embed=em)


@help.command()
async def playFor(ctx):
    em = discord.Embed(title="playFor", description="Set the number of seconds a song will play for in the game.")
    em.add_field(name="**Syntax**", value="!playFor <seconds>")

    await ctx.send(embed=em)


@help.command()
async def guessFor(ctx):
    em = discord.Embed(title="playFor", description="Set the number of seconds players will have to guess in the game.")
    em.add_field(name="**Syntax**", value="!guessFor <seconds>")

    await ctx.send(embed=em)


# ---------EVENTS---------
@client.event
async def on_ready():
    print('Bot is ready!')


# ---------HELPER METHODS---------

def random_song_selection():
    random_number = random.randint(0, len(song_key) - 1)
    return list(song_key.keys())[random_number]

def default_settings():
    global play_for_secs, guess_for_secs, players, in_game, song_key, category

    play_for_secs = 10
    guess_for_secs = 15
    players = {}
    in_game = False
    song_key = {}
    category = ""

load_dotenv('.env')
client.run(os.getenv('BOT_TOKEN'))
