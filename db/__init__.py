from motor.core import AgnosticDatabase
from motor.motor_asyncio import AsyncIOMotorClient

from config import MONGO_HOST, NAME

# TODO: https://www.mongodb.com/developer/products/mongodb/mongodb-network-compression/
MONGO_CLIENT = AsyncIOMotorClient(f'mongodb://{MONGO_HOST}/?replicaSet=rs0')
MONGO_DB: AgnosticDatabase = MONGO_CLIENT[NAME]

# TODO: test unicode normalization comparison
