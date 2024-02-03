"""
Script documentation

- Tool parameters are accessed using arcpy.GetParameter() or 
                                     arcpy.GetParameterAsText()
- Update derived parameter values using arcpy.SetParameter() or
                                        arcpy.SetParameterAsText()
"""
import arcpy
from arcpy import AddMessage as msg
from arcpy import AddWarning as warn
from sys import argv
import sys
import os
import json
import requests
from arcpy import env
from arcpy.sa import *


def Check_Source_Data(Tool_Template_Folder):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Checking Source Data in Tool Template Files Folder #####")
    
    if Tool_Template_Folder == "" or Tool_Template_Folder == None:
            Tool_Template_Folder = r"\\us0525-ppfss01\shared_projects\203432303012\FFRMS_Zone3\tools\Tool_Template_Files"
            arcpy.AddMessage("No Tool Template Files location provided, using location on Stantec Server: {0}".format(Tool_Template_Folder))
        
    #Check to see if Tool_Template_Folder exists
    if not os.path.exists(Tool_Template_Folder):
        arcpy.AddError("Tool Template Files folder does not exist at provided lcoation Stantec Server. Please manually provide path to Tool Template Files folder and try again")
        sys.exit()
    else:
        arcpy.AddMessage("Tool Template Files folder found")

    NFHL_data = os.path.join(Tool_Template_Folder, "rFHL_20230630.gdb")
    levee_features = os.path.join(Tool_Template_Folder, "NLD", "231020_system_areas.shp")

    #Check or existence of template data
    if not os.path.exists(NFHL_data):
        arcpy.AddError("No NFHL data found in Tool Template Files folder. Please manually add rFHL database to Tool Template Files folder and try again".format(os.path.basename(NFHL_data)))
        sys.exit()
    else:
        arcpy.AddMessage("{0} found".format(os.path.basename(NFHL_data)))

    if not os.path.exists(levee_features):
        arcpy.AddError("No levee features found in Tool Template Files folder. Please manually add levee features to Tool Template Files folder and try again".format(os.path.basename(levee_features)))
        sys.exit()
    else:
        arcpy.AddMessage("{0} found".format(os.path.basename(levee_features)))

    return NFHL_data, levee_features

def Convert_Rasters_to_Polygon(FFRMS_Geodatabase):
    # 1.    Find the FVA0 and FVA03 raster in the geodatabase
    # 2.	turn float grid to Integer (INT tool)
    # 3.	Raster to Polygon, choose simplify polygon option
    # 4.	Merge to a single multipart feature class

    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Converting FVA +0 and FVA0 +3 rasters to Polygon #####")

    arcpy.env.workspace = FFRMS_Geodatabase

    for raster in arcpy.ListRasters():
        try:
            Freeboard_Val = raster.split("_")[3]
        except:
            continue
        if Freeboard_Val == "00FVA":
            FVA00_raster = raster
            arcpy.AddMessage("FV00_raster: " + FVA00_raster)
        elif Freeboard_Val == "03FVA":
            FVA03_raster = raster
            arcpy.AddMessage("FV03_raster: " + FVA03_raster)

    try:
        FVA00_raster
    except NameError:
        arcpy.AddError("FVA00 Raster Not Found")
        exit()

    try:
        FVA03_raster
    except NameError:
        arcpy.AddError("FVA03 Raster Not Found")
        exit()
    
    try:
        for FVA_raster in FVA00_raster, FVA03_raster:
            arcpy.AddMessage("Converting {0} to polygon".format(FVA_raster))
            raster_name = os.path.basename(FVA_raster)
            FVA_value = raster_name.split("_")[3][:2]

            FVA_raster_int = Int(FVA_raster)

            conversion_type = "MULTIPLE_OUTER_PART"

            output_location = "in_memory"

            output_temp_polygon = os.path.join(output_location, "{0}_polygon".format(raster_name))
            
            FVA_polygon = arcpy.RasterToPolygon_conversion(in_raster=FVA_raster_int, out_polygon_features=output_temp_polygon, 
                                                        simplify="SIMPLIFY", create_multipart_features=conversion_type)
        
            output_polygon = os.path.join(output_location, "FVA{0}_polygon".format(FVA_value))
            try:
                arcpy.management.Dissolve(in_features=FVA_polygon, out_feature_class=output_polygon)

            except Exception as e: #If Dissolve Fails, try repairing geometry and dissolving again
                arcpy.AddMessage("Failed to dissolve {0} to polygon".format(FVA_raster))
                arcpy.AddMessage("Reparing geometry and trying again")

                FVA_polygon = arcpy.RepairGeometry_management(FVA_polygon)
                arcpy.management.Dissolve(in_features=FVA_polygon, out_feature_class=output_polygon)

    except Exception as e:
        arcpy.AddWarning("Failed to convert {0} to polygon".format(FVA_raster))
        arcpy.AddWarning(e)
        sys.exit()

    arcpy.AddMessage("FVA00 and FVA03 polygons successfully created")

    FVA00_polygon = os.path.join("in_memory", "FVA00_polygon")
    FVA03_polygon = os.path.join("in_memory", "FVA03_polygon")

    return FVA00_polygon, FVA03_polygon

