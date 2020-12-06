import sys
import os
import pickle

import discord

client = discord.Client()
botstate = {}
react_emoji = '🔴' # red_circle: U+1F534
react_name  = 'red_circle'

async def boardmsg(guild):
    s = 'React with :' + react_name + ': to set as looking for games.\n\n'
    if len(botstate[guild.id]['lfg-members']) == 0:
        s += 'No members looking for games.'
        return s
    s += 'Looking for games:\n'
    for uid in botstate[guild.id]['lfg-members']:
        member = None # guild.get_member(uid)
        if member == None:
            member = (await guild.query_members(user_ids=[uid]))[0]
        s += member.display_name + '\n'
    return s

async def init_guild(guild):
    botstate[guild.id] = {
        'id':          guild.id,
        'name':        guild.name,
        'bot-channel': None,
        'board-msg':   None,
        'lfg-role':    None,
        'lfg-members': []
    }

    perm = {
        guild.default_role: discord.PermissionOverwrite(send_messages=False,
                                                        read_messages=True),
        guild.me:           discord.PermissionOverwrite(send_messages=True,
                                                        read_messages=True)
    }

    try:
        channel = await guild.create_text_channel('lfg-board', overwrites=perm,
                                                  topic="Looking for games!")
        msg = await channel.send(await boardmsg(guild))
        await msg.add_reaction(react_emoji)
        lfgrole = None
        for role in guild.roles:
            if role.name == 'lfg':
                lfgrole = role
                break
        if lfgrole == None:
            lfgrole = await guild.create_role(name='lfg', hoist=True, mentionable=True)
            await lfgrole.edit(position=1)
            botstate[guild.id]['lfg-role-added'] = True

        botstate[guild.id]['bot-channel'] = channel.id
        botstate[guild.id]['board-msg']   = msg.id
        botstate[guild.id]['lfg-role']    = lfgrole.id

    except Exception as e:
        print(e)
        del botstate[guild.id]
        return

async def rem_guild(guild):
    del botstate[guild.id]

async def refr_guild(guild):
    oldmembers = botstate[guild.id]['lfg-members'][:]
    for mem in oldmembers:
        member = guild.get_member(mem)
        if member == None:
            member = (await guild.query_members(user_ids=[mem]))[0]
        await rem_lfg(guild, member)

    channel = guild.get_channel(botstate[guild.id]['bot-channel'])
    msg     = await channel.fetch_message(botstate[guild.id]['board-msg'])
    for reaction in msg.reactions:
        if str(reaction.emoji) == react_emoji:
            async for user in reaction.users():
                print(user.name)
                if user.id == client.user.id:
                    continue
                if type(user) == discord.Member:
                    member = user
                else:
                    member = guild.get_member(user.id)
                    if member == None:
                        member = (await guild.query_members(user_ids=[user.id]))[0]
                await add_lfg(guild, member)

async def add_lfg(guild, member):
    print('adding user:', member.display_name)
    if member.id not in botstate[guild.id]['lfg-members']:
        botstate[guild.id]['lfg-members'].append(member.id)
    channel = guild.get_channel(botstate[guild.id]['bot-channel'])
    role    = guild.get_role(botstate[guild.id]['lfg-role'])
    msg     = await channel.fetch_message(botstate[guild.id]['board-msg'])
    await member.add_roles(role)
    await msg.edit(content=await boardmsg(guild))

async def rem_lfg(guild, member):
    print('removing user:', member.display_name)
    if member.id in botstate[guild.id]['lfg-members']:
        botstate[guild.id]['lfg-members'].remove(member.id)
    channel = guild.get_channel(botstate[guild.id]['bot-channel'])
    role    = guild.get_role(botstate[guild.id]['lfg-role'])
    msg     = await channel.fetch_message(botstate[guild.id]['board-msg'])
    await member.remove_roles(role)
    await msg.edit(content=await boardmsg(guild))

# not guaranteed to be the first event called or called only once
@client.event
async def on_ready():
    print('Connected as', client.user)
    for guild in client.guilds:
        if guild.id not in botstate:
            await init_guild(guild)
        else:
            await refr_guild(guild)

# runs when a guild is created by the bot or the bot joins a guild
@client.event
async def on_guild_join(guild):
    await init_guild(guild)

# runs when a message recieves a reaction
@client.event
async def on_raw_reaction_add(payload):
    if (payload.guild_id in botstate and
        payload.channel_id == botstate[payload.guild_id]['bot-channel'] and
        payload.message_id == botstate[payload.guild_id]['board-msg'] and
        payload.emoji.name == react_emoji):

        guild  = client.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member == None:
            member = (await guild.query_members(user_ids=[payload.user_id]))[0]
        await add_lfg(guild, member)


# runs when a message loses a reaction
@client.event
async def on_raw_reaction_remove(payload):
    if (payload.guild_id in botstate and
        payload.channel_id == botstate[payload.guild_id]['bot-channel'] and
        payload.message_id == botstate[payload.guild_id]['board-msg'] and
        payload.emoji.name == react_emoji):

        guild  = client.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member == None:
            member = (await guild.query_members(user_ids=[payload.user_id]))[0]
        await rem_lfg(guild, member)

# runs when bot leaves a guild
@client.event
async def on_guild_remove(guild):
    await rem_guild(guild)

def main(argv):
    global botstate

    if len(argv) > 1:
        kname = argv[1]
    else:
        kname = 'key.txt'

    # ensure cache directory exists
    cname = 'cache'
    if os.path.exists(cname):
        if not os.path.isdir(cname):
            print(cname, "exists and isn't a directory", file=sys.stderr)
            exit(1)
        print('Using cache directory', cname)
    else:
        os.mkdir(cname, mode=0o700)
        print('Creating cache directory', cname)

    # Read cache
    for fname in os.listdir(cname):
        print('Reading cache entry:', fname)
        (nm, ext) = os.path.splitext(fname)
        if ext != '.pickle':
            print('skipping', ext)
            continue

        with open(os.path.join(cname, fname), 'rb') as f:
            botstate[int(nm)] = pickle.load(f)
    
    # Read bot key
    try:
        with open(kname, 'r') as f:
            key = f.read()
    except IOError:
        print('Key file not found:', fname, file=sys.stderr)
        exit(1)

    # Run client
    client.run(key)

    for fname in os.listdir(cname):
        print('Removing old entry:', fname)
        os.remove(os.path.join(cname, fname))

    # cache current state
    for (key, value) in botstate.items():
        fname = os.path.join(cname, str(key) + '.pickle')
        print('Writing cache:', fname)
        with open(fname, 'wb') as f:
            pickle.dump(value, f)

if __name__ == '__main__':
    main(sys.argv)
