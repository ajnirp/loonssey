import aiohttp
import discord
import os
import sqlite3
import urllib.parse
import util

class LastBot(discord.Client):
    def init(self):
        # Buncha constants.
        self.unames = {}
        self.prefixes = set(['!', '.', '_'])
        self.cmds = set(['set', 'show', 'last', 'fm', 'fmyt', 'unset', \
                         'collage', 'toptracks', 'topalbums', 'topartists'])
        self.last_api_root = 'http://ws.audioscrobbler.com/2.0/'
        self.last_api_key = os.environ['LAST_API_KEY']
        self.user_agent = 'last-fm (http://github.com/ajnirp/loonssey)'
        self.headers = {'User-Agent': self.user_agent}
        self.get_params = {'limit': 2}
        self.last_user_url = 'http://last.fm/user/{}'
        self.last_logo_url = 'https://i.imgur.com/04GyRqO.jpg'
        self.db = 'db/loonssey.db'
        self.last_colour = 0xd51007
        self.read_unames()
        self.refresh_emojis()
        # tapmusic_url format: user, type, size, caption, artistonly, playcount
        self.tapmusic_url = 'http://www.tapmusic.net/collage.php?user={}&type={}&size={}{}{}{}'
        self.time_ramges = ['7day', '1month', '3month', '6month', '12month', 'overall']
        self.collage_sizes = ['3x3', '4x4', '5x5', '2x6']
        # A user-friendly way to state the time range, used for forming reports.
        self.time_range_announce = {
            '7day': 'last 7 days',
            '1month': 'past month',
            '3month': 'last 3 months',
            '6month': 'last 6 months',
            '12month': 'past year',
            'overall': 'all time',
        }
        self.last_date_presets = {
            '7day': 'LAST_7_DAYS',
            '1month': 'LAST_30_DAYS',
            '3month': 'LAST_90_DAYS',
            '6month': 'LAST_180_DAYS',
            '12month': 'LAST_365_DAYS',
            'overall': 'ALL',
        }
        self.yt_api_key = os.environ['YOUTUBE_API_KEY']
        self.yt_search_url = 'https://www.googleapis.com/youtube/v3/search?part=snippet&key={}&maxResults=1&q={}'

    async def generic_lfm_failure_msg(self, channel):
        report = '{} Error retrieving your last.fm data'
        report = report.format(self.emojis['angerycry'])
        await self.send_message(channel, report)

    async def generic_yt_failure_msg(self, channel):
        report = '{} Error searching YouTube'
        report = report.format(self.emojis['angerycry'])
        await self.send_message(channel, report)

    def build_last_endpoint_url(self, method, uname):
        api_call_fragment = '?method={}&user={}&api_key={}&format=json'
        return self.last_api_root + api_call_fragment.format(
            method, uname, self.last_api_key)

    def build_yt_endpoint_url(self, query):
        quoted_query = urllib.parse.quote_plus(query)
        url = self.yt_search_url.format(self.yt_api_key, quoted_query)
        return url

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
        ignore = False
        for role in message.author.roles:
            if role.id == '220160015380512768' or role.name == 'botless':
                ignore = True
        if ignore:
            return
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
            target = message.author
            if len(message.mentions) == 1:
                target = message.mentions[0]
            await self.display_tracks(target, message.channel)
        elif tokens[0] == 'collage':
            target = message.author
            if len(message.mentions) == 1:
                target = message.mentions[0]
            await self.display_collage(target, message.channel, tokens[1:])
        elif tokens[0] in ['toptracks', 'topalbums', 'topartists']:
            target = message.author
            type_ = tokens[0][3:]
            if len(message.mentions) == 1:
                target = message.mentions[0]
            await self.display_top(type_, target, message.channel, tokens[1:])
        elif tokens[0] == 'fmyt':
            target = message.author
            if len(message.mentions) == 1:
                target = message.mentions[0]
            await self.display_fmyt(target, message.channel)

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
            url = self.build_last_endpoint_url('user.getinfo', uname)
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
            await self.generic_lfm_failure_msg(channel)
        else:
            embed = create_profile_embed(user_url, js)
            await self.send_message(channel, content=None, embed=embed)

    async def display_tracks(self, member, channel):
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
        url = self.build_last_endpoint_url('user.getrecenttracks', uname)
        async with aiohttp.get(url, params=self.get_params, headers=self.headers) as r:
            if r.status == 200:
                js = await r.json()
                tracks = parse_js(js)
                if tracks == None:
                    await self.generic_lfm_failure_msg(channel)
                else:
                    footer = self.last_user_url.format(uname)
                    footer = '<{}>'.format(footer)
                    tracks = tracks[:2]
                    captions = ['Current', 'Previous']
                    report = '\n'.join('**{}**: {} - {} [{}]'.format(captions[i], *t) for i, t in enumerate(tracks))
                    report += '\n' + footer
                    await client.send_message(channel, report)
            else:
                await self.generic_lfm_failure_msg(channel)

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

    # Handles top tracks, albums, and artists. A three-in-one method.
    async def display_top(self, type_, member, channel, tokens):
        def parse_js_helper(t, type_):
            if type_ in ['albums', 'tracks']:
                return (util.truncate(t['artist']['name']), util.truncate(t['name']), t['playcount'])
            elif type_ == 'artists':
                return (util.truncate(t['name']), t['playcount'])

        def parse_js(js, type_):
            result_type = 'top' + type_
            if result_type not in js: return None
            result = [parse_js_helper(t, type_) for t in js[result_type][type_[:-1]]]
            return result

        def report_format(type_):
            if type_ in ['albums', 'tracks']:
                return '{}. {} - {} [{} plays]'
            elif type_ == 'artists':
                return '{}. {} [{} plays]'

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
        date_preset = self.last_date_presets[range_]
        user_url = self.last_user_url.format(self.unames[member.id]) + \
                   '/library/{}?date_preset={}'.format(type_, date_preset)

        method = 'user.gettop{}'.format(type_)
        url = self.build_last_endpoint_url(method, uname) + '&limit=10&period={}'.format(range_)

        async with aiohttp.get(url, params=self.get_params, headers=self.headers) as r:
            if r.status == 200:
                js = await r.json()
                data = parse_js(js, type_)
                if data == None:
                    await self.generic_lfm_failure_msg(channel)
                else:
                    header = 'Top {} for **{}** ({})\n'
                    header = header.format(type_, uname, self.time_range_announce[range_])
                    report = '\n'.join(report_format (type_).\
                        format(i+1, *datum) for i, datum in enumerate(data))
                    footer = '\n<{}>'.format(user_url)
                    report = header + report + footer
                    await client.send_message(channel, report)
            else:
                await self.generic_lfm_failure_msg(channel)

    async def display_fmyt(self, member, channel):
        def parse_js(js):
            if 'recenttracks' not in js:
                return None
            if 'track' not in js['recenttracks']:
                return None
            tracks = js['recenttracks']['track']
            return [(t['artist']['#text'], t['name']) for t in tracks]

        if member.id not in self.unames:
            report = "{} {}, please set your last.fm username using `.set`. Example: `.set rj`"
            report = report.format(member.name, self.emojis['b_stop'])
            await self.send_message(channel, report)
            return
        uname = self.unames[member.id]
        lfm_url = self.build_last_endpoint_url('user.getrecenttracks', uname)
        async with aiohttp.get(lfm_url, params=self.get_params, headers=self.headers) as r1:
            if r1.status != 200:
                await self.generic_lfm_failure_msg(channel)
                return
            lfm_js = await r1.json()
            track = parse_js(lfm_js)
            if track == None:
                await self.generic_lfm_failure_msg(channel)
                return
            if len(track) == 0:
                report = 'No recent track found for **{}**'
                report = report.format(uname)
                await self.send_message(channel, report)
                return
            query = '{} - {}'.format(*track[0])
            yt_url = self.build_yt_endpoint_url(query)
            async with aiohttp.get(yt_url, headers=self.headers) as r2:
                if r2.status != 200:
                    await self.generic_yt_failure_msg(channel)
                    return
                yt_js = await r2.json()
                if 'items' not in yt_js:
                    await self.generic_yt_failure_msg(channel)
                    return
                results = yt_js['items']
                if len(results) == 0:
                    await self.generic_yt_failure_msg(channel)
                    return
                result = results[0]
                video_id = result['id']['videoId']
                video_url = 'https://youtu.be/{}'.format(video_id)
                video_title = result['snippet']['title']
                report = '{}\n{}'.format(video_title, video_url)
                await self.send_message(channel, report)

client = LastBot()
client.run(os.environ['LAST_BOT_TOKEN'])
