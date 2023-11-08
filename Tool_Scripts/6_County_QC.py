import arcpy
from sys import argv
import sys
import os
from arcpy import env
from arcpy.sa import *

def get_FFRMS_files(FFRMS_Geodatabase):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Checking Input Files #####")

    S_FFRMS_Ar = os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers", "S_FFRMS_Ar")
    S_FFRMS_Proj_Ar = os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers", "S_FFRMS_Proj_Ar")
    FVA0_Raster = None

    #List All Rasters in GDB
    arcpy.env.workspace = FFRMS_Geodatabase
    rasters = arcpy.ListRasters()

    #Look for 00FVA raster
    for raster in rasters:
        if "00FVA" in raster:
            FVA0_Raster = os.path.join(FFRMS_Geodatabase, raster)
            arcpy.AddMessage("Found 00FVA raster: {0}".format(os.path.basename(FVA0_Raster)))
            break

    if FVA0_Raster == None:
        arcpy.AddError("Could not find 00FVA raster within FFRMS geodatabase - please make sure 00FVA raster exists")
        sys.exit()

    for file in [S_FFRMS_Ar, S_FFRMS_Proj_Ar]:
        if not arcpy.Exists(file):
            arcpy.AddError("Could not find {0} within FFRMS geodatabase FFRMS_Spatial_Layers".format(os.path.basename(file)))
            sys.exit()

    arcpy.AddMessage("All necessary files found")
    
    return S_FFRMS_Ar, S_FFRMS_Proj_Ar, FVA0_Raster

def get_NFHL_data(NFHL_data):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting NFHL Data #####")

    if NFHL_data == "" or NFHL_data == None:
        NFHL_data = r"\\us0525-PPFSS01\shared_projects\203432303012\FFRMS_Zone3\production\source_data\NFHL\rFHL_20230630.gdb"
        arcpy.AddMessage("No NFHL Zone 3 database provided - using NFHL Zone 3 data on Stantec Server: {0}".format(NFHL_data))
    else:
        arcpy.AddMessage("Using provided NFHL data: {0}".format(NFHL_data))
    
    if not os.path.exists(NFHL_data):
        arcpy.AddError("Could not find NFHL_data at file location {0} - please make sure NFHL_data exists".format(NFHL_data))
        sys.exit()

    S_XS = os.path.join(NFHL_data, "FIRM_Spatial_Layers", "S_XS")
    S_Profil_Basln = os.path.join(NFHL_data, "FIRM_Spatial_Layers", "S_Profil_Basln")
    S_Wtr_Ln = os.path.join(NFHL_data, "FIRM_Spatial_Layers", "S_Wtr_Ln")

    for file in [S_XS, S_Profil_Basln, S_Wtr_Ln]:
        if not arcpy.Exists(file):
            arcpy.AddError("Could not find {0} within NFHL geodatabase FIRM_Spatial_Layers".format(os.path.basename(file)))
            sys.exit()

    return S_XS, S_Profil_Basln, S_Wtr_Ln

def select_NFHL_by_County(S_XS, S_Profil_Basln, S_FFRMS_Proj_Ar, S_Wtr_Ln):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Selecting NFHL Data within County Boundary #####")
    
    # S_XS_County = os.path.join("in_memory", "S_XS_County")
    # S_Profil_Basln_County = os.path.join("in_memory", "S_Profil_Basln_County")

    S_XS_County = os.path.join("in_memory", "S_XS_County")
    S_Profil_Basln_County = os.path.join("in_memory", "S_Profil_Basln_County")
    S_Wtr_Ln_County = os.path.join("in_memory", "S_Wtr_Ln_County")

    arcpy.AddMessage("Selecting S_XS")
    arcpy.MakeFeatureLayer_management(S_XS, "S_XS_copy")
    arcpy.management.SelectLayerByLocation(in_layer="S_XS_copy", overlap_type="WITHIN", 
                                           select_features=S_FFRMS_Proj_Ar, selection_type="NEW_SELECTION")
    arcpy.CopyFeatures_management("S_XS_copy", S_XS_County)

    # arcpy.AddMessage("Selecting S_Profil_Basln")
    # arcpy.MakeFeatureLayer_management(S_Profil_Basln, "S_Profil_Basln_copy")
    # arcpy.management.SelectLayerByLocation(in_layer="S_Profil_Basln_copy", overlap_type="WITHIN", 
    #                                        select_features=S_FFRMS_Proj_Ar, selection_type="NEW_SELECTION")
    # arcpy.CopyFeatures_management("S_Profil_Basln_copy", S_Profil_Basln_County)

    # arcpy.AddMessage("Selecting S_Wtr_Ln")
    # arcpy.MakeFeatureLayer_management(S_Wtr_Ln, "S_Wtr_Ln_copy")
    # arcpy.management.SelectLayerByLocation(in_layer="S_Wtr_Ln_copy", overlap_type="WITHIN", 
    #                                        select_features=S_FFRMS_Proj_Ar, selection_type="NEW_SELECTION")
    # arcpy.CopyFeatures_management("S_Wtr_Ln_copy", S_Wtr_Ln_County)

    # return S_XS_County, S_Profil_Basln_County, S_Wtr_Ln_County

    return S_XS_County

