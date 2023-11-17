
import arcpy
import sys
from sys import argv
import os
import json
import requests
from arcpy import env
from arcpy.sa import *
import shutil
import pandas as pd

def Convert_Rasters_to_Polygon(FFRMS_Geodatabase):
    # 1.    Find the FVA0 and FVA03 raster in the geodatabase
    # 2.	turn float grid to Integer (INT tool)
    # 3.	Raster to Polygon, choose simplify polygon option
    # 4.	Merge to a single multipart feature class

    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Converting FVA rasters to polygon #####")

    arcpy.env.workspace = FFRMS_Geodatabase

    #Create dictionary of all available FVA rasters
    raster_dict = {}
    expected_values = ["00FVA", "01FVA", "02FVA", "03FVA"]

    for raster in arcpy.ListRasters():
        try:
            Freeboard_Val = raster.split("_")[3]
        except IndexError:
            continue

        if Freeboard_Val in expected_values:
            arcpy.AddMessage("FVA{}_raster: {}".format(Freeboard_Val[:2], raster))
            raster_dict[Freeboard_Val] = raster

    for Freeboard_Val in expected_values:
        if Freeboard_Val not in raster_dict:
            arcpy.AddWarning("{} Raster Not Found".format(Freeboard_Val))

    #Loop through all available rasters
    for FVA_value, FVA_raster in raster_dict.items():
        try:
            arcpy.AddMessage("Converting {0} to polygon".format(FVA_raster))
            raster_name = os.path.basename(FVA_raster)

            #Convert to Int
            FVA_raster_int = Int(FVA_raster)

            #Convert to Polygon
            conversion_type = "MULTIPLE_OUTER_PART"
            output_location = FFRMS_Geodatabase #! Make in_memory after testing
            output_temp_polygon = os.path.join(output_location, "{0}_polygon".format(raster_name))
            FVA_polygon = arcpy.RasterToPolygon_conversion(in_raster=FVA_raster_int, out_polygon_features=output_temp_polygon, 
                                                        simplify="SIMPLIFY", create_multipart_features=conversion_type)
            
            #Dissolve
            output_dissolved_polygon = os.path.join(output_location, "FVA{0}_polygon".format(FVA_value))
            try:
                arcpy.management.Dissolve(in_features=FVA_polygon, out_feature_class=output_dissolved_polygon)

            except Exception as e: #If Dissolve Fails, try repairing geometry and dissolving again
                arcpy.AddMessage("Failed to dissolve {0} to polygon".format(FVA_raster))
                arcpy.AddMessage("Reparing geometry and trying again")

                FVA_polygon = arcpy.RepairGeometry_management(FVA_polygon)
                arcpy.management.Dissolve(in_features=FVA_polygon, out_feature_class=output_dissolved_polygon)

        except Exception as e: #Dissolve still failed after repairing geometry
            arcpy.AddWarning("Failed to convert {0} to polygon".format(FVA_raster))
            arcpy.AddWarning(e)
            sys.exit()

    arcpy.AddMessage("FVA polygons successfully created")

    FVA_Polygon_Dict = {}
    if "00FVA" in raster_dict:
        FVA_Polygon_Dict["00FVA"] = os.path.join(output_location, "FVA00_polygon")

    if "01FVA" in raster_dict:
        FVA_Polygon_Dict["01FVA"] = os.path.join(output_location, "FVA01_polygon")

    if "02FVA" in raster_dict:
        FVA_Polygon_Dict["02FVA"] = os.path.join(output_location, "FVA02_polygon")

    if "03FVA" in raster_dict:
        FVA_Polygon_Dict["03FVA"] = os.path.join(output_location, "FVA03_polygon")

    return FVA_Polygon_Dict



