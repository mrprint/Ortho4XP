import os
import time
import asyncio
from math import pi, sin, cos, sqrt, atan, exp
import numpy
from shapely import geometry, ops

# from PIL import Image, ImageDraw, ImageFilter
import O4_DEM_Utils as DEM
import O4_UI_Utils as UI
import O4_OSM_Utils as OSM
import O4_Vector_Utils as VECT
import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Airport_Utils as APT
import O4_ESP_Globals
import O4_Config_Utils

try:
    import httpx
    _has_httpx = True
except ImportError:
    _has_httpx = False

good_imagery_list = ()

################################################################################
def build_poly_file(tile):
    if UI.is_working:
        return 0
    UI.is_working = 1
    UI.red_flag = 0
    # in case that was forgotten by the user
    tile.iterate = 0
    # update the lat/lon scaling factor in VECT
    VECT.scalx = cos((tile.lat + 0.5) * pi / 180)
    # Let's go !
    UI.logprint(
        "Step 1 for tile lat=", tile.lat, ", lon=", tile.lon, ": starting."
    )
    UI.vprint(
        0,
        "\nStep 1 : Building vector data for tile "
        + FNAMES.short_latlon(tile.lat, tile.lon)
        + " : \n--------\n",
    )
    timer = time.time()

    if not os.path.exists(tile.build_dir):
        os.makedirs(tile.build_dir)
    if not os.path.exists(FNAMES.osm_dir(tile.lat, tile.lon)):
        os.makedirs(FNAMES.osm_dir(tile.lat, tile.lon))
    node_file = FNAMES.input_node_file(tile)
    poly_file = FNAMES.input_poly_file(tile)
    vector_map = VECT.Vector_Map()

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    # Airports
    (apt_array, apt_area) = include_airports(vector_map, tile)
    UI.vprint(
        1, "   Number of edges at this point:", len(vector_map.dico_edges)
    )

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    if O4_ESP_Globals.build_for_ESP and os.path.isfile(O4_Config_Utils.ESP_scenproc_loc):
        include_scenproc(tile)

    # Roads
    include_roads(vector_map, tile, apt_array, apt_area)
    if tile.road_level:
        UI.vprint(
            1, "   Number of edges at this point:", len(vector_map.dico_edges)
        )

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    # Sea
    include_sea(vector_map, tile)
    UI.vprint(
        1, "   Number of edges at this point:", len(vector_map.dico_edges)
    )

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    # Water
    include_water(vector_map, tile)
    UI.vprint(
        1, "   Number of edges at this point:", len(vector_map.dico_edges)
    )

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    # Buildings
    # include_buildings(vector_map)
    # if UI.red_flag: UI.exit_message_and_bottom_line(); return 0

    # Orthogrid
    UI.vprint(0, "-> Inserting edges related to the orthophotos grid")
    xgrid = set()  # x coordinates of vertical grid lines
    ygrid = set()  # y coordinates of horizontal grid lines
    (til_xul, til_yul) = GEO.wgs84_to_orthogrid(
        tile.lat + 1, tile.lon, tile.mesh_zl
    )
    (til_xlr, til_ylr) = GEO.wgs84_to_orthogrid(
        tile.lat, tile.lon + 1, tile.mesh_zl
    )
    for til_x in range(til_xul + 16, til_xlr + 1, 16):
        pos_x = til_x / (2 ** (tile.mesh_zl - 1)) - 1
        xgrid.add(pos_x * 180 - tile.lon)
    for til_y in range(til_yul + 16, til_ylr + 1, 16):
        pos_y = 1 - (til_y) / (2 ** (tile.mesh_zl - 1))
        ygrid.add(360 / pi * atan(exp(pi * pos_y)) - 90 - tile.lat)

    xgrid.add(0)
    xgrid.add(1)
    ygrid.add(0)
    ygrid.add(1)
    xgrid = list(sorted(xgrid))
    ygrid = list(sorted(ygrid))
    eps = 2 ** -5
    ortho_network = geometry.MultiLineString(
        [geometry.LineString([(x, 0.0 - eps), (x, 1.0 + eps)]) for x in xgrid]
        + [geometry.LineString([(0.0 - eps, y), (1.0 + eps, y)]) for y in ygrid]
    )
    vector_map.encode_MultiLineString(
        ortho_network, tile.dem.alt_vec, "DUMMY", check=True, skip_cut=True
    )

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    # Gluing edges
    UI.vprint(0, "-> Inserting additional boundary edges for gluing")
    segs = 2048
    gluing_network = geometry.MultiLineString(
        [
            geometry.LineString(
                [(x, 0) for x in numpy.arange(0, segs + 1) / segs]
            ),
            geometry.LineString(
                [(x, 1) for x in numpy.arange(0, segs + 1) / segs]
            ),
            geometry.LineString(
                [(0, y) for y in numpy.arange(0, segs + 1) / segs]
            ),
            geometry.LineString(
                [(1, y) for y in numpy.arange(0, segs + 1) / segs]
            ),
        ]
    )
    vector_map.encode_MultiLineString(
        gluing_network, tile.dem.alt_vec, "DUMMY", check=True, skip_cut=True
    )

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0
    UI.vprint(0, "-> Transcription to the files ", poly_file, "and .node")
    if not vector_map.seeds:
        if tile.dem.alt_dem.max() >= 1:
            vector_map.seeds["SEA"] = [numpy.array([1000, 1000])]
        else:
            vector_map.seeds["SEA"] = [numpy.array([0.5, 0.5])]
    vector_map.snap_to_grid(9)
    vector_map.write_node_file(node_file)
    vector_map.write_poly_file(poly_file)

    UI.vprint(
        1, "\nFinal number of constrained edges :", len(vector_map.dico_edges)
    )
    UI.timings_and_bottom_line(timer)
    UI.logprint(
        "Step 1 for tile lat=", tile.lat, ", lon=", tile.lon, ": normal exit."
    )
    return 1
