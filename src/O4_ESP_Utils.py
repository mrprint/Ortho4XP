# O4_ESP_Utils.py
from __future__ import annotations

import os
import subprocess
from queue import Queue
from threading import Thread

import O4_Config_Utils
import O4_ESP_Globals
import O4_File_Names as FNAMES
import O4_UI_Utils as UI
from O4_Geo_Utils import gtile_to_wgs84
from fast_image_mask import (
    create_autumn,
    create_hard_winter,
    create_night,
    create_spring,
    create_winter,
)

# ---------------------------------------------------------------------------
# INF-file helpers (unchanged from the original)
# ---------------------------------------------------------------------------

def create_INF_source_string(
    source_num, season, variation, type, layer,
    source_dir, source_file,
    lon, lat,
    num_cells_line, num_lines,
    cell_x_dim, cell_y_dim,
):
    contents = "[Source" + source_num + "]\n"
    if season:
        contents += "Season          = " + season + "\n"
    if variation:
        contents += "Variation          = " + variation + "\n"
    contents += "Type          = " + type + "\n"
    contents += "Layer          = " + layer + "\n"
    contents += "SourceDir  = " + source_dir + "\n"
    contents += "SourceFile = " + source_file + "\n"
    contents += "Lon               = " + lon + "\n"
    contents += "Lat               = " + lat + "\n"
    contents += "NumOfCellsPerLine = " + num_cells_line + "       ;Pixel isn't FSX/P3D\n"
    contents += "NumOfLines        = " + num_lines + "       ;Pixel isn't used in FSX/P3D\n"
    contents += "CellXdimensionDeg = " + cell_x_dim + "\n"
    contents += "CellYdimensionDeg = " + cell_y_dim + "\n"
    contents += "PixelIsPoint      = 0\n"
    contents += "SamplingMethod    = Point\n"
    contents += "NullValue         = 255,255,255"
    return contents


def get_total_num_sources(seasons_to_create, build_night, build_water_mask):
    total = 0
    if seasons_to_create:
        created_summer = False
        for season, should_build in seasons_to_create.items():
            if should_build:
                total += 1
                if season == "Summer":
                    created_summer = True
        if total > 0 and not created_summer:
            total += 1
    if build_water_mask:
        if total == 0:
            total += 2
        else:
            total += 1
    if build_night:
        if total == 0:
            total += 2
        else:
            total += 1
    if total == 0:
        total = 1
    return total


def source_num_to_source_num_string(source_num, total_sources):
    if total_sources == 1:
        return ""
    return str(source_num)


def get_variation(season):
    variation_map = {
        "Spring":     ("March,April,May",          "_spring"),
        "Fall":       ("September,October",         "_fall"),
        "Winter":     ("November",                  "_winter"),
        "HardWinter": ("December,January,February", "_hard_winter"),
    }
    return variation_map[season]


def get_seasons_inf_string(
    seasons_to_create, source_num,
    type, layer, source_dir, source_file,
    img_mask_folder_abs_path, img_mask_name,
    lon, lat,
    num_cells_line, num_lines,
    cell_x_dim, cell_y_dim,
    total_sources, should_mask,
):
    string = ""
    source_file_name, ext = os.path.splitext(source_file)
    months_used_dict = {
        m: False for m in (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        )
    }

    for season, create_season in seasons_to_create.items():
        if season != "Summer" and create_season:
            (variation, img_suffix) = get_variation(season)
            string += create_INF_source_string(
                source_num_to_source_num_string(source_num, total_sources),
                season, variation, type, layer,
                source_dir, source_file_name + img_suffix + ext,
                lon, lat,
                num_cells_line, num_lines, cell_x_dim, cell_y_dim,
            ) + "\n\n"
            if should_mask:
                string += (
                    "; pull the blend mask from Source" + str(total_sources) + ", band 0\n"
                    "Channel_BlendMask = " + str(total_sources) + ".0\n"
                    "; pull the land water mask from Source" + str(total_sources) + ", band 2\n"
                    "Channel_LandWaterMask = " + str(total_sources) + ".2\n\n"
                )
            source_num += 1
            if variation is not None:
                for month in variation.split(","):
                    months_used_dict[month] = True

    if seasons_to_create["Summer"] or string != "":
        months_str = ",".join(m for m, used in months_used_dict.items() if not used)
        string += create_INF_source_string(
            source_num_to_source_num_string(source_num, total_sources),
            "Summer", months_str, type, layer,
            source_dir, source_file_name + ext,
            lon, lat,
            num_cells_line, num_lines, cell_x_dim, cell_y_dim,
        ) + "\n\n"
        if should_mask:
            string += (
                "; pull the blend mask from Source" + str(total_sources) + ", band 0\n"
                "Channel_BlendMask = " + str(total_sources) + ".0\n"
                "; pull the land water mask from Source" + str(total_sources) + ", band 2\n"
                "Channel_LandWaterMask = " + str(total_sources) + ".2\n\n"
            )
        source_num += 1

    return (string if string != "" else None, source_num - 1)


