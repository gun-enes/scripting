import os
import sqlite3
import json
import uuid
from threading import Lock

from document import Document

class DocumentDbModel:
    def __init__(self, doc_id, root_id, path, markup, attributes):
        self.id = doc_id
        self.root_id = root_id
        self.markup = markup
        self.path = path
        self.attributes = attributes

class NewDb:
    DB_NAME = "document.db"
    def init_repo(self):
        with sqlite3.connect(NewDb.DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                create table if not exists repo(
                    id text primary key,
                    markup text not null,
                    attributes text not null,
                    root_id text not null,
                    path varchar(256)
                )
            """)

    def get_all(self):
        with sqlite3.connect(NewDb.DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""select id, markup, attributes, root_id, path from repo""")
            return cursor.fetchall()
    
    def insert_document_tree(self, doc):
        self._from_dict(doc.to_dict(), doc.id, "")

    def _from_dict(self, data, root_id, path):
        """Recursive helper to build the document tree from a dictionary."""
        if 'markup' not in data:
            raise ValueError("Missing 'markup' in data")
            
        markup = data['markup']
        doc_id = data.get('id', str(uuid.uuid4()))
        attr = {}

        reserved_keys = {'markup', 'id', 'children'}
        for key, value in data.items():
            if key not in reserved_keys:
                attr[key] = value
        attr_str = json.dumps(attr)

        db_model = DocumentDbModel(doc_id, root_id, path, markup, attr_str)
        
        with sqlite3.connect(NewDb.DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """insert or replace into repo (id, markup, path, root_id, attributes) values (?, ?, ?, ?, ?)""",
                (db_model.id, db_model.markup, db_model.path, db_model.root_id, db_model.attributes)
            )
            conn.commit()

        for i, child_data in enumerate(data.get('children', [])):
            if path:
                self._from_dict(child_data, root_id, path + "/" + str(i))
            else:
                self._from_dict(child_data, root_id, str(i))



    def search(self, text):
        with sqlite3.connect(NewDb.DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """select * from where markup like ? or attributes like ?""",
                ("%" + text + "%", "%" + text + "%")
            )
            return cursor.fetchall()

    def insert_document(self, db_model):
        with sqlite3.connect(NewDb.DB_NAME) as conn:
            cursor = conn.cursor()
            if db_model.root_id != db_model.id:
                self._update_siblings(cursor, db_model.path, 1)
            cursor.execute(
                """insert or replace into repo (id, markup, path, root_id, attributes) values (?, ?, ?, ?, ?)""",
                (db_model.id, db_model.markup, db_model.path, db_model.root_id, db_model.attributes)
            )
            conn.commit()

    def delete_document(self, doc_id):
        doc_meta = self._get_document_obj_by_id(doc_id)
        with sqlite3.connect(NewDb.DB_NAME) as conn:
            root_id = doc_meta[0]
            path = doc_meta[1]

            cursor = conn.cursor()

            cursor.execute( # remove descendants and itself in a single query, including root
                """
                delete from repo where path like ? and root_id = ?
                """,
                (path + "%", root_id)
            )

            if root_id != doc_id:
                print(f"Updating siblings for {path}")
                self._update_siblings(cursor, path, -1)
            conn.commit()

    def parent(self, doc_id):
        doc_meta = self._get_document_obj_by_id(doc_id)
        root_id, path = doc_meta
        if doc_meta == None:
            return None
        with sqlite3.connect(NewDb.DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""select id, markup, attributes from repo where path = ? """, (path.rsplit("/", 1)[0],))
            doc_tpl = cursor.fetchone()
            if doc_tpl == None:
                return None
            return Document(id = doc_tpl[0], markup=doc_tpl[1], attributes=json.loads(doc_tpl[2]))

    def get_document_by_path(self, path, root_id):
        with sqlite3.connect(NewDb.DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""select id, markup, attributes, path from repo where root_id = ? and path = ? """, (root_id, path))
            return cursor.fetchone()
                    
    def get_document_by_id(self, doc_id):
        doc_meta = self._get_document_obj_by_id(doc_id)
        if doc_meta == None:
            return None
        with sqlite3.connect(NewDb.DB_NAME) as conn:
            root_id, path = doc_meta
            cursor = conn.cursor()
            cursor.execute("""
                select id, markup, attributes, path
                from repo
                where root_id = ?
                and path like ?
                           """
            ,(root_id, f"{path}%")) # get itself and the descendants

            doc = cursor.fetchall()
            if doc:
                if root_id == doc_id:
                    return self._construct_document(doc, is_root=True)
                return self._construct_document(doc)
            else:
                return None

    def _get_document_obj_by_id(self, doc_id):
        with sqlite3.connect(NewDb.DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""select root_id, path from repo where id = ? """, (doc_id,))
            return cursor.fetchone()

    def _construct_document(self, doc, is_root=False):
        doc_obj = Document(id=doc[0][0])
        original_path = doc[0][3]
        path_size = len(original_path)
        if is_root:
            path_size = path_size - 1
        # doc: id markup attributes path
        for d in doc[1:]:
            cur_path = d[3][path_size+1:]
            doc_obj[cur_path] = d[0:3]
        return doc_obj

    def _update_siblings(self, cursor, path, operation):
        if len(path) == 1:
            path_var = path + "%"
        else:
            path_var = path.rsplit("/", 1)[0] + "/%" # include / to just match with the children
        # get sibling documents
        cursor.execute(
                """
                select id, path from repo where path like ?
                """,
                (path_var,)
            )
        siblings = cursor.fetchall()
        if siblings:
            for s in siblings:
                doc_parts = path.split("/")
                lng = len(doc_parts)
                sibling_parts = s[1].split("/")
                if int(sibling_parts[lng-1]) < int(doc_parts[lng-1]): # take the middle one
                    """
                    update is in 0/1/0
                    when inserting 0/1/0 -> 0/2/0
                    when deleting 0/1/0 -> 0/0/0
                    """
                    continue # <= means include the same, so <
                else:
                    print(s)
                    sibling_parts[lng-1]  = str(int(sibling_parts[lng-1]) + operation)
                    new_path = "/".join(sibling_parts)
                    cursor.execute(
                        """
                        update repo set path = ? where id = ?
                        """,
                        (new_path, s[0])
                    )