##############################################################################

##############################################################################
# Overpass sub-bbox size for ScenProc downloads (degrees).
# Smaller values → more parallel requests, lower per-request data volume,
# less risk of hitting the Overpass memory limit.
_SCENPROC_BBOX_STEP = 0.5

# How many times to retry an empty or failed response per sub-bbox.
_SCENPROC_MAX_RETRIES = 8


async def _fetch_scenproc_bbox(
    client: "httpx.AsyncClient",
    queries: tuple,
    bbox: tuple,
    out_path: str,
    semaphore: asyncio.Semaphore,
) -> bool:
    """
    Download one sub-bbox from Overpass and write it to *out_path*.

    Retries up to _SCENPROC_MAX_RETRIES times on:
      • network errors
      • HTTP 5xx
      • empty-but-valid responses (no <node>/<way>/<relation>)

    Returns True on success, False if all retries are exhausted.
    """
    if isinstance(queries, str):
        overpass_query = queries + str(bbox) + ";"
    else:
        overpass_query = "".join(q + str(bbox) + ";" for q in queries)

    servers = list(OSM.overpass_servers.values())
    tentative = 0

    while tentative < _SCENPROC_MAX_RETRIES:
        base_url = servers[tentative % len(servers)]
        url = base_url + "?data=(" + overpass_query + ");(._;>>;);out meta;"
        try:
            async with semaphore:
                resp = await client.get(url)

            if resp.status_code == 200:
                content = resp.content
                if b"</osm>" not in content[-10:] and b"</OSM>" not in content[-10:]:
                    UI.vprint(2, f"    ScenProc OSM: corrupted reply for {bbox}, retrying...")
                elif OSM._is_empty_osm(content):
                    # Server was busy, returned metadata-only response.
                    UI.vprint(
                        1,
                        f"    ScenProc OSM: empty response for {bbox} "
                        f"(attempt {tentative + 1}/{_SCENPROC_MAX_RETRIES}), retrying...",
                    )
                else:
                    # Good data — write to file.
                    with open(out_path, "wb") as f:
                        f.write(content)
                    UI.vprint(2, f"    ScenProc OSM: saved {out_path}")
                    return True

            elif resp.status_code in (400, 404):
                UI.vprint(1, f"    ScenProc OSM: server rejected query for {bbox} ({resp.status_code})")
                return False    # non-retriable
            else:
                UI.vprint(1, f"    ScenProc OSM: HTTP {resp.status_code} for {bbox}, retrying...")

        except Exception as exc:
            UI.vprint(1, f"    ScenProc OSM: error for {bbox}: {exc}, retrying...")

        tentative += 1
        if tentative < _SCENPROC_MAX_RETRIES:
            await asyncio.sleep(2 ** tentative)

    UI.vprint(
        1,
        f"    ScenProc OSM: giving up on {bbox} after "
        f"{_SCENPROC_MAX_RETRIES} attempts.",
    )
    return False


async def _download_all_scenproc_bboxes(
    queries: tuple,
    tile_lat: float,
    tile_lon: float,
    out_dir: str,
) -> int:
    """
    Download OSM data for all sub-bboxes covering the tile in parallel.

    Returns the number of successfully downloaded files.
    """
    # Build list of (bbox, out_path) pairs.
    jobs: list[tuple[tuple, str]] = []
    step = _SCENPROC_BBOX_STEP
    i = 0
    min_lon = tile_lon
    while min_lon < tile_lon + 1:
        max_lon = min(min_lon + step, tile_lon + 1)
        j = 0
        min_lat = tile_lat
        while min_lat < tile_lat + 1:
            max_lat = min(min_lat + step, tile_lat + 1)
            bbox = (min_lat, min_lon, max_lat, max_lon)
            out_path = os.path.join(out_dir, f"scenproc_osm_data{i}_{j}.osm")
            jobs.append((bbox, out_path))
            min_lat = max_lat
            j += 1
        min_lon = max_lon
        i += 1

    # Limit concurrency: at most 4 simultaneous connections to Overpass.
    # More than ~4 tends to trigger rate-limiting on public servers.
    semaphore = asyncio.Semaphore(4)

    async with httpx.AsyncClient(
        http2=True,
        timeout=60.0,
        follow_redirects=True,
        trust_env=False,
    ) as client:
        tasks = [
            _fetch_scenproc_bbox(client, queries, bbox, out_path, semaphore)
            for bbox, out_path in jobs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)

    ok = sum(1 for r in results if r)
    UI.vprint(1, f"    ScenProc OSM: {ok}/{len(jobs)} sub-bboxes downloaded successfully.")
    return ok