def make_ESP_inf_file(
    file_dir, file_name,
    til_x_left, til_x_right, til_y_top, til_y_bot,
    zoomlevel,
):
    file_name_no_extension, extension = os.path.splitext(file_name)
    img_top_left_tile     = gtile_to_wgs84(til_x_left,  til_y_top, zoomlevel)
    img_bottom_right_tile = gtile_to_wgs84(til_x_right, til_y_bot, zoomlevel)
    IMG_X_Y_DIM = 4096
    img_cell_x_dimension_deg = (
        (img_bottom_right_tile[1] - img_top_left_tile[1]) / IMG_X_Y_DIM
    )
    img_cell_y_dimension_deg = (
        (img_top_left_tile[0] - img_bottom_right_tile[0]) / IMG_X_Y_DIM
    )

    with open(
        os.path.join(file_dir, file_name_no_extension + ".inf"), "w"
    ) as inf_file:
        img_mask_name = (
            "_".join(file_name.split(".bmp")[0].split("_")[0:2]) + ".tif"
        )
        # Guard: mask_dir can be None when do_build_masks is False.
        mask_dir = O4_ESP_Globals.mask_dir or ""
        img_mask_folder_abs_path = os.path.abspath(mask_dir) if mask_dir else ""
        img_mask_abs_path = (
            os.path.abspath(os.path.join(img_mask_folder_abs_path, img_mask_name))
            if img_mask_folder_abs_path else ""
        )
        should_mask = (
            bool(O4_ESP_Globals.do_build_masks)
            and bool(img_mask_abs_path)
            and os.path.isfile(img_mask_abs_path)
        )

        seasons_to_create = {
            "Summer":     O4_Config_Utils.create_ESP_summer,
            "Spring":     O4_Config_Utils.create_ESP_spring,
            "Fall":       O4_Config_Utils.create_ESP_fall,
            "Winter":     O4_Config_Utils.create_ESP_winter,
            "HardWinter": O4_Config_Utils.create_ESP_hard_winter,
        }

        contents = ""
        total_num_sources = get_total_num_sources(
            seasons_to_create,
            O4_Config_Utils.create_ESP_night,
            should_mask,
        )
        if total_num_sources > 1:
            contents = (
                "[Source]\nType = MultiSource\nNumberOfSources = "
                + str(total_num_sources) + "\n\n"
            )

        current_source_num = 1
        seasons_string, num_seasons = get_seasons_inf_string(
            seasons_to_create, current_source_num,
            "BMP", "Imagery",
            os.path.abspath(file_dir), file_name,
            img_mask_folder_abs_path, img_mask_abs_path,
            str(img_top_left_tile[1]), str(img_top_left_tile[0]),
            str(IMG_X_Y_DIM), str(IMG_X_Y_DIM),
            str(img_cell_x_dimension_deg), str(img_cell_y_dimension_deg),
            total_num_sources, should_mask,
        )
        if seasons_string:
            current_source_num += num_seasons
            contents += seasons_string

        if O4_Config_Utils.create_ESP_night:
            source_num_str = source_num_to_source_num_string(
                current_source_num, total_num_sources
            )
            contents += create_INF_source_string(
                source_num_str, "LightMap", "LightMap", "BMP", "Imagery",
                os.path.abspath(file_dir),
                file_name_no_extension + "_night.bmp",
                str(img_top_left_tile[1]), str(img_top_left_tile[0]),
                str(IMG_X_Y_DIM), str(IMG_X_Y_DIM),
                str(img_cell_x_dimension_deg), str(img_cell_y_dimension_deg),
            ) + "\n\n"
            if should_mask:
                contents += (
                    "; pull the blend mask from Source" + str(total_num_sources) + ", band 0\n"
                    "Channel_BlendMask = " + str(total_num_sources) + ".0\n"
                    "; pull the land water mask from Source" + str(total_num_sources) + ", band 2\n"
                    "Channel_LandWaterMask = " + str(total_num_sources) + ".2\n\n"
                )
            current_source_num += 1

        if seasons_string is None:
            source_num_str = source_num_to_source_num_string(
                current_source_num, total_num_sources
            )
            contents += create_INF_source_string(
                source_num_str, None, None, "BMP", "Imagery",
                os.path.abspath(file_dir), file_name,
                str(img_top_left_tile[1]), str(img_top_left_tile[0]),
                str(IMG_X_Y_DIM), str(IMG_X_Y_DIM),
                str(img_cell_x_dimension_deg), str(img_cell_y_dimension_deg),
            ) + "\n\n"
            if should_mask:
                contents += (
                    "; pull the blend mask from Source" + str(total_num_sources) + ", band 0\n"
                    "Channel_BlendMask = " + str(total_num_sources) + ".0\n"
                    "; pull the land water mask from Source" + str(total_num_sources) + ", band 2\n"
                    "Channel_LandWaterMask = " + str(total_num_sources) + ".2\n\n"
                )
            current_source_num += 1

        if should_mask:
            source_num_str = source_num_to_source_num_string(
                current_source_num, total_num_sources
            )
            contents += create_INF_source_string(
                source_num_str, None, None, "TIFF", "None",
                img_mask_folder_abs_path, img_mask_name,
                str(img_top_left_tile[1]), str(img_top_left_tile[0]),
                str(IMG_X_Y_DIM), str(IMG_X_Y_DIM),
                str(img_cell_x_dimension_deg), str(img_cell_y_dimension_deg),
            ) + "\n\n"

        contents += "[Destination]\n"
        contents += (
            "DestDir             = "
            + os.path.abspath(file_dir)
            + os.sep + "ADDON_SCENERY" + os.sep + "scenery\n"
        )
        contents += "DestBaseFileName     = " + file_name_no_extension + "\n"
        contents += "BuildSeasons        = 0\n"
        contents += "UseSourceDimensions  = 1\n"
        contents += "CompressionQuality   = 100\n"

        LOD_13_DEG_PER_PIX = 4.27484e-05
        if (
            img_cell_x_dimension_deg > LOD_13_DEG_PER_PIX
            or img_cell_y_dimension_deg > LOD_13_DEG_PER_PIX
        ):
            contents += "LOD = Auto, 13\n"

        inf_file.write(contents)


