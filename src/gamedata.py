from byml import *
from utils import *
import mmh3
import zstd

# Includes a few presets for common sets of flags (such as adding new enemies, new materials)
# If you want to make your own presets, use the Int, UInt, Long, ULong, Float, and Double classes for numerical values
# Do not use the built-in Python types for those - there are strict typing requirements and we need to preserve those

# Data types found in GameDataList
valid_types = [
    'Bool',
    'BoolArray',
    'Int',
    'IntArray',
    'Float',
    'FloatArray',
    'Enum',
    'EnumArray',
    'Vector2',
    'Vector2Array',
    'Vector3',
    'Vector3Array',
    'String16',
    'String16Array',
    'String32',
    'String32Array',
    'String64',
    'String64Array',
    'Binary',
    'BinaryArray',
    'UInt',
    'UIntArray',
    'Int64',
    'Int64Array',
    'UInt64',
    'UInt64Array',
    'WString16',
    'WString16Array',
    'WString32',
    'WString32Array',
    'WString64',
    'WString64Array',
    'Struct',
    'BoolExp',
    'Bool64bitKey'
]

# ResetTypeValue - pass these as arguments to GetResetType to calculate the value
reset_types = {
    "BancChange" : 0,
    "NewDay" : 1,
    "OptionsReset" : 2,
    "BloodMoon" : 3,
    "LoadSave" : 4,
    "Type5" : 5,
    "Type6" : 6,
    "ZonaiRespawn" : 7,
    "MaterialRespawn" : 8,
    "NoResetOnNewGame" : 9
}

