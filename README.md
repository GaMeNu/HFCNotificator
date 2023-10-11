# Home Front Command Notificator
## A bot to send Discord notifications for HFC alerts
### Created by GaMeNu and yrrad8

> **IMPORTANT:** This bot is unofficial! Please do not rely on it alone.

## What is this?
This is a bot that connects to the HFC's servers and sends real-time notifications about alerts in Israel.

### Setup
 Just invite the bot to a server (see "Links" below), and /register a channel to start receiving notifications!

## Self-hosting
### Requirements
#### Required PyPI packages (run with `pip install`)
```
discord.py
mysql-connector-python
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

## Links
[GitHub](https://github.com/GaMeNu/HFCNotificator)

[Official Bot Invite Link](https://discord.com/api/oauth2/authorize?client_id=1160344131067977738&permissions=0&scope=applications.commands%20bot)

[Bot Profile (Use to open a Direct Message with the bot)](https://discord.com/users/1160344131067977738)

[HFC Website](https://www.oref.org.il/)


