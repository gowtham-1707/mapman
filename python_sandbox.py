import inspect
import ee
import geemap.foliumap as geemap
from rapidfuzz import process

class function_registry:
    #FloodRiskMapper:
    class_palette = {
        10: "#228B22",  # Tree cover — Forest green
        20: "#8B4513",  # Shrubland — Saddle brown
        30: "#FFD700",  # Grassland — Gold
        40: "#FF8C00",  # Cropland — Dark orange
        50: "#DC143C",  # Built-up — Crimson
        60: "#A9A9A9",  # Bare — Dark grey
        70: "#FFFFFF",  # Snow/Ice — White
        80: "#1E90FF",  # Water — Dodger blue
        90: "#00CED1",  # Wetland — Dark turquoise
        95: "#32CD32",  # Mangroves — Lime green
        100: "#8B0000", # Moss & lichen — Dark red
    }

    # Labels for legend
    
    class_labels = {
        10: "Tree cover",
        20: "Shrubland",
        30: "Grassland",
        40: "Cropland",
        50: "Built-up",
        60: "Bare",
        70: "Snow/Ice",
        80: "Water",
        90: "Wetland",
        95: "Mangroves",
        100: "Moss & Lichen",
    }
    
    @staticmethod
    def get_admin_dataset(level):
        level_map = {
            "country": ("FAO/GAUL/2015/level0", "ADM0_NAME"),
            "state":   ("FAO/GAUL/2015/level1", "ADM1_NAME"),
            "district":("FAO/GAUL/2015/level2", "ADM2_NAME")
        }
        if level not in level_map:
            raise ValueError("Level must be 'country', 'state', or 'district'")
        return level_map[level]

    @staticmethod
    def get_all_names(dataset, property_name):
        return list(set(dataset.aggregate_array(property_name).getInfo()))

    @staticmethod
    def fuzzy_match_name(user_input, name_list):
        match, score, _ = process.extractOne(user_input, name_list)
        return match

    @staticmethod
    def get_admin_boundary(place_name, level="district"):
        dataset_id, property_name = function_registry.get_admin_dataset(level.lower())
        dataset = ee.FeatureCollection(dataset_id)

        # 1. Try exact match first
        filtered = dataset.filter(ee.Filter.eq(property_name, place_name.title()))
        if filtered.size().getInfo() > 0:
            print(f"Exact match found: {place_name}")
            return filtered

        # 2. Fuzzy match fallback if u dont want it in future just return none
        print(f"No exact match for '{place_name}', trying fuzzy match...")
        all_names = function_registry.get_all_names(dataset, property_name)
        matched_name = function_registry.fuzzy_match_name(place_name, all_names)
        print(f"Fuzzy matched to: {matched_name}")
        return dataset.filter(ee.Filter.eq(property_name, matched_name))


    # 2️⃣ Multi-level thresholds — now using occurrence for rivers
    @staticmethod
    def get_thresholds(level):
        if level == "country":
            return {
                "vv_threshold": None,   # ignore Sentinel-1
                "use_permanent_water": True,
                "occurrence_threshold": 70,  # % of time it's water
                "scale": 100
            }
        elif level == "state":
            return {
                "vv_threshold": None,   # ignore Sentinel-1
                "use_permanent_water": True,
                "occurrence_threshold": 50,
                "scale": 50
            }
        elif level == "district":
            return {
                "vv_threshold": -17,    # use Sentinel-1 flood detection
                "use_permanent_water": True,
                "occurrence_threshold": 30,
                "scale": 20
            }
        else:
            raise ValueError("Level must be 'country', 'state', or 'district'")


    # 3️⃣ Sentinel-1 dynamic flood mask
    @staticmethod
    def get_recent_surface_water(aoi, start_date, end_date, vv_threshold):
        s1 = ee.ImageCollection("COPERNICUS/S1_GRD") \
            .filterBounds(aoi) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.eq('instrumentMode', 'IW')) \
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
            .select("VV")
        mean_vv = s1.mean().clip(aoi)
        water_mask = mean_vv.lt(vv_threshold).selfMask()
        return water_mask


    # 4️⃣ Permanent river mask from JRC
    @staticmethod
    def get_permanent_water_mask(aoi, occurrence_threshold=50):
        gsw = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
        occurrence = gsw.select("occurrence").clip(aoi)
        return occurrence.gt(occurrence_threshold).selfMask()


    # 5️⃣ Vectorize
    @staticmethod
    def compute_flood_risk_vector(boundary, start_date, end_date, level="district"):
        thresholds = function_registry.get_thresholds(level)
        aoi = boundary.geometry()

        if thresholds["use_permanent_water"]:
            flood_mask = function_registry.get_permanent_water_mask(
                aoi, thresholds["occurrence_threshold"])
        else:
            water = function_registry.get_recent_surface_water(
                aoi, start_date, end_date, vv_threshold=thresholds["vv_threshold"])
            lowlands = function_registry.get_low_elevation_mask(
                aoi, threshold=500)  # Optional DEM for district only
            flood_mask = water.updateMask(lowlands).clip(aoi)

        vectors = flood_mask.reduceToVectors(
            geometry=aoi,
            geometryType='polygon',
            scale=thresholds["scale"],
            maxPixels=1e10
        )

        return vectors


    # DEM mask (used only for district flood risk)
    @staticmethod
    def get_low_elevation_mask(aoi, threshold=500):
        dem = ee.Image("CGIAR/SRTM90_V4").clip(aoi)
        return dem.lt(threshold).selfMask()


    # 6️⃣ Visualize
    @staticmethod
    def Final_flood_risk(place_name, level="district",
                                    start_date="2024-12-01", end_date="2025-01-31"):
        boundary = function_registry.get_admin_boundary(place_name, level)
        vector_flood = function_registry.compute_flood_risk_vector(
            boundary, start_date, end_date, level=level)

        center = boundary.geometry().centroid().coordinates().getInfo()
        Map = geemap.Map(center=[center[1], center[0]], zoom=7)
        Map.addLayer(boundary, {"color": "orange"}, f"{place_name} boundary")
        Map.addLayer(vector_flood, {"color": "blue"}, "Flood / River Zones")
        return Map

    #LandCover:
    
    # # 1️⃣ Admin boundary
    # def get_admin_boundary(place_name, level="district"):
    #     level_map = {
    #         "country": ("FAO/GAUL/2015/level0", "ADM0_NAME"),
    #         "state": ("FAO/GAUL/2015/level1", "ADM1_NAME"),
    #         "district": ("FAO/GAUL/2015/level2", "ADM2_NAME")
    #     }
    #     if level.lower() not in level_map:
    #         raise ValueError("Level must be 'country', 'state', or 'district'")
    #     dataset_id, property_name = level_map[level.lower()]
    #     dataset = ee.FeatureCollection(dataset_id)
    #     return dataset.filter(ee.Filter.stringContains(property_name, place_name.title()))


    # 2️⃣ Thresholds for ESA WorldCover
    @staticmethod
    def get_landcover_thresholds(level):
        if level == "country":
            return {
                "classes": [10,20,30,40,50,60,70,80,90,95,100],
                "scale": 20
            }
        elif level == "state":
            return {
                "classes": [10,20,30,40,50,60,70,80,90,95,100],
                "scale": 20
            }
        elif level == "district":
            return {
                "classes": [10,20,30,40,50,60,70,80,90,95,100],
                "scale": 20
            }
        else:
            raise ValueError("Level must be 'country', 'state', or 'district'")


    # 3️⃣ Updated color palette — boy-friendly and distinct
    



    # 4️⃣ Land cover mask for ESA WorldCover
    @staticmethod
    def get_landcover_mask(aoi, classes):
        lc = ee.Image("ESA/WorldCover/v200/2021").select("Map").clip(aoi)
        mask = None
        for cls in classes:
            class_mask = lc.eq(cls)
            mask = class_mask if mask is None else mask.Or(class_mask)
        return lc.updateMask(mask)


    # 5️⃣ Visualization parameters
    @staticmethod
    def get_visualization_params(classes):
        colors = [function_registry.class_palette[cls] for cls in classes if cls in function_registry.class_palette]
        return {
            "min": min(classes),
            "max": max(classes),
            "palette": colors
        }


    # 6️⃣ Add clickable legend
    @staticmethod
    def add_legend(Map, classes):
        legend_dict = {function_registry.class_labels[cls]: function_registry.class_palette[cls] for cls in classes if cls in function_registry.class_palette}
        Map.add_legend(
            title="ESA WorldCover Land Cover",
            legend_dict=legend_dict,
            position="bottomright"
        )


    # 7️⃣ Visualize with legend
    @staticmethod
    def Final_land_cover(place_name, level="district"):
        boundary = function_registry.get_admin_boundary(place_name, level)
        thresholds = function_registry.get_landcover_thresholds(level)
        aoi = boundary.geometry()

        lc_mask = function_registry.get_landcover_mask(aoi, thresholds["classes"])
        vis_params = function_registry.get_visualization_params(thresholds["classes"])

        # Create map (no need to manually set center/zoom)
        Map = geemap.Map()

        # Add layers
        Map.addLayer(boundary, {"color": "orange"}, f"{place_name} boundary")
        Map.addLayer(lc_mask, vis_params, "Land Cover Classes")

        # 🔍 Fit to boundary's bounds
        bounds = boundary.geometry().bounds().getInfo()["coordinates"][0]
        lats = [coord[1] for coord in bounds]
        lngs = [coord[0] for coord in bounds]
        min_lat, max_lat = min(lats), max(lats)
        min_lng, max_lng = min(lngs), max(lngs)
        Map.fit_bounds([[min_lat, min_lng], [max_lat, max_lng]])

        # Add legend
        function_registry.add_legend(Map, thresholds["classes"])

        return Map
    
def execute_workflow(workflow, fr=function_registry):
    results = {}
    print("executing workflow:")

    for step in workflow['steps']:
        func = getattr(fr, step['function'])  # access function from fr argument
        args = step['args']
        sig = inspect.signature(func).parameters

        resolved_args = {}
        for key, val in args.items():
            if isinstance(val, str) and val in results:
                result = results[val]
                if isinstance(result, tuple) and key in sig:
                    idx = list(sig).index(key)
                    resolved_args[key] = result[idx] if idx < len(result) else result
                else:
                    resolved_args[key] = result
            else:
                resolved_args[key] = val

        results[step['id']] = func(**resolved_args)

    return results


# ee.Initialize(project="558258839591")
# workflow = {'task': 'Flood risk map for chennai', 'thoughts': ["The user is asking for a flood risk map for 'chennai'.", "Chennai is a major city in India, which typically corresponds to a 'district' administrative level.", 'The `Final_flood_risk` function is suitable for generating a high-level flood risk map for a specified place and administrative level.'], 'steps': [{'id': 'step1', 'function': 'Final_flood_risk', 'args': {'place_name': 'chennai', 'level': 'district'}}]}
# execute_workflow(workflow)

# get_thresholds