def include_scenproc(tile) -> None:
    """
    Download OSM data required by ScenProc for the given tile.

    Changes vs. the original implementation
    ────────────────────────────────────────
    • All sub-bbox requests are fired concurrently (asyncio + httpx HTTP/2)
      instead of sequentially, reducing wall-clock time roughly proportional
      to the number of sub-bboxes (4 for a default 1°×1° tile with step=0.5°).
    • Empty-but-valid Overpass responses (metadata only, no map elements) are
      detected and retried automatically up to _SCENPROC_MAX_RETRIES times.
    • Files are written only after a successful, non-empty response, so the
      scenproc_osm_data directory never contains stale placeholder files from
      a previous failed run.
    • Falls back gracefully to the old sequential requests path when httpx is
      not available.
    """
    if not _has_httpx:
        # Graceful degradation: run the original synchronous code path.
        _include_scenproc_sync_fallback(tile)
        return

    print(
        "Downloading OSM data for ScenProc using HTTP/2 parallel requests..."
    )

    scenproc_osm_dir = os.path.join(
        FNAMES.osm_dir(tile.lat, tile.lon), "scenproc_osm_data"
    )
    os.makedirs(scenproc_osm_dir, exist_ok=True)

    # Delete any stale files from a previous (possibly failed) run so that
    # build_for_ESP does not process empty OSM files.
    for fname in os.listdir(scenproc_osm_dir):
        if fname.endswith(".osm"):
            fpath = os.path.join(scenproc_osm_dir, fname)
            try:
                with open(fpath, "rb") as f:
                    content = f.read()
                if OSM._is_empty_osm(content):
                    os.remove(fpath)
                    UI.vprint(
                        1,
                        f"    ScenProc OSM: removed stale empty file {fname}",
                    )
            except OSError:
                pass

    queries = (
        'way["natural"]',
        'way["landuse"]',
        'way["leisure"]',
        'way["building"]',
        'rel["natural"]',
        'rel["landuse"]',
        'rel["leisure"]',
        'rel["building"]',
    )

    # asyncio.run works correctly when called from a worker thread
    # (which is always the case here — build_poly_file runs in a Thread).
    asyncio.run(
        _download_all_scenproc_bboxes(
            queries,
            tile.lat,
            tile.lon,
            scenproc_osm_dir,
        )
    )


def _include_scenproc_sync_fallback(tile) -> None:
    """
    Original sequential implementation kept as a fallback when httpx is absent.
    Detects and skips empty Overpass responses.
    """
    print(
        "Downloading OSM data for ScenProc (sequential fallback, no httpx)..."
    )
    scenproc_osm_dir = os.path.join(
        FNAMES.osm_dir(tile.lat, tile.lon), "scenproc_osm_data"
    )
    os.makedirs(scenproc_osm_dir, exist_ok=True)

    OFFSET = _SCENPROC_BBOX_STEP
    buildings_and_trees_tags = (
        'way["natural"]',
        'way["landuse"]',
        'way["leisure"]',
        'way["building"]',
        'rel["natural"]',
        'rel["landuse"]',
        'rel["leisure"]',
        'rel["building"]',
    )

    i = 0
    min_lon = tile.lon
    while min_lon < tile.lon + 1:
        max_lon = min(min_lon + OFFSET, tile.lon + 1)
        j = 0
        min_lat = tile.lat
        while min_lat < tile.lat + 1:
            max_lat = min(min_lat + OFFSET, tile.lat + 1)
            bbox = (min_lat, min_lon, max_lat, max_lon)
            UI.vprint(
                1,
                f"    Downloading OSM data from {min_lat},{min_lon} "
                f"to {max_lat},{max_lon}",
            )
            # get_overpass_data already retries empty responses.
            response = OSM.get_overpass_data(buildings_and_trees_tags, bbox)
            if response:
                file_name = os.path.join(
                    scenproc_osm_dir,
                    f"scenproc_osm_data{i}_{j}.osm",
                )
                with open(file_name, "wb") as f:
                    f.write(response)
                UI.vprint(1, "    Download successful")
            else:
                UI.vprint(
                    1,
                    f"    Warning: failed to download OSM data for bbox "
                    f"{bbox}, skipping.",
                )
            min_lat = max_lat
            j += 1
        min_lon = max_lon
        i += 1

##############################################################################

