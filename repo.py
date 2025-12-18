from document import Document
from threading import RLock

class DocumentRepo:
    def __init__(self):
        self.documents = {} 
        self.attached_users = {}
        self.lock = RLock()

    def find_document_by_id(self, document_id):
        for doc_id, doc in self.documents.items():
            found = doc.getid(document_id)
            if found:
                return found
        return None


    def create(self):
        with self.lock:
            doc = Document()
            self.documents[doc.id] = doc
            self.attached_users[doc.id] = set()
            return doc.id

    def list(self):
        with self.lock:
            return [(doc_id, doc.description) for doc_id, doc in self.documents.items()]

    def list_all(self):
        with self.lock:
            children_list = []
            for doc_id, doc in self.documents.items():
                children_list.append((doc_id, doc.markup))
                children_list.extend(doc.list())
            return children_list


    def listattached(self, user):
        with self.lock:
            attached_docs = []
            for doc_id, users in self.attached_users.items():
                if user in users:
                    if doc_id in self.documents:
                        attached_docs.append((doc_id, self.documents[doc_id].markup))
            return attached_docs

    def attach(self, id, user):
        with self.lock:
            if id not in self.documents:
                raise ValueError(f"No document with id: {id}")
                
            self.attached_users[id].add(user)
            return self.documents[id]

    def detach(self, id, user):
        with self.lock:
            if id in self.attached_users:
                self.attached_users[id].discard(user)

    def delete(self, id):
        with self.lock:
            if id not in [doc_id for doc_id, _ in self.list_all()]:
                raise ValueError(f"No document with id: {id}")
                
            if id in self.attached_users and self.attached_users[id]:
                # Check if the set of users is not empty
                raise PermissionError("Cannot delete document: users are still attached.")
                
            # Delete from all tracking dictionaries
            if id in self.documents:
                del self.documents[id]
            else:
                for doc in self.documents.values():
                    doc.del_id(id) 
            if id in self.attached_users:
                del self.attached_users[id]
