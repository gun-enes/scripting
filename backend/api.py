from flask import Flask, request, jsonify
from threading import RLock
from document import Document
from repo import DocumentRepo
from new_db import NewDb
import json  
import uuid
from flask_cors import CORS 


app = Flask(__name__)
app.secret_key = "super_secret_key"  
CORS(app)


newDb = NewDb()
newDb.init_repo()
repo = DocumentRepo(newDb)
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
    return jsonify({"result": "success", "value": document_id})

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
        root_document = repo.find_document_by_id(doc_id)
        if root_document == None:
            return jsonify({"result": "error", "reason": "Document not found"}), 404
        path = request.args.get('path')
        if path:
            try:
                val = root_document[path]
                if hasattr(val, 'json'): # Handle if the result is another Document object
                    return jsonify({"result": "success", "value": json.loads(val.json())})
                return jsonify({"result": "success", "value": val})
            except TypeError:
                return jsonify({"result": "error", "reason": "Type error in path retrieval"}), 500
            except KeyError:
                return jsonify({"result" :"error", "reason": "Path not found"}), 404
            except ValueError:
                return jsonify({"result": "error", "reason": "Path is not appropriate"}), 404
            except Exception as e:
                return jsonify({"result": "error", "reason": f"An error occurred while retrieving the path: {str(e)}"}), 500
        else:
            return jsonify({"result": "success", "value": json.loads(root_document.json())})

# insert document into document
@app.route('/api/document/<doc_id>/insert/<doc_to_insert>', methods=['POST'])
def insert_document(doc_id, doc_to_insert):
    if not is_valid_uuid(doc_id) or not is_valid_uuid(doc_to_insert):
        return jsonify({"result": "error", "reason": "Invalid UUID"}), 400
    with repo_lock:
        try:
            root_doc = repo.find_document_by_id(doc_id)
            found_doc = repo.find_document_by_id(doc_to_insert)
            path = request.args.get('path') # path is required

            if not root_doc:
                return jsonify({"result": "error", "reason": f"Document with {doc_id} id is not found"}), 404

            if not found_doc:
                return jsonify({"result": "error", "reason": f"Document with {doc_id} id is not found"}), 404

            if not path:
                return jsonify({"result": "error", "reason": "Path is required"}), 400

            root_doc[path] = found_doc
            newDb.insert_document_to_document(doc_id, payload_id, path)
            return jsonify({"result": "success", "value": f"Document with id {payload_id} is inserted at {path}"}), 201
        except Exception as e:
            return jsonify({"result": "error", "reason": str(e)}), 404



# insert value into document
@app.route('/api/document/<doc_id>/insert', methods=['POST'])
def insert_value(doc_id):
    """
    insert a document with its id at a given path
    create a document with the data at a given path
    """
    if not is_valid_uuid(doc_id):
        return jsonify({"result": "error", "reason": "Invalid UUID"}), 400
    with repo_lock:
        try:
            root_doc = repo.find_document_by_id(doc_id)
            path = request.args.get('path') # path is required

            if not root_doc:
                return jsonify({"result": "error", "reason": f"Document with {doc_id} id is not found"}), 404
            if not path:
                return jsonify({"result": "error", "reason": "Path is required"}), 400

            data = request.json 
            if not isinstance(data, dict):
                # doc[0/1] = 
                root_doc[path] = data
                return jsonify({"result": "success", "value": f"Data added at {path} path!"})

            if data.get("value"):
                # doc[0/1/content] = value
                value = data.get("value")
                root_doc[path] = value
                return jsonify({"result": "success", "value": value + " is inserted at " + path}), 200

        except Exception as e:
            return jsonify({"result": "error", "reason": str(e)}), 404

@app.route('/api/document/<doc_id>/delete', methods=['DELETE'])
def document_delete(doc_id):
    print("inside")
    if not is_valid_uuid(doc_id):
        print("invalid uuid")
        return jsonify({"result": "error", "reason": "Invalid UUID"}), 400
    with repo_lock:
        try:
            current_document = repo.find_document_by_id(doc_id)
            if not current_document:
                print("doc not found")
                return jsonify({"result": "error", "reason": f"Document with {doc_id} id is not found"}), 404
            path = request.args.get('path') # path is optional
            print(path)
            if not path:
                repo.delete(doc_id)
                print("Deleted without path")
                return jsonify({"result": "success", "value": f"Item with {doc_id} id is deleted!"})
            newDb.delete_document(current_document[path].id)
            del current_document[path]
            print("Deleted with path")
            return jsonify({"result": "success", "value": f"Item at {path} path is deleted!"})
        except ValueError as e:
            return jsonify({"result": "error", "reason": "Path is not appropriate"}), 404
        except Exception as e:
            return jsonify({"result": "error", "reason": str(e)}), 404

@app.route('/api/document/import', methods=['POST'])
def import_json():
    try:
        new_doc = Document()
        new_doc.importJson(request.json)
        new_doc.regenerate_ids() 
        newDb.insert_document_tree(new_doc)
        return jsonify({"result": "success", "value": new_doc.id}), 201
    except Exception as e:
        return jsonify({"result": "error", "reason": str(e)}), 400

@app.route('/api/document/<doc_id>/search', methods=['GET'])
def search_document(doc_id):
    current_document = repo.find_document_by_id(doc_id)
    query = request.args.get('q')
    results = [json.loads(curr) for curr in current_document.search(query)]
    return jsonify({"result": "success", "value": results})

@app.route('/api/document/<doc_id>/draw', methods=['GET'])
def draw_document(doc_id):
    # 1. Find the root
    current_document = repo.find_document_by_id(doc_id)
    if not current_document:
        return "Document not found", 404

    path = request.args.get('path')
    
    try:
        if path:
            target_node = current_document[path]
            return target_node.html()
        else:
            return current_document.html()
    except Exception as e:
        return f"Error resolving path: {str(e)}", 400

@app.route('/api/document/<doc_id>/parent', methods=['GET'])
def parent_document(doc_id):
    parent = newDb.parent(doc_id) # parent is fake, dont do any operations with it
    if parent == None:
        return jsonify({"result": "error", "reason": "Document does not have a parent"})

    result = {"id" : parent.id, "markup":parent.markup}
    if parent.attributes != {}:
        result.update(parent.attributes)
    return jsonify({"result": "success", "value": result})

if __name__ == '__main__':
    app.run(debug=True, port=8000)

"""
@app.route('/api/document', methods=['POST'])
@app.route('/api/document', methods=['GET'])
@app.route('/api/document/<doc_id>', methods=['GET'])
@app.route('/api/document/<doc_id>/insert', methods=['POST'])
@app.route('/api/document/<doc_id>/delete', methods=['DELETE'])
@app.route('/api/document/import', methods=['POST'])
@app.route('/api/document/<doc_id>/search', methods=['GET'])
@app.route('/api/document/<doc_id>/draw', methods=['GET'])
@app.route('/api/document/<doc_id>/parent', methods=['GET'])
"""