# ---------------------------------------------------------------------------
# Low-level subprocess helpers
# ---------------------------------------------------------------------------

def spawn_resample_process(filename: str) -> None:
    """
    Run resample.exe synchronously.

    Raises RuntimeError on non-zero exit so that the calling worker can catch
    the failure and record it in esp_incomplete_imgs.  The original
    implementation silently ignored the return code, which meant failures were
    never detected and no retry ever occurred.
    """
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 7  # SW_SHOWMINNOACTIVE
    process = subprocess.Popen(
        [O4_Config_Utils.ESP_resample_loc, filename],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        startupinfo=startupinfo,
    )
    process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            f"resample.exe exited with code {process.returncode} "
            f"for '{filename}'"
        )


def remove_file_if_exists(filename: str) -> None:
    try:
        os.remove(filename)
    except OSError:
        pass


def spawn_scenproc_process(
    scenproc_script_file: str,
    scenproc_osm_file: str,
    texture_folder: str,
) -> None:
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 7
    process = subprocess.Popen(
        [
            O4_Config_Utils.ESP_scenproc_loc,
            scenproc_script_file,
            "/run",
            scenproc_osm_file,
            texture_folder,
        ],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        startupinfo=startupinfo,
    )
    process.communicate()


# ---------------------------------------------------------------------------
# BMP / seasonal helpers
# ---------------------------------------------------------------------------

