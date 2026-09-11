import os

import pymongo
from dotenv import load_dotenv

load_dotenv()


client = pymongo.MongoClient(os.getenv("ATLAS_URI"))
db = client.myDatabase


# action-functionality collection
action_func_db = db["action-functionality"]
func_db = db["functionality"]
