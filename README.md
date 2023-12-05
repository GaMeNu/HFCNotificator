# Home Front Command Notificator
## A bot to send Discord notifications for HFC alerts
### Created by GaMeNu and yrrad8

> **IMPORTANT:** This bot is unofficial! Please do not rely on it alone.

## Table of Contents
- [What is this?](#what-is-this)
- [Setup](#setup)
- [Command Documentation](#command-documentation)
- [About Self Hosting](#self-hosting)
- [Important Links](#links)

## What is This?
This is a bot that connects to the HFC's servers and sends real-time notifications about alerts in Israel.

The bot's development began in 2023, at the start of the Simchat Torah (Iron Swords) War, and is developed by GaMeNu and yrrad8.
The bot aims to be relatively fast, reliable, and available for easy hosting and forking.

Feel free to send suggestions and bug reports through our [discord server](https://discord.gg/K3E4a5ekNy), or just fork the bot and add what you want yourself!


## Setup
Invite the bot to a server, and /register a channel, and you're ready to go!

Alternatively, you can /register a Direct Message / Group DM channel to receive alerts directly!

Please do note that the bot instance listed under the [links section](#links) is hosted on a private machine, and may be a bit slow. It is recommended to [host your own instance](#self-hosting), if possible.

## Command documentation
#### /register
Run in a channel to register it to receive alerts
#### /unregister
Run in a registered channel to stop it from receiving alerts
#### /latest \<time\> \<unit\> \[page\]
Get the latest alerts from up to a certain time back.
#### /about
Get some info about the bot itself
#### /info
Get info about the system and client

### Location commands
#### /locations add \<id\>
Register a location to receive alerts from
#### /locations remove \<id\>
Remove a location to receive alerts from
#### /locations clear \<id\>
Clear all registered locations (Get alerts from everywhere)
#### /locations list \[search\] \[page\]
List all valid locations
#### /locations registered \[search\] \[page\]
List all registered locations

## Self-hosting
### Requirements
#### Required PyPI packages (run each with `pip install`)
**Note:** On Windows you will have to write `python -m pip` instead of `pip` at the beginning of pip install commands

**Note:** as of 2023-10-23, discord.py seems to not install properly for Python 3.11 and above.
The fix we've found is to first install the beta version of package `aiohttp` separately (`aiohttp==3.9.0b0`).

Please use the requirements files (`pip install -r`):

Python 3.10 and below:
```
(python -m) pip install -r requirements.txt
```

Python 3.11 and above:
```
(python -m) pip install -r requirements-3_11.txt
```

#### Other requirements
- A discord bot app ([tutorial](https://github.com/discord-apps/bot-tutorial#how-to-create-an-application))
- MySQL Server (Download link: https://dev.mysql.com/downloads/mysql/) (also available on most package repositories)

### Local data:
#### .env file
Save the following to a file named ".env", and replace the angled brackets with the matching data. Do note that it has to be on the same directory as `main.py`.

```env
TOKEN = <Discord bot token>
AUTHOR_ID = <Your Discord user ID>

DB_USERNAME = <MySQL database username>
DB_PASSWORD = <MySQL database password>
```

#### botinfo file
In botinfo.json, change the "maintainer" value (default is "GaMeNu (@gamenu)") to your username, and maybe add contact information. This is in order to allow others to contact you about issues with your specific instance, and will be publicly available through /info.

**Make sure to not write any personal/private information there!**


## Links
[GitHub](https://github.com/GaMeNu/HFCNotificator)

[Official Bot Invite Link](https://discord.com/api/oauth2/authorize?client_id=1160344131067977738&permissions=0&scope=applications.commands%20bot)

[Bot Profile (Use to open a Direct Message with the bot)](https://discord.com/users/1160344131067977738)

[HFC Website](https://www.oref.org.il/)

[Support Server](https://discord.gg/K3E4a5ekNy)