################################################################################
def include_airports(vector_map, tile):
    UI.vprint(0, "-> Dealing with airports")
    airport_layer = OSM.OSM_layer()
    queries = [('node["aeroway"]', 'way["aeroway"]', 'rel["aeroway"]')]
    tags_of_interest = ["all"]
    if not OSM.OSM_queries_to_OSM_layer(
        queries,
        airport_layer,
        tile.lat,
        tile.lon,
        tags_of_interest,
        cached_suffix="airports",
    ):
        return (0, 0)
    dico_airports = {}
    APT.discover_airport_names(airport_layer, dico_airports)
    APT.attach_surfaces_to_airports(airport_layer, dico_airports)
    APT.sort_and_reconstruct_runways(tile, airport_layer, dico_airports)
    APT.discard_unwanted_airports(tile, dico_airports)
    APT.build_hangar_areas(tile, airport_layer, dico_airports)
    APT.build_apron_areas(tile, airport_layer, dico_airports)
    APT.build_taxiway_areas(tile, airport_layer, dico_airports)
    APT.update_airport_boundaries(tile, dico_airports)
    APT.list_airports_and_runways(dico_airports)
    UI.vprint(1, "   Loading elevation data and smoothing it over airports.")
    tile.dem = DEM.DEM(
        tile.lat,
        tile.lon,
        tile.custom_dem,
        tile.fill_nodata or "to zero",
        info_only=False,
    )
    APT.smooth_raster_over_airports(tile, dico_airports)
    (patches_area, patches_list) = include_patches(vector_map, tile)
    runway_taxiway_apron_area = APT.encode_runways_taxiways_and_aprons(
        tile, airport_layer, dico_airports, vector_map, patches_list
    )
    treated_area = ops.unary_union([patches_area, runway_taxiway_apron_area])
    APT.encode_hangars(tile, dico_airports, vector_map, patches_list)
    APT.flatten_helipads(airport_layer, vector_map, tile, treated_area)
    # APT.encode_aprons(tile,dico_airports,vector_map)
    apt_array = APT.build_airport_array(tile, dico_airports)
    return (apt_array, treated_area)


################################################################################
def include_roads(vector_map, tile, apt_array, apt_area):
    def road_is_too_much_banked(way, filtered_segs):
        (col, row) = numpy.minimum(
            numpy.maximum(numpy.round(way[0] * 1000), 0), 1000
        )
        if apt_array[int(1000 - row), int(col)]:
            return True
        (col, row) = numpy.minimum(
            numpy.maximum(numpy.round(way[-1] * 1000), 0), 1000
        )
        if apt_array[int(1000 - row), int(col)]:
            return True
        if filtered_segs >= tile.max_levelled_segs:
            return False
        return (
            numpy.abs(
                tile.dem.alt_vec(way)
                - tile.dem.alt_vec(VECT.shift_way(way, tile.lane_width))
            )
            >= tile.road_banking_limit
        ).any()

    def alt_vec_shift(way):
        return tile.dem.alt_vec(VECT.shift_way(way, tile.lane_width))

    if not tile.road_level:
        return
    UI.vprint(0, "-> Dealing with roads")
    tags_of_interest = ["bridge", "tunnel"]
    # Need to evaluate if including bridges is better or worse
    tags_for_exclusion = set(["bridge", "tunnel"])
    # tags_for_exclusion=set(["tunnel"])
    road_layer = OSM.OSM_layer()
    queries = [
        'way["highway"="motorway"]',
        'way["highway"="trunk"]',
        'way["highway"="primary"]',
        'way["highway"="secondary"]',
        'way["railway"="rail"]',
        'way["railway"="narrow_gauge"]',
    ]
    if not OSM.OSM_queries_to_OSM_layer(
        queries,
        road_layer,
        tile.lat,
        tile.lon,
        tags_of_interest,
        cached_suffix="big_roads",
    ):
        return 0
    UI.vprint(1, "    * Checking which large roads need levelling.")
    (road_network_banked, road_network_flat) = OSM.OSM_to_MultiLineString(
        road_layer,
        tile.lat,
        tile.lon,
        tags_for_exclusion,
        road_is_too_much_banked,
    )
    if UI.red_flag:
        return 0
    if tile.road_level >= 2:
        road_layer = OSM.OSM_layer()
        queries = ['way["highway"="tertiary"]']
        if tile.road_level >= 3:
            queries += [
                'way["highway"="unclassified"]',
                'way["highway"="residential"]',
            ]
        if tile.road_level >= 4:
            queries += ['way["highway"="service"]']
        if tile.road_level >= 5:
            queries += ['way["highway"="track"]']
        if not OSM.OSM_queries_to_OSM_layer(
            queries,
            road_layer,
            tile.lat,
            tile.lon,
            tags_of_interest,
            cached_suffix="small_roads",
        ):
            return 0
        UI.vprint(1, "    * Checking which smaller roads need levelling.")
        timer = time.time()
        (
            road_network_banked_2,
            road_network_flat_2,
        ) = OSM.OSM_to_MultiLineString(
            road_layer,
            tile.lat,
            tile.lon,
            tags_for_exclusion,
            road_is_too_much_banked,
        )
        UI.vprint(3, "Time for check :", time.time() - timer)
        road_network_banked = geometry.MultiLineString(
            list(road_network_banked.geoms) + list(road_network_banked_2.geoms)
        )
    if not road_network_banked.is_empty:
        UI.vprint(1, "    * Buffering banked road network as multipolygon.")
        timer = time.time()
        road_area = VECT.improved_buffer(
            road_network_banked.difference(
                VECT.improved_buffer(apt_area, tile.lane_width + 2, 0, 0)
            ),
            tile.lane_width,
            2,
            0.5,
            show_progress=True,
        )
        UI.vprint(3, "Time for improved buffering:", time.time() - timer)
        if UI.red_flag:
            return 0
        UI.vprint(1, "      Encoding it.")
        vector_map.encode_MultiPolygon(
            road_area, alt_vec_shift, "INTERP_ALT", check=True, refine=100
        )
        if UI.red_flag:
            return 0
    return 1


