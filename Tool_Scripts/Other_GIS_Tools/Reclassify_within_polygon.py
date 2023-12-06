import arcpy
import numpy as np
import sys
from sys import argv
import os
from arcpy import env
from arcpy.sa import *
import shutil
import pandas as pd
from arcpy import management as mgmt
from arcpy import AddMessage as msg
from arcpy import AddWarning as warn
from os import path as pth

def check_out_spatial_analyst():
    """
    The check_out_spatial_analyst function checks out the spatial analyst extension.

    :return: Nothing
    """
    class LicenseError(Exception):
        pass

    try:
        if arcpy.CheckExtension("Spatial") == "Available":
            arcpy.CheckOutExtension("Spatial")
            msg("Checked out Spatial Extension")
        else:
            raise LicenseError
    except LicenseError:
        msg("Spatial Analyst license is unavailable")
    except:
        msg("Exiting")
        exit()

def Fix_Spatial_reference(polygon, input_raster, temp_out_location):
    msg("Checking and fixing polygon spatial reference")
    polygon_sr = arcpy.Describe(polygon).spatialReference

    if polygon_sr.name != "NAD_1983_Contiguous_USA_Albers":
        polygon_projected = pth.join(temp_out_location, "polygon_projected")
        arcpy.Project_management(polygon, polygon_projected, input_raster)

    return polygon_projected

def Add_RasterVal_Field(polygon):
    fields = [field.name for field in arcpy.ListFields(polygon)]
    if "RasterVal" not in fields:
        msg("Adding RasterVal field to polygon")
        arcpy.AddField_management(polygon, "RasterVal", "SHORT")

def Convert_Polygon_to_Raster(polygon, temp_out_location):
    msg("Converting Polygon to Raster mask")
    mask_raster = pth.join(temp_out_location,'maskRaster')
    msg(f"Raster mask location: {mask_raster}")
    arcpy.FeatureToRaster_conversion(in_features=polygon, field="RasterVal", out_raster=mask_raster)
    return mask_raster

def Create_Intersect_Raster(input_raster, mask_raster, reclass_value, temp_out_location):
    msg("Creating intersection")
    intersect = Times(input_raster, mask_raster)
    
    #Use raster calculator to change all values to reclass_value
    intersect_calc = arcpy.sa.RasterCalculator([intersect], ["InRaster"], f"Con(~IsNull(InRaster), {reclass_value}, InRaster)")
    
    intersectRaster = pth.join(temp_out_location, "intersectRaster")
    arcpy.CopyRaster_management(intersect_calc, intersectRaster)

    return intersectRaster

def Check_Mask_Raster(raster):
    min_value = arcpy.GetRasterProperties_management(raster, "MINIMUM")
    max_value = arcpy.GetRasterProperties_management(raster, "MAXIMUM")
    if min_value.getOutput(0) == "None" and max_value.getOutput(0) == "None":
        warn("Mask raster is empty - check polygon inputs")

def Mosaic_to_Raster(intersectRaster, out_path):
    msg("Mosaicing fixed cell values to original raster")
    mgmt.Mosaic(inputs=intersectRaster,
                            target=out_path, 
                            mosaic_type="LAST", 
                            colormap= "FIRST", 
                            background_value =-99999,
                            nodata_value =-99999)
    
def Reclassify_within_polygon(input_raster, polygon, temp_out_location, reclass_value, out_path):

    polygon = Fix_Spatial_reference(polygon, input_raster, temp_out_location)

    Add_RasterVal_Field(polygon)

    mask_raster = Convert_Polygon_to_Raster(polygon, temp_out_location)

    intersectRaster = Create_Intersect_Raster(input_raster, mask_raster, reclass_value, temp_out_location)

    Check_Mask_Raster(intersectRaster)

    Mosaic_to_Raster(intersectRaster, out_path)

if __name__ == "__main__":
    
    #Get tool input parameters
    polygon = arcpy.GetParameterAsText(0)
    input_raster = arcpy.GetParameterAsText(1)
    reclass_value = arcpy.GetParameterAsText(2)
    out_path = arcpy.Describe(input_raster).catalogPath

    #Get current workspace
    check_out_spatial_analyst()
    arcpy.env.extent = input_raster
    arcpy.env.cellSize = input_raster
    workspace = arcpy.env.workspace
    arcpy.env.compression = "NONE"
    arcpy.env.overwriteOutput = True

    temp_out_location = "in_memory"

    # Run the reclassify function
    Reclassify_within_polygon(input_raster, polygon, temp_out_location, reclass_value, out_path)  