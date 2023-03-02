"""
r/Splatoon ModMail Bot

 DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
                   Version 2, December 2004

Copyright (C) 2004 Sam Hocevar <sam@hocevar.net>

Everyone is permitted to copy and distribute verbatim or modified
copies of this license document, and changing it is allowed as long
as the name is changed.

           DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
  TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION

 0. You just DO WHAT THE FUCK YOU WANT TO.
"""

import asyncio
import os
import random

import nextcord

import objects


bot = nextcord.Client(intents=nextcord.Intents.all(), status=nextcord.Status.online,
                      activity=nextcord.Activity(name="for DMs to forward", type=nextcord.ActivityType.watching))


home_server_id = os.environ["GUILD"]
home_server: nextcord.Guild
home_channel_id = os.environ["CHANNEL"]
home_channel: nextcord.TextChannel

mod_name = os.environ["NAME"]
mod_icon = os.environ["ICON_URL"]

new_thread_ping_role = os.environ["NOTIFICATION_ROLE"]


def make_anon_name():
    return f"Anonymous user #{hex(random.randrange(0xffff))}"


# Jobs for this bot
# 1) Track DMs.
#    On DM, check for open threads.
#     - If no thread is open, ask which thread to open (named/anon)
#     - Set the open thread flag and reset the individual staff flag
#     - If no thread exists, create one.
#    If a thread is open, mirror the message to the thread
# 2) Track threads.
#    When a message is sent to a thread, mirror it to the DM of the user that sent it.
#    When the thread is archived, send a close message to the user.
#     - Reset the open flag
# 3) Command list
#    /close (in dms) lets the user close the thread before archived
#    /block (in thread) blocks the user from sending new modmail
#    /settings (in thread) reposts the settings buttons
#    TODO: /reveal (in anonymous thread) shows who sent it (admins only)
#    TODO: /info (in thread) shows an info window for the target user (non-anon threads)
# 4) Right click message
#    > Report message. Quotes the selected message into an open thread
#      - Runs code to open a thread if a thread isn't already open.


class RequestOpenView(nextcord.ui.View):
    def __init__(self):
        super(RequestOpenView, self).__init__(timeout=60)
        self.value = None

    @nextcord.ui.button(label="Open normal thread", style=nextcord.ButtonStyle.blurple)
    async def start_named(self, btn, it):
        print("Opening regular thread")
        self.value = 1
        await it.response.edit_message(content="Starting a new ModMail thread.", view=None)
        self.stop()

    @nextcord.ui.button(label="Open anonymous thread", style=nextcord.ButtonStyle.gray)
    async def start_anon(self, btn, it):
        print("Opening anonymous thread")
        self.value = 2
        await it.response.edit_message(content="Starting a new anonymous ModMail thread.", view=None)
        self.stop()

    @nextcord.ui.button(label="Don't open thread", style=nextcord.ButtonStyle.red, row=1)
    async def dont_start(self, btn, it):
        print("Aborting")
        self.value = 0
        await it.response.edit_message(content="Cancelling ModMail.", embed=None, view=None)
        self.stop()


class ModControlView(nextcord.ui.View):
    def __init__(self, flags: objects.UserFlags):
        super(ModControlView, self).__init__(timeout=None)
        # This is a generic and custom view, so a lot of work will have to be done in
        # the callbacks.

        if flags.muted:
            self.mute.label = "Staff messages muted"
            self.mute.style = nextcord.ButtonStyle.grey
        else:
            self.mute.label = "Broadcasting staff messages"
            self.mute.style = nextcord.ButtonStyle.blurple

        if flags.individual_staff:
            self.anon.label = "Responding as yourself"
            self.anon.style = nextcord.ButtonStyle.grey
        else:
            self.anon.label = "Responding as anonymous"
            self.anon.style = nextcord.ButtonStyle.blurple

    @nextcord.ui.button(label="Broadcasting staff messages", style=nextcord.ButtonStyle.blurple,
                        custom_id="mod-control:mute", row=0)
    async def mute(self, btn: nextcord.Button, it: nextcord.Interaction):
        t, f = await objects.get_thread_user(it.channel_id)
        if t is None:
            await it.response.send_message("Something went wrong, this channel has no user associated?", ephemeral=True)
            return

        f.muted ^= True
        await objects.save_user_threads(t, flags=f)
        await it.response.edit_message(view=ModControlView(f))

    @nextcord.ui.button(label="Responding as anonymous", style=nextcord.ButtonStyle.blurple,
                        custom_id="mod-control:anon", row=1)
    async def anon(self, btn: nextcord.Button, it: nextcord.Interaction):
        t, f = await objects.get_thread_user(it.channel_id)
        if t is None:
            await it.response.send_message("Something went wrong, this channel has no user associated?", ephemeral=True)
            return

        f.individual_staff ^= True
        await objects.save_user_threads(t, flags=f)
        await it.response.edit_message(view=ModControlView(f))


