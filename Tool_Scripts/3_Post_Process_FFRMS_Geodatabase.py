"""
Script documentation

- Tool parameters are accessed using arcpy.GetParameter() or 
                                     arcpy.GetParameterAsText()
- Update derived parameter values using arcpy.SetParameter() or
                                        arcpy.SetParameterAsText()
"""
import arcpy
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

    #Check or existence of template data
    if not os.path.exists(NFHL_data):
        arcpy.AddError("No NFHL data found in Tool Template Files folder. Please manually add rFHL database to Tool Template Files folder and try again".format(os.path.basename(NFHL_data)))
        sys.exit()
    else:
        arcpy.AddMessage("{0} found".format(os.path.basename(NFHL_data)))

    return NFHL_data

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

def Populate_S_AOI_Ar(FFRMS_Geodatabase, county_name, NFHL_100yr, FV00_polygon, FIPS_code):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Populating S_AOI_Ar #####")    
        
    S_AOI_Ar = os.path.join(FFRMS_Geodatabase, "S_AOI_Ar")

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

    aoi_info_already_populated = [row[0] for row in arcpy.da.SearchCursor(S_AOI_Ar, ["AOI_INFO"])]
    NFHL_not_FVA00_text = "The FEMA Special Flood Hazard Area (SFHA) in this area is not included in the FVA0 grid. This may be due to differences in the terrain data used or engineering and mapping judgements made during the FEMA flood study."
    FVA00_not_NFHL_text = "The FVA0 grid in this area is not included in the FEMA Special Flood Hazard Area (SFHA). This may be due to differences in the terrain data used or engineering and mapping judgements made during the FEMA flood study."
    
    if NFHL_not_FVA00_text in aoi_info_already_populated:
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

    if FVA00_not_NFHL_text in aoi_info_already_populated:
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
    with arcpy.da.UpdateCursor(S_AOI_Ar, ["AOI_ID", "POL_NAME1", "FIPS", "NOTES", "AOI_INFO"]) as cursor:
        for i, row in enumerate(cursor):
            row[0] = "{0}{1}_{2}".format(riv_or_cst,FIPS_code,i + 1)
            row[1] = county_name
            row[2] = FIPS_code
            if row[3] == None:
                row[3] = "NP"
            if row[4] == None:
                row[4] = "NP"
            cursor.updateRow(row)

def Create_S_Raster_QC_Copies(S_Raster_QC_pt):
    #create temporary copys of S_Raster_QC_pt for 01 and 02 in memory
    S_Raster_copy_02 = r"in_memory/S_Raster_copy_02"
    S_Raster_copy_01 = r"in_memory/S_Raster_copy_01"
    S_Raster_copy_all = r"in_memory/S_Raster_copy_all"

    for S_Raster_copy_file in [S_Raster_copy_02, S_Raster_copy_01, S_Raster_copy_all]:
        arcpy.management.CopyFeatures(S_Raster_QC_pt, S_Raster_copy_file)
    
    return S_Raster_copy_02, S_Raster_copy_01, S_Raster_copy_all

def find_QC_point_files(tool_folder, HUC8):
    #set folder and shapefiles locations
    
    tool_folder = tool_folder.replace("'","") #Fixes One-Drive folder naming 

    for folder in os.listdir(tool_folder):
        if os.path.basename(folder) == os.path.basename(tool_folder):
            tool_folder = os.path.join(tool_folder, os.path.basename(folder))

    qc_folder = os.path.join(tool_folder, "qc_points")
    arcpy.AddMessage("## Compiling QC points from folder: {0} ##".format(HUC8))

    #Create a list of 01 and 02 qc shapefiles to process
    qc_points_shapefiles_02 = []
    qc_points_shapefiles_01 = []
    for root, dirs, files in os.walk(qc_folder):
        for file in files:
            if file.endswith(".shp") and "02" in file:
                qc_points_shapefiles_02.append(os.path.join(root, file))
            elif file.endswith(".shp") and not "02" in file:
                qc_points_shapefiles_01.append(os.path.join(root, file))

    #Print list of 01 and 0_2 shapefiles found in each folder
    shapefiles_01_list = [os.path.basename(shapefile) for shapefile in qc_points_shapefiles_01]
    shapefiles_02_list = [os.path.basename(shapefile) for shapefile in qc_points_shapefiles_02]
    arcpy.AddMessage("01PCT QC point shapefiles: {0}".format(shapefiles_01_list))
    arcpy.AddMessage("0_2PCT QC point shapefiles: {0}".format(shapefiles_02_list))

    return qc_points_shapefiles_02, qc_points_shapefiles_01