def create_intersection_points(S_XS_County, S_Profil_Basln_County, S_Wtr_Ln_County, output_spatial_reference):
    #create intersection points at each XS with the profile baseline
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Creating Intersection Points #####")

    #unsplit both lines
    arcpy.AddMessage("Cleaning up (unsplitting) spatial lines")
    S_XS_County_unsplit = os.path.join("in_memory", "S_XS_County_Unsplit")
    S_Profil_Basln_County_unsplit = os.path.join("in_memory", "S_Profil_Basln_County_Unsplit")
    S_Wtr_Ln_County_unsplit = os.path.join("in_memory", "S_Wtr_Ln_County_Unsplit")

    arcpy.UnsplitLine_management(S_XS_County, S_XS_County_unsplit)
    arcpy.UnsplitLine_management(S_Profil_Basln_County, S_Profil_Basln_County_unsplit)
    arcpy.UnsplitLine_management(S_Wtr_Ln_County, S_Wtr_Ln_County_unsplit)

    centerline_qc_points = os.path.join(QC_point_output_location, "centerline_qc_points")
    
    if not arcpy.Exists(centerline_qc_points):
        #Create centerline_qc_points feature class
        arcpy.AddMessage("Creating centerline_qc_points feature class")
        arcpy.management.CreateFeatureclass(out_path=QC_point_output_location, 
                                            out_name = "centerline_qc_points", 
                                            geometry_type="MULTIPOINT", 
                                            spatial_reference = output_spatial_reference)
        
        #Add fields to centerline_qc_points
        arcpy.management.AddField(centerline_qc_points, "WSEL_grid", "DOUBLE")
        arcpy.management.AddField(centerline_qc_points, "WSEL_diff", "DOUBLE")
        arcpy.management.AddField(centerline_qc_points, "PassFail", "Text", "", "", "10")
        arcpy.management.AddField(centerline_qc_points, "CL_Source", "Text", "", "", "25")
                                             
    #Run intersect tool
    arcpy.AddMessage("Finding intersections of S_XS and S_Profil_Basln")
    QC_Profile_Ln = os.path.join(QC_point_output_location, "QC_Profile_Ln")
    QC_Wtr_Ln = os.path.join(QC_point_output_location, "QC_Wtr_Ln")

    #Create Intersect Points
    arcpy.analysis.Intersect([S_XS_County_unsplit, S_Profil_Basln_County_unsplit], QC_Profile_Ln, "", "", "point")
    arcpy.analysis.Intersect([S_XS_County_unsplit, S_Wtr_Ln_County_unsplit], QC_Wtr_Ln, "", "", "point")

    #Add Field
    arcpy.management.AddField(QC_Profile_Ln, "CL_Source", "Text", "", "", "25")
    arcpy.management.AddField(QC_Wtr_Ln, "CL_Source", "Text", "", "", "25")

    #Calculate field
    arcpy.management.CalculateField(QC_Profile_Ln, "CL_Source", "'S_Profil_Basln'", "PYTHON3", "")
    arcpy.management.CalculateField(QC_Wtr_Ln, "CL_Source", "'S_Wtr_Ln'", "PYTHON3", "")

    #Append into centerline_qc_points
    arcpy.management.Append([QC_Profile_Ln, QC_Wtr_Ln], centerline_qc_points, "NO_TEST")

    # TODO: If there are multiple points that are within 0.5 meters of one another (assuming because there is an S_Profil_Basln and S_Water_Ln overlapping), 
    # keep only one. Choose the one to pick as having 'S_Profil_Basln' as the CL_Source. If multiple points have 'S_Profil_Basln' as the CL_Source,
    # just keep one. If there are multiple points with 'S_Wtr_Ln' as the CL_Source, just keep one.
    # Add a new field to store the distance for near analysis
    
    return centerline_qc_points

