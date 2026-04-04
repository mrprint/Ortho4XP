# O4_ESP_Globals.py
# TODO: these globals are hackish. try to not use globals

build_for_ESP = False
do_build_masks = False
ESP_build_dir = None
mask_dir = None

# Mirrors IMG.incomplete_imgs but scoped to the ESP download pass.
# Keys are tile_coords strings produced by FNAMES.short_latlon()
# (e.g. "+48-006"), values are lists of BMP file-names that contained
# white squares during the last resample pass.
esp_incomplete_imgs: dict[str, list[str]] = {}
