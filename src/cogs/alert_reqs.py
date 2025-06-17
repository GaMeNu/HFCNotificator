import json

import requests


class AlertReqs:
    """
    A class that handles all requests from HFC's website
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = True

    def request_alert_json(self) -> dict | None:
        """
        Request a json of the current running alert
        :return: JSON object as Python dict, or None if there's no alert running
        :raises requests.exceptions.Timeout: If request times out (5 seconds)
        """
        req = self.session.get('https://www.oref.org.il/WarningMessages/alert/alerts.json', headers={
            'Referer': 'https://www.oref.org.il/',
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
            'Accept-Language': 'en-US,en;q=0.6',
            'Client': 'HFC Notificator bot for Discord',
            'Nonexistent-Header': 'Yes'
        }, timeout=5)

        decoded = req.content.decode('utf-8-sig')

        if decoded is None or len(decoded) < 3:  # Why does it get a '\r\n' wtf
            ret_dict = {}
        else:
            try:
                ret_dict = json.loads(decoded)
            except (json.decoder.JSONDecodeError, json.JSONDecodeError):
                ret_dict = None

        return ret_dict

    def request_history_json(self) -> dict | None:
        """
        Request a json of the alert history from last day
        :return: JSON object as Python dict
        :raises requests.exceptions.Timeout: If request times out (5 seconds)
        """
        req = self.session.get("https://www.oref.org.il/warningMessages/alert/History/AlertsHistory.json", timeout=5)

        content = req.text

        try:
            ret_dict = json.loads(content)
        except (json.JSONDecodeError, json.decoder.JSONDecodeError):
            ret_dict = None
        return ret_dict
