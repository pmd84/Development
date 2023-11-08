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
from sys import argv
import os
import json
import requests
from arcpy import env
from arcpy.sa import *

#Set workspace to location of arcgis project

def check_erase_areas(FFRMS_Geodatabase):

    arcpy.env.workspace = FFRMS_Geodatabase
    fcs = arcpy.ListFeatureClasses()

    for fc in fcs:
        if "Erase_Areas" in fc:
            arcpy.AddMessage("Found Erase Areas Feature Class")
            Erase_Areas = os.path.join(FFRMS_Geodatabase, fc)
            break
    else:
        arcpy.AddWarning("No Erase Areas Feature Class Found")
        arcpy.AddWarning("No areas will be erased from stitched rasters")
        arcpy.AddWarning("If desired, ensure a feature class named 'Erase_Areas...' exists within county geodatabase")
        Erase_Areas = ""
    return Erase_Areas

def Check_Inputs(county_shapefile):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Checking Input Files #####")

    if county_shapefile == "" or county_shapefile == None:
        county_shapefile = r"\\us0525-PPFSS01\shared_projects\203432303012\FFRMS_Zone3\production\source_data\scope\FFRMS_Counties.shp"
        arcpy.AddMessage("No FFRMS Counties Shapefile provided - using FFRMS county boundary data found on Stantec Server here {0}".format(county_shapefile))
    else:
        arcpy.AddMessage("Using FFRMS Counties Shapefile provided by user at {0}".format(county_shapefile))
    if not arcpy.Exists(county_shapefile):
        arcpy.AddError("Missing FFRMS Counties Shapefile.  Please provide FFRMS county boundary shapefile and try again".format(county_shapefile))

    return county_shapefile

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