################################################################################
def include_sea(vector_map, tile):
    UI.vprint(0, "-> Dealing with coastline")
    sea_layer = OSM.OSM_layer()
    custom_source = False
    custom_coastline = FNAMES.custom_coastline(tile.lat, tile.lon)
    custom_coastline_dir = FNAMES.custom_coastline_dir(tile.lat, tile.lon)
    if os.path.isfile(custom_coastline):
        UI.vprint(1, "    * User defined custom coastline data detected.")
        sea_layer.update_dicosm(
            custom_coastline, input_tags=None, target_tags=None
        )
        custom_source = True
    elif os.path.isdir(custom_coastline_dir):
        UI.vprint(
            1,
            "    * User defined custom coastline data detected ",
            "(multiple files).",
        )
        for osm_file in os.listdir(custom_coastline_dir):
            UI.vprint(2, "      ", osm_file)
            sea_layer.update_dicosm(
                os.path.join(custom_coastline_dir, osm_file),
                input_tags=None,
                target_tags=None,
            )
            sea_layer.write_to_file(custom_coastline)
        custom_source = True
    else:
        queries = ['way["natural"="coastline"]']
        tags_of_interest = []
        if not OSM.OSM_queries_to_OSM_layer(
            queries,
            sea_layer,
            tile.lat,
            tile.lon,
            tags_of_interest,
            cached_suffix="coastline",
        ):
            return 0
    coastline = OSM.OSM_to_MultiLineString(sea_layer, tile.lat, tile.lon)
    if not coastline.is_empty:
        # 1) encoding the coastline
        UI.vprint(1, "    * Encoding coastline.")
        vector_map.encode_MultiLineString(
            VECT.cut_to_tile(coastline, strictly_inside=True),
            tile.dem.alt_vec,
            "SEA",
            check=True,
            refine=False,
        )
        UI.vprint(3, "...done.")
        # 2) finding seeds (transform multilinestring coastline to polygon
        # coastline linemerge being expensive we first set aside what is
        # already known to be closed loops
        UI.vprint(1, "    * Reconstructing its topology.")
        loops = geometry.MultiLineString(
            [line for line in coastline.geoms if line.is_ring]
        )
        remainder = VECT.ensure_MultiLineString(
            VECT.cut_to_tile(
                geometry.MultiLineString(
                    [line for line in coastline.geoms if not line.is_ring]
                ),
                strictly_inside=True,
            )
        )
        UI.vprint(3, "Linemerge...")
        if not remainder.is_empty:
            remainder = VECT.ensure_MultiLineString(ops.linemerge(remainder))
        UI.vprint(3, "...done.")
        coastline = geometry.MultiLineString(
            list(remainder.geoms) + list(loops.geoms)
        )
        sea_area = VECT.ensure_MultiPolygon(
            VECT.coastline_to_MultiPolygon(
                coastline, tile.lat, tile.lon, custom_source
            )
        )
        if sea_area.geoms:
            UI.vprint(
                1, "      Found ", len(sea_area.geoms), "contiguous patch(es)."
            )
        for polygon in sea_area.geoms:
            seed = numpy.array(polygon.representative_point().coords[0])
            if "SEA" in vector_map.seeds:
                vector_map.seeds["SEA"].append(seed)
            else:
                vector_map.seeds["SEA"] = [seed]