def Extract_NFHL_100yr_Floodplain(FIPS_code, FFRMS_Geodatabase, NFHL_data, county_boundary):
# a.	Clip NFHL S_Fld_Haz_Ar polygon to county
# b.	Select and merge polygons where the SFHA field is True ("T")
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting NFHL 1% Annual Chance Floodplain #####")

    arcpy.AddMessage("Extracting 1% NFHL floodplains")
    S_Fld_Haz_AR = os.path.join(NFHL_data, "S_FLD_HAZ_AR")
    query = "UPPER(SFHA_TF) = 'T' OR UPPER(SFHA_TF) = 'TRUE'"
    query = "SFHA_TF = 'T' OR SFHA_TF = 'TRUE'"
    arcpy.management.MakeFeatureLayer(S_Fld_Haz_AR, "NFHL_layer", query)

    #clip to county boundary
    arcpy.AddMessage("Clipping NFHL floodplains to county boundary")
    clipped_NFHL = r"in_memory/NFHL_layer_clip"
    arcpy.analysis.Clip("NFHL_layer", county_boundary, clipped_NFHL)

    #dissolve all features into single polygon feature class
    arcpy.AddMessage("Dissolving NFHL floodplains to single feature")
    NFHL_100yr = r"in_memory/NFHL_100yr_floodplain"
    arcpy.management.Dissolve(in_features=clipped_NFHL, out_feature_class=NFHL_100yr)
    
    return NFHL_100yr

def Populate_S_FFRMS_Ar(FV03_polygon, S_FFRMS_Proj_Ar, S_FFRMS_Ar, county_name, FIPS_code):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Populating S_FFRMS_Ar #####")
    
    #union FV03_polygon and county boundary
    arcpy.AddMessage("Unioning FV03_polygon and county boundary")

    #clip and uion FV03 to county boundary, sort by size
    arcpy.analysis.Clip(FV03_polygon, S_FFRMS_Proj_Ar, r"in_memory/FV03_clip")
    arcpy.analysis.Union([r"in_memory/FV03_clip", S_FFRMS_Proj_Ar], r"in_memory/FV03_union")
    arcpy.management.Sort(r"in_memory/FV03_union", r"in_memory/FV03_union_sorted", "Shape_Area ASCENDING")

    #delete any existing rows in S_FFRMS_Ar - then append
    arcpy.AddMessage("Appending FV03 and county features to S_FFRMS_Ar")
    arcpy.management.DeleteRows(S_FFRMS_Ar)
    arcpy.management.Append(r"in_memory/FV03_union_sorted", S_FFRMS_Ar, "NO_TEST")

    #get areas of each feature in S_FFRMS_Ar
    areas = [row[0] for row in arcpy.da.SearchCursor(S_FFRMS_Ar, ["Shape_Area"])]

    # Create a cursor to update the FFRMS_AVL field - the smaller area one with "T" and larger area with "F"
    arcpy.AddMessage("Populating FFRMS_AVL field")
    with arcpy.da.UpdateCursor(S_FFRMS_Ar, ["Shape_Area", "FFRMS_AVL", "FIPS", "POL_NAME1"]) as cursor:
        for row in cursor:
            if row[0] == min(areas):
                row[1] = "T"
            else:
                row[1] = "F"
            row[2] = FIPS_code
            row[3] = county_name
            cursor.updateRow(row)
 
def Erase_without_tool(input_features,erase_features,output_feature_class):
        """
        Works by UNIONing the two input feature classes, SELECTing the created
        features that do not overlap with the erase_features using the 
        "erasefeaturesname_FID", and then CLIPping the original input_features to 
        include just those features. If either input_features or erase_features is 
        not a polygon it will be BUFFERed to a polygon prior to the union.

        -- credit to jtgis on GitHub
        """

        attr = os.path.basename(erase_features)

        desc =arcpy.Describe(input_features)
        if desc.shapeType != 'Polygon':
            arcpy.AddWarning("CLIPPING FEATURE MUST BE POLYGON. CHECK {0} AND RETRY...".format(input_features))
            
        desc =arcpy.Describe(erase_features)
        if desc.shapeType != 'Polygon':
            arcpy.AddWarning("CLIPPING FEATURE MUST BE POLYGON. CHECK {0} AND RETRY...".format(input_features))

        #create feature layer in memory from input features
        memory_input = os.path.join("in_memory", "input_layer")
        unionized = os.path.join("in_memory", "Unioned")
        selected = os.path.join("in_memory", "Selected")
        clipped = os.path.join("in_memory", "Clipped")

        arcpy.CopyFeatures_management(input_features, r"in_memory/input_layer")

        arcpy.Union_analysis(in_features=[memory_input,erase_features], 
                            out_feature_class=unionized)

        arcpy.Select_analysis(in_features=unionized, 
                            out_feature_class=selected, 
                            where_clause="FID_"+attr+" = -1")

        arcpy.Clip_analysis(in_features=input_features, 
                            clip_features=selected, 
                            out_feature_class=clipped)

        #dissolve
        arcpy.Dissolve_management(in_features=clipped,
                                out_feature_class=output_feature_class)

def Create_S_Raster_QC_Copy(S_Raster_QC_pt):
    #create temporary copys of S_Raster_QC_pt for 01 and 02 in memory

    S_Raster_copy_all = r"in_memory/S_Raster_copy_all"

    arcpy.management.CopyFeatures(S_Raster_QC_pt, S_Raster_copy_all)
    
    return S_Raster_copy_all

