# -*- coding: utf-8 -*-
"""
Description:

Stitches together water surface elevation rasters, projects to UTM Survey Feet, and rounds to one tenth of a foot.

Parameters:
    Input_rasters: Use only the rasters with the same freeboard value. 
    Output_Raster: File Format - "ST_(FIPS)_UTM Zone_(Freeboard Value 2 Characters) _(Riv or Cst)_(03 or 10)m"
    Spatial_Reference: Choose the UTM Zone appropriate for the area of interest.


"""
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

def Check_Source_Data(Tool_Template_Folder):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Checking Source Data in Tool Template Files Folder #####")

    #If no Tool_Template_Files folder is provided, use Stantec server location
    if Tool_Template_Folder == "" or Tool_Template_Folder == None:
        Tool_Template_Folder = r"\\us0525-ppfss01\shared_projects\203432303012\FFRMS_Zone3\tools\Tool_Template_Files"
        arcpy.AddMessage("No Tool Template Files location provided, using location on Stantec Server: {0}".format(Tool_Template_Folder))
    
    #Check to see if Tool_Template_Folder exists
    if not os.path.exists(Tool_Template_Folder):
        arcpy.AddError("Tool Template Files folder does not exist at provided lcoation Stantec Server. Please manually provide path to Tool Template Files folder and try again")
        sys.exit()
    else:
        arcpy.AddMessage("Tool Template Files folder found")

    county_shapefile = os.path.join(Tool_Template_Folder, "FFRMS_Counties.shp")
    HUC8_shapefile = os.path.join(Tool_Template_Folder, "STARRII_FFRMS_HUC8s_Scope.shp")

    if not os.path.exists(county_shapefile):
        arcpy.AddError("No {0} found in Tool Template Files folder. Please manually add {0} to Tool Template Files folder and try again".format(os.path.basename(county_shapefile)))
        sys.exit()
    else:
        arcpy.AddMessage("{0} found".format(os.path.basename(county_shapefile)))

    return county_shapefile, HUC8_shapefile

def Check_Spatial_Reference(UTM_zone, FIPS_code):
        arcpy.AddMessage(u"\u200B")
        arcpy.AddMessage("##### Determining Spatial Reference #####")

        if UTM_zone == "" or UTM_zone == None:
            UTM_zone = Get_UTM_zone(FIPS_code)

        if UTM_zone == "55N":
            #GUAM spatial reference must be set differently
            arcpy.AddMessage("Setting spatial reference for Guam using projection file")
            Spatial_Reference_String = "NAD 1983 (MA11) UTM Zone 55N"
            Spatial_Reference_file = r"\\us0525-ppfss01\shared_projects\203432303012\FFRMS_Zone3\production\source_data\projection_files\Guam.prj"
            Output_Spatial_Reference = arcpy.SpatialReference(Spatial_Reference_file)

        else:
            Spatial_Reference_String = "NAD 1983 UTM Zone "+ UTM_zone 
            Output_Spatial_Reference = arcpy.SpatialReference(Spatial_Reference_String, "NAVD88 height (ftUS)")
            arcpy.AddMessage("Spatial Reference for Output Raster is " + Spatial_Reference_String)

        
        
        return UTM_zone, Output_Spatial_Reference, Spatial_Reference_String

def Get_UTM_zone(FIPS_code):
    arcpy.AddMessage("Determining UTM code from API")

    FIPS_code = FIPS_code[:5]

     # ArcGIS REST Endpoint for UTM Boundaries
    endpoint = "https://nrcsgeoservices.sc.egov.usda.gov/arcgis/rest/services/government_units/utm_zone/MapServer/0/query"

    # Parameters for the API request
    params = {
        'where': "FIPS_C ='" + FIPS_code +  "'",
        'outFields': 'UTMDESGN',
        'returnGeometry': 'false',
        'f': 'json'
    }

    # Make the API request
    response = requests.get(endpoint, params=params)
    if response.status_code == 200:
        json_data = response.json()
        if 'features' in json_data and len(json_data['features']) > 0 and 'attributes' in json_data['features'][0]:
            utm_designation = json_data['features'][0]['attributes']['UTMDESGN']
            utm_code_str = str(int(utm_designation))+'N'
            arcpy.AddMessage("UTM designation for county " + FIPS_code + " is " + utm_code_str)
            return utm_code_str
        else:
            raise Exception("Failed to retrieve UTM designation from API")
    else:
        raise Exception("Failed to retrieve UTM designation from API")
    
