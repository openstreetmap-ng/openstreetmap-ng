from fastapi import HTTPException


class APIError(HTTPException):
    pass
