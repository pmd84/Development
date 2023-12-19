
import arcpy
from arcpy import AddMessage as msg
from arcpy import AddWarning as warn
from arcpy import management as mgmt
import sys
from sys import argv
import os
import json
import requests
from arcpy import env
from arcpy.sa import *
import shutil
import pandas as pd

# Set up temp workspace
cur_dir = fr'{os.getcwd()}' #working directory of script / toolbox
temp_dir = fr'{cur_dir}\temp'
temp_gdb = fr'{temp_dir}\temp.gdb'

def setup_workspace():

    """
    The setup_workspace function creates a lib directory in the current working directory,
    and then creates a file geodatabase called temp.gdb within that lib directory.

    :return: Nothing
    """

    msg("Setting up Temporary Directory")

    msg("Current Working Directory: {}".format(cur_dir))

    # Ensure that required directories exist
    msg("Making temp folder within Curent Working Directory")
    if not os.path.exists(temp_dir):
        os.mkdir(temp_dir)

    # Create file geodatabase
    msg("Creating temp.gdb within temp folder")
    
    if not os.path.exists(temp_gdb):
        mgmt.CreateFileGDB(temp_dir, 'temp.gdb', 'CURRENT')

def Check_Source_Data(Tool_Template_Folder, S_AOI_Ar):
    msg(u"\u200B")
    msg("##### Checking Source Data in Tool Template Files Folder #####")

    #If no Tool_Template_Folder folder is provided, use Stantec server location
    if Tool_Template_Folder == "" or Tool_Template_Folder == None:
        Tool_Template_Folder = r"\\us0525-ppfss01\shared_projects\203432303012\FFRMS_Zone3\tools\Tool_Template_Files"
        msg("No Tool Template Files location provided, using location on Stantec Server: {0}".format(Tool_Template_Folder))
    
    #Check to see if Tool_Template_Folder exists
    if not os.path.exists(Tool_Template_Folder):
        arcpy.AddError("Tool Template Files folder does not exist at provided lcoation Stantec Server. Please manually provide path to Tool Template Files folder and try again")
        sys.exit()
    else:
        msg("Tool Template Files folder found")
    
    #Define paths for template data
    levee_features = os.path.join(Tool_Template_Folder, "NLD", "231020_system_areas.shp")

    #Check or existence of template data
    if not os.path.exists(levee_features):
        arcpy.AddError("No Levee Features found in Tool Template Files folder. Please check you are using the correct Tool Template Folder, or add Levee Features as '231020_system_areas.shp' to the 'NLD' folder with Tool Template Files folder and try again")
        sys.exit()
    else:
        msg("{0} found".format(os.path.basename(levee_features)))

        # Find S_AOI_Ar features within "FFRMS_Spatial_Layers"
    # msg("Finding S_AOI_Ar features within 'FFRMS_Spatial_Layers'...")
    # arcpy.env.workspace = os.path.join(HUC_AOI_Erase_Area, "FFRMS_Spatial_Layers")
    # fcs = arcpy.ListFeatureClasses()
    # S_AOI_Ar = None
    # for fc in fcs:
    #     if "S_AOI_Ar" in fc:
    #         msg("{0} found".format(fc))
    #         S_AOI_Ar = os.path.join(HUC_AOI_Erase_Area, "FFRMS_Spatial_Layers", fc)
    #         break
    # if S_AOI_Ar is None:
    #     arcpy.AddError("S_AOI_Ar feature class not found. Please add to AOIs_Erase_Area.gdb and try again")
    #     sys.exit()
    
    return levee_features, S_AOI_Ar