def Get_County_Boundary(FIPS_code, county_server_shapefile):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting county boundary data from location on server #####")

    #Select county boundary from server shapefile based on the field CO_FIPS and export to new county shapefile
    FIPS_code = FIPS_code[:5]
    arcpy.management.MakeFeatureLayer(county_server_shapefile, "county_layer")

    arcpy.management.SelectLayerByAttribute(in_layer_or_view="county_layer", selection_type="NEW_SELECTION", 
                                            where_clause="CO_FIPS = '{0}'".format(FIPS_code))
    
    County_Boundary = r"in_memory\County_Boundary"

    arcpy.management.CopyFeatures(in_features="county_layer", out_feature_class=County_Boundary)
    return County_Boundary

def Check_Raster_Inputs(Input_rasters, pixel_type_dict):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Checking Input Rasters - Must be 32 Bit Float #####")
    #check the bit count of the input rasters
    for input_raster in Input_rasters:
        try:
            pixel_type = arcpy.GetRasterProperties_management(input_raster, "VALUETYPE").getOutput(0)
        except:
            arcpy.AddError("Input raster {0} path not valid.  Please make sure there are no spaces in file name and try again".format(input_raster))
            exit()
        
        # arcpy.AddMessage(input_raster + " type is " + pixel_type_dict[int(pixel_type)])
        # if pixel_type != "9":
        #     arcpy.AddMessage(input_raster + " is not 32_BIT_FLOAT.  Please use only 32_BIT_FLOAT rasters as input.")

def Create_Empty_Raster(FFRMS_Geodatabase, Output_Spatial_Reference, Output_File_Name): 
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Creating Empty Raster Dataset #####")
    #Check to see if file already exists
    if arcpy.Exists(os.path.join(FFRMS_Geodatabase, Output_File_Name)):
        arcpy.AddMessage("{0} already exists - overwriting existing raster layer".format(Output_File_Name))
        #arcpy.management.Delete(os.path.join(FFRMS_Geodatabase, Output_File_Name))

    #Set up Temp Raster Name based on Output File Name extension (tif, GRID, etc.)
    Temp_Raster_Name = "Temp_Mosaic_Raster"
    Empty_Raster_Dataset = arcpy.management.CreateRasterDataset(out_path=FFRMS_Geodatabase, out_name=Temp_Raster_Name, 
                                                                 cellsize="3", pixel_type="32_BIT_FLOAT", 
                                                                 raster_spatial_reference=Output_Spatial_Reference, number_of_bands=1, 
                                                                 config_keyword="", pyramids="PYRAMIDS -1 NEAREST DEFAULT 75 NO_SKIP NO_SIPS", 
                                                                 tile_size="128 128", pyramid_origin="")[0]
    
    return Empty_Raster_Dataset

def Mosaic_Raster(Empty_Raster_Dataset, Input_rasters):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Mosaicing Rasters #####")

    mosaictype = "BLEND"
    rasters = ";".join(Input_rasters)

    Output_Mosaic_Dataset = arcpy.management.Mosaic(inputs=rasters, 
                                                    target=Empty_Raster_Dataset, 
                                                    mosaic_type=mosaictype, colormap="FIRST", background_value="-9999999", nodata_value="-9999999")[0]

 
    return Output_Mosaic_Dataset

