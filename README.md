# Find the latest version here: https://github.com/stackTom/Ortho4XP_FSX_P3D/releases

# Ortho4XP_FSX_P3D
A scenery generator for the X-Plane flight simulator

Work in progress at adding FSX/P3D (ESP support)

*Note: Checkout my updates to FSEarthTiles - https://github.com/stackTom/FSEarthTiles FSEarthTiles (FSET) has much better algorithms to avoid distortion of ortho imagery inside the sim. It supports FSX, P3D, and FS9, and allows for the creation of tiles which don't have to be 1 degree by 1 degree like Ortho4XP.

# Use at your own risk

# Prerequisites

1) Windows Vista (or greater) 64 bit is required.

2) Please also install Microsoft Visual c++ redistributable. Download it here: https://aka.ms/vs/16/release/vc_redist.x64.exe

3) Please install ImageMagick before attempting to run, otherwise the night/season creation won't work. An installer has been provided inside the dist/ directory. Run the installer with the default settings.
The same installer can also be found here: https://www.imagemagick.org/download/binaries/ImageMagick-7.0.8-10-Q8-x64-dll.exe

4) NOTE: Need to provide the location of your resample.exe from the P3D or FSX SDK in Ortho4XP.cfg, like this:

`ESP_resample_loc=C:\\LOCATION\\TO\\resample.exe`

