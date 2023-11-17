
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

def Check_Source_Data(Tool_Template_Folder, HUC_AOI_Erase_Area):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Checking Source Data in Tool Template Files Folder #####")

    #If no Tool_Template_Folder folder is provided, use Stantec server location
    if Tool_Template_Folder == "" or Tool_Template_Folder == None:
        Tool_Template_Folder = r"\\us0525-ppfss01\shared_projects\203432303012\FFRMS_Zone3\tools\Tool_Template_Files"
        arcpy.AddMessage("No Tool Template Files location provided, using location on Stantec Server: {0}".format(Tool_Template_Folder))
    
    #Check to see if Tool_Template_Folder exists
    if not os.path.exists(Tool_Template_Folder):
        arcpy.AddError("Tool Template Files folder does not exist at provided lcoation Stantec Server. Please manually provide path to Tool Template Files folder and try again")
        sys.exit()
    else:
        arcpy.AddMessage("Tool Template Files folder found")
    
    #Define paths for template data
    levee_features = os.path.join(Tool_Template_Folder, "NLD", "231020_system_areas.shp")

    #Check or existence of template data
    if not os.path.exists(levee_features):
        arcpy.AddError("No Levee Features found in Tool Template Files folder. Please check you are using the correct Tool Template Folder, or add Levee Features as '231020_system_areas.shp' to the 'NLD' folder with Tool Template Files folder and try again")
        sys.exit()
    else:
        arcpy.AddMessage("{0} found".format(os.path.basename(levee_features)))

        # Find S_AOI_Ar features within "FFRMS_Spatial_Layers"
    arcpy.AddMessage("Finding S_AOI_Ar features within 'FFRMS_Spatial_Layers'...")
    arcpy.env.workspace = os.path.join(HUC_AOI_Erase_Area, "FFRMS_Spatial_Layers")
    fcs = arcpy.ListFeatureClasses()
    S_AOI_Ar = None
    for fc in fcs:
        if "S_AOI_Ar" in fc:
            arcpy.AddMessage("{0} found".format(fc))
            S_AOI_Ar = os.path.join(HUC_AOI_Erase_Area, "FFRMS_Spatial_Layers", fc)
            break
    if S_AOI_Ar is None:
        arcpy.AddError("S_AOI_Ar feature class not found. Please add to AOIs_Erase_Area.gdb and try again")
        sys.exit()
    
    return levee_features, S_AOI_Ar

def Convert_Rasters_to_Polygon(FVA03_raster):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Converting FVA +0 and FVA0 +3 rasters to Polygon #####")

    if FVA03_raster == "" or FVA03_raster == None:
        arcpy.AddError("FVA03 Raster Not Found or not provided. Please provide FVA03 (wsel_grid_3) raster")
        exit()
    
    try:
        arcpy.AddMessage("Converting {0} to polygon".format(FVA03_raster))

        #Must convert to int first
        FVA_raster_int = Int(FVA03_raster)

        conversion_type = "MULTIPLE_OUTER_PART"

        output_location = HUC_AOI_Erase_Area
        output_temp_polygon = os.path.join(output_location, "raster_polygon")
        FVA03_polygon = os.path.join(output_location, "FVA03_polygon")
        
        #! Delete after testing
        if arcpy.Exists(FVA03_polygon):
            return FVA03_polygon
            
        FVA_polygon = arcpy.RasterToPolygon_conversion(in_raster=FVA_raster_int, out_polygon_features=output_temp_polygon, 
                                                    simplify="SIMPLIFY", create_multipart_features=conversion_type)

        try:
            arcpy.management.Dissolve(in_features=FVA_polygon, out_feature_class=FVA03_polygon)

        except Exception as e: #If Dissolve Fails, try repairing geometry and dissolving again
            arcpy.AddMessage("Failed to dissolve {0} to polygon".format(FVA03_raster))
            arcpy.AddMessage("Reparing geometry and trying again")

            FVA_polygon = arcpy.RepairGeometry_management(FVA_polygon)
            arcpy.management.Dissolve(in_features=FVA_polygon, out_feature_class=FVA03_polygon)

    except Exception as e:
        arcpy.AddWarning("Failed to convert {0} to polygon".format(FVA03_raster))
        arcpy.AddWarning(e)
        sys.exit()

    arcpy.AddMessage("FVA03 polygon successfully created")

    return FVA03_polygon