def _make_seasonal_bmps(file_name: str, img_mask_abs_path: str | None) -> None:
    """Create night / seasonal BMP variants beside the base BMP."""
    mask = img_mask_abs_path or None
    if O4_Config_Utils.create_ESP_night:
        create_night(file_name + ".bmp", file_name + "_night.bmp", mask)
    if O4_Config_Utils.create_ESP_spring:
        create_spring(file_name + ".bmp", file_name + "_spring.bmp", mask)
    if O4_Config_Utils.create_ESP_fall:
        create_autumn(file_name + ".bmp", file_name + "_fall.bmp", mask)
    if O4_Config_Utils.create_ESP_winter:
        create_winter(file_name + ".bmp", file_name + "_winter.bmp", mask)
    if O4_Config_Utils.create_ESP_hard_winter:
        create_hard_winter(
            file_name + ".bmp", file_name + "_hard_winter.bmp", mask
        )


def _remove_seasonal_bmps(file_name: str) -> None:
    """Remove temporary night / seasonal BMP variants."""
    for suffix in ("_night", "_spring", "_fall", "_winter", "_hard_winter"):
        remove_file_if_exists(file_name + suffix + ".bmp")


def _resolve_mask_path(full_file_name: str) -> tuple[str, bool]:
    """
    Return (abs_mask_path, should_mask).
    should_mask is True only when do_build_masks is set, mask_dir is
    configured, AND the mask file actually exists on disk.

    ``full_file_name`` must be a bare file name (no directory part), as
    returned by the ``file_names`` list from ``os.walk``.
    """
    mask_dir = O4_ESP_Globals.mask_dir or ""
    if not mask_dir:
        return ("", False)

    img_mask_name = (
        "_".join(full_file_name.split(".inf")[0].split("_")[0:2]) + ".tif"
    )
    img_mask_folder_abs_path = os.path.abspath(mask_dir)
    img_mask_abs_path = os.path.abspath(
        os.path.join(img_mask_folder_abs_path, img_mask_name)
    )
    should_mask = (
        bool(O4_ESP_Globals.do_build_masks)
        and os.path.isfile(img_mask_abs_path)
    )
    return (img_mask_abs_path if should_mask else "", should_mask)


# ---------------------------------------------------------------------------
# Worker threads
# ---------------------------------------------------------------------------

def _run_resample_worker(q: Queue, tile_coords: str) -> None:
    """
    Process [file_name_stem, inf_abs_path, img_mask_abs_path] entries from
    *q* until the sentinel ``None`` is received.

    ``tile_coords`` is ``FNAMES.short_latlon(tile.lat, tile.lon)`` — the same
    key used by O4_Tile_Utils.  Passing it explicitly (rather than deriving it
    from the BMP name) ensures the keys always match.

    On failure the BMP base-name is recorded in
    ``O4_ESP_Globals.esp_incomplete_imgs[tile_coords]`` so that the retry
    pass in O4_Tile_Utils can find and delete it.
    """
    for args in iter(q.get, None):
        file_name: str         = args[0]   # absolute stem, no extension
        inf_abs_path: str      = args[1]
        img_mask_abs_path: str = args[2] if args[2] else ""
        try:
            _make_seasonal_bmps(file_name, img_mask_abs_path or None)
            spawn_resample_process(inf_abs_path)
            _remove_seasonal_bmps(file_name)
        except Exception as exc:
            print(f"{args!r} failed: {exc}")
            _remove_seasonal_bmps(file_name)   # clean up even on failure
            bmp_name = os.path.basename(file_name + ".bmp")
            O4_ESP_Globals.esp_incomplete_imgs.setdefault(
                tile_coords, []
            ).append(bmp_name)


