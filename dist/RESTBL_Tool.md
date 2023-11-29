# RESTBL Tool
RESTBL Tool is a simple tool for working with and merging RESTBL files in *Tears of the Kingdom*. RESTBL files are used by the game's resource system to decide how much memory it should allocate for each file. Each entry in a RESTBL file contains a CRC32 hash of the corresponding file's path and its allocation size. The allocated size as listed in the RESTBL is not exactly equal to the size of the file, it is slightly larger.

When developing or using mods, the RESTBL oftens becomes an issue as changes to file sizes may lead to the existing RESTBL entry becoming too small. This will result in the game crashing when it attempts to load in said resource. As a result, many mods come with edited RESTBL files, tailored for that specific mod. The issue arises when you have multiple mods all requiring RESTBL edits. This tool aims to solve that issue by automating the process without the need for external changelog files (such as YAML patches or .rcl files).

## Usage
To use the tool, simply download `RESTBL Tool.exe` and run it. There are five options to choose from: Generate RESTBL from Mod(s), Select RESTBL to Merge, Generate Changelog, Apply Patches, and Exit.

### Generate RESTBL from Mod(s)
This option will analyze the provided mod directories and automatically generated an edited RESTBL file. However, it requires a dump of the game's ROM file system in order to access proper Zstd dictionaries (for decompression).

Selecting the Compress option will compress the generated RESTBL file with Zstd compression. Selecting the Use Existing RESTBL option will search each mod for an existing RESTBL file. If the file exists, that file will be used for that mod instead of analyzing the directory. Selecting Delete Existing RESTBL will automatically delete any existing RESTBL files present in the mod(s) during analysis to prevent any potential file conflicts. This option is compatible with Use Existing RESTBL. Selecting Use Checksums will compare each file in the mod with the unmodified file by comparing a SHA-256 hash of the file. This avoids creating unnecessary RESTBL entries for unmodified files that may be present in the mod.

When selecting this option, the first file prompt will ask you to provide the path to the folder containing your mods. This should be the folder so that the path `[selected_path]/[mod_name]/romfs` exists.

**Example:**
```
 Selected Folder/
    ├── Mod 1/
    │   └── romfs
    ├── Mod 2/
    │   └── romfs
    └── Mod 3/
        └── romfs
```

The second prompt will ask for the path to your unedited romfs dump. This should be a folder such that `[selected_path]/Pack/ZsDic.pack.zs` exists. The next prompt will ask whether or not to use or create a base RESTBL file. Selecting a base RESTBL will apply the detected changes to that file while creating a new one will apply the detected changes to an unedited RESTBL file. The latter will also prompt you to provide what game version you would like to create the RESTBL for.

### Select RESTBL Files to Merge
This option will create a merged RESTBL file from the two provided RESTBL files. Similar to the previous option, selecting Compress will compress the generated RESTBL file with Zstd compression.

### Generate Changelog
This option will generate a changelog in the format of your choice from the selected RESTBL file.

### Apply Patches
This option will apply all RCL/YAML patches in a folder to the selected RESTBL file.

### Exit
This option will close the program.