def Round_Raster(Output_Mosaic_Dataset, pixel_type_dict):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Rounding Raster Values #####")

    try:
        Output_Mosaic_Dataset_rounded = RasterCalculator([Output_Mosaic_Dataset], ["x"], "Float(Int(x*10.0 + 0.5)/10.0)")
    except:
        ras = Raster(Output_Mosaic_Dataset)
        Output_Mosaic_Dataset_rounded = Float(Int(ras*10.0 + 0.5)/10.0)   

    #Check pixel type of output raster - should be 32 bit float
    pixel_type = arcpy.GetRasterProperties_management(Output_Mosaic_Dataset_rounded, "VALUETYPE").getOutput(0)
    if pixel_type != "9":
        arcpy.AddWarning("Output raster is not 32_BIT_FLOAT.  Please check the output raster for inconsistencies.")
    else:
        arcpy.AddMessage("Output mosaic raster is type " + pixel_type_dict[int(pixel_type)])

    return Output_Mosaic_Dataset_rounded

def Clip_to_County(Output_Mosaic_Dataset_rounded, County_Boundary, Output_Raster):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Clipping Raster to County Boundary #####")

    Output_Raster_Clipped = arcpy.management.Clip(in_raster=Output_Mosaic_Dataset_rounded, out_raster = Output_Raster, 
                                                  in_template_dataset=County_Boundary, nodata_value="-9999999",
                                                clipping_geometry="ClippingGeometry", maintain_clipping_extent="MAINTAIN_EXTENT")[0]
    return Output_Raster_Clipped
    
def Extract_by_Clip_Mask(Output_Mosaic_Dataset_rounded, clip_mask, Output_Raster):

    inRaster = Output_Mosaic_Dataset_rounded
    inMaskData = clip_mask
    extraction_area = "INSIDE"

    # Execute ExtractByMask
    try:
        outExtractByMask = ExtractByMask(inRaster, inMaskData, extraction_area)
    except:
        outExtractByMask = ExtractByMask(inRaster, inMaskData)
    outExtractByMask.save(Output_Raster)

    return Output_Raster

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

        arcpy.CopyFeatures_management(input_features, r"in_memory/input_layer")

        arcpy.Union_analysis(in_features=[memory_input,erase_features], 
                            out_feature_class=unionized)

        arcpy.Select_analysis(in_features=unionized, 
                            out_feature_class=selected, 
                            where_clause="FID_"+attr+" = -1")

        arcpy.Clip_analysis(in_features=input_features, 
                            clip_features=selected, 
                            out_feature_class=output_feature_class)

        arcpy.AddMessage("File successfully clipped")

def Erase_Areas_and_Clip_To_County_Boundary(Erase_Areas, County_Boundary, Output_Raster, Output_Mosaic_Dataset_rounded):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Erasing Areas and Clipping to County Boundary #####")
    
    if arcpy.Exists(Erase_Areas):
    
        #Subset the erase areas polygon based on FVA value
        Raster_FVA_value = os.path.basename(Output_Raster).split("_")[3]
        if Raster_FVA_value =='0' and os.path.basename(Output_Raster).split("_")[4] == "2PCT": #fix naming convention based on split '0_2PCT' Freeboard
            Raster_FVA_value = '0_2PCT'
        
        field_name1 = "Erase_" + Raster_FVA_value
        field_name2 = "Erase_All_FVAs"
        query = "{0} = 'Yes' OR {1} = 'Yes'".format(field_name1, field_name2)

        arcpy.AddMessage("Selecting erase features based on FVA value {0}".format(Raster_FVA_value))
        arcpy.management.MakeFeatureLayer(Erase_Areas, "Erase_Area_subset", query)

        #Create Clip Mask
        clip_mask = r"in_memory/clip_mask"
        try:
            arcpy.analysis.Erase(in_features=County_Boundary, erase_features="Erase_Area_subset", out_feature_class=clip_mask)
        except: #Erase tool not licensed
            Erase_without_tool(County_Boundary,"Erase_Area_subset",clip_mask)

        Output_Raster = Extract_by_Clip_Mask(Output_Mosaic_Dataset_rounded, clip_mask, Output_Raster)
    else:
        arcpy.AddMessage("No Erase Areas chosen.  Clipping raster to county boundary")
        Output_Raster = Clip_to_County(Output_Mosaic_Dataset_rounded, County_Boundary, Output_Raster)

    return Output_Raster

