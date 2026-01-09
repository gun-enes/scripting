import json
import uuid
import time
from threading import RLock

class Document:
    """
    Represents a node in a JSON-based rich text document.
    Each Document object is a node in a tree, with a markup type,
    attributes (like content, style, src), and a list of children.
    """
    def __init__(self, markup='document', id=None, parent=None, attributes = {}):
        self.markup = markup
        self.description = "New document"
        self.id = id if id else str(uuid.uuid4())
        self.children = []
        self.attributes = attributes
        self.parent_doc = parent
        self.observers = set()
        self.lock = RLock()

    def _notify_observers(self):
        try:
            root = self
            while root.parent():
                root = root.parent()
            
            html_snapshot = root.html()
            
            # Notify observers on this node
            for obs in self.observers:
                obs.update(html_snapshot, self.id)
                
            # Bubble notification up to the parent
            if self.parent_doc:
                self.parent_doc._notify_observers_bubble(html_snapshot)
        except Exception as e:
            print(f"Error notifying observers: {e}")
            # Don't let observer errors crash the application

    def _notify_observers_bubble(self, html_snapshot):
        """Helper to bubble notifications up without re-rendering HTML."""
        for obs in self.observers:
            obs.update(html_snapshot, self.id)
        if self.parent_doc:
            self.parent_doc._notify_observers_bubble(html_snapshot)

    def _get_path(self,idstr, current_path=""):
        """
        Internal helper to find the path to a node with the given id.
        Returns the path as a string of indices separated by '/'.
        """
        if self.id == idstr:
            return current_path.rstrip('/')

        for idx, child in enumerate(self.children):
            child_path = f"{current_path}{idx}/"
            result = child._get_path(idstr, child_path)
            if result:
                return result

        return None
    
    def importJson(self, data):
        """
        Constructs (re-initializes) the document from a JSON string.
        This will overwrite the current node's data.
        """
        try:
            self._from_dict(data, parent=self.parent_doc)
            self._notify_observers()
        except KeyError as e:
            raise ValueError(f"Missing expected key in JSON: {e}")

    def _from_dict(self, data, parent):
        """Recursive helper to build the document tree from a dictionary."""
        if 'markup' not in data:
            raise ValueError("Missing 'markup' in data")
            
        self.markup = data['markup']
        self.id = data.get('id', str(uuid.uuid4()))
        self.parent_doc = parent
        self.attributes = {}
        self.children = []

        reserved_keys = {'markup', 'id', 'children'}
        for key, value in data.items():
            if key not in reserved_keys:
                self.attributes[key] = value

        for child_data in data.get('children', []):
            child_doc = Document(parent=self)
            child_doc._from_dict(child_data, parent=self)
            self.children.append(child_doc)

    def _find_node_and_key(self, path):
        """
        Internal helper to find the parent node and the final key/index from a path.
        """
        parts = path.split('/')
        if not parts:
            raise ValueError("Empty path")
            
        current = self
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # This is the last part, return the current node and the key
                return current, part
                
            if part.isdigit():
                try:
                    idx = int(part)
                    if 0 <= idx < len(current.children):
                        current = current.children[idx]
                    else:
                        raise IndexError("Path index out of bounds")
                except (ValueError, IndexError):
                    raise ValueError(f"Invalid path component: {part} at {path}")
            else:
                raise ValueError(f"Path must be numeric indices, except for final leaf: {part} at {path}")
        
        # Should not be reached if path has at least one part
        return None, None

    def __getitem__(self, path):
        """
        Return the Document at the given path, or the attribute
        if the leaf is 'text', 'content', 'style', or 'src'.

        doc['0/1'] -> children[0].children[1]
        doc['0/1/content'] -> children[0].children[1].content
        """
        with self.lock:
            try:
                node, key = self._find_node_and_key(path)

                if key.isdigit():
                    return node.children[int(key)]
                elif key == 'text':
                    return node.attributes.get('content')
                elif node.attributes.get(key):
                    return node.attributes.get(key)
                else:
                    if path.isdigit():
                        return self.children[int(path)]
                    else:
                        raise ValueError(f"Invalid path component: {path} at {path}")
            except Exception as e:
                raise ValueError(f"Error getting item at path '{path}': {e}")

    def regenerate_ids(self):
        self.id = str(uuid.uuid4())
        for child in self.children:
            if isinstance(child, Document):
                child.regenerate_ids()

    def __setitem__(self, path, value):
        """
        Inserts an empty markup or sets an attribute.
        doc['0/1'] = 'strong' -> Inserts a new 'strong' Document at children[0].children[1]
        doc['0/1/content'] = 'Hello' -> Sets the content of the node at children[0].children[1]
        """
        with self.lock:
            try:
                node, key = self._find_node_and_key(path)
                if key == 'style':
                    node.attributes['style'] = value

                if key.isdigit():
                    # This is an insertion/replacement at a numeric index
                    idx = int(key)
                    if isinstance(value, Document):
                        newNode = Document()
                        newNode.importJson(value.to_dict())
                        newNode.regenerate_ids() 
                        newNode.parent_doc = node
                        if idx == len(node.children):
                            node.children.append(newNode)
                        else:
                            node.children.insert(idx, newNode)
                    elif isinstance(value, tuple):
                        new_node = Document(id=value[0], markup=value[1], parent=node, attributes=json.loads(value[2]))
                        if idx == len(node.children):
                            node.children.append(new_node)
                        else:
                            node.children.insert(idx, new_node)

                    else:
                        new_node = Document(markup=str(value), parent=node)

                        if idx == len(node.children):
                            node.children.append(new_node)
                        else:
                            # Insert at position, shifting others
                            node.children.insert(idx, new_node)

                elif key in ('text', 'content'):
                    node.attributes['content'] = value
                elif node.attributes.get(key):
                    node.attributes[key] = value
                else:
                    node.attributes[key] = value

                # Notify observers starting from the modified node
                node._notify_observers()

            except Exception as e:
                raise ValueError(f"Error setting item at path {path}: {e}")

    def __delitem__(self, path):
        """
        Remove the component at the given path.
        del doc['0/1'] # Deletes node at children[0].children[1]
        del doc['0/1/content'] # Sets content to None
        """
        with self.lock:
            try:
                node, key = self._find_node_and_key(path)

                if key.isdigit():
                    idx = int(key)
                    if 0 <= idx < len(node.children):
                        del node.children[idx]
                    else:
                        raise IndexError("Index out of bounds")
                elif key == 'text':
                    if 'content' in node.attributes:
                        del node.attributes['content']
                elif key in node.attributes:
                    del node.attributes[key]
                else:
                    raise ValueError(f"Invalid key in path: {key}")

                # Notify observers starting from the modified node
                node._notify_observers()

            except Exception as e:
                raise ValueError(f"Error deleting item at path '{path}': {e}")

    def del_id(self, idstr):
        """
        Deletes the node with the given id from the document tree.
        """
        with self.lock:
            path = self._get_path(idstr)
            if path is not None:
                self.__delitem__(path)
                return True
            else:
                return False
    
    def insert(self, path, document):
        """
        Inserts a Document object at the given position.
        The leaf of the path must be an integer index.
        """
        with self.lock:
            if not isinstance(document, Document):
                raise TypeError("Item to insert must be a Document object")

            try:
                node, key = self._find_node_and_key(path)

                if key.isdigit():
                    idx = int(key)
                    newNode = Document()
                    newNode.importJson(document.to_dict())
                    # Set parent of the inserted document
                    newNode.parent_doc = node

                    if idx == len(node.children):
                        node.children.append(newNode)
                    else:
                        node.children.insert(idx, newNode)

                    # Notify observers
                    node._notify_observers()
                else:
                    raise ValueError("Path for insert() must end in a numeric index")

            except Exception as e:
                raise ValueError(f"Error inserting at path '{path}': {e}")

    def getid(self, idstr):
        if self.id == idstr:
            return self
        
        for child in self.children:
            found = child.getid(idstr)
            if found:
                return found
        return None

    def search(self, text):
        results = []

        content = self.attributes.get('content')
        if self.markup == 'text' and content and text in content:
            results.append(self.json())
            
        for child in self.children:
            results.extend(child.search(text))
            
        return results

    def parent(self):
        return self.parent_doc

    def draw(self):
        print(self.html())

    def html(self):

        style_attr = ""
        if self.attributes.get('style'):
            style_attribute = self.attributes.get('style')
            style_attr = f' style="{style_attribute}"' 

        if self.markup == 'text':
            return self.attributes.get('content') or ""
            
        if self.markup == 'image':
            src = self.attributes.get('src') or ""
            return f'\t<img src="{src}" alt="image" />\n' if src else '\t<img alt="image" />\n'

        # Handle other markups by processing children
        children_html = "".join([child.html() for child in self.children])
        
        tag_map = {
            'document': lambda: children_html,
            'paragraph': lambda: f'\t<p{style_attr}>\n{children_html}\n</p>\n',
            'strong': lambda: f'<strong{style_attr}>{children_html}</strong>',
            'list': lambda: f'\t<ul{style_attr}>\n{children_html}</ul>\n',
            'item': lambda: f'\t<li{style_attr}>\n{children_html}\n</li>\n',
            'table': lambda: f'\t<table{style_attr}>\n{children_html}</table>\n',
            'row': lambda: f'\t<tr{style_attr}>\n{children_html}</tr>\n',
            'cell': lambda: f'\t<td{style_attr}>\n{children_html}\n</td>\n',
        }
        
        if self.markup in tag_map:
            return tag_map[self.markup]()
        if children_html:
            # Default
            return f'\t<div{style_attr}>\n{children_html}\n</div>\n'
        else:
            return ""
    def to_dict(self):
        d = {}
        d["markup"] = self.markup
        d["id"] = self.id

        attrs = dict(self.attributes)
        d.update(attrs)

        if self.children:
            d["children"] = [child.to_dict() for child in self.children]

        return d

    def json(self):
        return json.dumps(self.to_dict(), indent=2)

    def watch(self, obj):
        self.observers.add(obj)

    def unwatch(self, obj):
        self.observers.discard(obj)

    def print(self):
        print(self.json())

    def list(self):
        children_list = []
        for child in self.children:
            children_list.append((child.id, child.markup))
            children_list.extend(child.list())
        return children_list