def Append_QC_points_to_S_Raster_Copies(qc_points_shapefiles_02, qc_points_shapefiles_01, S_Raster_copy_02, S_Raster_copy_01, HUC8):
    for i, shapefile_list in enumerate([qc_points_shapefiles_02, qc_points_shapefiles_01]):
        #Appends both 0_2PC and 01 qc points together, naming them respectively

        for qc_points in shapefile_list:
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

            #Append to specific copy of S_Raster_QC_pt
            if i == 0:
                arcpy.Append_management(inputs=qc_points_layer, target=S_Raster_copy_02, schema_type="NO_TEST")
            else:
                arcpy.Append_management(inputs=qc_points_layer, target=S_Raster_copy_01, schema_type="NO_TEST")

def update_fields_in_S_Raster_copies(S_Raster_copy_02, S_Raster_copy_01, S_Raster_copy_all):
    #clip to county boundary and append to geodatabase
        for i, S_Raster_copy in enumerate([S_Raster_copy_02, S_Raster_copy_01]):
            S_raster_clip = r"in_memory/S_raster_clip"

            if i == 0:
                fva_type = "0_2PCT"
            else:
                fva_type = "01PCT"
            arcpy.analysis.Clip(S_Raster_copy, county_boundary, S_raster_clip)

            #Add values for 3 fields: FIPS code, FRBD_RP, and Source_Cit to all rows
            with arcpy.da.UpdateCursor(S_raster_clip, ["FIPS", "POL_NAME1","FRBD_RP", "Source_Cit", "NOTES"]) as cursor:
                for row in cursor:
                    row[0] = FIPS_code
                    row[1] = county_name
                    row[2] = fva_type
                    row[3] = "STUDY1"
                    row[4] = "NP"
                    cursor.updateRow(row)

            #append to S_Raster_QC_pt
            arcpy.Append_management(inputs=S_raster_clip, target=S_Raster_copy_all, schema_type="NO_TEST")

def Select_QC_Points_on_S_XS(S_Raster_copy_all, S_Raster_QC_pt, NFHL_data):
    arcpy.AddMessage("Selecting QC points that intersect with NFHL S_XS and are within county boundary")
    S_XS = os.path.join(NFHL_data, "FIRM_Spatial_Layers", "S_XS")

    arcpy.MakeFeatureLayer_management(S_Raster_copy_all, "S_Raster_copy_intersect")
    arcpy.management.SelectLayerByLocation(in_layer="S_Raster_copy_intersect", overlap_type="WITHIN A DISTANCE", select_features=S_XS, search_distance="0.1 Meters", selection_type="NEW_SELECTION")
    
    arcpy.AddMessage("Appending selected QC points to S_Raster_QC_Pts")
    arcpy.management.Append(inputs="S_Raster_copy_intersect", target=S_Raster_QC_pt, schema_type="NO_TEST")

    return S_Raster_QC_pt
    