def find_QC_point_files(tool_folder, HUC8):
    #set folder and shapefiles locations
    
    tool_folder = tool_folder.replace("'","") #Fixes One-Drive folder naming 

    for folder in os.listdir(tool_folder):
        if os.path.basename(folder) == os.path.basename(tool_folder):
            tool_folder = os.path.join(tool_folder, os.path.basename(folder))

    qc_folder = os.path.join(tool_folder, "qc_points")
    arcpy.AddMessage("## Compiling QC points from folder: {0} ##".format(HUC8))

    #Create a list of 01 qc shapefiles to process
    qc_points_shapefiles_01 = []
    qc_points_cl = os.path.join(qc_folder, "qc_points_cl.shp")
    dense_qc_points = os.path.join(qc_folder, "dense_qc_points.shp")
    
    #Files should exist as-is, but will search through directory if not
    if not os.path.exists(qc_points_cl) or not os.path.exists(dense_qc_points):
        arcpy.AddWarning("Could not find qc_points_cl.shp or dense_qc_points.shp in qc_points folder: {0}".format(qc_folder))

        #Files didn't exist - loop through and get non 0_2pct shapefiles
        for root, dirs, files in os.walk(qc_folder):
            for file in files:
                if file.endswith(".shp") and not "02" in file:
                    arcpy.AddMessage("Adding {0} to list of qc_points".format(file))
                    qc_points_shapefiles_01.append(os.path.join(root, file))
    else:
        if os.path.exists(qc_points_cl):
            qc_points_shapefiles_01.append(qc_points_cl)
        if os.path.exists(dense_qc_points):
            qc_points_shapefiles_01.append(dense_qc_points)

    #Print list of 01 shapefiles found in each folder
    shapefiles_01_list = [os.path.basename(shapefile) for shapefile in qc_points_shapefiles_01]
    arcpy.AddMessage("01PCT QC point shapefiles: {0}".format(shapefiles_01_list))

    return qc_points_shapefiles_01

def Append_QC_points_to_S_Raster_Copies(qc_points_shapefiles_01, S_Raster_copy_all, HUC8):

    for qc_points in qc_points_shapefiles_01:
        #check that shapefile exists
        qc_points_filename = os.path.basename(qc_points)
        if not arcpy.Exists(qc_points):
            arcpy.AddWarning("{0} not found for HUC8 folder {1}".format(qc_points_filename, HUC8))
            continue

        #create temporary copy of qc_points in memory in order to change field names and append
        qc_points_layer = os.path.join("in_memory", "qc_points")
        arcpy.management.CopyFeatures(qc_points, qc_points_layer)

        #Change wsel_diff field to match target. If a_WTR_NM in fields (specifically for qc_points_cl), change it to WTR_NM.
        fields = arcpy.ListFields(qc_points_layer)
        field_names = [field.name for field in fields] 
        if "a_WTR_NM" in field_names:
            arcpy.management.AlterField(qc_points_layer, "a_WTR_NM", "WTR_NM")
        arcpy.management.AlterField(qc_points_layer, "wsel_diff", "ELEV_DIFF")
        arcpy.management.AlterField(qc_points_layer, "wsel_grid", "FVA_PLUS_0")

        #Append copy of S_Raster_QC_pt
        arcpy.Append_management(inputs=qc_points_layer, target=S_Raster_copy_all, schema_type="NO_TEST")

def update_fields_in_S_Raster_copies(S_Raster_copy_all, FIPS_code, county_name):

    #Add values for 3 fields: FIPS code, FRBD_RP, and Source_Cit to all rows
    with arcpy.da.UpdateCursor(S_Raster_copy_all, ["FIPS", "POL_NAME1", "SOURCE_CIT", "NOTES", "WSEL_REG", "FVA_PLUS_0", "ERROR_TOL", "PASS_FAIL"]) as cursor:
        for row in cursor:
            row[0] = FIPS_code
            row[1] = county_name
            row[2] = "STUDY1"
            row[3] = "NP"
            row[6] = abs(row[5] - row[4])
            if row[6] <= 0.5:
                row[7] = "Pass"
            else:
                row[7] = "Fail"

            cursor.updateRow(row)

    return S_Raster_copy_all

def Select_QC_Points_on_county_S_XS(S_Raster_copy_all, S_Raster_QC_pt, NFHL_data, county_boundary):
    arcpy.AddMessage("Selecting QC points that intersect with NFHL S_XS and are within county boundary")
    S_XS = os.path.join(NFHL_data, "FIRM_Spatial_Layers", "S_XS")

    #clip S_Raster_copy_all to county boundary
    S_raster_clip = r"in_memory/S_raster_clip"
    arcpy.analysis.Clip(S_Raster_copy_all, county_boundary, S_raster_clip)

    #select all points that intersect with S_XS
    arcpy.MakeFeatureLayer_management(S_raster_clip, "S_Raster_copy_intersect")
    arcpy.management.SelectLayerByLocation(in_layer="S_Raster_copy_intersect", overlap_type="WITHIN A DISTANCE", select_features=S_XS, search_distance="0.1 Meters", selection_type="NEW_SELECTION")
    
    #append selected points to S_Raster_QC_pt
    arcpy.AddMessage("Appending selected QC points to S_Raster_QC_Pts")
    arcpy.management.Append(inputs="S_Raster_copy_intersect", target=S_Raster_QC_pt, schema_type="NO_TEST")

    return S_Raster_QC_pt
    