def get_UTM_and_FIPS(FFRMS_Geodatabase):
    S_FFRMS_Proj_Ar = os.path.join(FFRMS_Geodatabase, "S_FFRMS_Proj_Ar")
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting UTM Zone and FIPS Code from S_FFRMS_Proj_Ar #####")

    with arcpy.da.SearchCursor(S_FFRMS_Proj_Ar, ["PROJ_ZONE", "FIPS"]) as cursor:
        for row in cursor:
            UTM_zone = row[0]
            FIPS_code = row[1][:5]
            break
        
    if 'N' not in UTM_zone:
        UTM_zone = UTM_zone + "N"

    arcpy.AddMessage("UTM Zone found: {0}".format(UTM_zone))
    arcpy.AddMessage("FIPS Code found: {0}".format(FIPS_code))

    return UTM_zone, FIPS_code

def Create_Tool_Output_Folder_Dictionary(Tool_Output_Folders):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Checking Tool Output Folder Naming Convention #####")

    HUC8_tool_folder_dict = {}
    for tool_folder in Tool_Output_Folders:
        
        #Run check of first 8 characters - must be numeric 8 digit HUC8 number
        HUC8 = check_HUC8_naming_convention(tool_folder, "First", "Tool Output Folder")
        arcpy.AddMessage("Tool Output Folder {0} is named correctly".format(tool_folder))

        #Add HUC8 and tool folder location to dictionary
        HUC8_tool_folder_dict[HUC8] = tool_folder

    return HUC8_tool_folder_dict

def check_HUC8_naming_convention(file_or_folder, first_last, type):
    if first_last == "First":
        HUC8 = os.path.basename(file_or_folder)[:8]
    elif first_last == "Last":
        HUC8 = os.path.basename(file_or_folder)[-8:]
        if HUC8[-4:] == ".gdb":
            HUC8 = os.path.basename(file_or_folder)[-12:-4]
    #if any characters are not alphanumeric, raise error
    for num in HUC8:
        if num not in "0123456789":
            arcpy.AddWarning("{0} {1} is not named correctly.".format(type, os.path.basename(file_or_folder)))
            arcpy.AddError("{0} 8 characters of {1} name MUST be HUC8 number. {0} 8 are '{2}'".format(first_last, type, HUC8))
            arcpy.AddError("Please rename {0} 8 characters of {1} to HUC8 number and try again".format(first_last, type))
            sys.exit()
    
    return HUC8
    
