from flask import Flask, request, jsonify, session
from threading import RLock
from document import Document
from repo import DocumentRepo
from db import Database
import json  
import uuid

app = Flask(__name__)
app.secret_key = "super_secret_key"  

repo = DocumentRepo()
database = Database(repo)
database.load_repo()
"""
return değerlerini result value olacak şekilde ayarlanamsı
errorlerin, result ve reason dönmesi
try except eklenmeli 
gereksiz şeyler silinmeli, userla ilgili şeyler gibi
document data ops ayrılmalı
search document ı test et





"""
repo_lock = RLock()

def get_current_user():
    return session.get('user', 'guest')

def is_valid_uuid(val):
    try:
        uuid.UUID(val)
        return True
    except ValueError:
        return False

@app.route('/api/document', methods=['POST'])
def create_document():
    user = get_current_user()
    with repo_lock:
        document_id = repo.create()
        database.save_repo()
    return jsonify({"message": f"{document_id} is added!", "id": document_id})

@app.route('/api/document/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    with repo_lock:
        repo.delete(doc_id)
        database.save_repo()
    return jsonify({"message": f"Item with {doc_id} id is deleted!"})

@app.route('/api/document', methods=['GET'])
def list_documents():
    with repo_lock:
        items = repo.list_all()
        return jsonify({"result": "success", "value": items})

@app.route('/api/document/<doc_id>', methods=['GET'])
def get_document_by_id(doc_id):
    with repo_lock:
        # try catch
        doc = repo.find_document_by_id(doc_id)
        if doc == None:
            return jsonify({"result": "error", "reason": "Object does not exist!"})
        return jsonify({"result": "success", "value": json.loads(doc.json())})

@app.route('/api/document/<doc_id>/data', methods=['GET', 'POST', 'DELETE'])
def document_data_ops(doc_id):
    if not is_valid_uuid(doc_id):
        return jsonify({"error": "Invalid UUID"}), 400

    with repo_lock:
        current_document = repo.find_document_by_id(doc_id)
        if not current_document:
            return jsonify({"error": f"Document with {doc_id} id is not found"}), 404

        if request.method == 'POST':
            data = request.json
            path = data.get('path')
            value = data.get('value') # should be json
            
            # if path is invalid, it should return proper error
            if isinstance(value, str) and is_valid_uuid(value): # insert document into document
                found_doc = repo.find_document_by_id(value)
                if found_doc:
                    current_document[path] = found_doc
                    return jsonify({"message": f"Document with {value} id is inserted at {path}!"})
            
            current_document[path] = value
            database.save_repo()
            return jsonify({"message": f"{value} is inserted at {path}!"})

        elif request.method == 'GET':
            path = request.args.get('path') # ?path=some_key
            
            if path:
                try:
                    val = current_document[path]
                    
                    if hasattr(val, 'json'): # Handle if the result is another Document object
                        return jsonify({"result": val.json()})
                    return jsonify({"result": val})
                except TypeError:
                     return jsonify({"error": "Type error in path retrieval"}), 500
                except KeyError:
                     return jsonify({"error": "Path not found"}), 404
            else:
                return jsonify({"result": current_document.json()})

        elif request.method == 'DELETE':
            path = request.args.get('path')
            if path in current_document:
                del current_document[path]
                database.save_repo()
                return jsonify({"message": f"Item at {path} path is deleted!"})
            return jsonify({"error": "Path not found"}), 404

@app.route('/api/document/<doc_id>/import', methods=['POST'])
def import_json(doc_id):
    current_document = repo.find_document_by_id(doc_id)
    if not current_document:
        return jsonify({"error": "Not found"}), 404
    
    json_data = request.json.get('json_data')
    current_document.importJson(json_data)
    database.save_repo()
    return jsonify({"message": "Json is successfully imported!"})

@app.route('/api/document/<doc_id>/search', methods=['GET'])
def search_document(doc_id):
    current_document = repo.find_document_by_id(doc_id)
    query = request.args.get('q')
    return jsonify({"results": str(current_document.search(query))})

@app.route('/api/document/<doc_id>/draw', methods=['GET'])
def draw_document(doc_id):
    current_document = repo.find_document_by_id(doc_id)
    return current_document.html()

if __name__ == '__main__':
    app.run(debug=True, port=8000)