async def add_users(thread):
    await thread.send(f"New ModMail thread: <@&{new_thread_ping_role}>")


async def request_open_modmail(user: nextcord.User, embed=None):
    print(f"Request open modmail thread for {user.name}")
    n, a, f = await objects.get_user_threads(user.id)
    if f.open_anon or f.open_named:
        raise RuntimeError("Trying to create a thread while a thread is open.")

    if f.banned:
        await user.send("You have been blocked from opening any more ModMail threads.")
        return

    content = "What kind of ModMail thread would you like to open?"
    if embed is not None:
        content += "\nThis is what will be sent:"

    view = RequestOpenView()

    msg = await user.send(content, embed=embed, view=view)
    await view.wait()

    if view.value is None:
        await msg.edit(content="Modmail request timed out.", embed=None, view=None)
        return None

    if view.value == 0:
        return None

    f.individual_staff = False
    f.muted = False

    if view.value == 1:
        # Create a thread if not already
        f.open_named = True
        if n is None:
            thread = await home_channel.create_thread(name=str(user), auto_archive_duration=1440,
                                                      type=nextcord.ChannelType.public_thread,
                                                      reason="New ModMail user.")
            n = thread.id
        else:
            thread = await home_server.fetch_channel(n)
            await thread.edit(archived=False, locked=False)
        await objects.save_user_threads(user.id, named=n, flags=f)

    elif view.value == 2:
        # Create a thread if not already
        f.open_anon = True
        if a is None:
            thread = await home_channel.create_thread(name=make_anon_name(), auto_archive_duration=1440,
                                                      type=nextcord.ChannelType.public_thread,
                                                      reason="New anonymous ModMail user.")
            a = thread.id
        else:
            thread = await home_server.fetch_channel(a)
            await thread.edit(archived=False, locked=False)
        await objects.save_user_threads(user.id, anon=a, flags=f)

    else:
        raise RuntimeError("wtf?")

    await user.send("Thank you for your message. A new request thread has been opened.")
    await add_users(thread)
    return thread


class ConfirmView(nextcord.ui.View):
    def __init__(self):
        super(ConfirmView, self).__init__(timeout=60)
        self.value = None

    @nextcord.ui.button(label="Yes", style=nextcord.ButtonStyle.blurple)
    async def confirm(self, btn, it):
        self.value = True
        await it.response.edit_message(content=None, view=None)
        self.stop()

    @nextcord.ui.button(label="No", style=nextcord.ButtonStyle.red)
    async def cancel(self, btn, it):
        self.value = False
        await it.delete_original_message()
        self.stop()


def message_to_embed(target: nextcord.Message, quoted=False, show_author=True):
    embed = nextcord.Embed()
    if target.guild and not show_author:
        embed.set_author(name=mod_name, icon_url=mod_icon)
    elif not target.guild and not show_author:
        embed.set_author(name="Anonymous")
    else:
        embed.set_author(name=f"{str(target.author)} ({target.author.id})",
                         icon_url=target.author.display_avatar.url)
    embed.description = target.content
    embed.timestamp = target.created_at
    embed.colour = 0x539CCA
    if quoted:
        embed.set_footer(text=target.channel.name)
        embed.colour = target.author.colour
        embed.title = "Jump to message"
        embed.url = target.jump_url
    if target.attachments:
        fmt = "[{e.filename}]({e.url})"
        if len(target.attachments) > 1:
            embed.add_field(name="Attachments", value="\n".join(fmt.format(e=a) for a in target.attachments))
        elif target.attachments[0].content_type.startswith("image/"):
            embed.set_image(url=target.attachments[0].url)
        else:
            embed.add_field(name="Attachment", value=fmt.format(e=target.attachments[0]))
    return embed


