
import os
import arcpy

# Script header
"""
Add_Levee_to_AOI.py
Version 1.0
This script selects all levee features that intersect a floodplain polygon and saves them to a new shapefile.
"""

# Define parameters
arcpy.AddMessage("Getting files:")
Tool_Template_Files = arcpy.GetParameterAsText(0)
floodplain_raster = arcpy.GetParameterAsText(1)

# Set workspace
arcpy.env.workspace = folder_location

# Find levee shapefile
levee_shp = os.path.join(Tool_Template_Files, "NLD", "NLD_levee.shp")
for file in arcpy.ListFiles():
    if file.endswith(".shp") and "levee" in file.lower():
        levee_shp = os.path.join(arcpy.env.workspace, file)
        break

if not levee_shp:
    arcpy.AddError("Levee shapefile not found.")
else:
    # Convert floodplain raster to polygon
    floodplain_poly = os.path.join(arcpy.env.workspace, "floodplain_poly.shp")
    arcpy.RasterToPolygon_conversion(floodplain_raster, floodplain_poly)

    # Select all levee features that intersect floodplain polygon
    levee_floodplain = os.path.join(arcpy.env.workspace, "levee_floodplain.shp")
    arcpy.SelectLayerByLocation_management(levee_shp, "INTERSECT", floodplain_poly)
    arcpy.CopyFeatures_management(levee_shp, levee_floodplain)