def remove_duplicate_points(centerline_qc_points, S_XS_County):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Removing Duplicate Points #####")

    num_points_before = arcpy.management.GetCount(centerline_qc_points)[0]
    num_XS = arcpy.management.GetCount(S_XS_County)[0]
    arcpy.AddMessage("Number of points before removing duplicates: {0}".format(num_points_before))
    arcpy.AddMessage("Number of XS: {0}".format(num_XS))

    for i in range(0, int(num_XS)):
        arcpy.AddMessage("Removing duplicate points for XS {0}".format(i))
        arcpy.management.MakeFeatureLayer(centerline_qc_points, "centerline_qc_points_lyr")
        arcpy.management.SelectLayerByAttribute(in_layer_or_view="centerline_qc_points_lyr", selection_type="NEW_SELECTION", 
                                                where_clause="CL_Source = 'S_Profil_Basln' AND FID_S_XS = {0}".format(i))
        arcpy.management.DeleteFeatures("centerline_qc_points_lyr")

def select_by_FFRMS_Ar(centerline_qc_points, S_FFRMS_Ar):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Selecting QC Points within FVA #####")

    #Select FVA0 grid 
    arcpy.AddMessage("Selecting S_FFRMS_Ar where FFRMS_AVL = TRUE")
    arcpy.management.MakeFeatureLayer(S_FFRMS_Ar, "FVA0_grid", "FFRMS_AVL = 'T'")

    #Select QC Points within FVA0 grid
    arcpy.AddMessage("Subsetting QC Points")
    centerline_qc_points_NFHL = os.path.join("in_memory", "centerline_qc_points_NHFL")

    arcpy.management.MakeFeatureLayer(centerline_qc_points, "centerline_qc_points_lyr")
    arcpy.management.SelectLayerByLocation(in_layer="centerline_qc_points_lyr", overlap_type="INTERSECT", 
                                           select_features="FVA0_grid", selection_type="NEW_SELECTION")
    arcpy.CopyFeatures_management("centerline_qc_points_lyr", centerline_qc_points_NFHL)

    return centerline_qc_points_NFHL

def remove_null_vals(centerline_qc_points_NFHL):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Removing Null WSEL_REG Values #####")
    with arcpy.da.UpdateCursor(centerline_qc_points_NFHL, ["WSEL_REG"]) as cursor:
        for row in cursor:
            if row[0] == -9999 or row[0] == -8888 or row[0] == None:
                arcpy.AddMessage("Deleting bad value {0}".format(row[0]))
                cursor.deleteRow()
    return centerline_qc_points_NFHL