async def quote_to_mail_thread(caller: nextcord.Member, target: nextcord.Message):
    # Check if a thread is open
    n, a, f = await objects.get_user_threads(caller.id)
    embed = message_to_embed(target, True)

    if not (f.open_anon or f.open_named):
        thread = await request_open_modmail(caller, embed)
        if thread is None:
            return

        # Anonymous check:
        n, a, f = await objects.get_user_threads(caller.id)
        if thread.id == n:
            content = f"New ModMail request from {caller.mention}, initiated with this quoted message:"
        else:
            content = f"New anonymous ModMail request, initiated with this quoted message:"

        mod_view = ModControlView(f)

    else:
        view = ConfirmView()
        msg = await caller.send(content="Do you want to send this message to your ModMail thread?",
                                embed=embed, view=view)
        await view.wait()
        if view.value is None:
            await msg.edit(content="Quote message timed out", embed=None, view=None, delete_after=5)
            return

        if view.value is False:
            return

        thread_id = n if f.open_named else a
        assert thread_id is not None

        if f.open_anon:
            content = "This message was quoted:"
        else:
            content = f"{caller.mention} quoted a message:"
        mod_view = None

        # Copy the quoted message to the thread
        thread = home_channel.get_thread(thread_id)
        print(thread, thread_id)

    await thread.send(content, embed=embed, view=mod_view)


async def mirror_message_to_thread(message: nextcord.Message):
    assert message.channel.type is nextcord.ChannelType.private
    n, a, f = await objects.get_user_threads(message.author.id)

    if not (f.open_anon or f.open_named):
        thread = await request_open_modmail(message.author, None)
        if thread is None:
            return

        mod_view = ModControlView(f)

    else:
        thread_id = n if f.open_named else a
        thread = home_channel.get_thread(thread_id)
        mod_view = None

    embed = message_to_embed(message, show_author=f.open_named)
    await thread.send(embed=embed, view=mod_view)


async def mirror_message_from_thread(message: nextcord.Message):
    target, f = await objects.get_thread_user(message.channel.id)
    if target is None:
        # Dont act on irrelevant threads
        return

    n, a, f_ = await objects.get_user_threads(target)

    thread_open = f.open_anon if message.channel.id == a else f.open_named
    if not thread_open:
        # Don't act on inactive or muted threads.
        return

    if f.muted:
        await message.add_reaction("\U0001f515")
        await asyncio.sleep(2)
        await message.remove_reaction("\U0001f515", bot.user)
        return

    embed = message_to_embed(message, show_author=f.individual_staff)
    user = bot.get_user(target)
    await user.send(embed=embed)
    await message.add_reaction("\U0001f514")
    await asyncio.sleep(2)
    await message.remove_reaction("\U0001f514", bot.user)


# Tasks that are triggered by on-message only
# 1) Create new threads: If a user DMs without a thread open, create it.
#    - This should be handled by the stock mirror message to thread method
# 2) Respond to open threads: If the message is in a thread that is
#    a) associated with a user's modmail
#    b) has an open modmail request
#    c) is not muted
#    then mirror the message back to the relevant user.
# No other tasks


@bot.event
async def on_message(message: nextcord.Message):
    if message.author.id == bot.user.id:
        # Don't reply to yourself, but controversially _do_ react to other bots.
        return

    if message.channel.type is nextcord.ChannelType.private:
        await mirror_message_to_thread(message)

    if message.channel.type is nextcord.ChannelType.public_thread and message.channel.parent_id == home_channel_id:
        await mirror_message_from_thread(message)


# Tasks that are triggered by on-thread-update
# 1) Close a thread if after.archived and not before.archived
#    - Also send a message to the user about it being closed.

