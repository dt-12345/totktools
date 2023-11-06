import zstandard as zs
import sarc
import os

class Zstd:
    def __init__(self, romfs_path):
        self.decompressor = zs.ZstdDecompressor()
        self.compressor = zs.ZstdCompressor()
        with open(os.path.join(romfs_path,"Pack/ZsDic.pack.zs"), 'rb') as file:
            data = file.read()
        self.dictionaries = self.decompressor.decompress(data)
        self.dictionaries = sarc.Sarc(self.dictionaries)
        self.dictionaries = self.dictionaries.files

    def DecompressFile(self, filepath, output_dir='', with_dict=False):
        if with_dict and os.path.basename(filepath) != 'ZsDic.pack.zs':
            if os.path.splitext(os.path.splitext(filepath)[0])[1] == '.pack':
                for dic in self.dictionaries:
                    if dic["Name"] == 'pack.zsdic':
                        dictionary = dic["Data"]
                        break
            elif os.path.splitext(os.path.splitext(filepath)[0])[1] == '.byml':
                if os.path.splitext(os.path.splitext(os.path.splitext(filepath)[0])[0])[1] == '.bcett':
                    for dic in self.dictionaries:
                        if dic["Name"] == 'bcett.byml.zsdic':
                            dictionary = dic["Data"]
                            break
            else:
                for dic in self.dictionaries:
                    if dic["Name"] == 'zs.zsdic':
                        dictionary = dic["Data"]
                        break
            self.decompressor = zs.ZstdDecompressor(zs.ZstdCompressionDict(dictionary))
        with open(filepath, 'rb') as file:
            data = file.read()
        if os.path.splitext(filepath)[1] in ['.zs', '.zstd']:
            filepath = os.path.splitext(filepath)[0]
        else:
            return
        with open(os.path.join(output_dir, os.path.basename(filepath)), 'wb') as file:
            file.write(self.decompressor.decompress(data))

    def Decompress(self, filepath, output_dir='', with_dict=False):
        if os.path.isfile(filepath):
            self.DecompressFile(filepath, output_dir, with_dict)
        elif os.path.isdir(filepath):
            for root_dir, dir, files in os.walk(filepath):
                for file in files:
                    if os.path.isfile(os.path.join(root_dir, file)):
                        rel_path = os.path.relpath(root_dir, filepath)
                        if not(os.path.exists(os.path.join(output_dir, rel_path))):
                            os.makedirs(os.path.join(output_dir, rel_path))
                        self.DecompressFile(os.path.join(root_dir, file), os.path.join(output_dir, rel_path), with_dict)
    
    def CompressFile(self, filepath, output_dir='', level=16, with_dict=False):
        if with_dict and os.path.basename(filepath) != 'ZsDic.pack.zs':
            if os.path.splitext(os.path.splitext(filepath)[0])[1] == '.pack':
                for dic in self.dictionaries:
                    if dic["Name"] == 'pack.zsdic':
                        dictionary = dic["Data"]
                        break
            elif os.path.splitext(os.path.splitext(filepath)[0])[1] == '.byml':
                if os.path.splitext(os.path.splitext(os.path.splitext(filepath)[0])[0])[1] == '.bcett':
                    for dic in self.dictionaries:
                        if dic["Name"] == 'bcett.byml.zsdic':
                            dictionary = dic["Data"]
                            break
            else:
                for dic in self.dictionaries:
                    if dic["Name"] == 'zs.zsdic':
                        dictionary = dic["Data"]
                        break
            self.compressor = zs.ZstdCompressor(level, zs.ZstdCompressionDict(dictionary))
        with open(filepath, 'rb') as file:
            data = file.read()
        filepath += '.zs'
        with open(os.path.join(output_dir, os.path.basename(filepath)), 'wb') as file:
            file.write(self.compressor.compress(data))
    
    def Compress(self, filepath, output_dir='', level=16, with_dict=False):
        if os.path.isfile(filepath):
            self.CompressFile(filepath, output_dir, level, with_dict)
        elif os.path.isdir(filepath):
            for root_dir, dir, files in os.walk(filepath):
                for file in files:
                    if os.path.isfile(os.path.join(root_dir, file)):
                        rel_path = os.path.relpath(root_dir, filepath)
                        if not(os.path.exists(os.path.join(output_dir, rel_path))):
                            os.makedirs(os.path.join(output_dir, rel_path))
                        self.CompressFile(os.path.join(root_dir, file), os.path.join(output_dir, rel_path), level, with_dict)