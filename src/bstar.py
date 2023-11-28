from utils import *
import os
import json
try:
    import yaml
except ImportError:
    raise ImportError("Would you be so kind as to LEARN TO FUCKING READ INSTRUCTIONS")

class Bstar:
    # Takes in a filepath or raw bytes as input
    # If passing in raw bytes, please also provide a filename
    def __init__(self, data, filename=''):
        if type(data) != bytes:
            if os.path.splitext(data)[1] in ['.json', '.yml', '.yaml', '.txt']:
                self.filename = os.path.basename(os.path.splitext(data)[0])
            else:
                self.filename = os.path.basename(data)
            if os.path.splitext(data)[1] == '.bstar':
                with open(data, 'rb') as file:
                    data = file.read()
            elif os.path.splitext(data)[1] == '.json':
                with open(data, 'r') as file:
                    self.entries = json.load(file)["Entries"]
                    self.magic = "STAR"
                    self.version = 1
                    return
            elif os.path.splitext(data)[1] in ['.yaml', '.yml']:
                with open(data, 'r') as file:
                    self.entries = yaml.safe_load(file)["Entries"]
                    self.magic = "STAR"
                    self.version = 1
                    return
            else:
                with open(data, 'r') as file:
                    self.entries = []
                    for line in file:
                        self.entries.append(line.replace('\n', ''))
                    self.magic = "STAR"
                    self.version = 1
                    return
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
        return
    
    # Converts Bstar object into .bstar file
    def Serialize(self, output_dir=''):
        with open(os.path.join(output_dir, self.filename), 'wb') as outfile:
            buffer = WriteStream(outfile)

            buffer.write(string(self.magic))
            buffer.write(u32(self.version))
            buffer.write(u32(len(self.entries)))
            for entry in self.entries:
                buffer.write(string(entry) + b'\x00')

    # Converts Bstar object into .json file
    def ToJson(self, output_dir=''):
        with open(os.path.join(output_dir, self.filename) + ".json", 'w', encoding='utf-8') as outfile:
            json.dump({"Entries" : self.entries}, outfile, ensure_ascii=False, indent=4)
    
    # Converts Bstar object into .yml file
    def ToYaml(self, output_dir=''):
        with open(os.path.join(output_dir, self.filename) + ".yml", 'w', encoding='utf-8') as outfile:
            yaml.dump({"Entries" : self.entries}, outfile, sort_keys=False, allow_unicode=True, encoding='utf-8')

    # Converts Bstar object into .txt file
    def ToText(self, output_dir=''):
        with open(os.path.join(output_dir, self.filename) + ".txt", 'w', encoding='utf-8') as outfile:
            for entry in self.entries:
                print(entry, file=outfile)

    # Takes in a string(s) to replace and a replacement string(s) and replaces them
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

    # Appends the provided string(s) to the end of the file
    def AddString(self, new_string):
        if type(new_string) == list:
            self.entries += new_string
        else:
            if type(new_string) != str:
                new_string = str(new_string)
            self.entries.append(new_string)

    # Inserts the provided string(s) at the provided position
    def InsertString(self, position, new_string):
        if type(new_string) == list:
            self.entries[position:position] = new_string
        else:
            if type(new_string) != str:
                new_string = str(new_string)
            self.entries.insert(position, new_string)

    # Removes the specified string(s) from the file
    def RemoveString(self, old_string):
        if type(old_string) == list:
            for string in old_string:
                self.entries.remove(string)
        else:
            if type(old_string) != str:
                old_string = str(old_string)
            self.entries.remove(old_string)

    # Removes all strings from file
    def ClearFile(self):
        self.entries = []