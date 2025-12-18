from flask import Flask, request, jsonify
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
+ return değerlerini result value olacak şekilde ayarlanması
+ parent function
+ get by path: this is going to be by query.
+ document data operations ayrılmalı, adı bence data da olmamalı
+ errorlerin, result ve reason dönmesi
+ import json çalışıyor
ben yaptım ama sen yine de bak: 
    gereksiz şeyler silinmeli, userla ilgili şeyler gibi, 
    is there anything we did not implement here, which we implemented in phase 1?

try except eklenmeli 
search document ı test et
save i kontrol et
draw'a bak

deepseek e biraz test yazdırdım sen yine de bakabilirsin
postman testleri zenginleştirilmeli:
    - crud operations
    - search draw import json functionalities
    - document to document, recursively
    - add content to the document
    - add image to the document
    - import json
    - import invalid json
    - delete not existent id
    - delete by path
    - delete at invalid path
    - update not existent id
    - update by path
    - update at invalid path
    - insert node at path
    - insert node at invalid path
    - insert node by replacing the existing document
"""

repo_lock = RLock()

def is_valid_uuid(val):
    try:
        uuid.UUID(val)
        return True
    except ValueError:
        return False

@app.route('/api/document', methods=['POST'])
def create_document():
    with repo_lock:
        document_id = repo.create()
        database.save_repo()
    return jsonify({"result": "success", "value": document_id})

@app.route('/api/document/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    with repo_lock:
        try:
            repo.delete(doc_id)
            database.save_repo()
            return jsonify({"result": "success", "value": f"Item with {doc_id} id is deleted!"})
        except Exception as e:
            return jsonify({"result": "error", "reason": str(e)}), 404


@app.route('/api/document', methods=['GET'])
def list_documents():
    with repo_lock:
        items = repo.list_all()
        return jsonify({"result": "success", "value": items})

@app.route('/api/document/<doc_id>', methods=['GET'])
def get_document(doc_id):
    if not is_valid_uuid(doc_id):
        return jsonify({"result": "error", "reason": "Invalid UUID"}), 400
    with repo_lock:
        current_document = repo.find_document_by_id(doc_id)
        if current_document == None:
            return jsonify({"result": "error", "reason": "Document not found"}), 404
        else:
            path = request.args.get('path')
            if path:
                try:
                    val = current_document[path]
                    if hasattr(val, 'json'): # Handle if the result is another Document object
                        return jsonify({"result": "success", "value": json.loads(val.json())})
                    return jsonify({"result": "success", "value": val})
                except TypeError:
                    return jsonify({"result": "error", "reason": "Type error in path retrieval"}), 500
                except KeyError:
                    return jsonify({"result" :"error", "reason": "Path not found"}), 404
                except:
                    return jsonify({"result": "error", "reason": "An error occurred while retrieving the path"}), 500
            else:
                return jsonify({"result": "success", "value": json.loads(current_document.json())})

@app.route('/api/document/<doc_id>/insert', methods=['POST'])
def document_insert(doc_id):
    if not is_valid_uuid(doc_id):
        return jsonify({"result": "error", "reason": "Invalid UUID"}), 400
    with repo_lock:
        try:
            current_document = repo.find_document_by_id(doc_id)
            if not current_document:
                return jsonify({"result": "error", "reason": f"Document with {doc_id} id is not found"}), 404
            path = request.args.get('path') # path is required
            if not path:
                return jsonify({"result": "error", "reason": "Path is required"}), 400

            data = request.json
            value = data.get('data')

            if isinstance(value, str) and is_valid_uuid(value): # insert document into document
                found_doc = repo.find_document_by_id(value)
                if found_doc:
                    current_document[path] = found_doc
                    database.save_repo()
                    return jsonify({"result": "success", "value": f"Document with id {value} is inserted at {path}"})
            current_document[path] = value
            database.save_repo()
            return jsonify({"result": "success", "value": f"Item at {path} path is deleted!"})
        except Exception as e:
            return jsonify({"result": "error", "reason": e}), 404



@app.route('/api/document/<doc_id>/delete', methods=['DELETE'])
def document_delete(doc_id):
    if not is_valid_uuid(doc_id):
        return jsonify({"result": "error", "reason": "Invalid UUID"}), 400
    with repo_lock:
        try:
            current_document = repo.find_document_by_id(doc_id)
            if not current_document:
                return jsonify({"result": "error", "reason": f"Document with {doc_id} id is not found"}), 404
            path = request.args.get('path') # path is required
            if not path:
                return jsonify({"result": "error", "reason": "Path is required"}), 400
            del current_document[path]
            database.save_repo()
            return jsonify({"result": "success", "value": f"Item at {path} path is deleted!"})
        except IndexError as e:
            return jsonify({"result": "error", "reason": e}), 404
        except ValueError as e:
            return jsonify({"result": "error", "reason": e}), 404
        except Exception as e:
            return jsonify({"result": "error", "reason": e}), 404


@app.route('/api/document/import', methods=['POST'])
def import_json():
    doc_id = repo.create()
    current_document = repo.find_document_by_id(doc_id)
    current_document.importJson(request.json)
    database.save_repo()
    return jsonify({"result": "success", "value": doc_id}), 201

@app.route('/api/document/<doc_id>/search', methods=['GET'])
def search_document(doc_id):
    current_document = repo.find_document_by_id(doc_id)
    query = request.args.get('q')
    return jsonify({"result": "success", "value": str(current_document.search(query))})

@app.route('/api/document/<doc_id>/draw', methods=['GET'])
def draw_document(doc_id):
    current_document = repo.find_document_by_id(doc_id)
    return current_document.html()

@app.route('/api/document/<doc_id>/parent', methods=['GET'])
def parent_document(doc_id):
    current_document = repo.find_document_by_id(doc_id)
    if current_document.parent() == None:
        return jsonify({"result": "error", "reason": "Document does not have a parent"})
    return jsonify({"result": "success", "value": (str(current_document.parent().id), str(current_document.parent().markup))})

if __name__ == '__main__':
    app.run(debug=True, port=8000)

"""
@app.route('/api/document', methods=['POST'])
@app.route('/api/document/<doc_id>', methods=['DELETE'])
@app.route('/api/document', methods=['GET']) #getall
@app.route('/api/document/<doc_id>/import', methods=['POST'])
@app.route('/api/document/<doc_id>/search', methods=['GET'])
@app.route('/api/document/<doc_id>/draw', methods=['GET'])
@app.route('/api/document/<doc_id>/parent', methods=['GET'])

# with path, path is given in the query as ?path=0/1
@app.route('/api/document/<doc_id>', methods=['GET']) # it should be testedwith and without path 
@app.route('/api/document/<doc_id>/insert', methods=['POST'])
@app.route('/api/document/<doc_id>/delete', methods=['DELETE'])
"""