################################################################################
def include_water(vector_map, tile):
    large_lake_threshold = (
        tile.max_area * 1e6 / (GEO.lat_to_m * GEO.lon_to_m(tile.lat + 0.5))
    )

    def filter_large_lakes(pol, osmid, dicosmtags):
        if pol.area < large_lake_threshold:
            return False
        area = int(pol.area * GEO.lat_to_m * GEO.lon_to_m(tile.lat + 0.5) / 1e6)
        if (osmid in dicosmtags) and ("name" in dicosmtags[osmid]):
            if dicosmtags[osmid]["name"] in good_imagery_list:
                UI.vprint(
                    1,
                    "      * ",
                    dicosmtags[osmid]["name"],
                    "kept will complete imagery although it is",
                    area,
                    "km^2.",
                )
                return False
            else:
                UI.vprint(
                    1,
                    "      * ",
                    dicosmtags[osmid]["name"],
                    "will be masked like the sea due to its large area of",
                    area,
                    "km^2.",
                )
                return True
        else:
            pt = (
                pol.exterior.coords[0]
                if "Multi" not in pol.geom_type
                else pol.geoms[0].exterior.coords[0]
            )
            UI.vprint(
                1,
                "      * ",
                "Some large OSM water patch close to lat=",
                "{:.2f}".format(pt[1] + tile.lon),
                "lon=",
                "{:.2f}".format(pt[0] + tile.lat),
                "will be masked due to its large area of",
                area,
                "km^2.",
            )
            return True

    UI.vprint(0, "-> Dealing with inland water")
    water_layer = OSM.OSM_layer()
    custom_water = FNAMES.custom_water(tile.lat, tile.lon)
    custom_water_dir = FNAMES.custom_water_dir(tile.lat, tile.lon)
    if os.path.isfile(custom_water):
        UI.vprint(1, "    * User defined custom water data detected.")
        water_layer.update_dicosm(
            custom_water, input_tags=None, target_tags=None
        )
    elif os.path.isdir(custom_water_dir):
        UI.vprint(
            1, "    * User defined custom water data detected (multiple files)."
        )
        for osm_file in os.listdir(custom_water_dir):
            UI.vprint(2, "      ", osm_file)
            water_layer.update_dicosm(
                os.path.join(custom_water_dir, osm_file),
                input_tags=None,
                target_tags=None,
            )
            water_layer.write_to_file(custom_water)
    else:
        queries = [
            'rel["natural"="water"]',
            'rel["waterway"="riverbank"]',
            'way["natural"="water"]',
            'way["waterway"="riverbank"]',
            'way["waterway"="dock"]',
        ]
        tags_of_interest = ["name"]
        if not OSM.OSM_queries_to_OSM_layer(
            queries,
            water_layer,
            tile.lat,
            tile.lon,
            tags_of_interest,
            cached_suffix="water",
        ):
            return 0
    UI.vprint(1, "    * Building water multipolygon.")
    (water_area, sea_equiv_area) = OSM.OSM_to_MultiPolygon(
        water_layer, tile.lat, tile.lon, filter_large_lakes
    )
    if not water_area.is_empty:
        UI.vprint(1, "      Cleaning it.")
        try:
            (idx_water, dico_water) = VECT.MultiPolygon_to_Indexed_Polygons(
                water_area, merge_overlappings=tile.clean_bad_geometries
            )
        except:
            return 0
        UI.vprint(
            2, "      Number of water Multipolygons : " + str(len(dico_water))
        )
        UI.vprint(1, "      Encoding it.")
        vector_map.encode_MultiPolygon(
            dico_water,
            tile.dem.alt_vec,
            "WATER",
            area_limit=tile.min_area / 10000,
            simplify=tile.water_simplification * GEO.m_to_lat,
            check=True,
        )
    if not sea_equiv_area.is_empty:
        UI.vprint(
            1, "      Separate treatment for larger pieces requiring masks."
        )
        try:
            (idx_water, dico_water) = VECT.MultiPolygon_to_Indexed_Polygons(
                sea_equiv_area, merge_overlappings=tile.clean_bad_geometries
            )
        except:
            return 0
        UI.vprint(
            2, "      Number of water Multipolygons : " + str(len(dico_water))
        )
        UI.vprint(1, "      Encoding them.")
        vector_map.encode_MultiPolygon(
            dico_water,
            tile.dem.alt_vec,
            "SEA_EQUIV",
            area_limit=tile.min_area / 10000,
            simplify=tile.water_simplification * GEO.m_to_lat,
            check=True,
        )
    return 1


