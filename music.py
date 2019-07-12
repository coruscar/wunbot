
import discord
from discord.ext import commands
import asyncio
import datetime
import glob, csv
import os, sys, subprocess, random
import psutil 
import sqlite3
import youtube_dl
import re


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.kick_sound_effects = ["wopwop.wav","denied.wav","e.wav","VHS.mp3"]
        self.bot = bot

    @commands.command()
    async def join(self, ctx, *, channel: discord.VoiceChannel):
        """Joins a voice channel"""

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()

    @commands.command()
    async def list_effects(self, ctx):
        """Joins a voice channel"""
        await ctx.send(self.kick_sound_effects)

    @commands.command()
    async def s(self, ctx):
        """Slaps user specified in message"""
        victim = ctx.message.mentions[0]
        kick_channel_name = "Slab"
        
        kick_sound = random.choice(self.kick_sound_effects)
        kick_channel_name = kick_sound[0:-4]
        kick_sound = "assets\\" + kick_sound

        if victim.voice is None:
            await ctx.send("Member not found")
            return
        
        await ctx.send('Slapping {}'.format(victim.name))
        kick_channel = await ctx.guild.create_voice_channel(kick_channel_name)

        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(kick_channel)
        await kick_channel.connect()
        await victim.move_to(kick_channel)

        await ctx.voice_client.move_to(kick_channel)
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(kick_sound))
        ctx.voice_client.play(source, after=lambda e: print('Player error: %s' % e) if e else None)
        await asyncio.sleep(3)
        for chan in ctx.guild.voice_channels:
            if chan.name == kick_channel_name:
                await chan.delete()
        await ctx.voice_client.disconnect()

    @commands.command()
    async def nick(self, ctx, arg1, arg2):
        victim = ctx.message.mentions[0]
        n = arg2
        await ctx.send('Changing `{}`\'s nickname to `{}`. Was `{}`.'.format(victim.name,arg2,victim.nick))
        await victim.edit(nick=n)

    @commands.command()
    async def play(self, ctx, *, query):
        """Plays a file from the local filesystem"""

        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(query))
        ctx.voice_client.play(source, after=lambda e: print('Player error: %s' % e) if e else None)

        await ctx.send('Now playing: {}'.format(query))

    @commands.command()
    async def yt(self, ctx, *, url):
        """Plays from a url (almost anything youtube_dl supports)"""

        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
            ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)

        await ctx.send('Now playing: {}'.format(player.title))

    @commands.command()
    async def stream(self, ctx, *, url):
        """Streams from a url (same as yt, but doesn't predownload)"""

        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)

        await ctx.send('Now playing: {}'.format(player.title))

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send("Changed volume to {}%".format(volume))

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""

        await ctx.voice_client.disconnect()

    @play.before_invoke
    @yt.before_invoke
    @stream.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()