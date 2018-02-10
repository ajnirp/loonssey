import aiohttp
import discord
import os

class LastBot(discord.Client):
    def init(self):
        self.unames = {}
        self.prefixes = set(['!', '.', '_'])
        self.cmds = set(['set', 'show', 'last', 'unset'])
        self.last_api_root = 'http://ws.audioscrobbler.com/2.0/'
        self.get_tracks_url = '?method=user.getrecenttracks&user={}&api_key={}&format=json'
        self.last_api_key = os.environ['LAST_API_KEY']
        self.user_agent = 'last-fm (http://github.com/ajnirp/loonssey)'
        self.headers = {'User-Agent': self.user_agent}
        self.get_params = {'limit': 2}
        self.last_user_url = 'http://last.fm/user/{}'

    async def on_ready(self):
        self.init()
        report = 'Logged in: {} / {}'
        report = report.format(self.user.name, self.user.id)
        print(report)

    async def on_message(self, message):
        msg = message.content
        if msg[0] not in self.prefixes: return
        tokens = msg[1:].split()
        if len(tokens) == 0: return
        if tokens[0] not in self.cmds: return
        if tokens[0] == 'set' and len(tokens) == 2:
            await self.set_uname(message.author, tokens[1], message.channel)
        elif tokens[0] == 'unset' and len(tokens) == 1:
            await self.unset_uname(message.author, message.channel)
        elif tokens[0] == 'show' and len(tokens) == 1:
            await self.show_uname(message.author, message.channel)
        elif tokens[0] == 'last' and len(tokens) == 1:
            await self.show_tracks(message.author, message.channel)

    async def set_uname(self, member, uname, channel):
        self.unames[member.id] = uname
        report = 'Your last.fm username has been set to: {}'
        report = report.format(uname)
        await self.send_message(channel, report)

    async def unset_uname(self, member, channel):
        if member.id not in self.unames:
            report = "You haven't set your last.fm username. Use `set` to do so"
            await self.send_message(channel, report)
            return
        uname = self.unames[member.id]
        del self.unames[member.id]
        report = 'Your last.fm username has been unset (it was: {})'
        report = report.format(uname)
        await self.send_message(channel, report)

    async def show_uname(self, member, channel):
        if member.id not in self.unames:
            report = "You haven't set your last.fm username. Use `set` to do so"
            await self.send_message(channel, report)
            return
        url = self.last_user_url.format(self.unames[member.id])
        report = 'Your last.fm is set to: {}'.format(url)
        await self.send_message(channel, report)

    def parse_json_response(self, js):
        if 'recenttracks' not in js:
            return None
        if 'track' not in js['recenttracks']:
            return None
        tracks = js['recenttracks']['track']
        return [(t['artist']['#text'], t['name'], t['album']['#text']) for t in tracks]

    async def show_tracks(self, member, channel):
        if member.id not in self.unames:
            report = "You haven't set your last.fm username. Use `set` to do so"
            await self.send_message(channel, report)
            return
        uname = self.unames[member.id]
        url = self.get_tracks_url.format(uname, self.last_api_key)
        url = self.last_api_root + url
        async with aiohttp.get(url, params=self.get_params, headers=self.headers) as r:
            if r.status == 200:
                js = await r.json()
                tracks = self.parse_json_response(js)
                if tracks == None:
                    report = 'Error retrieving your last.fm data'
                    await self.send_message(channel, report)
                else:
                    header = self.last_user_url.format(uname)
                    header = '<{}>'.format(header)
                    # TODO: truncate in case track names exceed 2000 chars
                    # TODO: sanitize in case track names contain asterisks etc.
                    # TODO: error handling for when album etc. is not supplied
                    # TODO: error handling for if there are no recent tracks
                    report = '\n'.join('{} - {} [{}]'.format(*t) for t in tracks)
                    report = header + '\n' + report
                    await client.send_message(channel, report)
            else:
                report = 'Error retrieving your last.fm data'
                await self.send_message(channel, report)

client = LastBot()
client.run(os.environ['LAST_BOT_TOKEN'])