def get_S_XS_values(S_XS, centerline_qc_points_NFHL):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting WSEL_REG and WTR_NM values from S_XS #####")

    #Spatially join temp layer with S_XS to get WSEL_REG values
    arcpy.AddMessage("Spatially joining S_XS and centerline_qc_points_NFHL")
    arcpy.management.MakeFeatureLayer(S_XS, "S_XS_lyr")
    arcpy.analysis.SpatialJoin(centerline_qc_points_NFHL, "S_XS_lyr", "centerline_qc_points_NFHL_WSEL_REG", "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "INTERSECT", "", "")
    
    #join WSEL_Reg values to centerline_qc_points_NFHL
    arcpy.AddMessage("Joining WSEL_REG and WTR_NM values")
    arcpy.management.JoinField(centerline_qc_points_NFHL, "FID", "centerline_qc_points_NFHL_WSEL_REG", "TARGET_FID", "WSEL_REG")
    arcpy.management.JoinField(centerline_qc_points_NFHL, "FID", "centerline_qc_points_NFHL_WSEL_REG", "TARGET_FID", "WTR_NM")

    #alter field to add "_manual" to end
    arcpy.management.AlterField(centerline_qc_points_NFHL, "WSEL_REG", "WSEL_REG_manual")
    arcpy.management.AlterField(centerline_qc_points_NFHL, "WTR_NM", "WTR_NM_manual")

    #delete extra field
    arcpy.management.DeleteField(centerline_qc_points_NFHL, "TARGET_FID")
    arcpy.management.Delete("centerline_qc_points_NFHL_WSEL_REG")

    return centerline_qc_points_NFHL

def calculate_grid_values(centerline_qc_points_NFHL, FVA0_Raster):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting WSEL_grid values from FVA0 grid #####")

    #Get WSEL_grid values from FVA0 grid
    arcpy.AddMessage("Extracting WSEL_grid values from FVA0 grid")
    ExtractMultiValuesToPoints(centerline_qc_points_NFHL, [[FVA0_Raster, "wsel_grid_manual"]], "NONE")

    #Calculate WSEL_diff
    arcpy.AddMessage("Calculating WSEL_diff")
    arcpy.management.CalculateField(centerline_qc_points_NFHL, "wsel_diff_manual", "abs(!wsel_grid_manual! - !WSEL_REG!)", "PYTHON3", "")

    return centerline_qc_points_NFHL

def Check_QC_Pass_Rate(centerline_qc_points_NFHL):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Assessing QC Point pass rate #####")

    num_handy_qc_points_failed = 0
    num_manual_qc_points_failed = 0
    total_qc_points = 0

    with arcpy.da.UpdateCursor(centerline_qc_points_NFHL, ["wsel_diff_handy", "wsel_diff_manual", "PassFail_handy", "PassFail_manual", "wsel_grid_manual"]) as cursor:
        for row in cursor:
            if row[4] is None: #Delete entry if there is no grid value
                cursor.deleteRow()
                continue
            if row[0] > 0.5:
                num_handy_qc_points_failed += 1
                row[2] = "Fail"
            else:
                row[2] = "Pass"
            if row[1] > 0.5:
                num_manual_qc_points_failed += 1
                row[3] = "Fail"
            else:
                row[3] = "Pass"

            total_qc_points += 1
            cursor.updateRow(row)
    
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("## HANDY QC STATS ##")

    num_passed_qc_points = total_qc_points - num_handy_qc_points_failed
    percent_failed = round((num_handy_qc_points_failed / total_qc_points) * 100, 2)
    percent_passed = round(100 - percent_failed, 2)
    arcpy.AddMessage("Number of QC points: {0}".format(total_qc_points))
    arcpy.AddMessage("Number of QC points passed with HANDy values (ELEV_DIFF < 0.5): {0}".format(num_passed_qc_points))
    arcpy.AddMessage("Percent QC points Passed with HANDy values: {0}%".format(percent_passed))

    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("### MANUAL QC STATS ###")
    num_passed_qc_points = total_qc_points - num_manual_qc_points_failed
    percent_failed = round((num_manual_qc_points_failed / total_qc_points) * 100, 2)
    percent_passed = round(100 - percent_failed, 2)
    arcpy.AddMessage("Number of QC points passed with manually extracted values (ELEV_DIFF < 0.5): {0}".format(num_passed_qc_points))
    arcpy.AddMessage("Percent QC points Passed with manually extracted values: {0}%".format(percent_passed))

    if percent_failed > 10:
        arcpy.AddWarning("QC Point pass rate is less than 90% - FVA Rasters do not meet FFRMS passing criteria")
    else:
        arcpy.AddMessage("QC Point pass rate is greater than 90% - raster quality is acceptable")

def find_CL_01_QC_point_files(tool_folder):
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
        arcpy.AddMessage("Found qc_points_cl.shp")
        return cl_01_points_file

def loop_through_tool_folders_for_cl_01_points_shapefiles(Tool_Output_Folders):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Finding CL QC Point Shapefiles within tool folders #####")

    cl_01_points_shapefiles_list = []

    for tool_folder in Tool_Output_Folders:
        
        tool_folder = tool_folder.replace("'","") #Fixes One-Drive folder naming 

        HUC8 = os.path.basename(tool_folder)
        arcpy.AddMessage("HUC {0}".format(HUC8))
        
        #Search tool folder for shapefile
        cl_01_points_shapefile = find_CL_01_QC_point_files(tool_folder)

        #If shapefile is found, add to list
        if cl_01_points_shapefile is not None:
            cl_01_points_shapefiles_list.append(cl_01_points_shapefile)

    #Merge all cl_01_points_shapefiles into one
    arcpy.AddMessage("Merging all handy centerline qc points")
    centerline_qc_points = os.path.join("in_memory", "all_handy_centerline_qc_points")
    arcpy.management.Merge(cl_01_points_shapefiles_list, centerline_qc_points)

    return centerline_qc_points

def rename_add_fields(centerline_qc_points):
    arcpy.AddMessage("Renaming handy fields")
    handy_fc = arcpy.ListFields(centerline_qc_points)
    arcpy.AddMessage("HANDy fields are: {0}".format([field.name for field in handy_fc]))
    for field in handy_fc:
        if field.name in ["wsel_grid","wsel_diff"]:
            arcpy.management.AlterField(centerline_qc_points, field.name, field.name + "_handy", field.name + "_handy")

        #Add fields to centerline_qc_points
    arcpy.AddMessage("Adding Manual fields")
    arcpy.management.AddField(centerline_qc_points, "WSEL_diff_manual", "DOUBLE")
    arcpy.management.AddField(centerline_qc_points, "PassFail_handy", "Text", "", "", "10")
    arcpy.management.AddField(centerline_qc_points, "PassFail_manual", "Text", "", "", "10")

    return centerline_qc_points

if __name__ == "__main__":

    #Take Tool inputs
    FFRMS_Geodatabase = arcpy.GetParameterAsText(0)
    Tool_Output_Folders = arcpy.GetParameterAsText(1).split(";")
    NFHL_data = arcpy.GetParameterAsText(2)

    #Set up environment
    arcpy.env.overwriteOutput = True
    #QC_point_output_location = os.path.dirname(os.path.dirname(os.path.dirname(FFRMS_Geodatabase)))
    QC_point_output_location = os.path.dirname(os.path.dirname(os.path.dirname(FFRMS_Geodatabase)))
    arcpy.env.workspace = FFRMS_Geodatabase

    #Get Data
    S_FFRMS_Ar, S_FFRMS_Proj_Ar, FVA0_Raster = get_FFRMS_files(FFRMS_Geodatabase)
    S_XS, S_Profil_Basln, S_Wtr_Ln = get_NFHL_data(NFHL_data)
    output_spatial_reference= arcpy.Describe(S_FFRMS_Ar).spatialReference
    arcpy.AddMessage("Spatial Reference is: {0}".format(output_spatial_reference.name))
    
    #Select NFHL data within County Boundary
    S_XS_County= select_NFHL_by_County(S_XS, S_Profil_Basln, S_FFRMS_Proj_Ar, S_Wtr_Ln)

    #Loop through folders, find centerline qc points, and merge into one
    centerline_qc_points = loop_through_tool_folders_for_cl_01_points_shapefiles(Tool_Output_Folders)
    centerline_qc_points = rename_add_fields(centerline_qc_points)

    #Select QC Points within FVA0 grid
    centerline_qc_points_NFHL = select_by_FFRMS_Ar(centerline_qc_points, S_FFRMS_Ar)

    #Project points to final zone
    arcpy.AddMessage("Projecting centerline_qc_points_NFHL to {0}".format(output_spatial_reference.name))
    centerline_qc_points_NFHL_projected = os.path.join(FFRMS_Geodatabase, "centerline_qc_points_NFHL_projected")
    arcpy.management.Project(centerline_qc_points_NFHL, centerline_qc_points_NFHL_projected, output_spatial_reference)

    #Spatially join with S_XS to get WSEL_REG values
    #centerline_qc_points_NFHL = get_S_XS_values(S_XS, centerline_qc_points_NFHL)

    #Erase any points where WSEL_REG values is null
    centerline_qc_points_NFHL_projected = remove_null_vals(centerline_qc_points_NFHL_projected)

    #Get WSEL_grid values from FVA0 grid    
    centerline_qc_points_NFHL_projected = calculate_grid_values(centerline_qc_points_NFHL_projected, FVA0_Raster)

    #Check QC Pass Rate
    Check_QC_Pass_Rate(centerline_qc_points_NFHL_projected)

    #Export centerline_qc_points_NFHL to shapefile
    arcpy.AddMessage("Exporting centerline_qc_points_NFHL to shapefile")
    arcpy.management.CopyFeatures(centerline_qc_points_NFHL_projected, os.path.join(QC_point_output_location, "Centerline_qc_points_NFHL_projected.shp"))

    #Create QC Points at intersection of S_XS and S_Profil_Basln
    # centerline_qc_points = create_intersection_points(S_XS_County, S_Profil_Basln_County, S_Wtr_Ln_County, output_spatial_reference)

    # #Remove Duplicate Points
    # centerline_qc_points = remove_duplicate_points(centerline_qc_points, S_XS_County)

    # TODO:
    #	Create points at the intersection of the NFHL profile baseline and the NFHL S_XS layer
    # •	Erase any points that are not located within the FFRMS_AR where the polygon is True (keep only points where the FVA grid exists)
    # •	Erase any points where WSEL_REG values is null = -9999
    # •	get the FVA0 grid value at the points using Extract Values to Points geoprocessing tool
    # •	get the WSEL_REG from S_XS layer by doing a spatial join with the QC points and the NFHL S_XS (or this may be able to be retained from when you create the points from NFHL to start)
    # •	computing absolute value of difference between grid value and WSEL_REG
    # •	determine and report out pass rate

    #sometimes there will be an S_Profil_Basln sometimes not. 
    #When there is not, the QC points will be created at the intersection of the S_XS and S_Wtr_Ln

    #When creating intersection points, I want loop through all S_XS, create an intersection point with S_Profil_Basln, if no point is made, intersect with S_WTR_Ln