def Populate_S_Raster_QC_pt(FFRMS_Geodatabase, NFHL_data, Tool_Output_Folders, county_boundary, FIPS_code, county_name):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Populating S_Raster_QC_pt #####")

    #delete existing entries in S_Raster_QC_pt
    S_Raster_QC_pt = os.path.join(FFRMS_Geodatabase, "S_Raster_QC_pt")
    arcpy.management.DeleteRows(S_Raster_QC_pt)

    #Add fields if needed to S_Raster_QC_pt
    og_fields = arcpy.ListFields(S_Raster_QC_pt)
    proper_fields = ["FIPS", "POL_NAME1", "WTR_NM", "WSEL_REG", "FVA_PLUS_0", "ERROR_TOL", "PASS_FAIL", "NOTES", "SOURCE_CIT"]
    field_types = ["TEXT", "TEXT", "TEXT", "DOUBLE", "DOUBLE", "DOUBLE", "TEXT", "TEXT", "TEXT"]
    for i, field in enumerate(proper_fields):
        if field not in [field.name for field in og_fields]:
            msg("Adding new schema field {0}".format(field))
            arcpy.management.AddField(S_Raster_QC_pt, field, field_types[i])
    
    #Delete fields if needed from S_Raster_QC_pt
    for field in og_fields:
        if field.name not in proper_fields:
            try:
                arcpy.management.DeleteField(S_Raster_QC_pt, field.name)
                msg("Deleted old schema field {0}".format(field.name))
            except:
                pass
    
    S_Raster_copy_all = Create_S_Raster_QC_Copy(S_Raster_QC_pt)

    #loop through Tool_Output_Folders (by HUC8)
    for tool_folder in Tool_Output_Folders:
        
        tool_folder = tool_folder.replace("'","") #Fixes One-Drive folder naming 

        HUC8 = os.path.basename(tool_folder)
        
        #find 01 and 02 qc point shapefiles within tool folder
        qc_points_shapefiles_01 = find_QC_point_files(tool_folder, HUC8)

        #Loop through both 01 and 02 qc shapefiles within HUC8 folder
        Append_QC_points_to_S_Raster_Copies(qc_points_shapefiles_01, S_Raster_copy_all, HUC8)

    #Combine QC points together and update fields based on their FVA type
    S_Raster_copy_all = update_fields_in_S_Raster_copies(S_Raster_copy_all, FIPS_code, county_name)

    #Select all points that intersect with NFHL S_XS (within county boundary) and append to S_Raster_QC_pt 
    S_Raster_QC_pt = Select_QC_Points_on_county_S_XS(S_Raster_copy_all, S_Raster_QC_pt, NFHL_data, county_boundary)

    return S_Raster_QC_pt

def get_FIPS(FFRMS_Geodatabase):
    S_FFRMS_Proj_Ar = os.path.join(FFRMS_Geodatabase, "S_FFRMS_Proj_Ar")
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting FIPS Code from S_FFRMS_Proj_Ar #####")

    with arcpy.da.SearchCursor(S_FFRMS_Proj_Ar, ["FIPS"]) as cursor:
        for row in cursor:
            FIPS_code = row[0][:5]
            break

    arcpy.AddMessage("FIPS Code found: {0}".format(FIPS_code))

    return FIPS_code

def find_CL_01_QC_point_files(tool_folder, HUC8):
    #set folder and shapefiles locations
    
    tool_folder = tool_folder.replace("'","") #Fixes One-Drive folder naming 

    #In case folder is neste4d
    for folder in os.listdir(tool_folder):
        if os.path.basename(folder) == os.path.basename(tool_folder):
            tool_folder = os.path.join(tool_folder, os.path.basename(folder))

    qc_folder = os.path.join(tool_folder, "qc_points")
    if not os.path.exists(qc_folder):
        arcpy.AddWarning("Could not find qc_points folder in tool output folder: {0}".format(tool_folder))
        return None
    
    cl_01_points_file = os.path.join(qc_folder,"qc_points_cl.shp")
    if not os.path.exists(cl_01_points_file):
        arcpy.AddWarning("Could not find qc_points_cl.shp in qc_points folder: {0}".format(qc_folder))
        return None
    else:
        arcpy.AddMessage("Found qc_points_cl.shp for HUC8 {0}".format(HUC8))
        return cl_01_points_file

def loop_through_tool_folders_for_cl_01_points_shapefiles(Tool_Output_Folders):

    cl_01_points_shapefiles_list = []

    for tool_folder in Tool_Output_Folders:
        
        tool_folder = tool_folder.replace("'","") #Fixes One-Drive folder naming 

        HUC8 = os.path.basename(tool_folder)
        
        #Search tool folder for shapefile
        cl_01_points_shapefile = find_CL_01_QC_point_files(tool_folder, HUC8)

        #If shapefile is found, add to list
        if cl_01_points_shapefile is not None:
            cl_01_points_shapefiles_list.append(cl_01_points_shapefile)

    #Merge all cl_01_points_shapefiles into one
    arcpy.AddMessage("Gathered all handy centerline qc points")
    centerline_qc_points = os.path.join("in_memory", "all_handy_centerline_qc_points")
    arcpy.management.Merge(cl_01_points_shapefiles_list, centerline_qc_points)

    return centerline_qc_points

def Select_cl_QC_Points_on_county_S_XS(centerline_qc_points, NFHL_data, county_boundary):
    arcpy.AddMessage("Selecting QC points that intersect with NFHL S_XS and are within county boundary")
    S_XS = os.path.join(NFHL_data, "FIRM_Spatial_Layers", "S_XS")

    #clip cl points to county boundary
    cl_points_clip = r"in_memory/cl_points_clip"
    arcpy.analysis.Clip(centerline_qc_points, county_boundary, cl_points_clip)

    #select all points that intersect with S_XS
    arcpy.MakeFeatureLayer_management(cl_points_clip, "cl_points_copy_intersect")
    arcpy.management.SelectLayerByLocation(in_layer="cl_points_copy_intersect", overlap_type="WITHIN A DISTANCE", select_features=S_XS, search_distance="0.1 Meters", selection_type="NEW_SELECTION")
    
    #append selected points to S_Raster_QC_pt
    centerline_qc_points_NFHL = os.path.join("in_memory", "centerline_qc_points_NFHL")
    arcpy.management.CopyFeatures("cl_points_copy_intersect", centerline_qc_points_NFHL)

    return centerline_qc_points_NFHL