################################################################################
def include_patches(vector_map, tile):
    def tanh_profile(alpha, x):
        return (numpy.tanh((x - 0.5) * alpha) / numpy.tanh(0.5 * alpha) + 1) / 2

    def spline_profile(x):
        return 3 * x ** 2 - 2 * x ** 3

    def plane_profile(x):
        return x

    patches_list = []
    patches_area = geometry.Polygon()
    patch_dir = FNAMES.patch_dir(tile.lat, tile.lon)
    if not os.path.exists(patch_dir):
        return (patches_area, patches_list)
    for pfile_name in os.listdir(patch_dir):
        if pfile_name[-10:] != ".patch.osm":
            continue
        UI.vprint(1, "   Patching", pfile_name)
        patch_layer = OSM.OSM_layer()
        try:
            patch_layer.update_dicosm(
                os.path.join(patch_dir, pfile_name),
                input_tags=None,
                target_tags=None,
            )
        except:
            UI.vprint(1, "     Error in treating", pfile_name, ", skipped.")
        patches_list.append(pfile_name[:-10])
        dw = patch_layer.dicosmw
        dn = patch_layer.dicosmn
        df = patch_layer.dicosmfirst
        dt = patch_layer.dicosmtags
        waylist = tuple(df["w"].intersection(dt["w"])) + tuple(
            df["w"].difference(dt["w"])
        )
        for wayid in waylist:
            way = numpy.array(
                [dn[nodeid] for nodeid in dw[wayid]], dtype=float
            )
            way = way - numpy.array([[tile.lon, tile.lat]])
            alti_way_orig = tile.dem.alt_vec(way)
            cplx_way = False
            if wayid in dt["w"]:
                wtags = dt["w"][wayid]
                if "cst_alt_abs" in wtags:
                    alti_way = numpy.ones((len(way), 1)) * float(
                        wtags["cst_alt_abs"]
                    )
                elif "cst_alt_rel" in wtags:
                    alti_way = numpy.ones((len(way), 1)) * (
                        numpy.mean(tile.dem.alt_vec(way))
                        + float(wtags["cst_alt_rel"])
                    )
                elif "var_alt_rel" in wtags:
                    alti_way = alti_way_orig + float(wtags["var_alt_rel"])
                elif (
                    "altitude" in wtags
                ):  # deprecated : for backward compatibility only
                    try:
                        alti_way = numpy.ones((len(way), 1)) * float(
                            wtags["altitude"]
                        )
                    except:
                        alti_way = numpy.ones((len(way), 1)) * numpy.mean(
                            tile.dem.alt_vec(way)
                        )
                elif "altitude_high" in wtags:
                    cplx_way = True
                    if len(way) != 5 or (way[0] != way[-1]).all():
                        UI.vprint(
                            1,
                            "    Wrong number of nodes or non closed way for ",
                            "a altitude_high/altitude_low polygon, skipped.",
                        )
                        continue
                    short_high = way[-2:]
                    short_low = way[1:3]
                    try:
                        altitude_high = float(wtags["altitude_high"])
                        altitude_low = float(wtags["altitude_low"])
                    except:
                        altitude_high = tile.dem.alt_vec(short_high).mean()
                        altitude_low = tile.dem.alt_vec(short_low).mean()
                    try:
                        cell_size = float(wtags["cell_size"])
                    except:
                        cell_size = 10
                    try:
                        rnw_profile = wtags["profile"]
                    except:
                        rnw_profile = "plane"
                    try:
                        alpha = float(wtags["steepness"])
                    except:
                        alpha = 2
                    if "tanh" in rnw_profile:
                        rnw_profile = lambda x: tanh_profile(alpha, x)
                    elif rnw_profile == "spline":
                        rnw_profile = spline_profile
                    else:
                        rnw_profile = plane_profile
                    rnw_vect = (
                        short_high[0]
                        + short_high[1]
                        - short_low[0]
                        - short_low[1]
                    ) / 2
                    rnw_length = (
                        sqrt(
                            rnw_vect[0] ** 2 * cos(tile.lat * pi / 180) ** 2
                            + rnw_vect[1] ** 2
                        )
                        * 111120
                    )
                    cuts_long = int(rnw_length / cell_size)
                    if cuts_long:
                        cuts_long += 1
                        way = numpy.array(
                            [
                                way[0] + i / cuts_long * (way[1] - way[0])
                                for i in range(cuts_long)
                            ]
                            + [way[1]]
                            + [
                                way[2] + i / cuts_long * (way[3] - way[2])
                                for i in range(cuts_long)
                            ]
                            + [way[3], way[4]]
                        )
                        alti_way = numpy.array(
                            [
                                altitude_high
                                - rnw_profile(i / cuts_long)
                                * (altitude_high - altitude_low)
                                for i in range(cuts_long + 1)
                            ]
                        )
                        alti_way = numpy.hstack(
                            [alti_way, alti_way[::-1], alti_way[0]]
                        )
                else:
                    alti_way = alti_way_orig
            else:
                alti_way = alti_way_orig
            if not cplx_way:
                for i in range(len(way)):
                    nodeid = dw[wayid][i]
                    if nodeid in dt["n"]:
                        ntags = dt["n"][nodeid]
                        if "alt_abs" in ntags:
                            alti_way[i] = float(ntags["alt_abs"])
                        elif "alt_rel" in ntags:
                            alti_way[i] = alti_way_orig[i] + float(
                                ntags["alt_rel"]
                            )
            alti_way = alti_way.reshape((len(alti_way), 1))
            if (way[0] == way[-1]).all():
                try:
                    pol = geometry.Polygon(way)
                    if pol.is_valid and pol.area:
                        patches_area = patches_area.union(pol)
                        vector_map.insert_way(
                            numpy.hstack([way, alti_way]),
                            "INTERP_ALT",
                            check=True,
                        )
                        seed = numpy.array(pol.representative_point().coords[0])
                        if "INTERP_ALT" in vector_map.seeds:
                            vector_map.seeds["INTERP_ALT"].append(seed)
                        else:
                            vector_map.seeds["INTERP_ALT"] = [seed]
                        if cplx_way and cuts_long:
                            for i in range(1, cuts_long):
                                id0 = vector_map.dico_nodes[tuple(way[i])]
                                id1 = vector_map.dico_nodes[tuple(way[-2 - i])]
                                vector_map.insert_edge(
                                    id0,
                                    id1,
                                    vector_map.dico_attributes["DUMMY"],
                                )
                    else:
                        UI.vprint(2, "     Skipping invalid patch polygon.")
                except:
                    UI.vprint(2, "     Skipping invalid patch polygon.")
            else:
                vector_map.insert_way(
                    numpy.hstack([way, alti_way]), "DUMMY", check=True
                )
    for pdir_name in os.listdir(patch_dir):
        if not os.path.isdir(os.path.join(patch_dir, pdir_name)):
            continue
        UI.vprint(1, "   Including OBJ8 objects from", pdir_name)
        patches_list.append(pdir_name)
        for pfile_name in os.listdir(os.path.join(patch_dir, pdir_name)):
            pfile_namelong = os.path.join(patch_dir, pdir_name, pfile_name)
            try:
                pfile = open(pfile_namelong, "r")
            except:
                continue
            firstline = pfile.readline()
            if not "ANCHOR" in firstline:
                UI.vprint(
                    1,
                    "     Object ",
                    pfile_name,
                    " is missing and ANCHOR in first line, skipping it.",
                )
                continue
            pfile.close()
            try:
                (lon_anchor, lat_anchor, alt_anchor, heading_anchor) = [
                    float(x) for x in firstline.split()[1:]
                ]
            except:
                try:
                    (lon_anchor, lat_anchor, heading_anchor) = [
                        float(x) for x in firstline.split()[1:]
                    ]
                    alt_anchor = tile.dem.alt(
                        (lon_anchor - tile.lon, lat_anchor - tile.lat)
                    )
                except:
                    UI.vprint(
                        1,
                        "     Anchor wrongly encode for : ",
                        pfile_name,
                        " skipping that one.",
                    )
                    continue
            patches_area = patches_area.union(
                keep_obj8(
                    lat_anchor,
                    lon_anchor,
                    alt_anchor,
                    heading_anchor,
                    pfile_namelong,
                    vector_map,
                    tile,
                )
            )
    return (patches_area, patches_list)