def _run_scenproc_worker(q: Queue) -> None:
    """Process [script, osm_file, texture_folder] entries from *q*."""
    for args in iter(q.get, None):
        try:
            spawn_scenproc_process(args[0], args[1], args[2])
        except Exception as exc:
            print(f"{args!r} failed: {exc}")


# ---------------------------------------------------------------------------
# Public helpers called from O4_Tile_Utils
# ---------------------------------------------------------------------------

def collect_esp_incomplete_imgs() -> dict[str, list[str]]:
    """
    Return a shallow copy of esp_incomplete_imgs.
    Mirrors the role of ``IMG.incomplete_imgs`` for the X-Plane path.
    """
    return dict(O4_ESP_Globals.esp_incomplete_imgs)


def delete_incomplete_esp_bmps(build_dir: str, tile_coords: str) -> None:
    """
    Delete BMP files (and their matching .inf files) that were recorded as
    incomplete for *tile_coords*.
    Mirrors ``O4_Tile_Utils.delete_incomplete_imgs``.
    """
    if tile_coords not in O4_ESP_Globals.esp_incomplete_imgs:
        return

    for bmp_name in O4_ESP_Globals.esp_incomplete_imgs[tile_coords]:
        for root, _, files in os.walk(build_dir):
            if bmp_name in files:
                bmp_path = os.path.join(root, bmp_name)
                remove_file_if_exists(bmp_path)
                # Remove the matching .inf so it gets regenerated on retry.
                inf_path = os.path.splitext(bmp_path)[0] + ".inf"
                remove_file_if_exists(inf_path)
                UI.lvprint(1, f"ESP retry: deleted {bmp_path}")

    del O4_ESP_Globals.esp_incomplete_imgs[tile_coords]


# ---------------------------------------------------------------------------
# Main entry-point called from O4_Tile_Utils.build_tile
# ---------------------------------------------------------------------------

