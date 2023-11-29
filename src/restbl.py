from utils import *
import zstd
try:
    import zstandard as zs
    import yaml
except ImportError:
    raise ImportError("Would you be so kind as to LEARN TO FUCKING READ INSTRUCTIONS")
import sarc
import os
import binascii
import json
import sys
from hashlib import sha256

# For pyinstaller relative paths
def get_correct_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class Restbl:
    def __init__(self, filepath): # Accepts both compressed and decompressed files
        if os.path.splitext(filepath)[1] in ['.zs', '.zstd']:
            decompressor = zs.ZstdDecompressor()
            with open(filepath, 'rb') as f:
                compressed = f.read()
                data = decompressor.decompress(compressed)
                filepath = os.path.splitext(filepath)[0]
        else:
            with open(filepath, 'rb') as f:
                data = f.read()
        
        self.stream = ReadStream(data)
        self.filename = os.path.basename(filepath)
        self.game_version = os.path.splitext(os.path.splitext(filepath)[0])[1][1:]
        self.hashmap = {}

        self.magic = self.stream.read(6).decode('utf-8')
        assert self.magic == "RESTBL", f"Invalid file magic, expected 'RESTBL' but got '{self.magic}'"
        self.version = self.stream.read_u32()
        assert self.version == 1, f"Invalid version, expected v1 but got v{self.version}"
        self.string_size = self.stream.read_u32()
        self.hash_count = self.stream.read_u32()
        self.collision_count = self.stream.read_u32()

        self.hash_table = {}
        self.collision_table = {}

        for i in range(self.hash_count):
            self.ReadHashEntry()
        
        for i in range(self.collision_count):
            self.ReadCollisionEntry()
    
    def ReadHashEntry(self):
        hash = self.stream.read_u32()
        self.hash_table[hash] = self.stream.read_u32()
        return
    
    def ReadCollisionEntry(self):
        filepath = self.stream.read_string()
        if len(filepath) > self.string_size:
            raise ValueError("Collision table filepath string was too large")
        self.stream.read(self.string_size - len(filepath) - 1)
        self.collision_table[filepath] = self.stream.read_u32()
        return

    def Reserialize(self, output_dir=''):
        if os.path.exists(output_dir):
            os.makedirs(output_dir)
        with open(os.path.join(output_dir, self.filename), 'wb') as outfile:
            self.buffer = WriteStream(outfile)
            self.buffer.write("RESTBL".encode('utf-8'))
            self.buffer.write(u32(self.version))
            self.buffer.write(u32(self.string_size))
            self.buffer.write(u32(len(self.hash_table)))
            self.buffer.write(u32(len(self.collision_table)))
            # Hash table is sorted by hash for fast lookup
            self.hash_table = dict(sorted(self.hash_table.items()))
            # Collision table is sorted by name for fast lookup
            self.collision_table = dict(sorted(self.collision_table.items()))
            for hash in self.hash_table:
                self.buffer.write(u32(hash))
                self.buffer.write(u32(self.hash_table[hash]))
            for name in self.collision_table:
                string = name.encode('utf-8')
                while len(string) != self.string_size:
                    string += b'\x00'
                self.buffer.write(string)
                self.buffer.write(u32(self.collision_table[name]))

    def AddEntry(self, path, size):
        hash = binascii.crc32(path.encode('utf-8'))
        if hash not in self.hash_table:
            self.hash_table[hash] = size
        else:
            self.collision_table[path] = size
    
    def DeleteEntry(self, path):
        hash = binascii.crc32(path.encode('utf-8'))
        if path in self.collision_table:
            del self.collision_table[path]
        elif hash in self.hash_table:
            del self.hash_table[hash]
        else:
            raise ValueError("Entry not found")
        
    def AddByHash(self, hash, size):
        self.hash_table[hash] = size
    
    def DeleteByHash(self, hash):
        try:
            del self.hash_table[hash]
        except KeyError:
            raise KeyError("Entry not found")
    
    # Generates mapping of CRC32 hashes to filepaths
    def _GenerateHashmap(self, paths=[]):
        if paths == []:
            version = os.path.splitext(os.path.splitext(os.path.basename(self.filename))[0])[1]
            string_list = "string_lists/" + version.replace('.', '') + ".txt"
            string_list = get_correct_path(string_list)
            paths = []
            with open(string_list, 'r') as strings:
                for line in strings:
                    paths.append(line[:-1])
        for path in paths:
            if path not in self.collision_table:
                self.hashmap[binascii.crc32(path.encode('utf-8'))] = path
        return self.hashmap

    # Returns all modified entries
    def _DictCompareChanges(self, edited, original):
        return {k: edited[k] for k in edited if k in original and edited[k] != original[k]}
    
    # Returns all entries not present in the modified version
    def _DictCompareDeletions(self, edited, original):
        return {k: original[k] for k in original if k not in edited}
    
    # Returns all entries only present in the modified version
    def _DictCompareAdditions(self, edited, original):
        return {k: edited[k] for k in edited if k not in original}

    # Merges the changes to the hash table and collision table into one dictionary
    # Function should be one of the DictCompare functions above
    def _GetCombinedChanges(self, original, function):
        changes_hash = function(self.hash_table, original["Hash Table"])
        changes_collision = function(self.collision_table, original["Collision Table"])
        changes = {}
        for hash in changes_hash:
            string = self._TryGetPath(hash, self.hashmap)
            changes[string] = changes_hash[hash]
        changes = changes | changes_collision
        return changes

    # Attempts to get the filepath from the hash and returns the hash if not found
    def _TryGetPath(self, hash, hashmap):
        if hash in hashmap:
            return hashmap[hash]
        else:
            return hash

    # Changelog comparing to the vanilla file
    def GenerateChangelog(self):
        original_filepath = "restbl/ResourceSizeTable.Product." + self.game_version + ".rsizetable.json"
        original_filepath = get_correct_path(original_filepath)
        with open(original_filepath, 'r') as file:
            original = json.load(file, object_pairs_hook=lambda d: {int(k) if k.isdigit() else k: v for k, v in d})
        changes = self._GetCombinedChanges(original, self._DictCompareChanges)
        additions = self._GetCombinedChanges(original, self._DictCompareAdditions)
        deletions = self._GetCombinedChanges(original, self._DictCompareDeletions)
        changelog = {"Changes" : changes, "Additions" : additions, "Deletions" : deletions}
        return changelog

    # RCL files for NX-Editor
    def GenerateRcl(self, filename=''):
        changelog = self.GenerateChangelog()
        if self.hashmap == {}:
            self._GenerateHashmap()
        if filename == "":
            filename = "changes.rcl"
        with open(filename, 'w') as rcl:
            for change in changelog["Changes"]:
                string = self._TryGetPath(change, self.hashmap)
                if type(string) == int:
                    string = hex(string)
                string = str(string)
                rcl.write('* ' + string + ' = ' + str(changelog["Changes"][change]) + '\n')
            for change in changelog["Additions"]:
                string = self._TryGetPath(change, self.hashmap)
                if type(string) == int:
                    string = hex(string)
                string = str(string)
                rcl.write('+ ' + string + ' = ' + str(changelog["Additions"][change]) + '\n')
            for change in changelog["Deletions"]:
                string = self._TryGetPath(change, self.hashmap)
                if type(string) == int:
                    string = hex(string)
                string = str(string)
                rcl.write('- ' + string + '\n')

    # Necessary to apply RCL files as patches
    def GenerateChangelogFromRcl(self, rcl_path):
        changelog = {"Changes" : {}, "Additions" : {}, "Deletions" : {}}
        with open(rcl_path, 'r') as rcl:
            for line in rcl:
                entry = line.split(" = ")
                match line[0]:
                    case "*":
                        changelog["Changes"][entry[0].lstrip("*+- ").rstrip("= ")] = int(entry[1])
                    case "+":
                        changelog["Additions"][entry[0].lstrip("*+- ").rstrip("= ")] = int(entry[1])
                    case "-":
                        changelog["Deletions"][entry[0].lstrip("*+- ").rstrip("= ")] = 0
        return changelog

    def GenerateYamlPatch(self, filename=''):
        changelog = self.GenerateChangelog()
        if filename == "":
            filename = "changes.yml"
        if self.hashmap == {}:
            self._GenerateHashmap()
        patch = {}
        for change in changelog["Changes"]:
            patch[self._TryGetPath(change, self.hashmap)] = changelog["Changes"][change]
        for addition in changelog["Additions"]:
            patch[self._TryGetPath(addition, self.hashmap)] = changelog["Additions"][addition]
        for deletion in changelog["Deletions"]:
            patch[self._TryGetPath(deletion, self.hashmap)] = 0
        with open(filename, 'w') as yaml_patch:
            yaml.dump(patch, yaml_patch, allow_unicode=True, encoding='utf-8', sort_keys=True)
    
    # Necessary to apply YAML patches
    # YAML patches don't appear to support entry deletion
    def GenerateChangelogFromYaml(self, yaml_path):
        changelog = {"Changes" : {}, "Additions" : {}, "Deletions" : {}}
        with open(yaml_path, 'r') as yml:
            patch = yaml.safe_load(yml)
        original_filepath = "restbl/ResourceSizeTable.Product." + self.game_version + ".rsizetable.json"
        original_filepath = get_correct_path(original_filepath)
        with open(original_filepath, 'r') as file:
            original = json.load(file, object_pairs_hook=lambda d: {int(k) if k.isdigit() else k: v for k, v in d})
        for change in patch:
            hash = binascii.crc32(change.encode('utf-8'))
            if hash in original["Hash Table"] or change in original["Collision Table"]:
                changelog["Changes"][change] = patch[change]
            else:
                changelog["Additions"][change] = patch[change]
        return changelog
    
    # Requires a single changelog (merge them first with MergeChangelogs)
    def ApplyChangelog(self, changelog):
        # Check if in collision table, then check if it's a hash, then check if the hash exists, otherwise add
        for change in changelog["Changes"]:
            if change in self.collision_table:
                self.collision_table[change] = changelog["Changes"][change]
            elif change in self.hash_table:
                self.hash_table[change] = changelog["Changes"][change]
            elif type(change) == str:
                if binascii.crc32(change.encode('utf-8')) in self.hash_table:
                    self.hash_table[binascii.crc32(change.encode('utf-8'))] = changelog["Changes"][change]
                else:
                    print(f"{change} was added as it was not an entry in the provided RESTBL")
                    self.hash_table[binascii.crc32(change.encode('utf-8'))] = changelog["Changes"][change]
            else:
                self.hash_table[change] = changelog["Changes"][change]
        for addition in changelog["Additions"]:
            if type(addition) == str:
                hash = binascii.crc32(addition.encode('utf-8'))
            else:
                hash = addition
            # No way to resolve hash collisions for new files if only the hash is known
            if hash not in self.hash_table or type(addition) == int:
                self.hash_table[hash] = changelog["Additions"][addition]
            else:
                self.collision_table[addition] = changelog["Additions"][addition]
        for deletion in changelog["Deletions"]:
            if deletion in self.collision_table:
                del self.collision_table[deletion]
            elif deletion in self.hash_table:
                del self.hash_table[deletion]
            else:
                if type(deletion) == str:
                    if binascii.crc32(deletion.encode('utf-8')) in self.hash_table:
                        del self.hash_table[binascii.crc32(deletion.encode('utf-8'))]
                else:
                    if deletion in self.hash_table:
                        del self.hash_table[deletion]
    
    def ApplyRcl(self, rcl_path):
        changelog = self.GenerateChangelogFromRcl(rcl_path)
        self.ApplyChangelog(changelog)
    
    def ApplyYamlPatch(self, yaml_path):
        changelog = self.GenerateChangelogFromYaml(yaml_path)
        self.ApplyChangelog(changelog)
    
    # Merges RCL/YAML patches in a single directory into one changelog
    def MergePatches(self, patches_folder):
        patches = [file for file in os.listdir(patches_folder) if os.path.splitext(file)[1] in ['.rcl', '.yml', '.yaml']]
        changelogs = []
        for patch in patches:
            if os.path.splitext(patch) in ['.yml', '.yaml']:
                changelogs.append(self.GenerateChangelogFromYaml(os.path.join(patches_folder, patch)))
            else:
                changelogs.append(self.GenerateChangelogFromRcl(os.path.join(patches_folder, patch)))
        changelog = {"Changes" : {}, "Additions" : {}, "Deletions" : {}}
        for log in changelogs:
            for change in log["Changes"]:
                if change not in changelog["Changes"]:
                    changelog["Changes"][change] = log["Changes"][change]
                else:
                    changelog["Changes"][change] = max(changelog["Changes"][change], log["Changes"][change])
            for addition in log["Additions"]:
                if addition not in changelog["Additions"]:
                    changelog["Additions"][addition] = log["Additions"][addition]
                else:
                    changelog["Additions"][addition] = max(changelog["Additions"][addition], log["Additions"][addition])
            for deletion in log["Deletions"]:
                if deletion not in changelog["Deletions"]:
                    changelog["Deletions"][deletion] = log["Deletions"][deletion]
        return changelog

    # Changelog from analyzing mod directory
    def GenerateChangelogFromMod(self, mod_path, dump_path='', checksum=False):
        if checksum:
            info = GetInfoWithChecksum(mod_path + '/romfs', dump_path, self.game_version)
        else:
            info = GetInfo(mod_path + '/romfs', dump_path)
        changelog = {"Changes" : {}, "Additions" : {}, "Deletions" : {}}
        if self.hashmap == {}:
            self._GenerateHashmap()
        strings = list(self.hashmap.values())
        with open(get_correct_path('restbl/ResourceSizeTable.Product.' + self.game_version + '.rsizetable.json'), 'r') as f:
            defaults = json.load(f, object_pairs_hook=lambda d: {int(k) if k.isdigit() else k: v for k, v in d})
        for file in info:
            if os.path.splitext(file)[1] not in ['.bwav', '.rsizetable'] and os.path.splitext(file)[0] != r"Pack\ZsDic":
                if type(file) == str:
                    hash = binascii.crc32(file.encode())
                else:
                    hash = file
                add = False
                if checksum:
                    # Only overwrite if the entry is larger than the original entry
                    # This is mostly in case the mod contains multiple copies of a file in a pack of differing sizes
                    if file in defaults["Collision Table"]:
                        if info[file] > defaults["Collision Table"][file]:
                            add = True
                    elif hash in defaults["Hash Table"]:
                        if info[file] > defaults["Hash Table"][hash]:
                            add = True
                    else:
                        add = True
                else:
                    add = True
                if add:
                    if file in strings:
                        changelog["Changes"][file] = info[file]
                    elif file in self.collision_table:
                        changelog["Changes"][file] = info[file]
                    else:
                        changelog["Additions"][file] = info[file]
        changelog = dict(sorted(changelog.items()))
        return changelog
    
    # Same as above but for multiple mods
    def GenerateChangelogFromModDirectory(self, mod_path, dump_path='', delete=False, smart_analysis=True, checksum=False):
        changelogs = []
        mods = [mod for mod in os.listdir(mod_path) if os.path.isdir(os.path.join(mod_path, mod))]
        for mod in mods:
            restbl_path = os.path.join(mod_path, mod, 'romfs/System/Resource/ResourceSizeTable.Product.' + self.game_version + '.rsizetable.zs')
            if smart_analysis:
                if os.path.exists(restbl_path):
                    print(f"Found RESTBL: {restbl_path}")
                    restbl = Restbl(restbl_path)
                    changelogs.append(restbl.GenerateChangelog())
                else:
                    print(f"Did not find RESTBL in {mod}")
                    changelogs.append(self.GenerateChangelogFromMod(os.path.join(mod_path, mod), dump_path, checksum))
            else:
                changelogs.append(self.GenerateChangelogFromMod(os.path.join(mod_path, mod), dump_path, checksum))
            if delete:
                try:
                    os.remove(restbl_path)
                    print(f"Removed {restbl_path}")
                except FileNotFoundError:
                    pass
        return MergeChangelogs(changelogs)
    
    # Loads the vanilla RESTBL values into the object
    def LoadDefaults(self):
        with open(get_correct_path('restbl/ResourceSizeTable.Product.' + self.game_version + '.rsizetable.json'), 'r') as f:
            data = json.load(f, object_pairs_hook=lambda d: {int(k) if k.isdigit() else k: v for k, v in d})
        self.hash_table = data["Hash Table"]
        self.collision_table = data["Collision Table"]