def Populate_S_Raster_QC_pt(FFRMS_Geodatabase, NFHL_data, Tool_Output_Folders, county_boundary, FIPS_code, county_name):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Populating S_Raster_QC_pt #####")

    #delete existing entries in S_Raster_QC_pt
    S_Raster_QC_pt = os.path.join(FFRMS_Geodatabase, "S_Raster_QC_pt")
    arcpy.management.DeleteRows(S_Raster_QC_pt)

    S_Raster_copy_02, S_Raster_copy_01, S_Raster_copy_all = Create_S_Raster_QC_Copies(S_Raster_QC_pt)

    #loop through Tool_Output_Folders (by HUC8)
    for tool_folder in Tool_Output_Folders:
        
        tool_folder = tool_folder.replace("'","") #Fixes One-Drive folder naming 

        HUC8 = os.path.basename(tool_folder)
        
        #find 01 and 02 qc point shapefiles within tool folder
        qc_points_shapefiles_02, qc_points_shapefiles_01 = find_QC_point_files(tool_folder, HUC8)

        #Loop through both 01 and 02 qc shapefiles within HUC8 folder
        Append_QC_points_to_S_Raster_Copies(qc_points_shapefiles_02, qc_points_shapefiles_01, S_Raster_copy_02, S_Raster_copy_01, HUC8)

    #Combine QC points together and update fields based on their FVA type
    update_fields_in_S_Raster_copies(S_Raster_copy_02, S_Raster_copy_01, S_Raster_copy_all)

    #Select all points that intersect with NFHL S_XS and append to S_Raster_QC_pt 
    S_Raster_QC_pt = Select_QC_Points_on_S_XS(S_Raster_copy_all, S_Raster_QC_pt, NFHL_data)

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

def Check_QC_Pass_Rate(centerline_qc_points_NFHL):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Assessing QC Point pass rate #####")

    num_handy_qc_points_failed = 0
    total_qc_points = 0

    with arcpy.da.SearchCursor(centerline_qc_points_NFHL, ["wsel_diff"]) as cursor:
        for row in cursor:
            if row[0] > 0.5:
                num_handy_qc_points_failed += 1
            total_qc_points += 1
    
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("## HANDY QC STATS ##")

    num_passed_qc_points = total_qc_points - num_handy_qc_points_failed
    percent_failed = round((num_handy_qc_points_failed / total_qc_points) * 100, 2)
    percent_passed = round(100 - percent_failed, 2)
    arcpy.AddMessage("Number of QC points: {0}".format(total_qc_points))
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
    
if __name__ == "__main__":

    # TODO: ADD/Calculate new fields in QC Points
    
    FFRMS_Geodatabase = arcpy.GetParameterAsText(0)
    Tool_Output_Folders = arcpy.GetParameterAsText(1).split(";")
    Tool_Template_Folder = arcpy.GetParameterAsText(2)

    arcpy.env.workspace = FFRMS_Geodatabase
    arcpy.env.overwriteOutput = True

    #Get FIPS code from S_FFRMS_Proj_Ar
    FIPS_code = get_FIPS(FFRMS_Geodatabase)
    State_code = FIPS_code[:2]
    County_code = FIPS_code[2:5]

    S_FFRMS_Proj_Ar, county_boundary, county_name = get_county_info(FFRMS_Geodatabase)

    NFHL_data = Check_Source_Data(Tool_Template_Folder)

    FV00_polygon, FV03_polygon = Convert_Rasters_to_Polygon(FFRMS_Geodatabase)

    NFHL_100yr = Extract_NFHL_100yr_Floodplain(FIPS_code, FFRMS_Geodatabase, NFHL_data, S_FFRMS_Proj_Ar)

    S_FFRMS_Ar = os.path.join(FFRMS_Geodatabase,"S_FFRMS_Ar")

    Populate_S_FFRMS_Ar(FV03_polygon, S_FFRMS_Proj_Ar, S_FFRMS_Ar, county_name, FIPS_code)

    Populate_S_AOI_Ar(FFRMS_Geodatabase, county_name, NFHL_100yr, FV00_polygon, FIPS_code)

    S_Raster_QC_pt = Populate_S_Raster_QC_pt(FFRMS_Geodatabase, NFHL_data, Tool_Output_Folders, county_boundary, FIPS_code, county_name)
    
    #Check_QC_Pass_Rate(S_Raster_QC_pt)
    centerline_qc_points = loop_through_tool_folders_for_cl_01_points_shapefiles(Tool_Output_Folders)


