from bson import ObjectId
import pymongo


connection_entries = {
    'host': '127.0.0.1',
    'port': 27017
}
client = pymongo.MongoClient(**connection_entries)
database = client['contracts-management']


def find_documents(collection_name, query):
    return database[collection_name].find(query)


def find_documents_under_operator(collection_name, operator, queries: list):
    return database[collection_name].find({f'${operator}': queries})


def find_one_document(collection_name, query):
    return database[collection_name].find_one(query)


def insert_one_document(collection_name, document):
    result = database[collection_name].insert_one(document)
    return str(result.inserted_id)


def insert_documents(collection_name, documents: list):
    database[collection_name].insert_many(documents)


def update_one_document(collection_name, document_id, new_document):
    database[collection_name].update_one({'_id': ObjectId(document_id)}, {'$set': new_document})


def delete_one_document(collection_name, query):
    database[collection_name].delete_one(query)


def delete_many_documents(collection_name, query):
    database[collection_name].delete_many(query)