def Convert_Rasters_to_Polygon(FVA03_raster):
    msg(u"\u200B")
    msg("##### Converting FVA0 +3 raster to Polygon #####")

    if FVA03_raster == "" or FVA03_raster == None:
        arcpy.AddError("FVA03 Raster Not Found or not provided. Please provide FVA03 (wsel_grid_3) raster")
        exit()
    
    try:
        msg("Converting {0} to polygon".format(FVA03_raster))

        output_location = temp_gdb
        output_temp_polygon = os.path.join(output_location, "raster_polygon")
        FVA03_polygon = os.path.join(output_location, "FVA03_polygon")

        if arcpy.Exists(FVA03_polygon):
            msg("FVA03 polygon already exists - using existing polygon in temp_gdb")
            return FVA03_polygon
        
        #Must convert to int first
        FVA_raster_int = Int(FVA03_raster)

        conversion_type = "MULTIPLE_OUTER_PART"

        FVA_polygon = arcpy.RasterToPolygon_conversion(in_raster=FVA_raster_int, out_polygon_features=output_temp_polygon, 
                                                    simplify="SIMPLIFY", create_multipart_features=conversion_type)

        try:
            arcpy.management.Dissolve(in_features=FVA_polygon, out_feature_class=FVA03_polygon)

        except Exception as e: #If Dissolve Fails, try repairing geometry and dissolving again
            msg("Failed to dissolve {0} to polygon".format(FVA03_raster))
            msg("Reparing geometry and trying again")

            FVA_polygon = arcpy.RepairGeometry_management(FVA_polygon)
            arcpy.management.Dissolve(in_features=FVA_polygon, out_feature_class=FVA03_polygon)

    except Exception as e:
        arcpy.AddWarning("Failed to convert {0} to polygon".format(FVA03_raster))
        arcpy.AddWarning(e)
        sys.exit()

    msg("FVA03 polygon successfully created")

    return FVA03_polygon

def select_levee_features(FV03_polygon):
        
    levee_output_location = temp_gdb

    levee_FVA03 = os.path.join(levee_output_location, "levee_FVA03")
    
    if arcpy.Exists(levee_FVA03):
        return levee_FVA03
    
    arcpy.MakeFeatureLayer_management(levee_features, "levee_features")
    arcpy.SelectLayerByLocation_management("levee_features", "INTERSECT", FV03_polygon)
    arcpy.CopyFeatures_management("levee_features", levee_FVA03)
    return levee_FVA03
    
def create_geometry_hash(feature_class, ID_Field="OBJECTID"):
    """
    Create a hash table of geometry WKTs.
    """
    geometry_hashes = {}
    with arcpy.da.SearchCursor(feature_class, [f"{ID_Field}", 'SHAPE@']) as cursor:
        for row in cursor:
            geom_hash = hash(row[1].WKT)
            geometry_hashes[geom_hash] = row[0]
    return geometry_hashes
    
if __name__ == '__main__':

    setup_workspace()

    # Define parameters
    FVA03_raster = arcpy.GetParameterAsText(0)
    S_AOI_Ar = arcpy.GetParameterAsText(1)
    Tool_Template_Folder = arcpy.GetParameterAsText(2)

    # Check for source data
    levee_features, S_AOI_Ar = Check_Source_Data(Tool_Template_Folder, S_AOI_Ar)

    # Convert FVA03 raster to polygon
    FV03_polygon = Convert_Rasters_to_Polygon(FVA03_raster)

    # Select all levee features that intersect floodplain polygon
    msg("Selecting all levee features that intersect floodplain polygon...")
    levee_FVA03 = select_levee_features(FV03_polygon)

    # Count number of entries in S_AOI_Ar before appending
    num_entries_before = int(arcpy.GetCount_management(S_AOI_Ar).getOutput(0))
    msg("Number of S_AOI_Ar entries before appending: {0}".format(num_entries_before))
    
    msg("Appending new levee features to S_AOI_Ar features...")
    arcpy.management.Append(levee_FVA03, S_AOI_Ar, "NO_TEST")

    # delete identical records:
    msg("Deleting identical records...")
    arcpy.management.DeleteIdentical(
    in_dataset=S_AOI_Ar,
    fields="Shape",
    xy_tolerance=None,
    z_tolerance=0
)

    #loop through appended feautres with update cursor and add values to 
    msg("Adding fields to new features ...")
    AOI_Typ = "4000" #Riverine
    AOI_Issue = "4030" #Levee
    S_AOI_Issues = r"Please contact your FEMA Regional FFRMS Specialist for additional information at FEMA-FFRMS-Support-Request@fema.dhs.gov"
    
    row_start = num_entries_before 
    with arcpy.da.UpdateCursor(S_AOI_Ar, ["AOI_TYP", "AOI_ISSUE", "AOI_INFO"]) as cursor:
        #only update new features
        for row_num, row in enumerate(cursor):
            if row_num >= row_start:
                row[0] = AOI_Typ
                row[1] = AOI_Issue
                row[2] = S_AOI_Issues
                cursor.updateRow(row)

    # Delete temp workspace
    msg("Deleting  temp workspace...")  
    try:  
        mgmt.Delete(temp_gdb)
        shutil.rmtree(temp_dir)
    except:
        msg("Unable to delete temp workspace. Please delete manually")

    msg("Script Complete")