Notice the double backslashes `\\` instead of single `\`.

5) You can obtain the P3D resample.exe by installing the P3D SDK provided by Lockheed Martin on their site where you download P3D.
For FSX, resample.exe can be found by installing the FSX SDK found in the FSX Deluxe Disc 1 or in FSX Acceleration Pack (or FSX Gold which includes the Acceleration pack). The Steam edition of FSX does have an SDK but doesn't include the resample.exe executable, so you will have to install the regular SDK from any of these other sources (the FSX SDK has its own installer and can be installed separately without having to install the full game). 

# Running from exe
An executable (.exe) file has been provided in the dist/ directory, if you don't want to build the binary yourself. Simply double click on it, and it'll run. It cannot run without the parent folders though.

# Running with Python
To install, follow the install guide for Ortho4XP, making sure to install all python libraries, and run Ortho4XP_v130.py from the command line.

# To create autogen with ScenProc
Credit to Harry Otter for the default ScenProc script!

*NOTE* -> the included default ScenProc script needs improvement. I will improve it as time permits. There is also the possibility to improve it yourself, or simply add new scripts which ScenProc can use (see below steps on how to do this)
1) Download ScenProc from here: https://www.scenerydesign.org/development-releases/
Either the x86 or x64 version, depending on whether your operating system is 32 bit (x86) or 64 bit (x64)
2) Extract ScenProc to the location of your choice
3) Make sure to run scenProc.exe at least once, and set the path to your sim. Do this by running scenProc.exe, accepting the message box which appears, and then selecting the sim you are using along with the path to the sim in the window which shows up
4) Set the path to scenProc.exe in Ortho4XP.cfg, like this:
`ESP_scenproc_loc=C:\\path\\to\\ScenProc\\scenProc.exe`
5) OPTIONAL: You can create more scripts to guide ScenProc in creating autogen. They *MUST* be placed inside the `ScenProc_configs` folder. You can select which script for ScenProc to utilize, by changing the following line in Ortho4XP.cfg:
`ESP_scenproc_script=default.spc`, where `default.spc` is the name of the script you wish to use inside the `ScenProc_configs` folder
*IMPORTANT*: *MAKE SURE* to include the `@0@` and `@1@` in the same locations in your custom ScenProc scripts as are found in the default ScenProc script. Namely, the first and last lines:
`IMPORTOGR|@0@|*|building;landuse;natural;leisure|NOREPROJ` and
`EXPORTAGN|FSX|@1@`
Everything else can be changed, just not `@0@` and `@1@`, as ScenProc needs these so Ortho4XP can tell it where to load the OSM data from and where to output the autogen files to, respectively

# Example run from exe
https://www.youtube.com/watch?v=fkvmlbJXAq4

# Building binary (only tested on windows 10 64 bit):
Use pyinstaller like this:

`pyinstaller --clean -F -p src Ortho4XP_v130.py`

Then, copy spatialindex-64.dll and spatialindex_c-64.dll (from rtree python module) into the dist folder where the new executable is:

`cp /c/Users/fery2/AppData/Local/Programs/Python/Python36/Lib/site-packages/rtree/lib/spatialindex* dist/`

If the executable crashes with errors like `OSError: could not find or load spatialindex_c-64.dll`, then follow these instructions: https://stackoverflow.com/questions/64398516/pyinstaller-exe-oserror-could-not-find-or-load-spatialindex-c-64-dll

(Basically, find the `Ortho4XP_v130.spec` file, which should be in the same directory as Ortho4XP_v130.py. Add this import to it: `from PyInstaller.utils.hooks import collect_dynamic_libs`. Then, change the line that says `binaries=[]` to `binaries=collect_dynamic_libs("rtree")`. A sample `Ortho4XP_v130.spec` file is provided for reference, but it is recommended to use the one produced by pyinstaller and edit it with the lines just mentioned. After doing this, run `pyinstaller Ortho4XP_v130.spec`).

To build the imagemagick based c++ dll, use the Visual Studio Native Tools Command Prompt, and do something like:

`"F:\ExtraPrograms\Microsoft Visual Studio\2017\Community\VC\Tools\MSVC\14.14.26428\bin\Hostx64\x64\cl.exe" /LD /I "C:\Program Files\ImageMagick-7.0.8-Q8\include" /I C:/Users/fery2/AppData/Local/Programs/Python/Python36/include src\cpp\fast_image_mask.cpp src\cpp\FSET_ports.cpp  C:\Users\fery2\AppData\Local\Programs\Python\Python36\libs\python36.lib "C:\Program Files\ImageMagick-7.0.8-Q8\lib\CORE_RL_Magick++_.lib" "C:\Program Files\ImageMagick-7.0.8-Q8\lib\CORE_RL_MagickCore_.lib" "C:\Program Files\ImageMagick-7.0.8-Q8\lib\CORE_RL_MagickWand_.lib"`

Make sure the visual ++ environment is set to the correct bit of your python (32 vs 64 bit), and rename the .dll to .pyd

Note:
Imagemagick is required, specifically the q8 quantum depth version. To build it on UNIX from source code, configure like this:

`./configure --with-tiff=yes --with-quantum-depth=8`

# WHERE TO FIND the .bgl FILES FOR FSX
Ortho4XP generates a bunch of .bgl files for each tile inside the `Orthophotos` directory (for instance: `Ortho4XP_FSX_P3D-master\Orthophotos\+30+000\+39+002\BI_16\ADDON_SCENERY`). Rename the `ADDON_SCENERY` folder to whatever you wish, and move it wherever you wish (recommended is inside the `Addons Scenery` folder inside FSX/P3D). Then, add the scenery using the add/remove scenery option inside of the sim

# FINISHED:
base satellite imagery creation for FSX and P3D
water masks for FSX and P3D
build binary
night/seasonal texture creation options

# TODO:
remove extra steps not needed for ESP scenery creation
improve default scenProc spc file so it looks good in as many areas of the world as possible

# BUGS:
Certain tiles don't appear when their BGL is too large in size (like when creating tiles at ZL 12 and enabling all the seasons which creates 2+ gig BGLs). Not sure if limitation of the sim, or some other issue.

# Original Readme
# Ortho4XP
![example](https://github.com/shred86/Ortho4XP/assets/32663154/f06ebfe5-ba1d-4f05-9439-8e569bd99ef5)

Ortho4XP is a scenery generation tool for [X-Plane](https://www.x-plane.com). It creates the scenery base mesh and texture layer using external data and orthophoto sources.

This is a forked version of [Ortho4XP](https://github.com/oscarpilote/Ortho4XP) developed by [@oscarpilote](https://github.com/oscarpilote) which includes some updates, fixes and documentation. The official version is infrequently updated which is the reason I created this forked version to provide quicker updates and documentation.

The specific changes in this forked version:

#### General
* Tile configurations are automatically loaded when the active tile is changed using the Tiles Collection and Management window. If a tile configuration doesn't exist, the global tile configuration settings are used. The tile configuration is not loaded if you manually type in coordinates to change the active tile.
* Code changes to enable using [PyInstaller](https://pyinstaller.org/en/stable/) to bundle Ortho4XP and its dependencies into a single package.

#### Tiles Collection and Management
* Batch building process modified in regards to configuration files. If a tile configuration exists, it will be used. If a tile configuration does not exist, the global configuration will be used.
* "Read per tile cfg" removed and a "Override tile cfg" option added. This override setting allows you to force using the global configuration setting on all tiles, overriding any existing tile configurations.
* Erased cached data feature works like batch building tiles now, meaning Shift-Click (red rectangle) to select tiles, choose deletion options, and click "Batch Delete". The batch delete has no effect on the active tile selection (yellow rectangle).
* Display asterisk next to each tile zoom level number in the Tiles and configuration window if custom zoom levels have been specified.
* Added ability to create a symlink to the yOrtho4XP_Overlays folder by pressing the "O" key in the Tiles Collection and Management window.

#### Config
* Ortho4XP Config window is now separated into three tabs: Tile Config, Global Config, and Application Config. 
* When a tile configuration doesn't exist, the Tile Tab fields will become read-only. Clicking "Save Tile Cfg" in this case will make the fields become editable again since a tile configuration now exists.
* Text added at the top of the Tile Tab window which provides information on whether a tile configuration was loaded, or global defaults are being used.
* "Apply" buttons removed since this occurs automatically when a tile is changed, and the configuration is loaded. It also occurs when you click "Save".
* A "Reset to Global" button was added to the Tile Config tab which will reset the tile settings to the global tile config settings. If custom zones exist, a prompt asserts asking to save the zones. You still must select "Save Tile Config" if you want to save the changes. 
* A "Reset to Defaults" button was added as a part of the Global Config and Application Config tabs which will reset the tile and application settings to the application defaults. You still must select "Save Tile Config" if you want to save the changes. These buttons are independent of each other so if you're on the Global Config tab, it will reset just the tile settings in your global config and if you're on the Application Config tab, it will reset just the application settings in your global config.
* "Load Backup Cfg" buttons added to the Tile, Global, and Application Config tabs which loads settings from a backup config file (if available).
* Added ability to set an alternate `custom_overlay_src` directory to resolve an issue for some users. The default X-Plane scenery files are split up between `/X-Plane 12/Global Scenery/X-Plane Global Scenery` and `/X-Plane 12/Global Scenery/X-Plane Demo Areas`. So if you set `custom_overlay_src` to the first directory and try to batch build a bunch of tiles, you might get an error that the .dsf file can't be found if it's a location where the .dsf files are located in the second directory.
* The `custom_dem` and `fill_nodata` settings are now saved to the global configuration.
* Prompt user if attempting to close the application or config window with unsaved changes.
* Prompt user if attempting to change the active tile with unsaved changes on the Tile Tab in the config window.
* Prompt user if attempting to build tiles with unsaved changes in the config window.
* Backup of the tile configuration is created when using the "Save Tile Config" button (previously was only during a tile build process).
* Default `imprint_mask_to_dds` to `False` to prevent issues with `water_tech=XP12`.
* Added a new setting `max_download_slots` to support a new feature allowing users to specify number of parallel threads for imagery download. @tlinkin
* Setting `max_convert_slots` can now be manually specified by the user.

#### Miscellaneous
* Automatically saves the same data (active tile, default provider, default zoom level and base folder) that the power button icon does when you close the application using the operating system close button.
* Additional console messages addeded to provide more feedback. These are categorized with a verbosity setting of 1 (default).
* Attempt to redownload images (only once) that were not properly downloaded (white squares) if using "All in one" or batch build.
* "Part of image could not be obtained" error will now show a summary message at the end of a batch build or "All in one" if redownload was unsuccessful.
* Minor visual tweaks which included moving the "Refresh" and "Exit" buttons to the bottom of the left side in the Tiles collection and management window to better illustrate the "Refresh" button is not tied to Batch Build only.
* Includes Windows Python dependency wheel files for gdal and scikit-fmm.
* Updated Python and pin requirements to latest working versions.
* Adds a bash script to automate the setup process for those that prefer not to use the packaged version.
* Removed Maxar and Mapbox image providers which are no longer publically available.
* Removed unavailable OSM FR, updated/added RU and JP overpass servers.
* Include 7-zip executable for Mac.
* Update EOX url template and deleted the broken EOX2.lay file. @A346fan
* Updated Windows & Linux nvcompress to latest version. @tlinkin
* Use DDSTool instead of nvcompress for Mac.
* Update DFSTool to latest version 24-5.
* Removed unused tools.

#### Bug Fixes
* If one-click symlink feature is used, added removal of symlink when "Erase cached data" "Tile (whole)" option is used.
* Fixed zones being saved to tile configuration that were outside of the tile location.
* Fixed a bug where symlinks weren't automatically deleted if you used the Erased cached data - Tile (whole) option.
* Fixed a bug if you created zones on a tile then clicked "Apply" (which no longer exists as a button) before saving the tile config, it would delete your zones.
* Fixed Viewfinderpanorama elevation source for certain regions of the world.
* Fixed Here (https://wego.here.com/) image provider API key.
* Fixed issue in certain coastal regions where .dds files were being deleted with cleaning_level set to 2 or higher.
* Corrected a few typos in setting descriptions.
* Default `imprint_mask_to_dds` to `False` to prevent issues when using `water_tech=XP12`.
* Fixed a bug with random OSM server selection not working correctly.
* Include recompiled version of Triangle4XP.exe with MinGW-GCC for Windows users to resolve an [issue](https://github.com/oscarpilote/Ortho4XP/issues/282).
* Fixed a bug when using manually installed dem files were not being used on certain tiles.
* Fixed a bug and improved handling of complex meshes (e.g., +30-085) that would cause the build process to get stuck.
* Fixed and improved automatically trying a lower `min_angle` value when the current value fails.
* Reverted to previous triangle.exe to fix issues with creation of extent masks and certain providers.

## Installation

For installation instructions, refer to the [Installation page](https://github.com/shred86/Ortho4XP/wiki/Installation) in the [Wiki](https://github.com/shred86/Ortho4XP/wiki).

## Support

Troubleshooting steps for some issues are provided in the [Wiki FAQ](https://github.com/shred86/Ortho4XP/wiki/FAQ). For additional support or questions, refer to the [Ortho4XP forum](https://forums.x-plane.org/index.php?/forums/forum/322-ortho4xp/) at [X-Plane.org](https://forums.x-plane.org).
