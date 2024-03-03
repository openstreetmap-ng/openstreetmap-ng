from enum import Enum


class FormatStyle(str, Enum):
    json = 'json'
    xml = 'xml'
    rss = 'rss'
    gpx = 'gpx'