def Check_QC_Pass_Rate(centerline_qc_points_NFHL):

    num_handy_qc_points_failed = 0
    total_qc_points = 0

    with arcpy.da.SearchCursor(centerline_qc_points_NFHL, ["wsel_diff"]) as cursor:
        for row in cursor:
            if row[0] > 0.5:
                num_handy_qc_points_failed += 1
            total_qc_points += 1
    
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("## HANDY QC STATS ##")
    arcpy.AddMessage("Number of QC points: {0}".format(total_qc_points))

    if total_qc_points == 0:
        arcpy.AddWarning("No QC points found - check for errors in tool output folders")
        return
    
    num_passed_qc_points = total_qc_points - num_handy_qc_points_failed
    percent_failed = round((num_handy_qc_points_failed / total_qc_points) * 100, 2)
    percent_passed = round(100 - percent_failed, 2)

    arcpy.AddMessage("Number of QC points passed based on HANDy qc values (ELEV_DIFF < 0.5): {0}".format(num_passed_qc_points))
    arcpy.AddMessage("Percent QC points passed based on HANDy qc values: {0}%".format(percent_passed))

    if percent_failed > 10:
        arcpy.AddWarning("QC Point pass rate is less than 90% - FVA Rasters do not meet FFRMS passing criteria")
    else:
        arcpy.AddMessage("QC Point pass rate is greater than 90% - raster quality is acceptable")

def get_county_info(FFRMS_Geodatabase):
    arcpy.AddMessage("Using S_FFRMS_Proj_Ar for county boundary")
    S_FFRMS_Proj_Ar = os.path.join(FFRMS_Geodatabase,"FFRMS_Spatial_Layers", "S_FFRMS_Proj_Ar")
    county_boundary = S_FFRMS_Proj_Ar
    county_name = arcpy.SearchCursor(S_FFRMS_Proj_Ar).next().getValue("POL_NAME1")
    return S_FFRMS_Proj_Ar, county_boundary, county_name

def remove_manual_AOI_entries(S_AOI_Ar):
    arcpy.AddMessage(u"\u200B")
    msg("#### Deleting manually added Levees, AH, and AO features from S_AOI_Ar ####")
    msg("This is to eliminate redundant entries... all required features will be automatically added in next steps")
    msg("There are {0} features in S_AOI_Ar before deleting Levees, AH, and AO".format(arcpy.GetCount_management(S_AOI_Ar).getOutput(0)))

    query = "AOI_ISSUE IN ('4030', '4050', '4060', 'Levee', 'AO Area', 'AH Area')"
    with arcpy.da.UpdateCursor(S_AOI_Ar, "AOI_ISSUE", query) as cursor:
        for row in cursor:
            cursor.deleteRow()
    
    msg("There are {0} features in S_AOI_Ar after deleting Levees, AH, and AO".format(arcpy.GetCount_management(S_AOI_Ar).getOutput(0)))
    msg("Now automatically adding in Levees, AH, and AO features as multipart entries...")
    return S_AOI_Ar
        
def select_levee_features(FV03_polygon, levee_features):
        
    levee_output_location = "in_memory"

    levee_FVA03 = os.path.join(levee_output_location, "levee_FVA03")
    
    arcpy.MakeFeatureLayer_management(levee_features, "levee_features")
    arcpy.SelectLayerByLocation_management("levee_features", "INTERSECT", FV03_polygon)
    arcpy.CopyFeatures_management("levee_features", levee_FVA03)

    return levee_FVA03

def Add_Levees_to_S_AOI_Ar(FV03_polygon, S_AOI_Ar, levee_features):

    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Populating S_AOI_Ar with Levee features #####")

    levee_FVA03 = select_levee_features(FV03_polygon, levee_features)
    num_levees = arcpy.GetCount_management(levee_FVA03).getOutput(0)

    #move on if no levees found
    if num_levees == "0":
        arcpy.AddMessage("No Levees found in FVA03")
        return S_AOI_Ar
    
    arcpy.AddMessage("Number of Levees found in FVA03: {0}".format(num_levees))

    #merging Levees into single multipart feature class
    msg("Merging Levees into one multipart feature class")
    merged_levees = os.path.join("in_memory", "merged_levees")
    arcpy.management.Dissolve(levee_FVA03, merged_levees)

    # Count number of entries in S_AOI_Ar before appending
    num_entries_before = int(arcpy.GetCount_management(S_AOI_Ar).getOutput(0))
    msg("Number of S_AOI_Ar entries before appending: {0}".format(num_entries_before))
    
    msg("Appending new levee features to S_AOI_Ar features...")
    arcpy.management.Append(merged_levees, S_AOI_Ar, "NO_TEST")

    #loop through appended feautres with update cursor and add values to 
    msg("Adding fields to new features ...")
    AOI_Typ = "4000" #Riverine
    AOI_Issue = "4030" #Levee
    
    row_start = num_entries_before 
    with arcpy.da.UpdateCursor(S_AOI_Ar, ["AOI_TYP", "AOI_ISSUE", "AOI_INFO", "NOTES"]) as cursor:
        #only update new features
        for row_num, row in enumerate(cursor):
            if row_num >= row_start:
                row[0] = AOI_Typ
                row[1] = AOI_Issue
                row[2] = "NP"
                row[3] = "NP"
                cursor.updateRow(row)
    
    return S_AOI_Ar

def clip_data_to_boundary(data_path, boundary, output_location):
    if not arcpy.Exists(data_path):
        arcpy.AddWarning(f"Could not find {os.path.basename(data_path)} in NFHL data")
        return None

    arcpy.AddMessage("Clipping NFHL data to county boundary")
    clipped_data = os.path.join(output_location, os.path.basename(data_path) + "_clip")
    arcpy.analysis.Clip(data_path, boundary, clipped_data)
    return clipped_data

def create_and_copy_features(source_layer, query, output_feature):
    arcpy.management.MakeFeatureLayer(source_layer, "temp_layer")
    arcpy.management.SelectLayerByAttribute(in_layer_or_view="temp_layer", selection_type="NEW_SELECTION", where_clause=query)
    arcpy.management.CopyFeatures(in_features="temp_layer", out_feature_class=output_feature)
    return output_feature

