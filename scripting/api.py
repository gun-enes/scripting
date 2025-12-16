import json
from typing import Any, Tuple

from django.http import JsonResponse, HttpRequest

from app.models.repo import DocumentRepo
from app.models.document import Document
from db import Database


# Singleton repo for the API lifecycle
_repo: DocumentRepo | None = None
_db: Database | None = None


def _get_repo() -> Tuple[DocumentRepo, Database]:
    global _repo, _db
    if _repo is None:
        _repo = DocumentRepo()
        _db = Database(_repo)
        # Load any persisted state if available
        try:
            _db.load_repo()
        except Exception as e:
            # Non-fatal — start with an empty repo
            print(f"Repo load failed: {e}")
    return _repo, _db  # type: ignore


def _ok(value: Any):
    return JsonResponse({"result": "success", "value": value})


def _err(reason: str, status: int = 400):
    return JsonResponse({"result": "error", "reason": reason}, status=status)


def _parse_json_body(request: HttpRequest) -> Any:
    if not request.body:
        return None
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON payload")


# Routes: /api/document (GET, POST)
def documents(request: HttpRequest):
    repo, db = _get_repo()

    if request.method == "GET":
        data = repo.list()
        # list returns list of tuples (id, description)
        docs = [{"id": doc_id, "description": desc} for doc_id, desc in data]
        return _ok({"documents": docs})

    if request.method == "POST":
        try:
            new_id = repo.create()
            # persist after mutation
            db.save_repo()
            # return the whole created document
            doc = repo.documents[new_id]
            return _ok({"id": new_id, "document": doc.to_dict()})
        except Exception as e:
            return _err(str(e))

    return _err("Method not allowed", status=405)


# Routes: /api/document/<doc_id> (GET, PUT, DELETE)
def document_detail(request: HttpRequest, doc_id: str):
    repo, db = _get_repo()
    if doc_id not in repo.documents:
        return _err("document does not exist", status=404)

    doc: Document = repo.documents[doc_id]

    if request.method == "GET":
        return _ok(doc.to_dict())

    if request.method == "PUT":
        try:
            payload = _parse_json_body(request)
            if not isinstance(payload, dict) or "value" not in payload:
                return _err("missing 'value' in request body")
            value = payload["value"]
            if not isinstance(value, dict):
                return _err("'value' must be an object containing the document")
            # Import new document structure (replace existing)
            doc.importJson(json.dumps(value))
            db.save_repo()
            return _ok(doc.to_dict())
        except Exception as e:
            return _err(str(e))

    if request.method == "DELETE":
        try:
            repo.delete(doc_id)
            db.save_repo()
            return _ok({"deleted": doc_id})
        except PermissionError as e:
            return _err(str(e), status=403)
        except Exception as e:
            return _err(str(e))

    return _err("Method not allowed", status=405)


# Routes: /api/document/<doc_id>/path/<path:subpath> (GET, POST, PUT, DELETE)
def document_path(request: HttpRequest, doc_id: str, subpath: str):
    repo, db = _get_repo()
    if doc_id not in repo.documents:
        return _err("document does not exist", status=404)

    doc: Document = repo.documents[doc_id]

    if request.method == "GET":
        try:
            node = doc[subpath]
            if isinstance(node, Document):
                return _ok(node.to_dict())
            else:
                return _ok({"value": node})
        except Exception as e:
            return _err(str(e), status=400)

    if request.method in ("POST", "PUT"):
        try:
            payload = _parse_json_body(request)
            if not isinstance(payload, dict) or "value" not in payload:
                return _err("missing 'value' in request body")
            value = payload["value"]

            # For numeric leaf insertion, pass a string markup for node creation
            # e.g., {"value": "paragraph"} at path "0/1" inserts a new node
            doc[subpath] = value
            db.save_repo()
            # Return the updated target's parent subtree for context
            return _ok(repo.documents[doc_id].to_dict())
        except Exception as e:
            return _err(str(e), status=400)

    if request.method == "DELETE":
        try:
            del doc[subpath]
            db.save_repo()
            return _ok({"deleted": subpath})
        except Exception as e:
            return _err(str(e), status=400)

    return _err("Method not allowed", status=405)