def select_levee_features(HUC_AOI_Erase_Area, FV03_polygon):
        
    levee_output_location = HUC_AOI_Erase_Area
    #levee_output_location = "in_memory" #! Replace after testing

    levee_FVA03 = os.path.join(levee_output_location, "levee_FVA03")
    
    if arcpy.Exists(levee_FVA03):
        return levee_FVA03
    
    arcpy.MakeFeatureLayer_management(levee_features, "levee_features")
    arcpy.SelectLayerByLocation_management("levee_features", "INTERSECT", FV03_polygon)
    arcpy.CopyFeatures_management("levee_features", levee_FVA03)
    return levee_FVA03
    
if __name__ == '__main__':

    # Define parameters
    FVA03_raster = arcpy.GetParameterAsText(0)
    HUC_AOI_Erase_Area = arcpy.GetParameterAsText(1)
    Tool_Template_Folder = arcpy.GetParameterAsText(2)

    # Set workspace
    arcpy.env.workspace = HUC_AOI_Erase_Area

    # Check for source data
    levee_features, S_AOI_Ar = Check_Source_Data(Tool_Template_Folder, HUC_AOI_Erase_Area)

    # Convert FVA03 raster to polygon
    FV03_polygon = Convert_Rasters_to_Polygon(FVA03_raster)

    # Select all levee features that intersect floodplain polygon
    arcpy.AddMessage("Selecting all levee features that intersect floodplain polygon...")
        
    levee_FVA03 = select_levee_features(HUC_AOI_Erase_Area, FV03_polygon)

    #Add Fields AOI_TYP, AOI_ISSUE, and AOI_INFO
    arcpy.AddMessage("Adding fields to levee features class...")
    for field in ["AOI_TYP", "AOI_ISSUE", "AOI_INFO"]:
        if field in [f.name for f in arcpy.ListFields(levee_FVA03)]:
            arcpy.AddMessage("{0} field already exists".format(field))
        else:
            arcpy.AddField_management(levee_FVA03, field, "TEXT")

    #Calculate Fields
    arcpy.AddMessage("Calculating fields in levee_FVA03 feature class...")
    AOI_Typ = "Riverine" #Riverine
    AOI_Issue = "Levee" #Levee
    S_AOI_Issues = r"Please contact your FEMA Regional FFRMS Specialist for additional information at FEMA-FFRMS-Support-Request@fema.dhs.gov"
    
    arcpy.CalculateField_management(levee_FVA03, "AOI_TYP", '"' + AOI_Typ + '"', "PYTHON3")
    arcpy.CalculateField_management(levee_FVA03, "AOI_ISSUE", '"' + AOI_Issue + '"', "PYTHON3")
    arcpy.CalculateField_management(levee_FVA03, "AOI_INFO", '"' + S_AOI_Issues + '"', "PYTHON3")

    #Append to S_AOI_Ar features
    arcpy.AddMessage("Appending to S_AOI_Ar features...")

    # Count number of entries in S_AOI_Ar before appending

    num_entries_before = int(arcpy.GetCount_management(S_AOI_Ar).getOutput(0))

    # Append to S_AOI_Ar features
    arcpy.Append_management(levee_FVA03, S_AOI_Ar, "NO_TEST")

    # Count number of entries in S_AOI_Ar after appending
    num_entries_after = int(arcpy.GetCount_management(S_AOI_Ar).getOutput(0))

    # Print results
    print(f"Number of entries before appending: {num_entries_before}")
    print(f"Number of entries after appending: {num_entries_after}")

    arcpy.Append_management(levee_FVA03, S_AOI_Ar, "NO_TEST")

    arcpy.AddMessage("Levee features added to S_AOI_Ar features successfully")