################################################################################
def keep_obj8(
    lat_anchor,
    lon_anchor,
    alt_anchor,
    heading_anchor,
    objfile_name,
    vector_map,
    tile,
):
    dico_idx_nodes = {}
    idx_node = 0
    dico_index = {}
    index = 0
    latscale = GEO.m_to_lat
    lonscale = latscale / cos(lat_anchor * pi / 180)
    f = open(objfile_name, "r")
    for line in f.readlines():
        if line[0:2] == "VT":
            (xo, yo, zo) = [float(s) for s in line.split()[1:4]]
            Xo = xo * cos(heading_anchor * pi / 180) - zo * sin(
                heading_anchor * pi / 180
            )
            Zo = xo * sin(heading_anchor * pi / 180) + zo * cos(
                heading_anchor * pi / 180
            )
            y = numpy.round(lat_anchor - latscale * float(Zo) - tile.lat, 7)
            x = numpy.round(lon_anchor + lonscale * float(Xo) - tile.lon, 7)
            z = yo + alt_anchor
            dico_idx_nodes[idx_node] = vector_map.insert_node(x, y, z)
            idx_node += 1
        elif line[0:3] == "IDX":
            dico_index[index] = [int(x) for x in line.split()[1:]]
            index += 1
        elif line[0:4] == "TRIS":
            (offset, count) = [int(x) for x in line.split()[1:3]]
            list = []
            count_tmp = 0
            try:
                polist = []
                while count_tmp < count:
                    list += dico_index[offset]
                    count_tmp += len(dico_index[offset])
                    offset += 1
                for j in range(count // 3):
                    (a, b, c) = [
                        dico_idx_nodes[x] for x in list[3 * j : 3 * j + 3]
                    ]
                    if a == b or a == c or b == c:
                        continue
                    for (initp, endp) in ((a, b), (b, c), (c, a)):
                        vector_map.insert_edge(
                            initp,
                            endp,
                            vector_map.dico_attributes["INTERP_ALT"],
                            check=True,
                        )
                    seed = (
                        numpy.array(vector_map.nodes_dico[a])
                        + numpy.array(vector_map.nodes_dico[b])
                        + numpy.array(vector_map.nodes_dico[c])
                    ) / 3
                    if "INTERP_ALT" in vector_map.seeds:
                        vector_map.seeds["INTERP_ALT"].append(seed)
                    else:
                        vector_map.seeds["INTERP_ALT"] = [seed]
                    polist.append(
                        geometry.Polygon(
                            [
                                vector_map.nodes_dico[a],
                                vector_map.nodes_dico[b],
                                vector_map.nodes_dico[c],
                                vector_map.nodes_dico[a],
                            ]
                        )
                    )
                multipol = VECT.ensure_MultiPolygon(ops.unary_union(polist))
            except:
                pass
    f.close()
    return multipol