# List of all files in a directory
def GetStringList(romfs_path, dump_path=''):
    paths = []
    if dump_path == '':
        dump_path = romfs_path
    zs = zstd.Zstd(dump_path)
    for dir,subdir,files in os.walk(romfs_path):
        for file in files:
            full_path = os.path.join(dir, file)
            filepath = full_path
            if os.path.isfile(filepath):
                filepath = os.path.join(os.path.relpath(dir, romfs_path), os.path.basename(filepath))
                if os.path.splitext(filepath)[1] in ['.zs', '.zstd', '.mc']:
                    filepath = os.path.splitext(filepath)[0]
                if os.path.splitext(filepath)[1] not in ['.bwav', '.rsizetable', '.rcl'] and os.path.splitext(filepath)[0] != r"Pack\ZsDic":
                    filepath = filepath.replace('\\', '/')
                    paths.append(filepath)
                    print(filepath)
                    if os.path.splitext(filepath)[1] == '.pack':
                        archive = sarc.Sarc(zs.Decompress(full_path, no_output=True))
                        paths += archive.ListFiles()
    paths = list(set(paths))
    paths.sort()
    return paths

# List of list of files for each mod in a directory
def GetFileLists(mod_path, dump_path=''):
    if dump_path == '':
        dump_path = mod_path
    mods = [mod for mod in os.listdir(mod_path) if os.path.isdir(os.path.join(mod_path, mod))]
    files = {}
    for mod in mods:
        if os.path.exists(os.path.join(mod_path, mod) + "/romfs"):
            files[mod] = GetStringList(os.path.join(mod_path, mod) + "/romfs", dump_path)
    return files

