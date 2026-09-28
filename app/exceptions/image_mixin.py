from flask import current_app


def image_not_readable():
    return current_app.api.response(422, description="Image is not readable or its format is not supported")


def image_too_large():
    return current_app.api.response(413, description="Image is too large or its dimensions exceed allowed limits (2000x2000)")
