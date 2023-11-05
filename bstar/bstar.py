from utils import *
import os
import json
import yaml

class Bstar:
    def __init__(self, data, filename=''):
        if type(data) != bytes:
            self.filename = os.path.basename(data)
            with open(data, 'rb') as file:
                data = file.read()
        else:
            if os.path.splitext(filename)[1] != '.bstar':
                filename += '.bstar'
            self.filename = filename
        self.stream = ReadStream(data)

        self.magic = self.stream.read(4).decode('utf-8')
        assert self.magic == "STAR", f"Invalid file magic, expected 'STAR' but got '{self.magic}'"
        self.version = self.stream.read_u32()
        assert self.version == 1, f"Unsupported version, expected 1 but got {self.version}"
        self.count = self.stream.read_u32()

        self.entries = []
        for i in range (self.count):
            self.entries.append(self.stream.read_string())
    
    def Serialize(self, output_dir=''):
        with open(os.path.join(output_dir, self.filename), 'wb') as outfile:
            buffer = WriteStream(outfile)

            buffer.write(string(self.magic))
            buffer.write(u32(self.version))
            buffer.write(u32(len(self.entries)))
            for entry in self.entries:
                buffer.write(string(entry) + b'\x00')

    def ToJson(self, output_dir=''):
        with open(os.path.join(output_dir, self.filename) + ".json", 'w', encoding='utf-8') as outfile:
            json.dump({"Entries" : self.entries}, outfile, ensure_ascii=False, indent=4)
    
    def ToYaml(self, output_dir=''):
        with open(os.path.join(output_dir, self.filename) + ".yml", 'w', encoding='utf-8') as outfile:
            yaml.dump({"Entries" : self.entries}, outfile, sort_keys=False, allow_unicode=True, encoding='utf-8')

    def ToText(self, output_dir=''):
        with open(os.path.join(output_dir, self.filename) + ".txt", 'w', encoding='utf-8') as outfile:
            for entry in self.entries:
                print(entry, file=outfile)

    def ReplaceString(self, original, replacement):
        if type(original) == list and type(replacement) == list:
            if len(original) != len(replacement):
                raise ValueError("Replacement list must be the same length as the original")
            for entry in original:
               self.entries[self.entries.index(entry)] = replacement[self.entries.index(entry)]
        else:
            if type(new_string) != str:
                new_string = str(new_string)
            self.entries[self.entries.index(original)] = replacement

    def AddString(self, new_string):
        if type(new_string) == list:
            self.entries += new_string
        else:
            if type(new_string) != str:
                new_string = str(new_string)
            self.entries.append(new_string)

    def InsertString(self, position, new_string):
        if type(new_string) == list:
            self.entries[position:position] = new_string
        else:
            if type(new_string) != str:
                new_string = str(new_string)
            self.entries.insert(position, new_string)

    def RemoveString(self, old_string):
        if type(old_string) == list:
            for string in old_string:
                self.entries.remove(string)
        else:
            if type(old_string) != str:
                old_string = str(old_string)
            self.entries.remove(old_string)