def Create_AOI_and_Erase_Area_Dictionaries(HUC_Erase_Area_gdbs):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Checking for Erase Areas and AOI Feature Classes #####")

    HUC8_erase_area_dict, HUC8_AOI_dict = {}, {}
    for gdb in HUC_Erase_Area_gdbs:
        gdb_name = os.path.basename(gdb)
        HUC8 = check_HUC8_naming_convention(gdb, "Last", "AOI Erase Area Geodatabase")
        arcpy.AddMessage("AOI_Erase_Areas geodatabase {0} is named correctly".format(gdb_name))

        #Check for existence of Erase Areas and AOI feature classes
        Erase_Area_Feature = os.path.join(gdb, "Erase_Areas_{0}".format(HUC8))
        AOI_Feature = os.path.join(gdb, "FFRMS_Spatial_Layers", "S_AOI_Ar_{0}".format(HUC8))

        if not arcpy.Exists(Erase_Area_Feature):
            arcpy.env.workspace = gdb
            features = arcpy.ListFeatureClasses()
            for feature in features:
                if "Erase_Areas" in feature:
                    Erase_Area_Feature = os.path.join(gdb, feature)
                    break 
            if Erase_Area_Feature == None:        
                #arcpy.AddError("Feature 'Erase_Areas_{0}' does not exist in {1}. Please rename Erase Areas to 'Erase_Areas_{0}' and try again".format(HUC8, gdb_name))
                arcpy.AddError("'Erase_Areas' does not exist in {0}. Please add Erase Areas to geodatabase and try again".format(gdb_name))
                sys.exit()
        else:
            arcpy.AddMessage("Found {0} in {1}".format(os.path.basename(Erase_Area_Feature), gdb_name))
        
        if not arcpy.Exists(AOI_Feature):
            arcpy.env.workspace = os.path.join(gdb, "FFRMS_Spatial_Layers")
            features = arcpy.ListFeatureClasses()
            for feature in features:
                if "S_AOI_Ar" in feature:
                    AOI_Feature = os.path.join(gdb, "FFRMS_Spatial_Layers", feature)
                    arcpy.AddMessage("Found {0} in {1}".format(os.path.basename(AOI_Feature), gdb_name))
                    break
            if AOI_Feature == None:
                arcpy.AddError("'S_AOI_Ar' does not exist in {0}. Please add AOI to geodatabase and try again".format(gdb_name))
                sys.exit()
        else:
            arcpy.AddMessage("Found {0} in {1}".format(os.path.basename(AOI_Feature), gdb_name))

        #Add to dictionary
        HUC8_erase_area_dict[HUC8] = Erase_Area_Feature
        HUC8_AOI_dict[HUC8] = AOI_Feature

    return HUC8_erase_area_dict, HUC8_AOI_dict

def Check_Erase_Areas(HUC8_erase_area_dict):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Checking Erase Areas Yes/No Values #####")

    for HUC8, Erase_Area_Feature in HUC8_erase_area_dict.items():
        #Search cursor through fields to find any True values
        search_fields = ["OBJECTID", "Erase_All_FVAs", "Erase_00FVA", "Erase_01FVA", "Erase_02FVA", "Erase_03FVA", "Erase_0_2PCT"]
        arcpy.AddMessage("HUC8 {0}".format(HUC8))

        with arcpy.da.UpdateCursor(Erase_Area_Feature, search_fields) as cursor:
            for row in cursor:
                if "Y" not in row:
                    arcpy.AddError("Erase Areas for HUC8 {0} has no 'Yes' values in row with OBJECTID {1}. Please update Erase Areas to contain at least one T value per row, and try again".format(HUC8, row[0]))
                    sys.exit()
                
                #Make sure lower FVAs are true if higher FVAs are true - ignoring 0_2PCT
                if row[1] == "Y":
                    row[2] = row[3] = row[4] = row[5] = row[6] = "Y"
                elif row[5] == "Y":
                    row[2] =row[3] = row[4] = "Y"
                elif row[4] == "Y":
                    row[2] = row[3] = "Y"
                elif row[3] == "Y":
                    row[2] = "Y"
                cursor.updateRow(row)

        arcpy.AddMessage("Erase Areas are formatted properly")
    return