# Same as above but stores the estimated entry size as well
def GetInfo(romfs_path, dump_path=''):
    info = {}
    if dump_path == '':
        dump_path = romfs_path
    zs = zstd.Zstd(dump_path)
    for dir,subdir,files in os.walk(romfs_path):
        for file in files:
            full_path = os.path.join(dir, file)
            filepath = full_path
            if os.path.isfile(filepath):
                filepath = os.path.join(os.path.relpath(dir, romfs_path), os.path.basename(filepath))
                if os.path.splitext(filepath)[1] in ['.zs', '.zstd', '.mc']:
                    filepath = os.path.splitext(filepath)[0]
                if os.path.splitext(filepath)[1] not in ['.bwav', '.rsizetable', '.rcl'] and os.path.splitext(filepath)[0] != r"Pack\ZsDic":
                    filepath = filepath.replace('\\', '/')
                    info[filepath] = CalcSize(full_path, dump_path)
                    print(filepath)
                    if os.path.splitext(filepath)[1] == '.pack':
                        archive = sarc.Sarc(zs.Decompress(full_path, no_output=True))
                        archive_info = archive.ListFileInfo()
                        for f in archive_info:
                            size = CalcSize(f, dump_path, archive_info[f])
                            if f not in info:
                                info[f] = size
                            else:
                                info[f] = max(info[f], size)
    info = dict(sorted(info.items()))
    return info

