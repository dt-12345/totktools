from utils import *
import os
import json
try:
    import yaml
except ImportError:
    raise ImportError("Would you be so kind as to LEARN TO FUCKING READ INSTRUCTIONS")

"""
Node Types:
HashArray(1-16)         = 0x20->0x2F
HashArrayWithRemap(1-16)= 0x30->0x3F
StringIndex             = 0xA0
BinaryData              = 0xA1
BinaryDataWithAlignment = 0xA2
Array                   = 0xC0
Dictionary              = 0xC1
StringTable             = 0xC2
DictionaryWithRemap     = 0xC4
RelocatedStringTable    = 0xC5
MonoTypedArray          = 0xC8
Bool                    = 0xD0
Int                     = 0xD1
Float                   = 0xD2
UInt                    = 0xD3
Long                    = 0xD4
ULong                   = 0xD5
Double                  = 0xD6
Null                    = 0xFF
"""

class Int(int):
    pass

class Float(float):
    pass

class UInt(int):
    pass

class Long(int):
    pass

class ULong(int):
    pass

class Double(float):
    pass

# From zeldamods byml-v2 library
def add_representers(dumper):
    yaml.add_representer(Int, lambda d, data: d.represent_int(data), Dumper=dumper)
    yaml.add_representer(Float, lambda d, data: d.represent_float(data), Dumper=dumper)
    yaml.add_representer(UInt, lambda d, data: d.represent_scalar(u'!u', str(data)), Dumper=dumper)
    yaml.add_representer(Long, lambda d, data: d.represent_scalar(u'!l', str(data)), Dumper=dumper)
    yaml.add_representer(ULong, lambda d, data: d.represent_scalar(u'!ul', str(data)), Dumper=dumper)
    yaml.add_representer(Double, lambda d, data: d.represent_scalar(u'!f64', str(data)), Dumper=dumper)

def add_constructors(loader):
    yaml.add_constructor(u'tag:yaml.org,2002:int', lambda l, node: Int(l.construct_yaml_int(node)), Loader=loader)
    yaml.add_constructor(u'tag:yaml.org,2002:float', lambda l, node: Float(l.construct_yaml_float(node)), Loader=loader)
    yaml.add_constructor(u'!u', lambda l, node: UInt(l.construct_yaml_int(node)), Loader=loader)
    yaml.add_constructor(u'!l', lambda l, node: Long(l.construct_yaml_int(node)), Loader=loader)
    yaml.add_constructor(u'!ul', lambda l, node: ULong(l.construct_yaml_int(node)), Loader=loader)
    yaml.add_constructor(u'!f64', lambda l, node: Double(l.construct_yaml_float(node)), Loader=loader)