def find_and_process_rasters_in_folder(folder, raster_name, FVA, HUC8_erase_area_dict, County_Boundary):
            
    #Find tool output rasters:
    HUC8_raster_list = []
    raster_num = 0
    for tool_folder in Tool_Output_Folders:
        tool_folder = tool_folder.replace("'","") #Fixes One-Drive folder naming 

        #Check for extra subfolder level - can be caused by unzipping to folder with same name
        for folder in os.listdir(tool_folder):
            if os.path.basename(folder) == os.path.basename(tool_folder):
                tool_folder = os.path.join(tool_folder, os.path.basename(folder))

        #Get HUC8 from folder name
        HUC8 = os.path.basename(tool_folder)[:8]
        arcpy.AddMessage("## Processing HUC8 {0} ##".format(HUC8))
        
        #look for raster based on FVA
        raster_path = None
        for file in os.listdir(tool_folder):
            if raster_name in file: 
                if file.endswith(".tif") or file.endswith(".tiff"):
                    raster_path = os.path.join(tool_folder, file)
                    arcpy.AddMessage("Found {0} raster in {1}".format(raster_name, os.path.basename(tool_folder)))
                    break

        if raster_path == None:
            arcpy.AddMessage("No {0} raster found in {1}".format(raster_name, os.path.basename(tool_folder)))
            continue

        #Erase Raster based on Erase_Area
        try:
            Erase_Area_Feature = HUC8_erase_area_dict[HUC8]

            #Create feature where FVA field is equal to 'T'        
            field_name1 = "Erase_" + FVA
            field_name2 = "Erase_All_FVAs"
            query = "{0} = 'Y' OR {1} = 'Y'".format(field_name1, field_name2)
            arcpy.management.MakeFeatureLayer(Erase_Area_Feature, "Erase_Area_subset", query)

            arcpy.AddMessage("Erasing {0} raster based on Erase_Areas in {1}".format(raster_name, os.path.basename(Erase_Area_Feature)))
            erase = True
        except:
            arcpy.AddMessage("No Erase_Area feature given for HUC8 {0}".format(HUC8))
            erase = False

        #if Clip_By_HUC8 is true, create feature for HUC8 boundary by querying 'huc8' field
        # Mask_boundary = "in_memory/Mask_boundary"
        # if Clip_By_HUC8 == "Yes":
        #     arcpy.management.MakeFeatureLayer(HUC8_shapefile, "HUC8_Boundary", "huc8 = '{0}'".format(HUC8))
        #     arcpy.analysis.Clip("HUC8_Boundary",county_shapefile,Mask_boundary)
        #     arcpy.AddMessage("Clipping {0} raster to HUC8 and county boundary {1}".format(raster_name, HUC8))
        # else:
        #     arcpy.AddMessage("Clipping {0} raster to county boundary".format(raster_name))
        #     arcpy.management.CopyFeatures(County_Boundary, Mask_boundary)

        #Create mask (used later for extracting raster) using Mask_boundary and Erase_Area_subset
        
        arcpy.AddMessage("Creating mask")
        Mask_boundary = County_Boundary

        if erase == False:
            #Dont add erase areas
            clip_mask = Mask_boundary
        else:
            #add erase areas to clip mask
            clip_mask = r"in_memory/clip_mask"
            try:
                arcpy.analysis.Erase(in_features=Mask_boundary, erase_features="Erase_Area_subset", out_feature_class=clip_mask)
            except:
                #if erase doesn't work, use Erase_without_tool function
                Erase_without_tool(Mask_boundary, "Erase_Area_subset", clip_mask)

        #Extract raster by mask
        inRaster = raster_path
        inMaskData = clip_mask
        extraction_area = "INSIDE"

        # Execute ExtractByMask
        arcpy.AddMessage("Extracting HUC8 {0} Raster using mask".format(HUC8))
        try:
            outExtractByMask = ExtractByMask(inRaster, inMaskData, extraction_area)
        except:
            outExtractByMask = ExtractByMask(inRaster, inMaskData)
        
        #save temp raster
        temp_raster_path = os.path.join(FFRMS_Geodatabase, "Temp_HUC8_Raster_{0}".format(raster_num))
        arcpy.management.CopyRaster(outExtractByMask, temp_raster_path)
        raster_num += 1

        HUC8_raster_list.append(temp_raster_path)
    return HUC8_raster_list

