class Alert:
    """
    Represents an HFC Alert
    """
    def __init__(self, id: int, cat: int, title: str, districts: list[str], desc: str):
        """
        Init an Alert instance
        :param id: Alert ID
        :param cat: Alert category
        :param title: Alert title
        :param districts: districts the alert is running for
        :param desc: Alert description/extra info
        """
        self.id = id
        self.category = cat
        self.title = title
        self.districts = districts
        self.description = desc

    @classmethod
    def from_dict(cls, data: dict):
        """
        Return a new Alert instance from an Alert-formatted dict (matching HFC alert requests)

        Dict format:

        {
            "id": int,
            "cat": int,
            "title": str,
            "data": list[str],
            "desc": str
        }

        :param data: A dict of matching format

        :return: The new Alert instance
        """
        return cls(int(data.get('id', '0')),
                   int(data.get('cat', '0')),
                   data.get('title'),
                   data.get('data'),
                   data.get('desc'))
