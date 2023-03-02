# r/Splatoon ModMail Bot

Built using Python and Nextcord.
                         
### What it does

* Listens for incoming DMs by server members.
* Mirrors those messages into a thread specific to that user.
* Messages sent into that thread are mirrored back to the user's DMs again.
* Each user has access to two threads, one normal and one anonymous.
* The normal thread's name matches that of the user that created it.
  Note that this is set on first creation, and will not automatically update
  to reflect name changes.
* The anonymous thread will be named "Anonymous user #X" where X is a 6 digit
  hex number.
* When the same user opens multiple threads, the same thread(s) will be reused.
* Threads can be closed either by letting Discord auto-close them, manually
  closing the thread (mods) or using the /close command (users)
* Mods can use the buttons to control how messages are sent.
  * "Broadcasting staff messages" vs "Staff messages muted" enables/disables
    message mirroring from the staff thread to the user DMs. The user can
    still message while muted.
  * "Responding as anonymous" vs "Responding as yourself" decides whether
    the mirrored messages will be credited to the staff member sending them
    or to the configured default identity.
* Mods can use the /settings command in a thread to have these buttons
  posted again, though they're also posted every time a new thread starts.
* Mods can use the /block command in a thread to prevent the user from opening
  any more threads of any kind.
* Users can right-click a message and select "Apps > Quote message in ModMail"
  to copy a server message into their modmail thread.

### Environment variables

* `GUILD`: The ID of the server the bot belongs to.
* `CHANNEL`: The ID of the channel that new threads should be created on.
* `NAME`: The username of the staff default identity.
* `ICON_URL`: An avatar for the staff default identity.
* `NOTIFICATION_ROLE`: The ID of the role to mention when a thread is opened.
* `TOKEN`: The bot's login token.
                                                                      
### Contributing

Make your own fork, I'm bad at maintaining personal projects like this.