@bot.event
async def on_thread_update(before: nextcord.Thread, after: nextcord.Thread):
    target, f = await objects.get_thread_user(before.id)
    if target is None:
        return

    if after.archived and not before.archived:
        # Thread has been archived
        n, a, _ = await objects.get_user_threads(target)

        # Failsafe, actually check which thread is open, as it is possible to have two
        # open threads where only one is active.
        # Don't act if the thread has already been closed though.
        if not ((f.open_anon and before.id == a) or (f.open_named and before.id == n)):
            return

        if f.open_anon:
            f.open_anon = False
        else:
            f.open_named = False
        await objects.save_user_threads(target, flags=f)
        user = bot.get_user(target)
        await user.send("Your ModMail thread has been closed. "
                        "Attempting to send another message will create a new thread.\n"
                        "Thank you for using /r/Splatoon ModMail.")


# Now I just need to do the slash commands.
# Copied from above:
#    /close (in dms) lets the user close the thread before archived
#    /block (in thread) blocks the user from sending new modmail
#    /settings (in thread) reposts the settings buttons
#    /reveal (in anonymous thread) shows who sent it (admins only)

@bot.slash_command(name="close", description="Closes your ModMail thread.", dm_permission=True)
async def close_command(it: nextcord.Interaction):
    # Sanity check
    if it.guild_id is not None:
        return await it.response.send_message("To close a thread from the server, archive the thread. "
                                              "This command is for the user to close their thread in DMs.",
                                              ephemeral=True)

    n, a, f = await objects.get_user_threads(it.user.id)
    if not (f.open_anon or f.open_named):
        return await it.response.send_message("You do not have a ModMail thread open.")

    if f.open_named:
        f.open_named = False
        thread = home_channel.get_thread(n)
    else:
        f.open_anon = False
        thread = home_channel.get_thread(a)

    await objects.save_user_threads(it.user.id, flags=f)
    await thread.send("The user has closed this thread using the /close command. No more messages will be shared.")
    await it.response.send_message("Your thread has been closed. Thank you for using /r/Splatoon ModMail.")


@bot.slash_command(name="block", description="Blocks a user from opening new ModMail threads.",
                   guild_ids=[home_server_id])
async def block_command(it: nextcord.Interaction):
    target, f = await objects.get_thread_user(it.channel_id)
    if target is None:
        await it.response.send_message("I couldn't find the user associated with this channel or thread. "
                                       "Ensure this command is used in a ModMail thread.", ephemeral=True)
        return

    if f.banned:
        f.banned = False
        response = "I have unblocked this user. They will be able to create ModMail threads again."
    else:
        f.banned = True
        response = "I have blocked this user. They will no longer be able to create any kind of ModMail thread."

    await objects.save_user_threads(target, flags=f)
    await it.response.send_message(response)


@bot.slash_command(name="settings", description="Reposts the thread settings message", guild_ids=[home_server_id])
async def settings_command(it: nextcord.Interaction):
    target, f = await objects.get_thread_user(it.channel_id)
    if target is None:
        await it.response.send_message("I couldn't find the user associated with this channel or thread. "
                                       "Ensure this command is used in a ModMail thread.", ephemeral=True)
        return

    view = ModControlView(f)
    await it.response.send_message(view=view)


@bot.message_command(name="Quote message in ModMail", guild_ids=[home_server_id])
async def quote_command(it: nextcord.Interaction, message: nextcord.Message):
    await it.response.send_message("Check DMs to continue command.", ephemeral=True)
    await quote_to_mail_thread(it.user, message)


@bot.event
async def on_ready():
    print("Connecting to db")
    await objects.Database.connect()
    await objects.init_tables()

    print("Got connection, finding home channel")
    global home_channel, home_server
    home_server = bot.get_guild(home_server_id)
    home_channel = home_server.get_channel(home_channel_id)
    print("Found:", home_server.name, home_channel.name)

    bot.add_view(ModControlView(objects.UserFlags(0)))
    print("Ready.")


async def run():
    try:
        await bot.login(os.environ["TOKEN"])
        await bot.connect()
    finally:
        await objects.Database.close()
        await bot.close()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
