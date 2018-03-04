import aiohttp
import discord
import os
import sqlite3
import util

class LastBot(discord.Client):
    def init(self):
        # Buncha constants.
        self.unames = {}
        self.prefixes = set(['!', '.', '_'])
        self.cmds = set(['set', 'show', 'last', 'fm', 'unset', 'collage', 'toptracks'])
        self.last_api_root = 'http://ws.audioscrobbler.com/2.0/'
        self.last_api_key = os.environ['LAST_API_KEY']
        self.user_agent = 'last-fm (http://github.com/ajnirp/loonssey)'
        self.headers = {'User-Agent': self.user_agent}
        self.get_params = {'limit': 2}
        self.last_user_url = 'http://last.fm/user/{}'
        self.last_logo_url = 'https://i.imgur.com/04GyRqO.jpg'
        self.db = 'db/loonssey.db'
        self.last_colour = 0xd51007
        self.methods = {
            'get_tracks': 'user.getrecenttracks',
            'get_info': 'user.getinfo',
            'top_tracks': 'user.gettoptracks',
        }
        self.read_unames()
        self.refresh_emojis()
        self.tapmusic_url = 'http://www.tapmusic.net/collage.php?user={}&type={}&size={}{}{}{}'
        # tapmusic_url format: user, type, size, caption, artistonly, playcount
        self.time_ramges = ['7day', '1month', '3month', '6month', '12month', 'overall']
        self.collage_sizes = ['3x3', '4x4', '5x5', '2x6']
        self.time_range_announce = {
            '7day': 'last 7 days',
            '1month': 'past month',
            '3month': 'last 3 months',
            '6month': 'last 6 months',
            '12month': 'past year',
            'overall': 'all time',
        }
        # A user-friendly way to state the time range, used for forming reports.

    async def generic_failure_msg(self, channel):
        report = '{} Error retrieving your last.fm data'
        report = report.format(self.emojis['angerycry'])
        await self.send_message(channel, report)

    def build_endpoint_url(self, method, uname):
        api_call_fragment = '?method={}&user={}&api_key={}&format=json'
        return self.last_api_root + api_call_fragment.format(
            self.methods[method], uname, self.last_api_key)

    def refresh_emojis(self):
        self.emojis = {}
        for emoji in self.get_all_emojis():
            emoji_str = '<:{}:{}>'.format(emoji.name, emoji.id)
            self.emojis[emoji.name] = emoji_str

    async def on_ready(self):
        self.init()
        report = 'Logged in: {} / {}'
        report = report.format(self.user.name, self.user.id)
        print(report)

    def read_unames(self):
        conn = sqlite3.connect(self.db)
        for row in conn.execute('select * from unames'):
            self.unames[row[0]] = row[1]
        conn.close()

    async def on_message(self, message):
        # https://stackoverflow.com/a/611708
        prefixes = getattr(self, 'prefixes', False)
        if not prefixes:
            self.init()
        msg = message.content
        if len(msg) == 0: return
        if msg[0] not in self.prefixes: return
        tokens = msg[1:].split()
        if len(tokens) == 0: return
        if tokens[0] not in self.cmds: return
        if tokens[0] == 'set' and len(tokens) == 2:
            await self.set_uname(message.author, tokens[1], message.channel)
        elif tokens[0] == 'unset' and len(tokens) == 1:
            await self.unset_uname(message.author, message.channel)
        elif tokens[0] == 'show' and len(tokens) == 1:
            await self.display_profile(message.author, message.channel)
        elif tokens[0] in ['fm', 'last']:
            if len(message.mentions) == 0:
                await self.show_tracks(message.author, message.channel)
            elif len(message.mentions) == 1:
                await self.show_tracks(message.mentions[0], message.channel)
        elif tokens[0] == 'collage':
            if len(message.mentions) == 0:
                await self.display_collage(message.author, message.channel, tokens[1:])
            elif len(message.mentions) == 1:
                await self.display_collage(message.mentions[0], message.channel, tokens[1:])
        elif tokens[0] == 'toptracks':
            if len(message.mentions) == 0:
                await self.display_toptracks(message.author, message.channel, tokens[1:])
            elif len(message.mentions) == 1:
                await self.display_toptracks(message.mentions[0], message.channel, tokens[1:])

    async def set_uname(self, member, uname, channel):
        self.unames[member.id] = uname
        conn = sqlite3.connect(self.db)
        conn.execute('insert or replace into unames values(?, ?)', (member.id, uname))
        conn.commit()
        conn.close()
        report = '{} Your last.fm username has been set to: {}'
        report = report.format(self.emojis['b_approve'], uname)
        await self.send_message(channel, report)

    async def unset_uname(self, member, channel):
        if member.id not in self.unames:
            report = "{} {}, please set your last.fm username using `.set`. Example: `.set rj`"
            report = report.format(member.name, self.emojis['b_stop'])
            await self.send_message(channel, report)
            return
        uname = self.unames[member.id]
        del self.unames[member.id]
        conn = sqlite3.connect(self.db)
        conn.execute('delete from unames where uid=?', (member.id,))
        conn.commit()
        conn.close()
        report = '{} Your last.fm username has been unset (it was: {})'
        report = report.format(self.emojis['b_approve'], uname)
        await self.send_message(channel, report)

    async def display_profile(self, member, channel):

        async def get_profile(uname):
            url = self.build_endpoint_url('get_info', uname)
            async with aiohttp.get(url, headers=self.headers) as r:
                if r.status == 200:
                    js = await r.json()
                    return js
                else:
                    return None

        def parse_js(js):
            thumb_url = self.last_logo_url
            url = js['url']
            for _dict in js['image']:
                if _dict['size'] == 'extralarge':
                    thumb_url = _dict['#text']
                    # Replace 'png' with 'jpg' in the URL.
                    # This is a hack to allow Discord embeds to work.
                    thumb_url = thumb_url[:-3] + 'jpg'
            data = {}
            data['account_created'] = js['registered']['unixtime']
            data['account_created'] = util.parse_timestamp(data['account_created'])
            data['scrobbles'] = js['playcount']
            data['country'] = js['country']
            if data['country'] == '': del data['country']
            data['age'] = js['age']
            if data['age'] == '0': del data['age']
            return thumb_url, url, data

        def create_profile_embed(user_url, js):
            embed = discord.Embed(
                title=uname,
                type='rich',
                description='last.fm profile',
                url=user_url,
                timestamp=discord.Embed.Empty,
                footer=discord.Embed.Empty,
                colour=self.last_colour)
            thumb_url, url, data = parse_js(js['user'])
            embed = embed.set_thumbnail(url=thumb_url)
            for key, val in data.items():
                embed = embed.add_field(name=util.snake_case_to_title_case(key), value=val)
            return embed

        if member.id not in self.unames:
            report = "{} {}, please set your last.fm username using `.set`. Example: `.set rj`"
            report = report.format(member.name, self.emojis['b_stop'])
            await self.send_message(channel, report)
            return
        uname = self.unames[member.id]
        user_url = self.last_user_url.format(self.unames[member.id])
        js = await get_profile(uname)
        if js is None or 'user' not in js:
            await self.generic_failure_msg(channel)
        else:
            embed = create_profile_embed(user_url, js)
            await self.send_message(channel, content=None, embed=embed)

    async def show_tracks(self, member, channel):
        def parse_js(js):
            if 'recenttracks' not in js:
                return None
            if 'track' not in js['recenttracks']:
                return None
            tracks = js['recenttracks']['track']
            return [(t['artist']['#text'], t['name'], t['album']['#text']) for t in tracks]

        if member.id not in self.unames:
            report = "{} {}, please set your last.fm username using `.set`. Example: `.set rj`"
            report = report.format(member.name, self.emojis['b_stop'])
            await self.send_message(channel, report)
            return
        uname = self.unames[member.id]
        url = self.build_endpoint_url('get_tracks', uname)
        async with aiohttp.get(url, params=self.get_params, headers=self.headers) as r:
            if r.status == 200:
                js = await r.json()
                tracks = parse_js(js)
                if tracks == None:
                    await self.generic_failure_msg(channel)
                else:
                    footer = self.last_user_url.format(uname)
                    footer = '<{}>'.format(footer)
                    tracks = tracks[:2]
                    captions = ['Current', 'Previous']
                    report = '\n'.join('**{}**: {} - {} [{}]'.format(captions[i], *t) for i, t in enumerate(tracks))
                    report += '\n' + footer
                    await client.send_message(channel, report)
            else:
                await self.generic_failure_msg(channel)

    async def display_collage(self, member, channel, tokens):
        def form_filename(uname, data):
            return uname + '_'.join(data) + '.jpg'

        if member.id not in self.unames:
            report = "{} {}, please set your last.fm username using `.set`. Example: `.set rj`"
            report = report.format(member.name, self.emojis['b_stop'])
            await self.send_message(channel, report)
            return

        # Parse tokens to identify the URL we will send a GET req to
        tokens = set(tokens)
        artistonly = '&artistonly=true' if 'artists' in tokens else ''
        playcounts = '&playcount=true' if 'playcounts' in tokens else ''
        captions = '&caption=true' if len(playcounts) > 0 or 'captions' in tokens else ''
        size = '3x3'
        for _s in self.collage_sizes:
            if _s in tokens:
                size = _s
                break
        range_ = '7day'
        for _r in self.time_ramges:
            if _r in tokens:
                range_ = _r

        uname = self.unames[member.id]

        # Make the GET req, download the image and upload it to the channel
        url = self.tapmusic_url.format(uname, range_, size, captions, artistonly, playcounts)
        async with aiohttp.get(url, headers=self.headers) as r:
            if r.status != 200:
                report = '{} Error retrieving your last.fm data'
                report = report.format(self.emojis['angerycry'])
                await self.send_message(channel, report)
                return
            data = await r.read()
            fname = form_filename(uname, [artistonly, playcounts, captions, size, range_])
            with open(fname, 'wb') as f:
                f.write(data)
            if not os.path.isfile(fname):
                report = '{} Error retrieving your last.fm data'
                report = report.format(self.emojis['angerycry'])
                await self.send_message(channel, report)
                return
            report = "{} Here's the {} last.fm collage for <{}>"
            user_url = self.last_user_url.format(uname)
            report = report.format(self.emojis['b_go'], size, user_url)
            await client.send_file(channel, fname, filename='collage.jpg', content=report)
            os.remove(fname)

    async def display_toptracks(self, member, channel, tokens):
        def parse_js(js):
            def truncate_name(s):
                TRACK_NAME_LIMIT = 47
                if len(s) < TRACK_NAME_LIMIT:
                    return s
                else:
                    return s[:TRACK_NAME_LIMIT] + '...'
            if 'toptracks' not in js: return None
            result = [(truncate_name(t['artist']['name']), truncate_name(t['name']), t['playcount']) \
                      for t in js['toptracks']['track']]
            return result

        if member.id not in self.unames:
            report = "{} {}, please set your last.fm username using `.set`. Example: `.set rj`"
            report = report.format(member.name, self.emojis['b_stop'])
            await sel

        range_ = '7day'
        for _r in self.time_ramges:
            if _r in tokens:
                range_ = _r
                break

        uname = self.unames[member.id]
        user_url = self.last_user_url.format(self.unames[member.id]) + '/library/tracks'

        url = self.build_endpoint_url('top_tracks', uname) + '&limit=10&period={}'.format(range_)

        async with aiohttp.get(url, params=self.get_params, headers=self.headers) as r:
            if r.status == 200:
                js = await r.json()
                data = parse_js(js)
                if data == None:
                    await self.generic_failure_msg(channel)
                else:
                    header = 'Top tracks for <{}> ({})\n\n'
                    header = header.format(user_url, self.time_range_announce[range_])
                    report_lines = []
                    report = '\n'.join('{}. {} - {} [{} plays]'.\
                        format(i+1, *datum) for i, datum in enumerate(data))
                    report = header + report
                    await client.send_message(channel, report)
            else:
                await self.generic_failure_msg(channel)

client = LastBot()
client.run(os.environ['LAST_BOT_TOKEN'])