def append_and_update_features(source_features, target_features, AOI_Typ, AOI_Issue, AOI_Name, temp_output_location):
    num_features = arcpy.GetCount_management(source_features).getOutput(0)
    arcpy.AddMessage(f"Number of {AOI_Name} features found in county: {num_features}")
    if num_features != "0":
        
        merged_features = os.path.join(temp_output_location, f"features_merged_{AOI_Name}")
        arcpy.management.Dissolve(source_features, merged_features)

        msg("Number of merged {0} features: {1}".format(AOI_Name, arcpy.GetCount_management(merged_features).getOutput(0)))

        num_entries_before = int(arcpy.GetCount_management(target_features).getOutput(0))

        arcpy.management.Append(merged_features, target_features, "NO_TEST")
        
        arcpy.AddMessage(f"Appending {AOI_Name} features to {os.path.basename(target_features)}")

        arcpy.AddMessage(f"Adding fields to new {AOI_Name} features ...")
        with arcpy.da.UpdateCursor(target_features, ["AOI_TYP", "AOI_ISSUE", "AOI_INFO", "NOTES"]) as cursor:
            for row_num, row in enumerate(cursor):
                if row_num >= num_entries_before:
                    row[0] = AOI_Typ
                    row[1] = AOI_Issue
                    row[2] = "NP"
                    row[3] = "NP"
                    cursor.updateRow(row)

def Add_AH_AO_to_S_AOI_Ar(NFHL_data, county_boundary, S_AOI_Ar):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Populating S_AOI_Ar with AH and AO features #####")

    temp_output_location = "in_memory"

    S_Fld_Haz_Ar = os.path.join(NFHL_data, "FIRM_Spatial_Layers", "S_Fld_Haz_Ar")
    NFHL_data_clip = clip_data_to_boundary(S_Fld_Haz_Ar, county_boundary, temp_output_location)
    if not NFHL_data_clip:
        return S_AOI_Ar

    AO_features = create_and_copy_features(NFHL_data_clip, "FLD_ZONE = 'AO'", os.path.join(temp_output_location, "AO_features"))
    AH_features = create_and_copy_features(NFHL_data_clip, "FLD_ZONE = 'AH'", os.path.join(temp_output_location, "AH_features"))

    append_and_update_features(AO_features, S_AOI_Ar, "4000", "4050", "AO", temp_output_location)  # Riverine, AO
    append_and_update_features(AH_features, S_AOI_Ar, "4000", "4060", "AH", temp_output_location)  # Riverine, AH

    return S_AOI_Ar

def Populate_S_AOI_Ar(FFRMS_Geodatabase, county_name, NFHL_100yr, FV00_polygon, FIPS_code):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Populating S_AOI_Ar #####")    
        
    S_AOI_Ar = os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers", "S_AOI_Ar")

    riv_or_cst = os.path.basename(FFRMS_Geodatabase).split("_")[-1][:1]

    #set paths
    NFHL_not_FVA00 = os.path.join("in_memory", "NFHL_100yr_not_FVA00")
    FVA00_not_NFHL = os.path.join("in_memory", "FVA00_not_NFHL_100yr")

    #Erases features from input, and dissolves to single multipart feature class
    arcpy.AddMessage("Creating comparison polygons between NFHL_100yr and FVA00")
    Erase_without_tool(input_features = NFHL_100yr, erase_features=FV00_polygon, output_feature_class=NFHL_not_FVA00)
    Erase_without_tool(input_features = FV00_polygon, erase_features=NFHL_100yr, output_feature_class=FVA00_not_NFHL)

    #Append both feature classes to S_AOI_Ar
    arcpy.AddMessage("Appending to S_AOI_Ar")

    aoi_notes_already_populated = [row[0] for row in arcpy.da.SearchCursor(S_AOI_Ar, ["NOTES"])]
    aoi_info_already_populated = [row[0] for row in arcpy.da.SearchCursor(S_AOI_Ar, ["AOI_INFO"])]

    NFHL_not_FVA00_text = "The FEMA Special Flood Hazard Area (SFHA) in this area is not included in the FVA0 grid. This may be due to differences in the terrain data used or engineering and mapping judgements made during the FEMA flood study."
    FVA00_not_NFHL_text = "The FVA0 grid in this area is not included in the FEMA Special Flood Hazard Area (SFHA). This may be due to differences in the terrain data used or engineering and mapping judgements made during the FEMA flood study."
    
    #populate S_AOI with NFHL_not_FVA00 polygon
    if NFHL_not_FVA00_text in aoi_notes_already_populated or NFHL_not_FVA00_text in aoi_info_already_populated:
        arcpy.AddWarning("NFHL vs FVA00 comparison polygons already exist in S_AOI_Ar - manually delete and re-run if you want to update")
    else:
        arcpy.management.Append(NFHL_not_FVA00, S_AOI_Ar, "NO_TEST")
        row_count = int(arcpy.GetCount_management(S_AOI_Ar).getOutput(0))
        with arcpy.da.UpdateCursor(S_AOI_Ar, ["AOI_TYP", "AOI_ISSUE", "AOI_INFO", "NOTES"]) as cursor:
            for i, row in enumerate(cursor):
                if i == row_count - 1:
                    row[0] = "4000"
                    row[1] = "4100"
                    row[2] = NFHL_not_FVA00_text
                    row[3] = "NP"
                    cursor.updateRow(row)

    #populate S_AOI with FVA00_not_NFHL polygon
    if FVA00_not_NFHL_text in aoi_notes_already_populated or FVA00_not_NFHL_text in aoi_info_already_populated:
        arcpy.AddWarning("FVA00 vs NFHL comparison polygons already exist in S_AOI_Ar - manually delete and re-run if you want to update")
    else:
        arcpy.management.Append(FVA00_not_NFHL, S_AOI_Ar, "NO_TEST")
        row_count = int(arcpy.GetCount_management(S_AOI_Ar).getOutput(0))
        with arcpy.da.UpdateCursor(S_AOI_Ar, ["AOI_TYP", "AOI_ISSUE", "AOI_INFO", "NOTES"]) as cursor:
            for i, row in enumerate(cursor):
                if i == row_count - 1:
                    row[0] = "4000"
                    row[1] = "4100"
                    row[2] = FVA00_not_NFHL_text
                    row[3] = "NP"
                    cursor.updateRow(row)

    #populate all fields
    arcpy.AddMessage("Updating Fields in S_AOI_Ar")
    with arcpy.da.UpdateCursor(S_AOI_Ar, ["AOI_ID", "POL_NAME1", "FIPS", "AOI_INFO", "NOTES"]) as cursor:
        for i, row in enumerate(cursor):
            aoi_id = "{0}{1}_{2}".format(riv_or_cst,FIPS_code,i + 1)
            row[0] = aoi_id
            row[1] = county_name
            row[2] = FIPS_code
            if row[3] == None:
                msg(f"No AOI_Info text found for {aoi_id} - populating with 'NP'")
                row[3] = "NP"
            if row[4] == None:
                msg(f"No Notes text found for {aoi_id} - populating with 'NP'")
                row[4] = "NP"
            cursor.updateRow(row)