def build_for_ESP(build_dir: str, tile) -> None:  # type: ignore[type-arg]
    """
    Run resample (and optionally ScenProc) over every .inf file found under
    *build_dir*.

    Behaviour
    ─────────
    • Respects O4_Tile_Utils.skip_downloads / skip_converts:
        skip_downloads → early exit (nothing was downloaded, nothing to resample).
        skip_converts  → skip resample but still run ScenProc if configured.
    • Runs up to O4_Config_Utils.max_resample_processes parallel resample
      workers.  A non-zero exit code from resample.exe is treated as failure
      and the BMP name is recorded in O4_ESP_Globals.esp_incomplete_imgs so
      that O4_Tile_Utils can delete the bad file and retry.
    • ScenProc runs concurrently with resample in a dedicated thread.
    """
    # Deferred import to break the circular dependency:
    # O4_Tile_Utils imports O4_ESP_Utils at module level, so O4_ESP_Utils
    # must not import O4_Tile_Utils at module level.
    import O4_Tile_Utils as TILE  # noqa: PLC0415

    if not build_dir:
        print(
            "ESP build_dir is None inside build_for_ESP – "
            "something went wrong, aborting."
        )
        return

    # ── respect skip_downloads ────────────────────────────────────────────
    if TILE.skip_downloads:
        UI.vprint(1, "   ESP: skip_downloads is set – skipping resample entirely.")
        return

    # ── validate resample.exe ─────────────────────────────────────────────
    if not O4_Config_Utils.ESP_resample_loc:
        print("No resample.exe specified in Ortho4XP.cfg – aborting ESP build.")
        return
    if not os.path.isfile(O4_Config_Utils.ESP_resample_loc):
        print(
            f"resample.exe not found at {O4_Config_Utils.ESP_resample_loc!r} "
            "– aborting ESP build."
        )
        return

    # tile_coords is the canonical key shared with O4_Tile_Utils.
    tile_coords: str = FNAMES.short_latlon(tile.lat, tile.lon)

    # ── optionally start ScenProc concurrently ────────────────────────────
    scenproc_thread: Thread | None = None
    scenproc_queue:  Queue  | None = None

    scenproc_osm_directory = os.path.abspath(
        os.path.join(FNAMES.osm_dir(tile.lat, tile.lon), "scenproc_osm_data")
    )

    if (
        os.path.isfile(O4_Config_Utils.ESP_scenproc_loc)
        and os.path.isdir(scenproc_osm_directory)
    ):
        scenproc_script_file = os.path.abspath(
            os.path.join(
                FNAMES.ScenProc_configs_dir,
                O4_Config_Utils.ESP_scenproc_script,
            )
        )
        addon_scenery_folder = os.path.abspath(
            os.path.join(build_dir, "ADDON_SCENERY")
        )
        texture_folder = os.path.abspath(
            os.path.join(addon_scenery_folder, "texture")
        )
        os.makedirs(addon_scenery_folder, exist_ok=True)
        os.makedirs(texture_folder, exist_ok=True)

        scenproc_queue = Queue()
        scenproc_thread = Thread(
            target=_run_scenproc_worker, args=(scenproc_queue,), daemon=True
        )
        scenproc_thread.start()

        osm_files = [
            os.path.abspath(os.path.join(scenproc_osm_directory, f))
            for f in os.listdir(scenproc_osm_directory)
        ]
        if osm_files:
            print(
                "Running ScenProc concurrently with resample. "
                "Manual command for first file:\n"
                f"  {O4_Config_Utils.ESP_scenproc_loc} "
                f"{scenproc_script_file} /run {osm_files[0]} {texture_folder}"
            )
        for osm_file in osm_files:
            scenproc_queue.put_nowait(
                [scenproc_script_file, osm_file, texture_folder]
            )

    # ── respect skip_converts ─────────────────────────────────────────────
    if TILE.skip_converts:
        UI.vprint(
            1,
            "   ESP: skip_converts is set – skipping resample "
            "(ScenProc will still run if configured).",
        )
        if scenproc_queue is not None:
            scenproc_queue.put_nowait(None)
        if scenproc_thread is not None:
            scenproc_thread.join()
        return

    # ── collect .inf files ────────────────────────────────────────────────
    # Each entry: [file_name_stem, inf_abs_path, img_mask_abs_path]
    inf_entries: list[list[str]] = []

    for dirpath, _dir_names, file_names in os.walk(build_dir):
        for full_file_name in file_names:
            if not full_file_name.endswith(".inf"):
                continue
            # Use dirpath (not build_dir) to handle sub-directory .inf files
            # with the correct absolute path.
            inf_abs_path = os.path.abspath(
                os.path.join(dirpath, full_file_name)
            )
            file_stem = os.path.splitext(inf_abs_path)[0]
            img_mask_abs_path, _ = _resolve_mask_path(full_file_name)
            inf_entries.append([file_stem, inf_abs_path, img_mask_abs_path])

    if not inf_entries:
        UI.vprint(1, "   ESP: no .inf files found – nothing to resample.")
        if scenproc_queue is not None:
            scenproc_queue.put_nowait(None)
        if scenproc_thread is not None:
            scenproc_thread.join()
        return

    # ── launch parallel resample workers ─────────────────────────────────
    max_workers: int = max(1, O4_Config_Utils.max_resample_processes)
    UI.vprint(
        1,
        f"Starting ESP resample queue with {max_workers} worker(s). "
        "Resample windows will open minimised. "
        "You will be notified when finished.",
    )

    resample_queue: Queue = Queue()
    # Pass tile_coords explicitly so workers use the same dict key as
    # O4_Tile_Utils (FNAMES.short_latlon result), not a BMP-name heuristic.
    workers = [
        Thread(
            target=_run_resample_worker,
            args=(resample_queue, tile_coords),
            daemon=True,
        )
        for _ in range(max_workers)
    ]
    for w in workers:
        w.start()

    for entry in inf_entries:
        resample_queue.put_nowait(entry)

    # One sentinel per worker guarantees every worker exits cleanly.
    for _ in workers:
        resample_queue.put_nowait(None)

    for w in workers:
        w.join()

    # ── wait for ScenProc ─────────────────────────────────────────────────
    if scenproc_queue is not None:
        scenproc_queue.put_nowait(None)
    if scenproc_thread is not None:
        scenproc_thread.join()

    UI.vprint(1, "   ESP: resample (and ScenProc if configured) completed.")
