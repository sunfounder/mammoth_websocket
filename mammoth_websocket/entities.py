import threading

class Entity:
    def __init__(self, name, id, types):
        self.name = name
        self.id = id
        self.types = types
        self.length = 0
        for t in types:
            if t == 'uint8':
                self.length += 1
            elif t == 'int8':
                self.length += 1
            elif t == 'uint16':
                self.length += 2
            elif t == 'int16':
                self.length += 2
        self._values = None

    @property
    def value(self):
        if self._values is None:
            return None
        return self._values[0]

    @value.setter
    def value(self, value):
        if self._values is None:
            self._values = [value]
        else:
            self._values[0] = value

    @property
    def values(self):
        return self._values

    @values.setter
    def values(self, values):
        self._values = values

class Entities():
    def __init__(self):
        self.ids = {}
        self.data_lock = threading.Lock()

    def add(self, name, id, types):
        entity = Entity(name, id, types)
        self.ids[id] = entity
        self.__setattr__(name, entity)

    def clear_datas(self):
        with self.data_lock:
            for _, entity in self.ids.items():
                entity.values = None

