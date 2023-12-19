from utils import *
from ruamel import yaml
import json
import os
import re

class Msbt:
    def __init__(self, filepath):
        self.filename = os.path.basename(filepath)
        with open(filepath, 'rb') as f:
            self.stream = ReadStream(f.read())

        self.magic = self.stream.read(8).decode('utf-8')
        assert self.magic == "MsgStdBn", f"Invalid file magic, expected 'MsgStdBn' but got '{self.magic}'"
        self.byte_order = self.stream.read_u16('>')
        if self.byte_order == 0xFEFF:
            self.bom = '>'
        elif self.byte_order == 0xFFFE:
            self.bom = '<'
        else:
            raise ValueError("Invalid byte order mark")
        self.stream.read(2)
        if self.stream.read_u8():
            self.encoding = 'utf-16-le' if self.byte_order == 0xFFFE else 'utf-16-be'
        else:
            self.encoding = 'utf-8'
        self.version = self.stream.read_u8()
        assert self.version == 3, f"Invalid version, expected v3 but got v{self.version}"
        self.section_count = self.stream.read_u32(self.bom)
        self.file_size = self.stream.read_u32(self.bom)
        self.stream.read(10) # padding

        self.messages = {}
        self.labels = []
        self.indices = []
        self.attributes = []
        self.text = []
        self.functions = []

        for i in range(self.section_count):
            magic, size = self.ReadHeader()
            match magic:
                case "LBL1":
                    self.ReadLabelSection(size)
                case "ATR1":
                    self.ReadAttributeSection(size)
                case "TXT2":
                    self.ReadTextSection(size)
                case _:
                    raise ValueError(f"Invalid section type: {magic}")
                
        for i in range(len(self.labels)):
            message = {}
            index = self.indices[i]
            attr = self.attributes[index] if index < len(self.attributes) else None
            text = self.text[index]
            funcs = re.findall("{{([0-9]+)}}", text)
            for func in funcs:
                text = text.replace("{{" + func + "}}", "{{" + f"{self.ParseFunction(self.functions[index][int(func)])}" + "}}")
            if attr != None:
                text = "<a>" + attr.hex() + "</a>" + text
            message[self.labels[i]] = text
            self.messages[index] = message
        self.messages = list(dict(sorted(self.messages.items())).values())

        self.output_dict = {
            "ByteOrder" : self.byte_order,
            "Version" : self.version,
            "Encoding" : "UTF-8" if self.encoding == 'utf-8' else "Unicode",
            "Data" : self.messages
        }

    def ToBytes(self, dest=''):
        with open(os.path.join(dest, self.filename), 'wb') as f:
            buffer = WriteStream(f)
            buffer.write("MsgStdBn".encode('utf-8'))
            buffer.write(u16(self.byte_order, ">"))
            buffer.write(u16(0))
            if self.encoding == 'utf-8':
                buffer.write(u8(0))
            else:
                buffer.write(u8(1))
            buffer.write(u8(self.version))
            buffer.write(u32(self.section_count, self.bom))
            buffer.skip(14) # write file size later
            if self.labels:
                buffer.write("LBL1".encode('utf-8'))
                buffer.skip(12) # write section size later
                start = buffer.tell()
                buffer.write(u32(len(self.labels), self.bom))
                for label in self.labels:
                    pass
                for label in self.labels:
                    buffer.write(u8(len(label)))
                    buffer.write(label.encode('utf-8'))
                    buffer.write(u32(self.indices[self.labels.index(label)], self.bom))

    def ToYaml(self, dest=''):
        file = yaml.YAML(typ='rt')
        with open(os.path.join(dest, self.filename.replace('.msbt', '.yml')), 'w', encoding='utf-8') as f:
            file.dump(self.output_dict, f)

    def ToJson(self, dest=''):
        with open(os.path.join(dest, self.filename.replace('.msbt', '.json')), 'w', encoding='utf-8') as f:
            json.dump(self.output_dict, f, indent=4, ensure_ascii=False)

    def ReadHeader(self):
        while self.stream.tell() % 16 != 0:
            self.stream.read(1)
        magic = self.stream.read(4).decode('utf-8')
        size = self.stream.read_u32(self.bom)
        self.stream.read(8) # padding
        return magic, size
    
    def ReadLabelSection(self, size):
        start = self.stream.tell()
        count = self.stream.read_u32(self.bom)
        entries = []
        for i in range(count):
            entry = {}
            entry["Label Count"] = self.stream.read_u32(self.bom)
            entry["Offset"] = self.stream.read_u32(self.bom)
            entries.append(entry)
        for entry in entries:
            self.stream.seek(start + entry["Offset"])
            for i in range(entry["Label Count"]):
                length = self.stream.read_u8()
                self.labels.append(self.stream.read(length).decode('utf-8'))
                self.indices.append(self.stream.read_u32(self.bom))
        self.stream.seek(start + size)

    def ReadAttributeSection(self, size):
        start = self.stream.tell()
        count = self.stream.read_u32(self.bom)
        atr_size = self.stream.read_u32(self.bom)
        for i in range(count):
            self.attributes.append(self.stream.read(atr_size))
        self.stream.seek(start + size)

    def ReadTextSection(self, size):
        start = self.stream.tell()
        count = self.stream.read_u32(self.bom)
        offsets = []
        for i in range(count):
            offsets.append(self.stream.read_u32(self.bom))
        for i in range(len(offsets)):
            self.stream.seek(start + offsets[i])
            if i < len(offsets) - 1:
                self.text.append(self.ParseText(start + offsets[i+1]))
            elif i == len(offsets) - 1:
                self.text.append(self.ParseText(start + size))
        self.stream.seek(start + size)
    
    def ParseText(self, end_pos):
        string = ''
        functions = []
        while self.stream.tell() < end_pos:
            char = self.stream.read(2) if self.encoding != 'utf-8' else self.stream.read(1)
            match int.from_bytes(char, 'little' if self.byte_order == 0xFFFE else 'big'):
                case 0x0E:
                    string += "{{" + f"{str(len(functions))}" + "}}"
                    func = {}
                    func["Group"] = self.stream.read_u16(self.bom)
                    func["Type"] = self.stream.read_u16(self.bom)
                    func["Args"] = self.stream.read(self.stream.read_u16(self.bom))
                    functions.append(func)
                case 0x0F:
                    string += "{{" + f"{str(len(functions))}" + "}}"
                    func = {}
                    func["Group"] = 0x0F
                    func["Type"] = 0x00
                    func["Args"] = self.stream.read(4)
                    functions.append(func)
                case _:
                    string += char.decode(self.encoding)
        self.functions.append(functions)
        return string[:-1]

    def ParseFunction(self, function):
        args = []
        arg_stream = ReadStream(function["Args"])
        match [function["Group"], function["Type"]]:
            case [0, 0]:
                name = "ruby"
                args += [{"charSpan" : arg_stream.read_u16(self.bom)},
                            {"value" : arg_stream.read().decode(self.encoding)[1:]}]
            case [0, 1]:
                name = "font"
                args.append({"face" : arg_stream.read().decode(self.encoding)})
            case [0, 2]:
                name = "size"
                args.append({"value" : arg_stream.read_u16(self.bom)})
            case [0, 3]:
                name = "color"
                # 0 = red (highlighting), 1 = blue-green, 2 = gray, 3 = red (tips), 4 = pale white-green, 5 = pink
                args.append({"id" : arg_stream.read_u16(self.bom)})
            case [0, 4]:
                name = "pageBreak"
            case [1, 0]:
                name = "delay"
                args.append({"frames" : arg_stream.read_u16(self.bom)})
            case [1, 3]:
                name = "playSound"
                args.append({"id" : arg_stream.read_u16(self.bom)})
            case [1, 4]:
                name = "icon"
                args.append({"id" : arg_stream.read_u8()})
            case [2, 2]:
                name = "number2"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 3]:
                name = "currentHorseName"
            case [2, 4]:
                name = "selectedHorseName"
            case [2, 7]:
                name = "cookingAdjective"
            case [2, 8]:
                name = "cookingEffectCaption"
            case [2, 9]:
                name = "number9"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 11]:
                name = "string11"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 12]:
                name = "string12"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 14]:
                name = "number14"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 15]:
                name = "number15"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 16]:
                name = "number16"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 18]:
                name = "shopTradePriceItem"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 19]:
                name = "time"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 20]:
                name = "coords"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 21]:
                name = "number21"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 22]:
                name = "number22"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 24]:
                name = "attachmentAdjective"
            case [2, 25]:
                name = "equipmentBaseName"
            case [2, 26]:
                name = "essenceAdjective"
            case [2, 27]:
                name = "essenceBaseName"
            case [2, 28]:
                name = "weaponName"
            case [2, 29]:
                name = "playerName"
            case [2, 30]:
                name = "questItemName"
            case [2, 31]:
                name = "shopSelectItemName"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 32]:
                name = "sensorTargetNameOnActorMode"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 33]:
                name = "shopSelectItemName"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 35]:
                name = "yonaDynamicName"
            case [2, 36]:
                name = "shopSelectItemName"
                args.append({"ref" : arg_stream.read().decode(self.encoding)})
            case [2, 37]:
                name = "recipeName"
            case [3, 0]:
                name = "resetAnim"
                args.append({"info" : function["Args"].hex()})
            case [3, 1]:
                name = "setItalicFont"
            case [4, 0]:
                name = "anim"
                args.append({"type" : arg_stream.read().decode(self.encoding)})
            case [5, 0]:
                name = "delay0"
            case [5, 1]:
                name = "delay1"
            case [5, 2]:
                name = "delay2"
            case [7, 0]:
                name = "extendVerticalSpace"
            case [15, 0]:
                name = "resetFontStyle"
            case [201, 0]:
                name = "wordInfo"
                args += [{"gender" : arg_stream.read_u8()},
                             {"defArticle" : arg_stream.read_u8()},
                             {"indefArticle" : arg_stream.read_u8()},
                             {"isPlural" : arg_stream.read_u8()}]
            case [201, 5]:
                name = "gender"
                args += [{"m" : self.ReadString(arg_stream, self.encoding)},
                             {"f" : self.ReadString(arg_stream, self.encoding)},
                             {"n" : self.ReadString(arg_stream, self.encoding)}]
            case [201, 6]:
                name = "pluralCase"
                args += [{"arg1" : self.ReadString(arg_stream, self.encoding)},
                             {"arg2" : self.ReadString(arg_stream, self.encoding)},
                             {"arg3" : self.ReadString(arg_stream, self.encoding)}]
            case [201, 8]:
                name = "gender8"
                args += [{"arg1" : self.ReadString(arg_stream, self.encoding)},
                             {"arg2" : self.ReadString(arg_stream, self.encoding)}]
            case [201, 10]:
                name = "nounCase"
                args += [{"nomSingle" : self.ReadString(arg_stream, self.encoding)},
                             {"genSingle" : self.ReadString(arg_stream, self.encoding)},
                             {"datSingle" : self.ReadString(arg_stream, self.encoding)},
                             {"accSingle" : self.ReadString(arg_stream, self.encoding)},
                             {"insSingle" : self.ReadString(arg_stream, self.encoding)},
                             {"prepSingle" : self.ReadString(arg_stream, self.encoding)},
                             {"nomPlural" : self.ReadString(arg_stream, self.encoding)},
                             {"genPlural" : self.ReadString(arg_stream, self.encoding)},
                             {"datPlural" : self.ReadString(arg_stream, self.encoding)},
                             {"accPlural" : self.ReadString(arg_stream, self.encoding)},
                             {"insPlural" : self.ReadString(arg_stream, self.encoding)},
                             {"prepPlural" : self.ReadString(arg_stream, self.encoding)}]
            case _:
                name = f"fun_{function['Group']}_{function['Type']}"
        func_string = name
        for arg in args:
            for arg1 in arg:
                func_string += " " + arg1 + "=" + str(arg[arg1])
        return func_string
    
    # not functional
    def GenerateLabelSection(self):
        labels = [k for entry in self.output_dict['Data'] for k in entry]
        label_groups = {}
        for label in labels:
            hash = self.CalcHash(label)
            if hash not in label_groups:
                label_groups[hash] = [label]
            else:
                label_groups[hash].append(label)
        print(len(label_groups))

    def SetEndianness(self, endianness):
        if endianness.lower() in ['le', 'little', 'little endian', 'little_endian', 'littleendian']:
            self.byte_order = 0xFFFE
            self.bom = '<'
        else:
            self.byte_order = 0xFEFF
            self.bom = '>'

    @staticmethod
    def ReadString(stream, encoding):
        string = ""
        if encoding == 'utf-8':
            char = stream.read(1)
            while char != b'\x00':
                string += char.decode(encoding)
                char = stream.read(1)
        else:
            char = stream.read(2)
            while char != b'\x00\x00':
                string += char.decode(encoding)
                char = stream.read(2)
        return string
    
    @staticmethod
    def CalcHash(label):
        hash = 0
        for char in label:
            hash = hash * 0x492 + ord(char)
        return (hash & 0xFFFFFFFF) % 101 # 101 groups is apparently the default