# Same as GetInfo but does a checksum comparison first to see if the file has been modified
def GetInfoWithChecksum(romfs_path, dump_path='', version=121):
    info = {}
    if dump_path == '':
        dump_path = romfs_path
    zs = zstd.Zstd(dump_path)
    with open(get_correct_path('checksums/TearsOfTheKingdom' + str(version).replace('.', '') + '.json'), 'r') as f:
        checksums = json.load(f)
    for dir,subdir,files in os.walk(romfs_path):
        for file in files:
            full_path = os.path.join(dir, file)
            filepath = full_path
            checksum = CalcFileChecksum(full_path)
            if os.path.isfile(filepath):
                filepath = os.path.join(os.path.relpath(dir, romfs_path), os.path.basename(filepath))
                if os.path.splitext(filepath)[1] in ['.zs', '.zstd', '.mc']:
                    filepath = os.path.splitext(filepath)[0]
                if os.path.splitext(filepath)[1] not in ['.bwav', '.rsizetable', '.rcl'] and os.path.splitext(filepath)[0] != r"Pack\ZsDic":
                    filepath = filepath.replace('\\', '/')
                    add = False
                    if filepath in checksums:
                        if checksum != checksums[filepath]:
                            add = True
                    else:
                        add = True
                    if add:
                        info[filepath] = CalcSize(full_path, dump_path)
                        print(filepath)
                        if os.path.splitext(filepath)[1] == '.pack':
                            archive = sarc.Sarc(zs.Decompress(full_path, no_output=True))
                            archive_info = archive.files
                            for f in archive_info:
                                cs = sha256(f["Data"]).hexdigest()
                                add = False
                                if f["Name"] in checksums:
                                    if cs != checksums[f["Name"]]:
                                        add = True
                                else:
                                    add = True
                                if add:
                                    size = CalcSize(f["Name"], dump_path, len(f["Data"]))
                                    if f["Name"] not in info:
                                        info[f["Name"]] = size
                                    else:
                                        info[f["Name"]] = max(info[f["Name"]], size)
    info = dict(sorted(info.items()))
    return info