def Add_CNMS_Lines_to_S_AOI_Ar(FFRMS_Geodatabase, NFHL_data, county_boundary, FV03_polygon, S_AOI_Ar):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Populating S_AOI_Ar with CNMS Lines without MIP Data #####")
    
    CNMS_file = r"\\us0525-ppfss01\shared_projects\203432303012\FFRMS_Zone3\production\source_data\CNMS\230613_FY23Q2_STARRII_CNMS_Tiers345.gdb\R8_R9_10_FFRMS_All_Scope"
    if not arcpy.Exists(CNMS_file):
        arcpy.AddWarning("Could not find CNMS file (on Stantec Server Only) - skipping adding CNMS lines with no MIP/NFHL Data to AOIs")
        arcpy.AddWarning("Please manually buffer and add any CNMS Lines with no NFHL or MIP Data as AOIs with AOI_ISSUE = 'MIP search undertaken - data not found'")
        return
    
    NFHL_S_XS = os.path.join(NFHL_data, "FIRM_Spatial_Layers", "S_XS")
    NFHL_S_BFE = os.path.join(NFHL_data, "FIRM_Spatial_Layers", "S_BFE")
    temp_output_location = "in_memory"
    
    #Create combined S_XS and S_BFE feature class
    arcpy.AddMessage("Creating combined S_XS and S_BFE feature class")
    NFHL_S_XS_BFE = os.path.join(temp_output_location, "NFHL_S_XS_BFE")
    arcpy.management.Merge([NFHL_S_XS, NFHL_S_BFE], NFHL_S_XS_BFE)

    #select CNMS AOIs that intersect with county boundary
    arcpy.AddMessage("Selecting CNMS AOIs that intersect with county boundary")
    County_CNMS_Lines = os.path.join(temp_output_location, "County_CNMS_Lines")
    arcpy.analysis.Clip(CNMS_file, county_boundary, County_CNMS_Lines)

    #Select CNMS AOIs where the MIP_Data_Avail field is Null or F
    arcpy.AddMessage("Selecting CNMS AOIs where the MIP_Data_Avail field is Null or F")
    CNMS_Lines_MIP_False = arcpy.MakeFeatureLayer_management(County_CNMS_Lines, "CNMS_Lines_MIP_False")
    arcpy.management.SelectLayerByAttribute(CNMS_Lines_MIP_False, "NEW_SELECTION", "MIP_Data_Avail = 'F' OR MIP_Data_Avail = 'FALSE (No)' or MIP_Data_Avail = 'FALSE'")
    
    #Select CNMS AOIs that intersect 1 or fewer NFHL XS or BFE
    arcpy.AddMessage("Selecting CNMS AOIs that intersect 1 or fewer NFHL XS or BFE")
    target_features = CNMS_Lines_MIP_False
    intersect_features = NFHL_S_XS_BFE

    # Perform a Spatial Join
    msg("Performing spatial join...")
    spatial_join_result = os.path.join(temp_output_location, "SpatialJoinResult")
    arcpy.analysis.SpatialJoin(target_features, intersect_features, spatial_join_result, "JOIN_ONE_TO_ONE", "KEEP_ALL", match_option="INTERSECT")

    # Select the features from target where the count is 0 or 1
    count_field = "Join_Count"
    CNMS_Lines_MIP_False_No_NFHL = arcpy.MakeFeatureLayer_management(spatial_join_result, "CNMS_Lines_MIP_False_No_NFHL")
    arcpy.management.SelectLayerByAttribute(CNMS_Lines_MIP_False_No_NFHL, "NEW_SELECTION", f"{count_field} <= 1")

    # Export the selected features to a new feature class
    msg("Copying chosen CNMS lines features")
    Selected_CNMS_Lines = os.path.join(temp_output_location, "Selected_CNMS_Lines")
    arcpy.CopyFeatures_management(CNMS_Lines_MIP_False_No_NFHL, Selected_CNMS_Lines)

    #Get count of CNMS_Lines_MIP_False_No_NFHL
    Num_CNMS_Lines = arcpy.GetCount_management(CNMS_Lines_MIP_False_No_NFHL).getOutput(0)
    arcpy.AddMessage("Number of CNMS AOIs that intersect 1 or fewer NFHL XS or BFE: {0}".format(Num_CNMS_Lines))

    if Num_CNMS_Lines == "0":
        arcpy.AddMessage("No CNMS AOIs that intersect 1 or fewer NFHL XS or BFE - skipping CNMS AOI processing")
        return

    #Buffer selected CNMS AOIs by 20 feet
    CNMS_Lines_MIP_False_No_NFHL_buffer = os.path.join(temp_output_location, "CNMS_Lines_MIP_False_No_NFHL_buffer")
    buffer_distance = "300 Feet"
    dissolve = "ALL"
    arcpy.AddMessage(f"Buffering selected CNMS lines by {buffer_distance}")
    arcpy.analysis.Buffer(CNMS_Lines_MIP_False_No_NFHL, CNMS_Lines_MIP_False_No_NFHL_buffer, buffer_distance, "FULL", "ROUND", dissolve_option = dissolve, method = "PLANAR")

    #Delete any part of the buffer that is within with the FVA03 floodplain
    arcpy.AddMessage("Deleting any part of the buffer that is within with the FVA03 floodplain")
    CNMS_AOIs = os.path.join(temp_output_location, "CNMS_AOIs")
    arcpy.analysis.Erase(CNMS_Lines_MIP_False_No_NFHL_buffer, FV03_polygon, CNMS_AOIs)

    #Get count of CNMS_AOIS
    arcpy.AddMessage("Number of Merged CNMS AOIs: {0}".format(arcpy.GetCount_management(CNMS_AOIs).getOutput(0)))

    #Append CNMS AOIs to S_AOI_Ar
    arcpy.AddMessage("Appending CNMS AOIs to S_AOI_Ar")
    num_entries_before = int(arcpy.GetCount_management(S_AOI_Ar).getOutput(0))
    arcpy.management.Append(CNMS_AOIs, S_AOI_Ar, "NO_TEST")

    #Populate Fields
    row_start = num_entries_before 
    with arcpy.da.UpdateCursor(S_AOI_Ar, ["AOI_TYP", "AOI_ISSUE", "AOI_INFO", "NOTES"]) as cursor:
        #only update new features
        for row_num, row in enumerate(cursor):
            if row_num >= row_start:
                row[0] = "1000" #Data Collection 
                row[1] = "1020" #MIP search undertaken - data not found
                row[2] = "NP"
                row[3] = "NP"
                cursor.updateRow(row)