def Determine_FVAs_To_Process(FVAs):
    FVAs_to_process = []
    All_FVAs = ["00FVA", "01FVA", "02FVA", "03FVA", "0_2PCT"]
    for FVA in FVAs:
        if FVA == "All_Available_FVAs":
            FVAs_to_process = All_FVAs
            break
        else:
            FVAs_to_process.append(FVA)
    
    raster_dict = {}
    raster_dict["00FVA"] = "wsel_grid_0"
    raster_dict["01FVA"] = "wsel_grid_1"
    raster_dict["02FVA"] = "wsel_grid_2"
    raster_dict["03FVA"] = "wsel_grid_3"
    raster_dict["0_2PCT"] = "wsel_grid_02_pct_0"

    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Tool will process the following FVAs: {0} #####".format(FVAs_to_process))
    return FVAs_to_process, raster_dict

def get_name_parts(FFRMS_Geodatabase):
    Geodatabase_name_parts = FFRMS_Geodatabase.split("_")
    riv_or_cst = Geodatabase_name_parts[-1][:3]
    state_abrv = Geodatabase_name_parts[-3]
    county_all_caps = " ".join(Geodatabase_name_parts[:-3])
    return riv_or_cst, state_abrv, county_all_caps
    
if __name__ == '__main__':

    # Gather Parameter inputs from tool
    Tool_Output_Folders = arcpy.GetParameterAsText(0).split(";") #First 8 characters MUST be HUC8 number
    HUC_Erase_Area_gdbs = arcpy.GetParameterAsText(1).split(";")
    FFRMS_Geodatabase = arcpy.GetParameterAsText(2)
    FVAs = arcpy.GetParameterAsText(3).split(";")
    Append_AOI_Areas = arcpy.GetParameterAsText(4)
    Tool_Template_Folder = arcpy.GetParameterAsText(5)
    
    #Environment settings
    arcpy.env.workspace = FFRMS_Geodatabase
    arcpy.env.overwriteOutput = True
    arcpy.env.compression = "LZW"

    #Fix One-Drive Naming convention:
    HUC_Erase_Area_gdbs_fixed = []
    for gdb in HUC_Erase_Area_gdbs:
        gdb = gdb.replace("'","")
        HUC_Erase_Area_gdbs_fixed.append(gdb)

    #Check tool output folder naming
    HUC8_tool_folder_dict = Create_Tool_Output_Folder_Dictionary(Tool_Output_Folders)
    
    #Check that Erase Areas have at least one True value for each feature
    HUC8_erase_area_dict, HUC8_AOI_dict = Create_AOI_and_Erase_Area_Dictionaries(HUC_Erase_Area_gdbs_fixed)
    Check_Erase_Areas(HUC8_erase_area_dict)

    #Create pixel type dictionary for naming purposes when checking raster pixel depth
    pixel_type_dict = {
        0: "1_BIT",
        1: "2_BIT",
        2: "4_BIT",
        3: "8_BIT_UNSIGNED",
        4: "8_BIT_SIGNED",
        5: "16_BIT_UNSIGNED",
        6: "16_BIT_SIGNED",
        7: "32_BIT_UNSIGNED",
        8: "32_BIT_SIGNED",
        9: "32_BIT_FLOAT",
        10: "64_BIT_DOUBLE",
        11: "8_BIT_COMPLEX",
        12: "16_BIT_COMPLEX",
        13: "32_BIT_COMPLEX",
        14: "64_BIT_COMPLEX"}   
    
    #Get state, county, and riv/cst from geodatabase name    
    riv_or_cst, state_abrv, county_all_caps = get_name_parts(FFRMS_Geodatabase)

    #Get UTM code and FIPS code from S_FFRMS_Proj_Ar
    UTM_zone, FIPS_code = get_UTM_and_FIPS(FFRMS_Geodatabase)

    #Determine Spatial Reference
    UTM_zone, Output_Spatial_Reference, Spatial_Reference_String = Check_Spatial_Reference(UTM_zone, FIPS_code)

    #Check for county boundary
    county_shapefile, HUC8_shapefile = Check_Source_Data(Tool_Template_Folder)

    #Create County Boundary shapefile
    County_Boundary = Get_County_Boundary(FIPS_code, county_shapefile)
    
    #Determine which FVAs to process    
    FVAs_to_process, raster_dict = Determine_FVAs_To_Process(FVAs)
    
    #loop through FVAs, create raster name, and process
    for FVA in FVAs_to_process:
        arcpy.AddMessage(u"\u200B")
        arcpy.AddMessage("##### Processing Rasters for {0} #####".format(FVA))

        #Set Output Mosaiced Raster path
        Output_Raster_Filename = "{0}_{1}_{2}_{3}_{4}_{5}m".format(state_abrv, FIPS_code, UTM_zone, FVA, riv_or_cst, "03")
        Output_Raster = os.path.join(FFRMS_Geodatabase, Output_Raster_Filename)
        
        #Check for existence of HANDy Rasters
        handy_raster_name = raster_dict[FVA]
        Input_rasters = find_and_process_rasters_in_folder(Tool_Output_Folders, handy_raster_name, FVA, HUC8_erase_area_dict, County_Boundary)
        if Input_rasters == []:
            arcpy.AddMessage("No {0} rasters found in any of the tool output folders. Moving on to next raster".format(FVA))
            continue
        
        #Create Empty Raster
        Empty_Raster_Dataset = Create_Empty_Raster(FFRMS_Geodatabase, Output_Spatial_Reference, Output_Raster_Filename)

        #Mosaic Rasters
        Output_Mosaic_Dataset = Mosaic_Raster(Empty_Raster_Dataset, Input_rasters)
        
        #Round Raster to 10th of a foot
        Output_Mosaic_Dataset_rounded = Round_Raster(Output_Mosaic_Dataset, pixel_type_dict)

        #Save raster to Output Raster name
        arcpy.AddMessage("Saving Raster")
        arcpy.management.CopyRaster(Output_Mosaic_Dataset_rounded, Output_Raster)

        #Delete Temp Files
        arcpy.AddMessage("Deleting Temporary HUC8 Rasters")
        for file in Input_rasters:
            arcpy.management.Delete(file)
        arcpy.management.Delete(Empty_Raster_Dataset)
        
        
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### All FVA Rasters Processed #####")

    #Append all AOIs
    if Append_AOI_Areas == "Yes":
        arcpy.AddMessage(u"\u200B")
        arcpy.AddMessage("##### Appending AOIs to County Geodatabase S_AOI_Ar #####")

        AOI_Target = os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers", "S_AOI_Ar")

        #If there no items in the HUC8_AOI_dict, then there are no AOIs to append
        if len(HUC8_AOI_dict) == 0:
            arcpy.AddMessage("No AOIs to append")
        else:
            #Make sure geodtabase has S_AOI_Target feature class
            if not arcpy.Exists(AOI_Target):
                arcpy.AddWarning("No S_AOI_Ar found in county geodatabase. Creating feature from first HUC8 AOI provided")
                #copy first AOI to AOI_Target
                first_AOI = list(HUC8_AOI_dict.values())[0]
                arcpy.management.CopyFeatures(first_AOI, AOI_Target)
                loop_start = 1
            else:
                loop_start = 0
            
            for HUC, AOI_Feature in list(HUC8_AOI_dict.items())[loop_start:]:
                arcpy.AddMessage("Appending HUC8 {0} AOIs".format(HUC))
                arcpy.management.Append(AOI_Feature, AOI_Target, "NO_TEST")

        arcpy.AddMessage(u"\u200B")
        arcpy.AddMessage("##### All AOIs Appended #####")
        arcpy.AddMessage(u"\u200B")
        arcpy.AddMessage("##### Script Finished #####")