# Same as above but for multiple mods
def GetInfoList(mod_path, dump_path=''):
    if dump_path == '':
        dump_path = mod_path
    mods = [mod for mod in os.listdir(mod_path) if os.path.isdir(os.path.join(mod_path, mod))]
    files = {}
    for mod in mods:
        files[mod] = GetInfo(os.path.join(mod_path, mod) + "/romfs", dump_path)
    return files

# Returns a SHA-256 hash of file
def CalcFileChecksum(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    return sha256(data).hexdigest()

# These are estimates, would be nice to have more precise values
def CalcSize(file, romfs_path, size=None):
    if size == None:
        size = os.path.getsize(file)
    decompressor = zstd.Zstd(romfs_path)
    if os.path.splitext(file)[1] in ['.zs', '.zstd']:
        size = decompressor.GetDecompressedSize(file)
        file = os.path.splitext(file)[0]
    elif os.path.splitext(file)[1] in ['.mc']:
        size = os.path.getsize(file) * 5 # MC decompressor wasn't working so this is an estimate of the decompressed size
        file = os.path.splitext(file)[0]
    if os.path.splitext(file)[1] == '.txtg':
        return size + 5000
    elif os.path.splitext(file)[1] == '.bgyml':
        return (size + 1000) * 8
    else:
        return (size + 1500) * 4

# Merges list of changelogs into one (doesn't accept RCL or YAML)
def MergeChangelogs(changelogs):
    changelog = {"Changes" : {}, "Additions" : {}, "Deletions" : {}}
    for log in changelogs:
        for change in log["Changes"]:
            if change not in changelog["Changes"]:
                changelog["Changes"][change] = log["Changes"][change]
            else:
                changelog["Changes"][change] = max(changelog["Changes"][change], log["Changes"][change])
        for addition in log["Additions"]:
            if addition not in changelog["Additions"]:
                changelog["Additions"][addition] = log["Additions"][addition]
            else:
                changelog["Additions"][addition] = max(changelog["Additions"][addition], log["Additions"][addition])
        for deletion in log["Deletions"]:
            if deletion not in changelog["Deletions"]:
                changelog["Deletions"][deletion] = log["Deletions"][deletion]
    changelog = dict(sorted(changelog.items()))
    return changelog

# Analyzes a directory of mods, generates a combined changelog, and generates a RESTBL from it
def MergeMods(mod_path, romfs_path, restbl_path='', version=121, compressed=True, delete=False, smart_analysis=True, checksum=False):
    if not(os.path.exists(restbl_path)):
        print("Creating empty resource size table...")
        filename = os.path.join(restbl_path, 'ResourceSizeTable.Product.' + str(version).replace('.', '') + '.rsizetable')
        with open(filename, 'wb') as file:
            buffer = WriteStream(file)
            buffer.write("RESTBL".encode('utf-8'))
            buffer.write(u32(1))
            buffer.write(u32(0xA0))
            buffer.write(u32(0))
            buffer.write(u32(0))
        restbl = Restbl(filename)
        restbl.LoadDefaults()
    else:
        restbl = Restbl(restbl_path)
    print("Generating changelogs...")
    changelog = restbl.GenerateChangelogFromModDirectory(mod_path, romfs_path, delete, smart_analysis, checksum)
    with open('test.json', 'w') as f:
        json.dump(changelog, f, indent=4)
    print("Applying changes...")
    restbl.ApplyChangelog(changelog)
    restbl.Reserialize()
    if compressed:
        with open(restbl.filename, 'rb') as file:
            data = file.read()
        if os.path.exists(restbl.filename + '.zs'):
            os.remove(restbl.filename + '.zs')
        os.rename(restbl.filename, restbl.filename + '.zs')
        with open(restbl.filename + '.zs', 'wb') as file:
            compressor = zs.ZstdCompressor()
            file.write(compressor.compress(data))
    print("Finished")

# Simple GUI, nothing special
import PySimpleGUI as sg
from tkinter import filedialog as fd
def open_tool():
    sg.theme('Black')
    event, values = sg.Window('RESTBL Tool',
                              [[sg.Text('Options:'), sg.Checkbox(default=True, text='Compress', size=(8,5), key='compressed'),
                                sg.Checkbox(default=True, text='Use Existing RESTBL', size=(17,5), key='smart_analyze'),
                                sg.Checkbox(default=False, text='Delete Existing RESTBL', size=(19,5), key='delete'),
                                sg.Checkbox(default=True, text='Use Checksums', size=(12,5), key='checksum')],
                               [sg.Button('Generate RESTBL from Mod(s)'), sg.Button('Select RESTBL to Merge'), sg.Button('Generate Changelog'),
                                sg.Button('Apply Patches'), sg.Button('Exit')]]).read(close=True)
    
    match event:
        case 'Generate RESTBL from Mod(s)':
            mod_path, romfs_path, restbl_path, version = merge_mods()
            MergeMods(mod_path, romfs_path, restbl_path, version, values['compressed'], values['delete'], values['smart_analyze'], values['checksum'])
        case 'Select RESTBL to Merge':
            changelog0, changelog1, restbl = merge_restbl()
            print("Calculating merged changelog...")
            changelog = MergeChangelogs([changelog0, changelog1])
            print("Applying changes...")
            restbl.ApplyChangelog(changelog)
            restbl.Reserialize()
            if values['compressed']:
                with open(restbl.filename, 'rb') as file:
                    data = file.read()
                if os.path.exists(restbl.filename + '.zs'):
                    os.remove(restbl.filename + '.zs')
                os.rename(restbl.filename, restbl.filename + '.zs')
                with open(restbl.filename + '.zs', 'wb') as file:
                    compressor = zs.ZstdCompressor()
                    file.write(compressor.compress(data))
            print("Finished")
        case 'Generate Changelog':
            gen_changelog()
        case 'Apply Patches':
            apply_patches(values['compressed'])
        case 'Exit':
            sys.exit()
    
    open_tool()

# Gets the necessary filepaths and version info for MergeMods()
def merge_mods():
    mod_path = fd.askdirectory(title="Select Directory Containing Mods to Merge")
    romfs_path = fd.askdirectory(title="Select RomFS Dump")
    event, value = sg.Window('Options', [[sg.Button('Add Base RESTBL File'), sg.Button('Create Base RESTBL File')]]).read(close=True)
    if event == 'Add Base RESTBL File':
        restbl_path = fd.askopenfilename(title="Select RESTBL File", filetypes=[('RESTBL Files', '.rsizetable'),
                                                                            ('RESTBL Files', '.rsizetable.zs')])
        version = 121
    else:
        restbl_path = ''
        event, value = sg.Window('Select Version', [[sg.Button('1.0.0'), sg.Button('1.1.0'), sg.Button('1.1.1'),
                                                     sg.Button('1.1.2'), sg.Button('1.2.0'), sg.Button('1.2.1')]]).read(close=True)
        version = int(event.replace('.', ''))

    return mod_path, romfs_path, restbl_path, version

# Generates changelogs for the two RESTBL files to merge
def merge_restbl():
    restbl_path0 = fd.askopenfilename(title="Select RESTBL File 1", filetypes=[('RESTBL Files', '.rsizetable'),
                                                                           ('RESTBL Files', '.rsizetable.zs')])
    restbl0 = Restbl(restbl_path0)
    restbl_path1 = fd.askopenfilename(title="Select RESTBL File 2", filetypes=[('RESTBL Files', '.rsizetable'),
                                                                           ('RESTBL Files', '.rsizetable.zs')])
    restbl1 = Restbl(restbl_path1)
    return restbl0.GenerateChangelog(), restbl1.GenerateChangelog(), restbl0

# Generates a changelog in the specified format
def gen_changelog():
    restbl_path = fd.askopenfilename(title="Select RESTBL File", filetypes=[('RESTBL Files', '.rsizetable'),
                                                                           ('RESTBL Files', '.rsizetable.zs')])
    event, value = sg.Window('Select Format', [[sg.Button('JSON Changelog'), sg.Button('RCL'), sg.Button('YAML Patch')]]).read(close=True)
    restbl = Restbl(restbl_path)
    print("Generating changelog...")
    match event:
        case 'JSON Changelog':
            changelog = restbl.GenerateChangelog()
            with open('changelog.json', 'w') as f:
                json.dump(changelog, f, indent=4)
        case 'RCL':
            restbl.GenerateRcl()
        case 'YAML Patch':
            restbl.GenerateYamlPatch()
    print("Finished")

# Applies all RCL/YAML patches in a patch folder
def apply_patches(compressed=True):
    restbl_path = fd.askopenfilename(title="Select RESTBL File", filetypes=[('RESTBL Files', '.rsizetable'),
                                                                           ('RESTBL Files', '.rsizetable.zs')])
    patches_path = fd.askdirectory(title="Select Patches Folder")
    restbl = Restbl(restbl_path)
    print("Analyzing patches...")
    patches = [i for i in os.listdir(patches_path) if os.path.isfile(i) and os.path.splitext(i)[1].lower() in ['.json', '.yml', '.yaml', '.rcl']]
    changelogs = []
    for patch in patches:
        match os.path.splitext(patch)[1].lower():
            case '.json':
                with open(os.path.join(patches_path, patch), 'r') as f:
                    changelogs.append(json.load(f, object_pairs_hook=lambda d: {int(k) if k.isdigit() else k: v for k, v in d}))
            case '.yml' | '.yaml':
                changelogs.append(restbl.GenerateChangelogFromYaml(os.path.join(patches_path, patch)))
            case '.rcl':
                changelogs.append(restbl.GenerateChangelogFromRcl(os.path.join(patches_path, patch)))
    print("Merging patches...")
    changelog = MergeChangelogs(changelogs)
    print("Applying patches...")
    restbl.ApplyChangelog(changelog)
    restbl.Reserialize()
    if compressed:
        with open(restbl.filename, 'rb') as file:
            data = file.read()
        if os.path.exists(restbl.filename + '.zs'):
            os.remove(restbl.filename + '.zs')
        os.rename(restbl.filename, restbl.filename + '.zs')
        with open(restbl.filename + '.zs', 'wb') as file:
            compressor = zs.ZstdCompressor()
            file.write(compressor.compress(data))
    print("Finished")

if __name__ == "__main__":
    open_tool()