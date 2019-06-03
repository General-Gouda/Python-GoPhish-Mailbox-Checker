import json

class Configuration:
    def __init__(self):
        with open(r"./Config/Config.json") as config_json:
            self.__dict__ = json.load(config_json)