class Gamedata:
    def __init__(self, self_path):
        print("Initializing GameData...")
        self.gamedata = Byml(self_path)
        print("Initialization complete")

    def Save(self, output_dir=''):
        print("Saving changes... (may take a moment so please be patient)")
        self.gamedata.Reserialize(output_dir)
        print("Saved")

    # Returns flag entry
    def GetFlag(self, name, datatype):
        hash = self.GetHash(name)
        flag = self.IterTryFindFlagByType(hash, datatype)
        return flag

    # Returns flag entry from flag name of a flag in a struct
    def GetStructFlag(self, name, struct_name):
        name_hash = self.GetHash(name)
        struct_hash = self.GetHash(struct_name)
        struct = self.IterTryFindFlagByType(struct_hash, "Struct")
        if struct is None:
            print(f"Struct {struct_name} not found")
            return None
        hash = 0
        for entry in struct["DefaultValue"]:
            if name_hash == entry["Hash"]:
                hash = entry["Value"]
        if hash == 0:
            print(f"Flag {name} was not found in {struct_name}")
            return None
        flag = self.IterTryFindFlag(hash)
        return flag

    # Sets/adds flag of the specified type
    def SetFlag(self, datatype, new_flag):
        if datatype not in valid_types:
            raise ValueError(f"Invalid type {datatype}")
        if datatype == "BinaryArray":
            assert len(new_flag) == 6, "Invalid entry"
            assert set(list(new_flag.keys())) == {"ArraySize", "DefaultValue",
                                                  "Hash", "OriginalSize",
                                                  "ResetTypeValue", "SaveFileIndex"}, "Invalid entry"
        elif datatype == "Enum":
            assert len(new_flag) == 6, "Invalid entry"
            assert set(list(new_flag.keys())) == {"RawValues", "DefaultValue",
                                                  "Hash", "Values",
                                                  "ResetTypeValue", "SaveFileIndex"}, "Invalid entry"
        elif datatype == "EnumArray":
            assert len(new_flag) == 7, "Invalid entry"
            assert set(list(new_flag.keys())) == {"RawValues", "DefaultValue",
                                                  "Hash", "Values", "Size",
                                                  "ResetTypeValue", "SaveFileIndex"}, "Invalid entry"
        elif "Array" in datatype:
            assert len(new_flag) == 5
            assert set(list(new_flag.keys())) == {"DefaultValue",
                                                  "Hash", "OriginalSize",
                                                  "ResetTypeValue", "SaveFileIndex"}, "Invalid entry"
        else:
            assert len(new_flag) == 4
            assert set(list(new_flag.keys())) == {"DefaultValue", "Hash",
                                                  "SaveFileIndex", "ResetTypeValue"}, "Invalid entry"
        hash = new_flag["Hash"]
        if datatype not in self.gamedata.root_node["Data"]:
            self.gamedata.root_node[datatype] = []
        for i in range(len(self.gamedata.root_node["Data"][datatype])):
            if self.gamedata.root_node["Data"][datatype][i]["Hash"] == hash:
                self.gamedata.root_node["Data"][datatype][i] = new_flag
                return
        self.gamedata.root_node["Data"][datatype].append(new_flag)

    # Not for EnumArray
    def SetArrayValueByIndexAndType(self, array_name, index, value, datatype):
        hash = self.GetHash(array_name)
        if datatype not in valid_types or "Array" not in datatype:
            raise ValueError("Invalid array type")
        if "Bool" in datatype:
            if not(isinstance(value, bool)):
                raise ValueError("Invalid value")
        if "Int" in datatype:
            if not(isinstance(value, Int)):
                raise ValueError("Invalid value")
        if "Float" in datatype:
            if not(isinstance(value, Float)):
                raise ValueError("Invalid value")
        if "Vector" in datatype:
            if not(isinstance(value, dict)):
                raise ValueError("Invalid value")
        if "String" in datatype:
            if not(isinstance(value, str)):
                raise ValueError("Invalid value")
        if "UInt" in datatype:
            if not(isinstance(value, UInt)):
                raise ValueError("Invalid value")
        if "Int64" in datatype:
            if not(isinstance(value, Long)):
                raise ValueError("Invalid value")
        if "UInt64" in datatype:
            if not(isinstance(value, ULong)):
                raise ValueError("Invalid value")
        for i in range(len(self.gamedata.root_node["Data"][datatype])):
            if self.gamedata.root_node["Data"][datatype][i]["Hash"] == hash:
                self.gamedata.root_node["Data"][datatype][i]["DefaultValue"][index] = value
                return
        raise ValueError("Unable to set array value")
    
    # Sets/adds Bool64bitKey entry
    def SetBoolKey(self, entry):
        for i in range(len(self.gamedata.root_node["Data"]["Bool64bitKey"])):
            if self.gamedata.root_node["Data"]["Bool64bitKey"][i]["Hash"] == entry["Hash"]:
                self.gamedata.root_node["Data"]["Bool64bitKey"][i] = entry
                return
        self.gamedata.root_node["Data"]["Bool64bitKey"].append(entry)

    # Adds entry to struct
    def AddEntryToStruct(self, entry, struct_name):
        hash = self.GetHash(struct_name)
        matched = False
        for i in range(len(self.gamedata.root_node["Data"]["Struct"])):
            if self.gamedata.root_node["Data"]["Struct"][i]["Hash"] == hash:
                for j in range(len(self.gamedata.root_node["Data"]["Struct"][i]["DefaultValue"])):
                    if self.gamedata.root_node["Data"]["Struct"][i]["DefaultValue"][j] == entry:
                        matched = True
                        break
                if not(matched):
                    self.gamedata.root_node["Data"]["Struct"][i]["DefaultValue"].append(entry)
                return
        raise ValueError("Struct not found")

    # Find flag by hash and type
    def IterTryFindFlagByType(self, hash, datatype):
        if datatype not in valid_types:
            raise ValueError(f"Invalid type {datatype}")
        if datatype not in self.gamedata.root_node["Data"]:
            return None
        else:
            for entry in self.gamedata.root_node["Data"][datatype]:
                if entry["Hash"] == hash:
                    return entry
        return None
    
    # Find flag without knowing type, returns first result
    def IterTryFindFlag(self, hash):
        for datatype in valid_types:
            result = self.IterTryFindFlagByType(hash, datatype)
            if result is not None:
                return result
        return None
    
    # If you ever need to reference this
    def GetSaveDirectories(self):
        return self.gamedata.root_node["MetaData"]["SaveDirectory"]
    
    @staticmethod
    def GetHash(value):
        if isinstance(value, int):
            return UInt(value)
        elif isinstance(value, UInt):
            return value
        elif isinstance(value, str):
            return UInt(mmh3.hash(value, signed=False))
        raise ValueError("Invalid value")
    
    @staticmethod
    def GetResetType(*types):
        value = 0
        for reset_type in types:
            value = value | (2 ** reset_types[reset_type])
        return Int(value)
    
    @staticmethod
    def GetExtraByte(map_unit):
        letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
        if len(map_unit) != 2 or not(isinstance(map_unit, str)):
            raise ValueError("Invalid map unit - should be in a form such as F5")
        if map_unit[0] not in letters:
            raise ValueError("Out of range (A1 - J8)")
        if not(map_unit[1].isdigit()) or int(map_unit[1]) not in range(9):
            raise ValueError("Out of range (A1 - J8)")
        return Int(letters.index(map_unit[0]) + 10 * (int(map_unit[1]) - 1) + 1)

    # these are just a few presets for common sets of flags you may need to add to gamedata
    def AddPictureBookData(self, actor_name):
        struct = {
        "DefaultValue": [
            {
            "Hash": self.GetHash("IsNew"),
            "Value": self.GetHash(f"PictureBookData.{actor_name}.IsNew")
            },
            {
            "Hash": self.GetHash("State"),
            "Value": self.GetHash(f"PictureBookData.{actor_name}.State")
            }
        ],
        "Hash": self.GetHash(f"PictureBookData.{actor_name}"),
        "ResetTypeValue": Int(0),
        "SaveFileIndex": Int(-1)
        }
        isnew = {
        "DefaultValue": False,
        "Hash": self.GetHash(f"PictureBookData.{actor_name}.IsNew"),
        "ResetTypeValue": Int(80),
        "SaveFileIndex": Int(0)
        }
        state = {
        "DefaultValue": self.GetHash("Unopened"),
        "Hash": self.GetHash(f"PictureBookData.{actor_name}.State"),
        "RawValues": [
            "Unopened",
            "TakePhoto",
            "Buy"
        ],
        "ResetTypeValue": Int(80),
        "SaveFileIndex": Int(0),
        "Values": [
            self.GetHash("Unopened"),
            self.GetHash("TakePhoto"),
            self.GetHash("Buy")
        ]
        }
        self.SetFlag("Struct", struct)
        self.SetFlag("Bool", isnew)
        self.SetFlag("Enum", state)

    def AddBattleData(self, actor_name):
        struct = {
            "DefaultValue": [
                {
                "Hash": self.GetHash("GuardJustCount"),
                "Value": self.GetHash(f"EnemyBattleData.{actor_name}.GuardJustCount")
                },
                {
                "Hash": self.GetHash("JustAvoidCount"),
                "Value": self.GetHash(f"EnemyBattleData.{actor_name}.JustAvoidCount")
                },
                {
                "Hash": self.GetHash("DefeatedNoDamageCount"),
                "Value": self.GetHash(f"EnemyBattleData.{actor_name}.DefeatedNoDamageCount")
                },
                {
                "Hash": self.GetHash("HeadShotCount"),
                "Value": self.GetHash(f"EnemyBattleData.{actor_name}.HeadShotCount")
                }
            ],
            "Hash": self.GetHash(f"EnemyBattleData.{actor_name}"),
            "ResetTypeValue": Int(0),
            "SaveFileIndex": Int(-1)
            }
        guardjust = {
            "DefaultValue": Int(0),
            "Hash": self.GetHash(f"EnemyBattleData.{actor_name}.GuardJustCount"),
            "ResetTypeValue": Int(80),
            "SaveFileIndex": Int(0)
        }
        justavoid = {
            "DefaultValue": Int(0),
            "Hash": self.GetHash(f"EnemyBattleData.{actor_name}.JustAvoidCount"),
            "ResetTypeValue": Int(80),
            "SaveFileIndex": Int(0)
        }
        nodmg = {
            "DefaultValue": Int(0),
            "Hash": self.GetHash(f"EnemyBattleData.{actor_name}.DefeatedNoDamageCount"),
            "ResetTypeValue": Int(80),
            "SaveFileIndex": Int(0)
        }
        headshot = {
            "DefaultValue": Int(0),
            "Hash": self.GetHash(f"EnemyBattleData.{actor_name}.HeadShotCount"),
            "ResetTypeValue": Int(80),
            "SaveFileIndex": Int(0)
        }
        self.SetFlag("Struct", struct)
        self.SetFlag("Int", guardjust)
        self.SetFlag("Int", justavoid)
        self.SetFlag("Int", nodmg)
        self.SetFlag("Int", headshot)
        self.AddEntryToStruct({"Hash" : self.GetHash(actor_name),
                               "Value" : self.GetHash(f"EnemyBattleData.{actor_name}")}, "EnemyBattleData")

    def AddEnemyFlags(self, enemy_name):
        print(f"Adding {enemy_name} flags...")
        self.AddPictureBookData(enemy_name)
        self.AddBattleData(enemy_name)
        self.AddEntryToStruct({"Hash" : self.GetHash(enemy_name),
                               "Value" : self.GetHash(f"DefeatedEnemyNum.{enemy_name}")}, "DefeatedEnemyNum")
        self.SetFlag("Int", {"DefaultValue": Int(0), "Hash": self.GetHash(f"DefeatedEnemyNum.{enemy_name}"),
                            "ResetTypeValue": Int(80), "SaveFileIndex": Int(0)})

    def AddMaterialFlags(self, material_name, throwable=True):
        print(f"Adding {material_name} flags...")
        self.AddPictureBookData(material_name)
        self.AddEntryToStruct({"Hash" : self.GetHash(material_name),
                            "Value" : self.GetHash(f"IsGetAnyway.{material_name}")}, "IsGetAnyway")
        self.AddEntryToStruct({"Hash" : self.GetHash(material_name),
                            "Value" : self.GetHash(f"IsGet.{material_name}")}, "IsGet")
        isget = {
        "DefaultValue": False,
        "Hash": self.GetHash(f"IsGet.{material_name}"),
        "ResetTypeValue": Int(16),
        "SaveFileIndex": Int(0)
        }
        isgetanyway = {
        "DefaultValue": False,
        "Hash": self.GetHash(f"IsGetAnyway.{material_name}"),
        "ResetTypeValue": Int(16),
        "SaveFileIndex": Int(0)
        }
        self.SetFlag("Bool", isget)
        self.SetFlag("Bool", isgetanyway)
        if throwable:
            self.AddEntryToStruct({"Hash" : self.GetHash(material_name),
                               "Value" : self.GetHash(f"MaterialShortCutCounter.{material_name}")}, "MaterialShortCutCounter")
            self.SetFlag("UInt", {"DefaultValue": UInt(0), "Hash": self.GetHash(f"MaterialShortCutCounter.{material_name}"),
                                    "ResetTypeValue": Int(16), "SaveFileIndex": Int(0)})

# Example usage (use the zstd module to decompress/recompress if necessary)
gmd = Gamedata("GameDataList.Product.110.byml")
gmd.AddMaterialFlags("Item_Fruit_Z")
gmd.AddEnemyFlags("Enemy_Moriblin_F")
gmd.Save()