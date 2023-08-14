import discord
import peewee
from discord.ext import commands
import modules.models as models
import modules.utilities as utilities
import settings
import logging
import asyncio
import modules.exceptions as exceptions
import re
import datetime
import random
from modules.games import PolyGame
from modules.league import free_agent_role_name
# import modules.imgen as imgen
# import modules.achievements as achievements

logger = logging.getLogger('polybot.' + __name__)


def roleelo_server_check():
    def predicate(ctx):
        if ctx.guild.id == settings.server_ids['polychampions']:
            return True
        # elif ctx.guild.id == settings.server_ids['main'] and settings.is_staff(ctx.author):
        #     return True
        elif settings.is_staff(ctx.author):
            return True
        return False
    return commands.check(predicate)


class misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if settings.run_tasks:
            self.bg_task = bot.loop.create_task(self.task_broadcast_newbie_message())
            self.bg_task3 = bot.loop.create_task(self.task_broadcast_newbie_steam_message())

    @commands.command(hidden=True, aliases=['ts'])
    @commands.is_owner()
    async def test(self, ctx, *, args: str = None):

        pass

    @commands.command(usage=None)
    @settings.in_bot_channel_strict()
    async def guide(self, ctx):
        """
        Show an overview of what the bot is for

        Type `[p]guide` for an overview of what this bot is for and how to use it.
        """
        bot_desc = ('This bot is designed to improve Polytopia multiplayer by filling in gaps in two areas: competitive leaderboards, and matchmaking.\n'
                    # 'Its primary home is [PolyChampions](https://discord.gg/YcvBheSv), a server focused on team play organized into a league.\n'
                    f'To register as a player with the bot use __`{ctx.prefix}setname Mobile User Name`__ or  __`{ctx.prefix}steamname Steam User Name`__')

        embed = discord.Embed(title='PolyELO Bot Donation Link', url='https://www.buymeacoffee.com/nelluk', description=bot_desc)

        embed.add_field(name='Matchmaking',
            value=f'This helps players organize and find games.\nFor example, use __`{ctx.prefix}opengame 1v1`__ to create an open 1v1 game that others can join.\n'
                f'To see a list of open games you can join use __`{ctx.prefix}opengames`__. Once the game is full the host would use __`{ctx.prefix}startgame`__ to close it and track it for the leaderboards.\n'
                f'See __`{ctx.prefix}help matchmaking`__ for all commands.', inline=False)

        embed.add_field(name='ELO Leaderboards',
            value='Win your games and climb the leaderboards! Earn sweet ELO points!\n'
                'ELO points are gained or lost based on your game results. You will gain more points if you defeat an opponent with a higher ELO.\n'
                f'Use __`{ctx.prefix}lb`__ to view the individual leaderboards. There is also a __`{ctx.prefix}lbsquad`__ squad leaderboard. Form a squad by playing with the same person in multiple games!'
                f'\nSee __`{ctx.prefix}help`__ for all commands.', inline=False)

        embed.add_field(name='Finishing tracked games',
            value=f'Use the __`{ctx.prefix}win`__ command to tell the bot that a game has concluded.\n'
            f'For example if Nelluk wins game 10150, he would type __`{ctx.prefix}win 10150 nelluk`__. The losing player can confirm using the same command. '
            'Games are auto-confirmed after 24 hours, or sooner if the losing side manually confirms.', inline=False)

        embed.set_thumbnail(url=self.bot.user.display_avatar.replace(size=512, format='webp'))
        embed.set_footer(text='Developer: Nelluk')
        await ctx.send(embed=embed)

    @commands.command(usage=None)
    @settings.in_bot_channel_strict()
    async def credits(self, ctx):
        """
        Display development credits
        """
        embed = discord.Embed(title='Support this project', url='https://www.buymeacoffee.com/nelluk')

        embed.add_field(name='Developer', value='Nelluk')
        embed.add_field(name='Source code', value='https://github.com/Nelluk/Polytopia-ELO-Bot')

        embed.add_field(name='Contributions', value='rickdaheals, koric, Gerenuk, alphaSeahorse, Octo, Artemis, Legorooj,  theoldlove', inline=False)

        embed.set_thumbnail(url=self.bot.user.display_avatar.replace(size=512, format='webp'))
        await ctx.send(embed=embed)

    @commands.command()
    @settings.in_bot_channel_strict()
    async def stats(self, ctx):
        """ Display statistics on games logged with this bot """

        embed = discord.Embed(title='PolyELO Statistics')
        last_month = (datetime.datetime.now() + datetime.timedelta(days=-30))
        last_quarter = (datetime.datetime.now() + datetime.timedelta(days=-90))
        last_week = (datetime.datetime.now() + datetime.timedelta(days=-7))

        games_played = models.Game.select().where(models.Game.is_completed == 1)
        games_played_90d = models.Game.select().where((models.Game.is_pending == 0) & (models.Game.date > last_quarter))
        games_played_30d = models.Game.select().where((models.Game.is_pending == 0) & (models.Game.date > last_month))
        games_played_7d = models.Game.select().where((models.Game.is_pending == 0) & (models.Game.date > last_week))

        incomplete_games = models.Game.select().where((models.Game.is_pending == 0) & (models.Game.is_completed == 0))

        participants_90d = models.Lineup.select(models.Lineup.player.discord_member).join(models.Game).join_from(models.Lineup, models.Player).join(models.DiscordMember).where(
            (models.Lineup.game.date > last_quarter)
        ).group_by(models.Lineup.player.discord_member).distinct()

        participants_30d = models.Lineup.select(models.Lineup.player.discord_member).join(models.Game).join_from(models.Lineup, models.Player).join(models.DiscordMember).where(
            (models.Lineup.game.date > last_month)
        ).group_by(models.Lineup.player.discord_member).distinct()

        participants_7d = models.Lineup.select(models.Lineup.player.discord_member).join(models.Game).join_from(models.Lineup, models.Player).join(models.DiscordMember).where(
            (models.Lineup.game.date > last_week)
        ).group_by(models.Lineup.player.discord_member).distinct()

        embed.add_field(value='\u200b', name=f'`{"----------------------------------":<35}` Global (Local)', inline=False)

        stats_0 = (f'`{"Total games completed:":<35}\u200b` {games_played.count()} ({games_played.where(models.Game.guild_id == ctx.guild.id).count()})\n'
                   f'`{"Incomplete games:":<35}\u200b` {incomplete_games.count()} ({incomplete_games.where(models.Game.guild_id == ctx.guild.id).count()})\n')
        embed.add_field(value='\u200b', name=stats_0[:256], inline=False)
        stats_1 = (f'`{"Games created in last 90 days:":<35}\u200b`\u200b {games_played_90d.count()} ({games_played_90d.where(models.Game.guild_id == ctx.guild.id).count()})\n'
                      f'`{"Games created in last 30 days:":<35}\u200b`\u200b {games_played_30d.count()} ({games_played_30d.where(models.Game.guild_id == ctx.guild.id).count()})\n'
                      f'`{"Games created in last 7 days:":<35}\u200b`\u200b {games_played_7d.count()} ({games_played_7d.where(models.Game.guild_id == ctx.guild.id).count()})\n'
                   )
        embed.add_field(value='\u200b', name=stats_1[:256], inline=False)

        stats_2 = (f'`{"Participants in last 90 days:":<35}\u200b` {participants_90d.count()} ({participants_90d.where(models.Game.guild_id == ctx.guild.id).count()})\n'
                   f'`{"Participants in last 30 days:":<35}\u200b` {participants_30d.count()} ({participants_30d.where(models.Game.guild_id == ctx.guild.id).count()})\n'
                   f'`{"Participants in last 7 days:":<35}\u200b` {participants_7d.count()} ({participants_7d.where(models.Game.guild_id == ctx.guild.id).count()})\n')
        embed.add_field(value='\u200b', name=stats_2[:256], inline=False)
        await ctx.send(embed=embed)

    @commands.command(hidden=True, usage='message', aliases=['pingmobile', 'pingsteam'])
    @commands.cooldown(1, 30, commands.BucketType.user)
    @settings.in_bot_channel_strict()
    @models.is_registered_member()
    async def pingall(self, ctx, *, message: str = None):
        """ Ping everyone in all of your incomplete games

        Not useable by all players.
        You can use `pingsteam` to only ping players in your Steam platform games,
        or `pingmobile` to only ping players in your Mobile games.

         **Examples**
        `[p]pingall My phone died and I will make all turns tomorrow`
        Send a message to everyone in all of your incomplete games
        `[p]pingall @Glouc3stershire Glouc is in Tahiti and will play again tomorrow`
        *Staff:* Send a message to everyone in another player's games
        `[p]pingmobile My phone died but I'm still taking turns on Steam!`

        """
        if not message:
            return await ctx.send('Message is required.')

        m = utilities.string_to_user_id(message.split()[0])

        if m:
            logger.debug(f'Third party use of {ctx.invoked_with}')
            # Staff member using command on third party
            if settings.get_user_level(ctx.author) <= 3:
                logger.debug('insufficient user level')
                return await ctx.send('You do not have permission to use this command on another player\'s games.')
            message = ' '.join(message.split()[1:])  # remove @Mention first word of message
            target = str(m)
            log_message = f'{models.GameLog.member_string(ctx.author)} used pingall on behalf of player ID `{target}` with message: '
        else:
            logger.debug('first party usage of pingall')
            # Play using command on their own games
            if settings.get_user_level(ctx.author) <= 2:
                logger.debug('insufficient user level')
                return await ctx.send('You do not have permission to use this command. You can ask a server staff member to use this command on your games for you.')
            target = str(ctx.author.id)
            log_message = f'{models.GameLog.member_string(ctx.author)} used {ctx.invoked_with} with message: '

        try:
            player_match = models.Player.get_or_except(player_string=target, guild_id=ctx.guild.id)
        except exceptions.NoSingleMatch:
            return await ctx.send(f'User <@{target}> is not a registered ELO player.')

        if ctx.invoked_with == 'pingall':
            platform_filter = 2
            title_str = 'Message to all players in unfinished games'
        elif ctx.invoked_with == 'pingmobile':
            platform_filter = 1
            title_str = 'Message to players in unfinished mobile games'
        elif ctx.invoked_with == 'pingsteam':
            platform_filter = 0
            title_str = 'Message to players in unfinished Steam games'
        else:
            raise ValueError(f'{ctx.invoked_with} is not a handled alias for this command')

        game_list = models.Game.search(player_filter=[player_match], status_filter=2, guild_id=ctx.guild.id, platform_filter=platform_filter)
        logger.debug(f'{len(game_list)} incomplete games for target')

        list_of_players = []
        for g in game_list:
            list_of_players += g.mentions()

        list_of_players = list(set(list_of_players))
        logger.debug(f'{len(list_of_players)} unique opponents for target')
        clean_message = utilities.escape_role_mentions(message)
        if len(list_of_players) > 100:
            await ctx.send('*Warning:* More than 100 unique players are addressed. Only the first 100 will be mentioned.')
        await ctx.send(f'{title_str} for <@{target}> ({player_match.name}): *{clean_message}*')

        recipient_message = f'Message recipients: {" ".join(list_of_players[:100])}'
        await ctx.send(recipient_message[:2000])

        for game in game_list:
            logger.debug(f'Sending message to game channels for game {game.id} from {ctx.invoked_with}')
            models.GameLog.write(game_id=game, guild_id=ctx.guild.id, message=f'{log_message} *{discord.utils.escape_markdown(clean_message)}*')
            await game.update_squad_channels(self.bot.guilds, game.guild_id, message=f'{title_str} for **{player_match.name}**: *{clean_message}*')

    @commands.command(usage='game_id message')
    @models.is_registered_member()
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def ping(self, ctx, *, args=''):
        """ Ping everyone in one of your games with a message

         **Examples**
        `[p]ping 100 I won't be able to take my turn today` - Send a message to everyone in game 100
        `[p]ping This game is amazing!` - You can omit the game ID if you send the command from a game-specific channel

        See `[p]help pingall` for a command to ping ALL incomplete games simultaneously.

        """

        usage = (f'**Example usage:** `{ctx.prefix}ping 100 Here\'s a nice note for everyone in game 100.`\n'
                    'You can also omit the game ID if you use the command from a game-specific channel.')

        if ctx.message.attachments:
            attachment_urls = '\n'.join([attachment.url for attachment in ctx.message.attachments])
            args += f'\n{attachment_urls}'

        if not args:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(usage)

        if settings.is_mod(ctx.author):
            ctx.command.reset_cooldown(ctx)

        args = args.split()
        try:
            game_id = int(args[0])
            message = ' '.join(args[1:])
        except ValueError:
            game_id = None
            message = ' '.join(args)

        # TODO:  should prioritize inferred game above an integer. currently something like '$ping 1 city island plz restart'
        # will try to ping game ID #1 even if done within a game channel

        inferred_game = None
        if not game_id:
            try:
                inferred_game = models.Game.by_channel_id(chan_id=ctx.message.channel.id)
            except exceptions.TooManyMatches:
                logger.error(f'More than one game with matching channel {ctx.message.channel.id}')
                return await ctx.send('Error looking up game based on current channel - please contact the bot owner.')
            except exceptions.NoMatches:
                ctx.command.reset_cooldown(ctx)
                logger.debug('Could not infer game from current channel.')
                return await ctx.send(f'Game ID was not included. {usage}')
            logger.debug(f'Inferring game {inferred_game.id} from ping command used in channel {ctx.message.channel.id}')

        if not message:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f'Message was not included. {usage}')

        message = utilities.escape_role_mentions(message)

        if inferred_game:
            game = inferred_game
        else:
            game = await PolyGame().convert(ctx, int(game_id), allow_cross_guild=True)

        if not game.player(discord_id=ctx.author.id) and not settings.is_staff(ctx.author):
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f'You are not a player in game {game.id}')

        permitted_channels = settings.guild_setting(game.guild_id, 'bot_channels').copy()
        if game.game_chan:
            permitted_channels.append(game.game_chan)

        game_player_ids = [l.player.discord_member.discord_id for l in game.lineup]
        game_members = [ctx.guild.get_member(p_id) for p_id in game_player_ids]
        player_mentions = [f'<@{p_id}>' for p_id in game_player_ids]

        game_channels = [gs.team_chan for gs in game.gamesides]
        game_channels = [chan for chan in game_channels if chan]  # remove Nones

        mention_players_in_current_channel = True  # False when done from game channel, True otherwise

        if ctx.channel.id in game_channels and len(game_channels) >= len(game.gamesides):
            logger.debug('Allowing ping since it is within a game channel, and all sides have a game channel')
            mention_players_in_current_channel = False
        elif settings.is_mod(ctx.author) and len(game_channels) >= len(game.gamesides):
            logger.debug('Allowing ping since it is from a mod and all sides have a game channel')
            mention_players_in_current_channel = False
        elif None not in game_members and all(ctx.channel.permissions_for(member).read_messages for member in game_members):
            logger.debug('Allowing ping since all members have read access to current channel')
            mention_players_in_current_channel = True
        elif ctx.channel.id in permitted_channels:
            logger.debug('Allowing ping since it is a bot channel or central game channel')
            mention_players_in_current_channel = True
        else:
            logger.debug(f'Not allowing ping in {ctx.channel.id}')
            if len(game_channels) >= len(game.gamesides):
                permitted_channels = game_channels + permitted_channels

            channel_tags = [f'<#{chan_id}>' for chan_id in permitted_channels]
            ctx.command.reset_cooldown(ctx)

            if len(game_channels) < len(game.gamesides):
                error_str = 'Not all sides have access to a private channel. '
            else:
                error_str = ''

            return await ctx.send(f'This command can not be used in this channel. {error_str}Permitted channels: {" ".join(channel_tags)}')

        full_message = f'Message from **{ctx.author.display_name}** regarding game {game.id} **{game.name}**:\n*{message}*'
        models.GameLog.write(game_id=game, guild_id=game.guild_id, message=f'{models.GameLog.member_string(ctx.author)} pinged the game with message: *{discord.utils.escape_markdown(message)}*')

        try:
            if mention_players_in_current_channel:
                logger.debug(f'Ping triggered in non-private channel {ctx.channel.id}')
                await game.update_squad_channels(self.bot.guilds, ctx.guild.id, message=full_message, suppress_errors=True)
                await ctx.send(f'{full_message}\n{" ".join(player_mentions)}')
            else:
                logger.debug(f'Ping triggered in private channel {ctx.channel.id}')
                await game.update_squad_channels(self.bot.guilds, game.guild_id, message=f'{full_message}', suppress_errors=False, include_message_mentions=True)
                if ctx.channel.id not in game_channels:
                    await ctx.send(f'Sending ping to game channels:\n{full_message}')
        except exceptions.CheckFailedError as e:
            channel_tags = [f'<#{chan_id}>' for chan_id in permitted_channels]
            return await ctx.send(f'{e}\nTry sending `{ctx.prefix}ping` from a public channel that all members can view: {" ".join(channel_tags)}')

    @commands.command(aliases=['helpstaff'], hidden=False)
    @commands.cooldown(2, 30, commands.BucketType.user)
    # @settings.guild_has_setting(setting_name='staff_help_channel')
    async def staffhelp(self, ctx, *, message: str = ''):
        """
        Get staff help on bot usage or game disputes

        The message will be relayed to a staff channel and someone should assist you shortly.
        You can attach screenshots or links to the message.

        **Example:**
        `[p]staffhelp Game 42500 was claimed incorrectly`
        `[p]staffhelp Game 42500 Does this screenshot show a restartable spawn?`
        """

        potential_game_id = re.search(r'\d{4,6}', message)
        game_id_search = potential_game_id[0] if potential_game_id else None
        try:
            related_game = models.Game.by_channel_or_arg(chan_id=ctx.channel.id, arg=game_id_search)
            guild_id = related_game.guild_id
            # Send game embed summary if message includes a numeric ID of a game or command is used in a game channel
        except (ValueError, exceptions.MyBaseException):
            related_game = None
            guild_id = ctx.guild.id

        guild = self.bot.get_guild(guild_id)
        if guild:
            channel = guild.get_channel(settings.guild_setting(guild_id, 'staff_help_channel'))
        else:
            channel = None

        if not channel:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send('Cannot load staff channel. You will need to ping a staff member.')

        if ctx.message.attachments:
            attachment_urls = '\n'.join([attachment.url for attachment in ctx.message.attachments])
            message += f'\n{attachment_urls}'

        if not message or len(message) < 7:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f'You must supply a help request, ie: `{ctx.prefix}{ctx.invoked_with} Game 42500 Does this screenshot show a restartable spawn?`')

        helper_role_str = 'server staff'
        helper_role_name = settings.guild_setting(guild_id, 'helper_roles')[0]
        helper_role = discord.utils.get(guild.roles, name=helper_role_name)
        helper_role_str = f'{helper_role.mention}' if helper_role else 'server staff'

        if ctx.channel.guild.id == guild_id:
            chan_str = f'({ctx.channel.name})'
        else:
            chan_str = f'({ctx.channel.name} on __{ctx.guild.name}__)'
        await channel.send(f'Attention {helper_role_str} - {ctx.author.mention} ({ctx.author.name}) asked for help from channel <#{ctx.channel.id}> {chan_str}:\n{ctx.message.jump_url}\n{message}')

        if related_game:
            embed, content = related_game.embed(guild=guild, prefix=ctx.prefix)
            await channel.send(embed=embed, content=content)
            game_id = related_game.id
        else:
            game_id = 0

        models.GameLog.write(game_id=game_id, guild_id=ctx.guild.id, message=f'{models.GameLog.member_string(ctx.author)} requested staffhelp: *{message}*')
        await ctx.send('Your message has been sent to server staff. Please wait patiently or send additional information on your issue.')

    @commands.command(hidden=False, aliases=['random_tribes', 'rtribe'], usage='game_size [-banned_tribe ...]')
    @settings.in_bot_channel()
    async def rtribes(self, ctx, *, arg):
        """Select a random set of n tribes.
        **Example:**
        `[p]rtribes 4` - Shows 4 random tribes.
        `[p]rtribes 6 -hoodrick -aquarion` - Remove Hoodrick and Aquarion from the random pool.
        `[p]rtribes 7 seed=12345` - Fix the seed of the random number generator to give the same output each time
        `[p]rtribes 7 force_free=2` - Force selection of at least 2 free tribes [NOT IMPLEMENTED]
        `[p]rtribes 7 allow_duplicates` - Allow multiples of the same tribe to show up in the selection
        """
        
        args = arg.split() if arg else []

        # set default params
        n: int = 1
        allow_duplicates=False
        seed=None
        force_free: int = 0
        banned_tribes=[]

        # override default params if provided
        for a in args:
            print(a)
            try:
                n = int(a)
            except ValueError:
                pass
            if a[0]=='-':
                banned_tribes.append(a[1:])
            elif a[0:4]=='seed':
                try:
                    seed=int(a[5:])
                except:
                    return await ctx.send(f'The seed provided must be an integer.')
                random.seed(seed)
            elif a[0:10]=='force_free':
                try:
                    force_free=int(a[11:])
                except:
                    return await ctx.send(f'You can only force 0 through 4 free tribes.')
                if force_free<0 or force_free>4:
                    return await ctx.send(f'You can only force 0 through 4 free tribes.')
            elif a=='allow_duplicates':
                allow_duplicates=True

        if n > 16 or n < 1:
            return await ctx.send(f'Invalid number of tribes selected, {n}. Must be between 1 and 16')
        
        free_tribes = ['Xin-xi',
                       'Imperius',
                       'Bardur',
                       'Oumaji']
        tribes = free_tribes + ['Kickoo',
                                'Hoodrick',
                                'Luxidoor',
                                'Vengir',
                                'Zebasi',
                                'Ai-mo',
                                'Quetzali',
                                'Yadakk',
                                'Aquarion',
                                'Elyrion',
                                'Polaris',
                                'Cymanti']
        
        for ban in banned_tribes:
            # Remove tribes from tribe list
            # todo: match by first letter(s) provided?
            removal = next(t for t in tribes if t.upper() == ban.upper())
            tribes.remove(removal)

        if allow_duplicates:
            await ctx.send(', '.join(sorted(random.choices(tribes,k=n))))
        else:
            if len(tribes) < n:
                return await ctx.send(f'Invalid number of tribes selected, {n}, is greater than the number of unbanned tribes.')
            await ctx.send(', '.join(sorted(random.sample(tribes,k=n))))

    @commands.command(aliases=['freeagents', 'roleeloany'], usage='[sort] [role name list]')
    @roleelo_server_check()
    @settings.in_bot_channel_strict()
    @commands.cooldown(1, 5, commands.BucketType.channel)
    async def roleelo(self, ctx: commands.Context, *, arg=None):
        """Prints list of players with a given role and their ELO stats

        You can check more than one role at a time by separating them with a comma.
        By default, will return members with ALL the specified roles.
        Use `[p]roleeloany` to list members with ANY of the roles.

        Use one of the following options as the first argument to change the sorting:
        **g_elo** - Global ELO (default)
        **elo** - Local ELO
        **games** - Total number of games played
        **recent** - Recent games played (14 days)

        Members with the Inactive role will be skipped unless it is explicitly listed.
        Include `-file` in the argument for a CSV attachment.

        This command has some shortcuts:
        `[p]freeagents` - List members with the Free Agent role

        **Examples**
        `[p]roleelo novas` - List all members with a role matching 'novas'
        `[p]roleelo novas -file` - Load all 'nova' members into a CSV file
        `[p]roleelo elo novas` - List all members with a role matching 'novas', sorted by local elo
        `[p]roleeloany g_elo crawfish, ronin` - List all members with any of two roles, sorted by global elo
        """
        args = arg.split() if arg else []
        usage = (f'**Example usage:** `{ctx.prefix}roleelo Ronin`\n'
                 f'See `{ctx.prefix}help roleelo` for sorting options and more examples.')

        if args and '-file' in args:
            args.remove('-file')
            file_export = True
        else:
            file_export = False

        if args and args[0].upper() == 'G_ELO':
            sort_key = 1
            args = args[1:]
            sort_str = 'Global ELO'
        elif args and args[0].upper() == 'ELO':
            sort_key = 2
            args = args[1:]
            sort_str = 'Local ELO'
        elif args and args[0].upper() == 'GAMES':
            sort_key = 3
            args = args[1:]
            sort_str = 'total games played'
        elif args and args[0].upper() == 'RECENT':
            sort_key = 4
            args = args[1:]
            sort_str = 'recent games played'
        else:
            sort_key = 1  # No argument supplied, use g_elo default
            # args = ' '.join(args)
            sort_str = 'Global ELO'

        if ctx.invoked_with == 'freeagents':
            args = [free_agent_role_name]
        else:
            if not settings.is_staff(ctx.author):
                return await ctx.send(
                    f'You\'re not permitted to use this command. Only staff & Team Leaders may use this command.')
            if ctx.invoked_with == 'roleelo':
                if not args:
                    return await ctx.send(f'No role name was supplied.\n{usage}')

        player_list = []
        player_obj_list, member_obj_list = [], []

        args = [a.strip().title() for a in ' '.join(args).split(',')]  # split arguments by comma

        roles = [discord.utils.find(lambda r: arg.upper() in r.name.upper(), ctx.guild.roles) for arg in args]
        roles = [r for r in roles if r]  # remove Nones

        if ctx.invoked_with == 'roleeloany':
            members = list(set(member for role in roles if role for member in role.members))
            method = 'any'
        else:
            members = [member for member in ctx.guild.members if all(role in member.roles for role in roles)]
            method = 'all'

        if not roles:
            return await ctx.send(
                f'Could not load roles from the guild matching **{"/".join(args)}**. Multiple roles should be separated by a comma.',
                allowed_mentions=discord.AllowedMentions.none()
            )

        inactive_role = discord.utils.get(ctx.guild.roles, name=settings.guild_setting(ctx.guild.id, 'inactive_role'))
        for member in members:
            if inactive_role and inactive_role in member.roles and inactive_role not in roles:
                logger.debug(f'Skipping {member.name} since they have Inactive role')
                continue

            try:
                dm = models.DiscordMember.get(discord_id=member.id)
                player = models.Player.get(discord_member=dm, guild_id=ctx.guild.id)
                player_obj_list.append(player)
                member_obj_list.append(member)
            except peewee.DoesNotExist:
                logger.debug(f'Player {member.name} not registered.')
                continue

            g_wins, g_losses = dm.get_record()
            wins, losses = player.get_record()
            recent_games = dm.games_played(in_days=14).count()
            all_games = dm.games_played().count()
            message = (f' {dm.mention()} **{player.name}**'
                       f'\n\u00A0\u00A0 \u00A0\u00A0 \u00A0\u00A0 {recent_games} games played in last 14 days, {all_games} all-time'
                       f'\n\u00A0\u00A0 \u00A0\u00A0 \u00A0\u00A0 ELO:  {dm.elo_moonrise} *global* / {player.elo_moonrise} *local*\n'
                       f'\u00A0\u00A0 \u00A0\u00A0 \u00A0\u00A0 __W {g_wins} / L {g_losses}__ *global* \u00A0\u00A0 - \u00A0\u00A0 __W {wins} / L {losses}__ *local*\n')

            player_list.append((message, dm.elo_moonrise, player.elo_moonrise, all_games, recent_games, member, player))

        player_list.sort(key=lambda tup: tup[sort_key], reverse=False)  # sort the list by argument supplied

        message = []
        for player in player_list:
            message.append(player[0])

        if not player_list:
            await ctx.send('No matching players found.')
        elif file_export:
            import io

            player_obj_list = [p[6] for p in player_list]
            member_obj_list = [p[5] for p in player_list]

            def async_call_export_func():

                filename = utilities.export_player_data(player_list=player_obj_list, member_list=member_obj_list)
                return filename

            async with ctx.typing():
                filename = await self.bot.loop.run_in_executor(None, async_call_export_func)
                with open(filename, 'rb') as f:
                    file = io.BytesIO(f.read())
                file = discord.File(file, filename=filename)
                await ctx.send(
                    f'Exporting {len(player_list)} active players with {method} of the following roles: **{"/".join([r.name for r in roles])}**\nLoaded into a file `{filename}`, sorted by {sort_str}',
                    file=file)
        else:
            await ctx.send(
                f'Listing {len(player_list)} active members with {method} of the following roles: **{"/".join([r.name for r in roles])}** (sorted by {sort_str})...')

            message = []
            am = discord.AllowedMentions(everyone=False, users=False, roles=False)
            for player in player_list:
                message.append(player[0])
            async with ctx.typing():

                await utilities.buffered_send(destination=ctx, content=''.join(message).replace(".", "\u200b "),
                                              allowed_mentions=am)

    async def task_broadcast_newbie_message(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            sleep_cycle = (60 * 60 * 3)
            await asyncio.sleep(10)

            for guild in self.bot.guilds:
                broadcast_channels = [guild.get_channel(chan) for chan in settings.guild_setting(guild.id, 'newbie_message_channels')]
                if not broadcast_channels:
                    continue

                prefix = settings.guild_setting(guild.id, 'command_prefix')
                # ranked_chan = settings.guild_setting(guild.id, 'ranked_game_channel')
                # unranked_chan = settings.guild_setting(guild.id, 'unranked_game_channel')
                bot_spam_chan = settings.guild_setting(guild.id, 'bot_channels_strict')[0]
                elo_guide_channel = 533391050014720040

                broadcast_message = (f'To register for ELO leaderboards and matchmaking use the command __`{prefix}setname Your Mobile Name`__')
                broadcast_message += f'\nTo get started with joining an open game, go to <#{bot_spam_chan}> and type __`{prefix}games`__'
                broadcast_message += f'\nFor full information go read <#{elo_guide_channel}>.'

                for broadcast_channel in broadcast_channels:
                    if broadcast_channel:
                        message = await broadcast_channel.send(broadcast_message, delete_after=(sleep_cycle - 5))
                        self.bot.purgable_messages = self.bot.purgable_messages[-20:] + [(guild.id, broadcast_channel.id, message.id)]

            await asyncio.sleep(sleep_cycle)

    async def task_broadcast_newbie_steam_message(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            sleep_cycle = (60 * 60 * 6)
            await asyncio.sleep(10)

            for guild in self.bot.guilds:
                broadcast_channel = guild.get_channel(settings.guild_setting(guild.id, 'steam_game_channel'))
                if not broadcast_channel:
                    continue

                prefix = settings.guild_setting(guild.id, 'command_prefix')
                elo_guide_channel = 533391050014720040

                broadcast_message = (f'To register for ELO leaderboards and matchmaking use the command __`{prefix}steamname Your Steam Name`__')
                broadcast_message += f'\nTo get started with joining an open game, type __`{prefix}games`__ or open your own with __`{prefix}opensteam`__'
                broadcast_message += f'\nFor full information go read <#{elo_guide_channel}>.'

                message = await broadcast_channel.send(broadcast_message, delete_after=(sleep_cycle - 5))
                self.bot.purgable_messages = self.bot.purgable_messages[-20:] + [(guild.id, broadcast_channel.id, message.id)]

            await asyncio.sleep(sleep_cycle)


async def setup(bot):
    await bot.add_cog(misc(bot))
