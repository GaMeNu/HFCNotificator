# Home Front Command Notificator
## A bot to send Discord notifications for HFC alerts
### Created by GaMeNu and yrrad8

> **IMPORTANT:** This bot is unofficial! Please do not rely on it alone.

## What is this?
This is a bot that connects to the HFC's servers and sends real-time notifications about alerts in Israel.

### Setup
Invite the bot to a server, and /register a channel, and you're ready to go!

Alternatively, you can DM the bot to receive alerts directly to your DMs!

Please do note that the bot instance listed here is hosted on a private machine, and may be a bit slow.

## Command documentation
### /about
Get some info about the bot
### /register
Run in a channel to register it to receive alerts
### /unregister
Run in a registered channel to stop it from receiving alerts
### /latest \<time\> \<unit\> \[page\]
Get the latest alerts from up to a certain time back.

## Self-hosting
### Requirements
#### Required PyPI packages (run each with `pip install`)
```
discord.py
mysql-connector-python
requests
python-dotenv
```
#### Other requirements
MySQL Server: https://dev.mysql.com/downloads/mysql/

### .env format:
Replace the angled brackets with the matching data
```env
TOKEN = <Discord bot token>
AUTHOR_ID = <Your Discord user ID>

DB_USERNAME = <MySQL database username>
DB_PASSWORD = <MySQL database password>
```

note that the .env file must be in the same directory as main.py

## Links
[GitHub](https://github.com/GaMeNu/HFCNotificator)

[Official Bot Invite Link](https://discord.com/api/oauth2/authorize?client_id=1160344131067977738&permissions=0&scope=applications.commands%20bot)

[Bot Profile (Use to open a Direct Message with the bot)](https://discord.com/users/1160344131067977738)

[HFC Website](https://www.oref.org.il/)