class Byml:
    def __init__(self, data, filename=''):
        if type(data) != bytes:
            self.filename = os.path.basename(data)
            if os.path.splitext(self.filename)[1] in ['.yml', '.yaml']:
                with open(data, 'r', encoding='utf-8') as file:
                    loader = yaml.SafeLoader
                    add_constructors(loader)
                    self.root_node = yaml.load(file, Loader=loader)
                    self.magic = 'YB'
                    self.version = 7
                    return
            elif os.path.splitext(self.filename)[1] in ['.byml', '.byaml', '.bgyml']:
                with open(data, 'rb') as file:
                    data = file.read()
        else:
            self.filename = filename

        self.stream = ReadStream(data)

        self.magic = self.stream.read(2).decode('utf-8')
        if self.magic not in ['BY', 'YB']:
            raise ValueError(f"Invalid file magic, expected 'BY' or 'YB' but got {self.magic}")
        if self.magic == 'BY':
            self.bom = ">"
        elif self.magic == 'YB':
            self.bom = "<"
        self.version = self.stream.read_u16(self.bom)
        if self.version > 0x7:
            raise ValueError(f"Only versions <=7 are supported, got version {self.version}")
        self.key_table_offset = self.stream.read_u32(self.bom) # String table of key names
        self.string_table_offset = self.stream.read_u32(self.bom) # String table of string values
        self.root_node_offset = self.stream.read_u32(self.bom) # Root node must be a hash array, array, or dictionary

        self.stream.seek(self.key_table_offset)
        self.key_table = self.ParseNode()
        self.stream.seek(self.string_table_offset)
        self.string_table = self.ParseNode()
        if self.root_node_offset != 0:
            self.stream.seek(self.root_node_offset)
            self.root_node = self.ParseNode()
        else:
            self.root_node = {}

    def ToYaml(self):
        dumper = yaml.Dumper
        add_representers(dumper)
        with open(self.filename + '.yml', 'w') as file:
            yaml.dump(self.root_node, file, sort_keys=False, allow_unicode=True, Dumper=dumper)

    def ParseNode(self):
        node_info = self.GetContainerInfo()
        return self.GetValue(node_info)

    def GetContainerInfo(self):
        return (self.stream.read_u8(), self.stream.read_u24(self.bom))

    def GetValue(self, node_info):
        if node_info[0] <= 0x20 and node_info[0] >= 0x2f:
            return self.HashArray(node_info)
        elif node_info[0] <= 0x30 and node_info[0] >= 0x3f:
            return self.HashArrayWithRemap(node_info)
        elif node_info[0] == 0xa0:
            return self.StringIndex(node_info)
        elif node_info[0] == 0xa1:
            return self.BinaryData(node_info)
        elif node_info[0] == 0xa2:
            return self.BinaryDataWithAlignment(node_info)
        elif node_info[0] == 0xc0:
            return self.Array(node_info)
        elif node_info[0] == 0xc1:
            return self.Dictionary(node_info)
        elif node_info[0] == 0xc2:
            return self.StringTable(node_info)
        elif node_info[0] == 0xc4:
            return self.DictionaryWithRemap(node_info)
        elif node_info[0] == 0xc5:
            return self.MonoTypedArray(node_info)
        elif node_info[0] == 0xd0:
            return bool(self.stream.read_u32(self.bom))
        elif node_info[0] == 0xd1:
            return Int(self.stream.read_s32(self.bom))
        elif node_info[0] == 0xd2:
            return Float(self.stream.read_f32(self.bom))
        elif node_info[0] == 0xd3:
            return UInt(self.stream.read_u32(self.bom))
        elif node_info[0] == 0xd4:
            return Long(self.stream.read_s64(self.bom))
        elif node_info[0] == 0xd5:
            return ULong(self.stream.read_u64(self.bom))
        elif node_info[0] == 0xd6:
            return Double(self.stream.read_f64(self.bom))
        elif node_info[0] == 0xff:
            return
        else:
            raise ValueError(f"Invalid node type: {hex(node_info[0])}")
        
    def GetArrayValue(self, node_info):
        if node_info[0] < 0xa0 or node_info[0] in [0xc0, 0xc1, 0xc4, 0xc8]:
            pos = self.stream.tell() + 4
            self.stream.seek(self.stream.read_u32(self.bom))
            node = self.ParseNode()
            self.stream.seek(pos)
            return node
        elif node_info[0] in [0xa1, 0xa2, 0xd4, 0xd5, 0xd6]:
            pos = self.stream.tell() + 4
            self.stream.seek(self.stream.read_u32(self.bom))
            node = self.GetValue(node_info)
            self.stream.seek(pos)
            return node
        else:
            return self.GetValue(node_info)

    def HashArray(self, node_info):
        entry_size = (node_info[0] & 0xf) * 0x4 + 0x4
        pos = self.stream.tell()
        self.stream.skip(entry_size * node_info[1])
        types = []
        for i in range(node_info[1]):
            types.append(self.stream.read_u8())
        self.stream.seek(pos)
        entries = []
        for i in range(node_info[1]):
            entry = {}
            hash = ''
            for j in range(node_info[0] & 0xf):
                hash_part = self.stream.read(4).hex()
                while len(hash_part) != 8:
                    hash_part = '0' + hash_part
                hash += hash_part
            entry[hash] = self.GetArrayValue((types[i], 1))
            entries.append(entry)
        return entry

    # Unsupported
    def HashArrayWithRemap(self, node_info):
        pass

    def StringIndex(self, node_info):
        return self.string_table[self.stream.read_u32(self.bom)]

    def BinaryData(self, node_info):
        size = self.stream.read_u32(self.bom)
        return self.stream.read(size)
    
    def BinaryDataWithAlignment(self, node_info):
        size = self.stream.read_u32(self.bom)
        align = self.stream.read_u32(self.bom)
        while self.stream.tell() % align != 0:
            self.stream.read(1)
        return self.stream.read(size)

    def Array(self, node_info):
        types = []
        for i in range(node_info[1]):
            types.append(self.stream.read_u8())
        while self.stream.tell() % 4 != 0:
            self.stream.read(1)
        entries = []
        for i in range(node_info[1]):
            entries.append(self.GetArrayValue((types[i], 1)))
        return entries

    def Dictionary(self, node_info):
        entries = {}
        for i in range(node_info[1]):
            name_index = self.stream.read_u24(self.bom)
            node_type = self.stream.read_u8()
            entries[self.key_table[name_index]] = self.GetArrayValue((node_type, 1))
        return entries

    def StringTable(self, node_info):
        base_offsets = self.stream.tell() - 4
        offsets = []
        for i in range(node_info[1]):
            offsets.append(self.stream.read_u32(self.bom))
        strings = []
        for i in range(node_info[1]):
            self.stream.seek(base_offsets + offsets[i])
            strings.append(self.stream.read_string())
        return strings

    # Unsupported
    def DictionaryWithRemap(self, node_info):
        pass
    
    # Unsupported
    def RelocatedStringTable(self, node_info):
        pass

    def MonoTypedArray(self, node_info):
        array_type = self.stream.read_u8()
        self.stream.read(3)
        entries = []
        for i in range(node_info[1]):
            entries.append(self.GetArrayValue((array_type, 1)))
        return entries
    
def ExtractPtcl(path_to_esetb):
    filepath = path_to_esetb
    files = os.listdir(filepath)
    if not(os.path.exists('ptcl')):
        os.makedirs('ptcl')
    for file in files:
        print(file)
        byml = Byml(os.path.join(filepath, file))
        if 'PtclBin' in byml.root_node:
            with open('ptcl/' + os.path.splitext(byml.filename)[0] + '.ptcl', 'wb') as f:
                f.write(byml.root_node['PtclBin'])