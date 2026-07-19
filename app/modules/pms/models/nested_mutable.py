from sqlalchemy.ext.mutable import Mutable

class TrackedDict(Mutable, dict):
    def __init__(self, seq=None, **kwargs):
        # Initialize standard SQLAlchemy parents mapping tracking dictionary
        self._parents = {}
        self.ancestor = kwargs.pop("ancestor", None)
        if seq is not None:
            super().__init__(seq, **kwargs)
        else:
            super().__init__(**kwargs)
        # Recursively convert internal maps
        for k, v in self.items():
            super().__setitem__(k, NestedMutable.convert(v, self.ancestor or self))

    def __setitem__(self, key, value):
        super().__setitem__(key, NestedMutable.convert(value, self.ancestor or self))
        if self.ancestor:
            self.ancestor.changed()
        else:
            self.changed()

    def __delitem__(self, key):
        super().__delitem__(key)
        if self.ancestor:
            self.ancestor.changed()
        else:
            self.changed()

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        for k, v in self.items():
            super().__setitem__(k, NestedMutable.convert(v, self.ancestor or self))
        if self.ancestor:
            self.ancestor.changed()
        else:
            self.changed()


class TrackedList(Mutable, list):
    def __init__(self, iterable=None):
        # Initialize standard SQLAlchemy parents mapping tracking dictionary
        self._parents = {}
        self.ancestor = None
        if iterable is not None:
            super().__init__(iterable)
        else:
            super().__init__()

    def set_ancestor(self, ancestor):
        self.ancestor = ancestor
        for i, v in enumerate(self):
            super().__setitem__(i, NestedMutable.convert(v, ancestor))

    def append(self, item):
        super().append(NestedMutable.convert(item, self.ancestor or self))
        if self.ancestor:
            self.ancestor.changed()
        else:
            self.changed()

    def extend(self, iterable):
        super().extend([NestedMutable.convert(item, self.ancestor or self) for item in iterable])
        if self.ancestor:
            self.ancestor.changed()
        else:
            self.changed()

    def pop(self, index=-1):
        res = super().pop(index)
        if self.ancestor:
            self.ancestor.changed()
        else:
            self.changed()
        return res

    def __setitem__(self, index, value):
        super().__setitem__(index, NestedMutable.convert(value, self.ancestor or self))
        if self.ancestor:
            self.ancestor.changed()
        else:
            self.changed()


class NestedMutable(Mutable):
    """Tracks deep mutations for nested dictionaries and lists in JSONB."""
    
    @classmethod
    def change_tracking_on(cls, ancestor):
        pass

    @classmethod
    def convert(cls, value, ancestor):
        if isinstance(value, dict) and not isinstance(value, TrackedDict):
            return TrackedDict(value, ancestor=ancestor)
        elif isinstance(value, list) and not isinstance(value, TrackedList):
            t_list = TrackedList(value)
            t_list.set_ancestor(ancestor)
            return t_list
        return value

    @classmethod
    def coerce(cls, key, value):
        if value is None:
            return value
        
        if isinstance(value, dict) and not isinstance(value, TrackedDict):
            return TrackedDict(value)
        if isinstance(value, list) and not isinstance(value, TrackedList):
            return TrackedList(value)
            
        return value