def Get_UTM_zone(fips_code):
    arcpy.AddMessage("Determining UTM code from API")

    fips_code = fips_code[:5]

     # ArcGIS REST Endpoint for UTM Boundaries
    endpoint = "https://nrcsgeoservices.sc.egov.usda.gov/arcgis/rest/services/government_units/utm_zone/MapServer/0/query"

    # Parameters for the API request
    params = {
        'where': "FIPS_C ='" + fips_code +  "'",
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
            arcpy.AddMessage("UTM designation for county " + fips_code + " is " + utm_code_str)
            return utm_code_str
        else:
            raise Exception("Failed to retrieve UTM designation from API")
    else:
        raise Exception("Failed to retrieve UTM designation from API")
    
def Check_Naming_Convention(Output_Raster_Filename, Spatial_Reference_String):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Checking Output Raster Naming Convention #####")

    Output_Raster_Filename = os.path.splitext(Output_Raster_Filename)[0]
    Output_Fileparts = Output_Raster_Filename.split("_")

    #assign variables
    state = Output_Fileparts[0]
    fips_code = Output_Fileparts[1]
    UTM_code = Output_Fileparts[2]
    freeboard = Output_Fileparts[3]
    river_or_coast = Output_Fileparts[4]
    resolution = Output_Fileparts[5]
    fips_num = fips_code[:5]
        
    #Spatial reference string is in form "NAD 1983 BLM Zone 1N (US Feet)", set variable for chosen_zone as "1N"
    chosen_zone = Spatial_Reference_String.split(" ")[4]

    if freeboard =='0' and river_or_coast == "2PCT":
        #fix naming convention based on split '0_2PCT' Freeboard
        freeboard = '0_2PCT'
        river_or_coast = Output_Fileparts[5]
        resolution = Output_Fileparts[6]

    error_count = 0

    if len(state) != 2 and state not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        arcpy.AddWarning("First part of filename must be state abbreviation as two capital letters, i.e. 'NH_33015_19N_00FVA_RIV_03m'")
        error_count += 1

    if len(fips_code) != 5 and fips_num not in "0123456789":
        arcpy.AddWarning("Second part of filename must be 5 digit FIPS code without the county designation 'C', i.e. 'NH_33015_19N_00FVA_RIV_03m'")
        error_count += 1

    if UTM_code != chosen_zone:
        arcpy.AddWarning("Third part of filename must match UTM Zone in Spatial Reference. Filename shows UTM zone {0} and spatial reference was chosen as {1}".format(UTM_code, chosen_zone))
        error_count += 1

    if freeboard not in ['00FVA', '01FVA', '02FVA', '03FVA', '0_2PCT' ]:
        arcpy.AddWarning("Fourth part of filename must be freeboard value in form 00FVA, 01FVA, 02FVA, 03FVA, or 0_2PCT, i.e. 'NH_33015_19N_00FVA_RIV_03m'")
        error_count += 1

    if river_or_coast not in ['RIV', 'CST']:
        arcpy.AddWarning("Fifth part of filename must be either RIV or CST in ALL CAPS, i.e. 'NH_33015_19N_00FVA_RIV_03m'")
        error_count += 1

    if resolution not in ['03m', '10m']:
        arcpy.AddWarning("Sixth part of filename must be resolution in form 03m or 10m, i.e. 'NH_33015_19N_00FVA_RIV_03m'")
        error_count += 1

    if error_count > 0:
        arcpy.AddError("Filename does not match naming convention.  Please rename file and try again.")
        exit()
    else:
        arcpy.AddMessage("File naming convention for output raster {0} is correct".format(Output_Raster_Filename))

def Get_County_Boundary(fips_code, FFRMS_Geodatabase, county_server_shapefile):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting county boundary data from location on server #####")

    #Select county boundary from server shapefile based on the field CO_FIPS and export to new county shapefile
    fips_code = fips_code[:5]
    arcpy.management.MakeFeatureLayer(county_server_shapefile, "county_layer")

    arcpy.management.SelectLayerByAttribute(in_layer_or_view="county_layer", selection_type="NEW_SELECTION", 
                                            where_clause="CO_FIPS = '{0}'".format(fips_code))
    
    county_boundary = r"in_memory\county_boundary"

    arcpy.management.CopyFeatures(in_features="county_layer", out_feature_class=county_boundary)
    return county_boundary

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

    #Set up Temp Raster Name based on Output File Name extension (tif, GRID, etc.)
    Temp_Raster_Name = "Temp_Raster"
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

def Clip_to_County(Output_Mosaic_Dataset_rounded, county_boundary, Output_Raster):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Clipping Raster to County Boundary #####")

    Output_Raster_Clipped = arcpy.management.Clip(in_raster=Output_Mosaic_Dataset_rounded, out_raster = Output_Raster, 
                                                  in_template_dataset=county_boundary, nodata_value="-9999999",
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

def Erase_Areas_and_Clip_To_County_Boundary(Erase_Areas, county_boundary, Output_Raster, Output_Mosaic_Dataset_rounded):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Erasing Areas and Clipping to County Boundary #####")
    
    if arcpy.Exists(Erase_Areas):
    
        #Subset the erase areas polygon based on FVA value
        Raster_FVA_value = os.path.basename(Output_Raster).split("_")[3]
        if Raster_FVA_value =='0' and os.path.basename(Output_Raster).split("_")[4] == "2PCT": #fix naming convention based on split '0_2PCT' Freeboard
            Raster_FVA_value = '0_2PCT'
        
        field_name1 = "Erase_" + Raster_FVA_value
        field_name2 = "Erase_All_FVAs"
        query = "{0} = 'T' OR {1} = 'T'".format(field_name1, field_name2)

        arcpy.AddMessage("Selecting erase features based on FVA value {0}".format(Raster_FVA_value))
        arcpy.management.MakeFeatureLayer(Erase_Areas, "Erase_Area_subset", query)

        #Create Clip Mask
        clip_mask = r"in_memory/clip_mask"
        try:
            arcpy.analysis.Erase(in_features=county_boundary, erase_features="Erase_Area_subset", out_feature_class=clip_mask)
        except: #Erase tool not licensed
            Erase_without_tool(county_boundary,"Erase_Area_subset",clip_mask)

        Output_Raster = Extract_by_Clip_Mask(Output_Mosaic_Dataset_rounded, clip_mask, Output_Raster)
    else:
        arcpy.AddMessage("No Erase Areas chosen.  Clipping raster to county boundary")
        Output_Raster = Clip_to_County(Output_Mosaic_Dataset_rounded, county_boundary, Output_Raster)

    return Output_Raster

def get_UTM_and_FIPS(FFRMS_Geodatabase):
    S_FFRMS_Proj_Ar = os.path.join(FFRMS_Geodatabase, "S_FFRMS_Proj_Ar")
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting UTM Zone and FIPS Code from S_FFRMS_Proj_Ar #####")

    with arcpy.da.SearchCursor(S_FFRMS_Proj_Ar, ["PROJ_ZONE", "FIPS"]) as cursor:
        for row in cursor:
            UTM_zone = row[0]
            FIPS_CODE = row[1][:5]
            break
        
    if 'N' not in UTM_zone:
        UTM_zone = UTM_zone + "N"

    arcpy.AddMessage("UTM Zone found: {0}".format(UTM_zone))
    arcpy.AddMessage("FIPS Code found: {0}".format(FIPS_CODE))

    return UTM_zone, FIPS_CODE


if __name__ == '__main__':

    # Gather Parameter inputs from tool
    Tool_Output_Folders = arcpy.GetParameterAsText(0).split(";")
    FFRMS_Geodatabase = arcpy.GetParameterAsText(1)
    FVAs = arcpy.GetParameterAsText(2).split(";")
    county_shapefile = arcpy.GetParameterAsText(3)
    Output_Folder = os.path.dirname(FFRMS_Geodatabase) #Raster output as given by user

    # TODO: Add Clip By HUC8 boundary option
    # TODO: Add Erase Area specific HUC8 only option

    #Environment settings
    arcpy.env.workspace = FFRMS_Geodatabase
    arcpy.env.overwriteOutput = True
    
    Erase_Areas = check_erase_areas(FFRMS_Geodatabase)

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
    
    #Get state abbreviation from geodatabase name
    Geodatabase_name_parts = FFRMS_Geodatabase.split("_")
    riv_or_cst = Geodatabase_name_parts[-1][:3]
    state_abrv = Geodatabase_name_parts[-3]
    county_all_caps = " ".join(Geodatabase_name_parts[:-3])

    #Get UTM code and FIPS code from S_FFRMS_Proj_Ar
    UTM_zone, FIPS_code = get_UTM_and_FIPS(FFRMS_Geodatabase)

    #Determine UTM Spatial Reference based on FIPS code, if not given manually
    UTM_zone, Output_Spatial_Reference, Spatial_Reference_String = Check_Spatial_Reference(UTM_zone, FIPS_code)

    #Check if county shapefile is provided, if not use default
    county_shapefile = Check_Inputs(county_shapefile)

    #Create County Boundary shapefile
    County_Boundary = Get_County_Boundary(FIPS_code, FFRMS_Geodatabase, county_shapefile)

    #Determine which FVAs to process
    FVAs_to_process = []
    All_FVAs = ["00FVA", "01FVA", "02FVA", "03FVA", "0_2PCT"]
    for FVA in FVAs:
        if FVA == "All_Available_FVAs":
            FVAs_to_process = All_FVAs
            break
        else:
            FVAs_to_process.append(FVA)
    
    raster_dict = {}
    raster_dict["00FVA"] = "wsel_grid_0.tif"
    raster_dict["01FVA"] = "wsel_grid_1.tif"
    raster_dict["02FVA"] = "wsel_grid_2.tif"
    raster_dict["03FVA"] = "wsel_grid_3.tif"
    raster_dict["0_2PCT"] = "wsel_grid_02_pct_0.tif"

    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Tool will process the following FVAs: {0} #####".format(FVAs_to_process))
    
    #loop through FVAs, create raster name, and process
    for FVA in FVAs_to_process:
        arcpy.AddMessage(u"\u200B")
        arcpy.AddMessage("##### Processing Rasters for {0} #####".format(FVA))

        Output_Raster_Filename = "{0}_{1}_{2}_{3}_{4}_{5}m".format(state_abrv, FIPS_code, UTM_zone, FVA, riv_or_cst, "03")
        Output_Raster = os.path.join(FFRMS_Geodatabase, Output_Raster_Filename)

        #Find tool output rasters:
        Input_rasters = []
        for tool_folder in Tool_Output_Folders:
            tool_folder = tool_folder.replace("'","") #Fixes One-Drive folder naming 

            #Check for extra subfolder level - can be caused by unzipping to folder with same name
            for folder in os.listdir(tool_folder):
                if os.path.basename(folder) == os.path.basename(tool_folder):
                    tool_folder = os.path.join(tool_folder, os.path.basename(folder))

            #look for raster based on FVA
            raster_name = raster_dict[FVA]
            raster_path = os.path.join(tool_folder, raster_name)

            if os.path.exists(raster_path):
                arcpy.AddMessage("Found {0} raster in folder {1}".format(FVA, tool_folder))
                Input_rasters.append(raster_path)
            else:
                arcpy.AddWarning("No {0} raster found in folder {1}".format(FVA, tool_folder))
        
        if Input_rasters == []:
            arcpy.AddMessage("No {0} rasters found in any of the tool output folders. Moving on to next raster".format(FVA))
            continue
        
        #Create Empty Raster
        Empty_Raster_Dataset = Create_Empty_Raster(FFRMS_Geodatabase, Output_Spatial_Reference, Output_Raster_Filename)

        #Mosaic Rasters
        Output_Mosaic_Dataset = Mosaic_Raster(Empty_Raster_Dataset, Input_rasters)
        
        #Round Raster to 10th of a foot
        Output_Mosaic_Dataset_rounded = Round_Raster(Output_Mosaic_Dataset, pixel_type_dict)

        #Clip Raster to County Boundary and delete area if requested
        Erase_Areas_and_Clip_To_County_Boundary(Erase_Areas, County_Boundary, Output_Raster, Output_Mosaic_Dataset_rounded)

        #Delete Temp Files
        arcpy.AddMessage("Deleting Temporary Files")
        arcpy.management.Delete(Empty_Raster_Dataset)
    
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### All FVA Rasters Processed Complete #####")