if __name__ == "__main__":
    
    FFRMS_Geodatabase = arcpy.GetParameterAsText(0)
    Tool_Output_Folders = arcpy.GetParameterAsText(1).split(";")
    Tool_Template_Folder = arcpy.GetParameterAsText(2)

    arcpy.env.workspace = FFRMS_Geodatabase
    arcpy.env.overwriteOutput = True

    #Get FIPS code from S_FFRMS_Proj_Ar
    FIPS_code = get_FIPS(FFRMS_Geodatabase)
    State_code = FIPS_code[:2]
    County_code = FIPS_code[2:5]

    #Get and Check Source Data
    S_FFRMS_Proj_Ar, county_boundary, county_name = get_county_info(FFRMS_Geodatabase)
    NFHL_data, levee_features = Check_Source_Data(Tool_Template_Folder)
    S_FFRMS_Ar = os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers", "S_FFRMS_Ar")
    S_AOI_Ar = os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers", "S_AOI_Ar")

    FV00_polygon, FV03_polygon = Convert_Rasters_to_Polygon(FFRMS_Geodatabase)

    NFHL_100yr = Extract_NFHL_100yr_Floodplain(FIPS_code, FFRMS_Geodatabase, NFHL_data, S_FFRMS_Proj_Ar)

    #Populate all S_FFRMS_AR Fields
    Populate_S_FFRMS_Ar(FV03_polygon, S_FFRMS_Proj_Ar, S_FFRMS_Ar, county_name, FIPS_code)

    #CNMS AOIs
    Add_CNMS_Lines_to_S_AOI_Ar(FFRMS_Geodatabase, NFHL_data, county_boundary, FV03_polygon, S_AOI_Ar)
    
    #Delete entries in S_AOI_Ar with levees, AH, AO
    S_AOI_Ar = remove_manual_AOI_entries(S_AOI_Ar)

    #Levees
    S_AOI_Ar = Add_Levees_to_S_AOI_Ar(FV03_polygon, S_AOI_Ar, levee_features)

    #AH and AO
    S_AOI_Ar = Add_AH_AO_to_S_AOI_Ar(NFHL_data, county_boundary, S_AOI_Ar)

    #Populate all S_AOI_Ar fields
    Populate_S_AOI_Ar(FFRMS_Geodatabase, county_name, NFHL_100yr, FV00_polygon, FIPS_code)

    #Delete identical records based on SHAPE

    # msg("Deleting any identical records...")
    # msg("Number of features prior to deleting identical features: {0}".format(arcpy.GetCount_management(S_AOI_Ar).getOutput(0)))
    # arcpy.management.DeleteIdentical(in_dataset=S_AOI_Ar, fields=["Shape"], xy_tolerance="1 Meters")
    # msg("Number of features after deleting identical records: {0}".format(arcpy.GetCount_management(S_AOI_Ar).getOutput(0)))
    
    # Populate S_Raster_QC_pt
    S_Raster_QC_pt = Populate_S_Raster_QC_pt(FFRMS_Geodatabase, NFHL_data, Tool_Output_Folders, county_boundary, FIPS_code, county_name)
    
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Assessing QC Point pass rate #####")

    centerline_qc_points = loop_through_tool_folders_for_cl_01_points_shapefiles(Tool_Output_Folders)
    centerline_qc_points_NFHL = Select_cl_QC_Points_on_county_S_XS(centerline_qc_points, NFHL_data, county_boundary)
    Check_QC_Pass_Rate(centerline_qc_points_NFHL)
