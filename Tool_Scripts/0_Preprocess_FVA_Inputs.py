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
    
    #Define paths for template data
    NFHL_data = os.path.join(Tool_Template_Folder, "rFHL_20230630.gdb")
    county_shapefile = os.path.join(Tool_Template_Folder, "FFRMS_Counties.shp")
    HUC8_Shapefile = os.path.join(Tool_Template_Folder, "STARRII_FFRMS_HUC8s_Scope.shp")
    HUC_AOI_Erase_gdb = os.path.join(Tool_Template_Folder, "HUC_AOIs_Erase_Areas_XXXXXXXX.gdb")

    #Check or existence of template data
    for files in [NFHL_data, county_shapefile, HUC8_Shapefile, HUC_AOI_Erase_gdb]:
        if not os.path.exists(files):
            arcpy.AddError("No {0} found in Tool Template Files folder. Please manually add {0} to Tool Template Files folder and try again".format(os.path.basename(files)))
            sys.exit()
        else:
            arcpy.AddMessage("{0} found".format(os.path.basename(files)))
    
    return NFHL_data, county_shapefile, HUC8_Shapefile, HUC_AOI_Erase_gdb

def Create_Handy_Folder(County_Folder):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Creating HANDy Folder within County Production Folder #####")

    handy_folder = os.path.join(County_Folder, "handy")
    if not os.path.exists(handy_folder):
        arcpy.AddMessage("Handy folder created: {0}".format(handy_folder))
        os.makedirs(handy_folder)
    else:
        arcpy.AddMessage("Tool output will go in existing handy folder: {0}".format(handy_folder))

    return handy_folder

def Get_County_Info(FIPS_Code, county_shapefile):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting County Boundary Geometry and Information #####")
    
    #Select county boundary from server shapefile based on the field CO_FIPS and export to new county shapefile
    arcpy.management.MakeFeatureLayer(county_shapefile, "county_layer")

    arcpy.management.SelectLayerByAttribute(in_layer_or_view="county_layer", selection_type="NEW_SELECTION", 
                                            where_clause="CO_FIPS = '{0}'".format(FIPS_Code))
    
    #Export county boundary to new shapefile (in memory)
    arcpy.AddMessage("Exporting county boundary")
    county_boundary = r"in_memory\county_boundary"
    arcpy.management.CopyFeatures(in_features="county_layer", out_feature_class=county_boundary)

    #Get county name from county boundary shapefile
    county_name = arcpy.da.SearchCursor(county_boundary, "CO_FNAME").next()[0]
    arcpy.AddMessage("County is {0}".format(county_name))

    state_name = arcpy.da.SearchCursor(county_boundary, "ST_NAME").next()[0]

    state_name_abrv_dict = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
                            "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
                            "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
                            "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
                            "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
                            "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
                            "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
                            "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
                            "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN",
                            "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
                            "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY"}
    
    state_abrv = state_name_abrv_dict[state_name]
    arcpy.AddMessage("State is {0} ({1})".format(state_name, state_abrv))


    return county_boundary, county_name, state_name, state_abrv

def Get_All_HUC8s_in_County(county_boundary, HUC8_Shapefile):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting HUC8 Information for County #####")    

    #Intersect the S_FFRMS_Proj_Ar shapefile with the HUC8 shapefile
    arcpy.AddMessage("Intersecting country boundary with the HUC8 shapefile")
    
    #County_HUC8s_clipped= r"in_memory/County_HUC8s"
    memory = "in_memory"
    County_HUC8s_clipped = os.path.join(memory, "County_HUC8s_clipped")

    #Execute Intersect
    arcpy.Intersect_analysis([county_boundary, HUC8_Shapefile], County_HUC8s_clipped, "ALL", "", "INPUT")

    HUC8_list = []
    with arcpy.da.SearchCursor(County_HUC8s_clipped, "huc8") as cursor:
        for row in cursor:
            HUC8_list.append(row[0])

    #create feature layer of HUC8_shapefile
    arcpy.management.MakeFeatureLayer(HUC8_Shapefile, "HUC8_layer")

    #Select feature layer by huc8 in HUC8_list
    arcpy.management.SelectLayerByAttribute(in_layer_or_view="HUC8_layer", selection_type="NEW_SELECTION", 
                                            where_clause="huc8 IN {0}".format(tuple(HUC8_list)))
    
    #Copy selected features to new shapefile
    County_HUC8s = os.path.join(memory, "County_HUC8s")
    arcpy.management.CopyFeatures(in_features="HUC8_layer", out_feature_class=County_HUC8s)

    arcpy.AddMessage("HUC8s in county: {0}".format(HUC8_list))

    return County_HUC8s, HUC8_list
    
def Create_HUC8_folders(HUC8_list):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Creating HUC8 FVA Input Folders #####")

    HUC8s_to_process = []

    for HUC8 in HUC8_list:
        HUC8_folder = os.path.join(handy_folder, HUC8)
        HUC8_input_folder = os.path.join(HUC8_folder, "inputs")
        HUC8_output_folder = os.path.join(HUC8_folder, "outputs")
        HUC8_input_a_folder = os.path.join(HUC8_input_folder, "{0}_a".format(HUC8))
        
        #Remove HUC from processing list if it's already been processed
        if os.path.exists(HUC8_folder):
            arcpy.AddMessage("HUC8 {0} has already been processed".format(HUC8))
        else:
            HUC8s_to_process.append(HUC8)    
            arcpy.AddMessage("Creating HUC8 {0} HANDy folders".format(HUC8))
            for folder in [HUC8_folder, HUC8_input_folder, HUC8_output_folder, HUC8_input_a_folder]:
                if not os.path.exists(folder):
                    os.makedirs(folder)

    return HUC8s_to_process

def Create_HUC8_Shapefiles(HUC8_list, County_HUC8s):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Buffering HUC8s #####")

    for HUC8 in HUC8_list:
        HUC8_folder = os.path.join(handy_folder, HUC8, "inputs", "{0}_a".format(HUC8))
        arcpy.AddMessage("Buffering HUC8 {0} by 1 km".format(HUC8))

        HUC8_File = os.path.join(HUC8_folder, "HUC8_{0}.shp".format(HUC8))
        HUC8_Buffer = os.path.join(HUC8_folder, "HUC8_{0}_Buffer.shp".format(HUC8))

        #Select the HUC8
        arcpy.management.MakeFeatureLayer(County_HUC8s, "HUC8_layer")
        arcpy.management.SelectLayerByAttribute(in_layer_or_view="HUC8_layer", selection_type="NEW_SELECTION", 
                                            where_clause="huc8 = '{0}'".format(HUC8))
        
        #Create HUC8_file
        arcpy.management.CopyFeatures(in_features="HUC8_layer", out_feature_class=HUC8_File)

        #Create Buffer
        arcpy.Buffer_analysis("HUC8_layer", HUC8_Buffer, buffer_distance_or_field="1 Kilometers", dissolve_option="ALL", method="PLANAR")

def find_file(filename, directory):
    for file in os.listdir(directory):
        if file.lower() == filename.lower():
            output_filename = os.path.join(directory, file)
            return output_filename 
    return None

def find_NFHL_files(NFHL_data):
    spatial_layers = os.path.join(NFHL_data, "FIRM_Spatial_Layers")
    #Search for S_Profil_Baseline, S_BFE, S_XS, and L_XS_Elev in NFHL database folder - not case sensitive
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Checking NFHL Data #####")
    arcpy.AddMessage("Searching for S_Profil_Basln, S_BFE, S_XS, L_XS_Elev, and S_Fld_Haz_Ar in NFHL database")

    S_Profil_Basln = os.path.join(spatial_layers,"S_Profil_Basln")
    S_BFE = os.path.join(spatial_layers,"S_BFE")
    S_XS = os.path.join(spatial_layers,"S_XS")
    S_Fld_Haz_Ar = os.path.join(spatial_layers,"S_Fld_Haz_Ar")
    L_XS_Elev = os.path.join(NFHL_data,"L_XS_Elev")

    for feature in [S_Profil_Basln, S_BFE, S_XS, L_XS_Elev, S_Fld_Haz_Ar]:
        if not arcpy.Exists(feature):
            arcpy.AddError("No {0} data found in NFHL database. Please check NFHL data and try again".format(feature))
            sys.exit()
    
    arcpy.AddMessage("All NFHL features found")

    return S_Profil_Basln, S_BFE, S_XS, L_XS_Elev, S_Fld_Haz_Ar

def move_to_convert_folder(FVA_feature, HUC8_folder):
    convert_folder = os.path.join(HUC8_folder, "Convert_elevations_in_these_files_from_NGVD29_to_NAVD88")
    if not os.path.exists(convert_folder):
        os.makedirs(convert_folder)

    feature_name = os.path.basename(FVA_feature)
    convert_features = os.path.join(convert_folder, feature_name)
    arcpy.AddMessage("Please perform vertical transformation - NGVD29 to NAVD88 - in the following file: {0}".format(convert_features))
    arcpy.management.CopyFeatures(FVA_feature, convert_features)
    arcpy.management.Delete(FVA_feature)

def Select_NFHL_by_HUC(feature_type, NFHL_File, HUC8_list, buffer):

    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Creating FVA {} files #####".format(feature_type))

    #Loop through HUC8s
    for HUC8 in HUC8_list:
        HUC8_folder = os.path.join(handy_folder, HUC8, "inputs", "{0}_a".format(HUC8))

        if buffer == True:
            HUC8_Boundary = os.path.join(HUC8_folder, "HUC8_{0}_Buffer.shp".format(HUC8))
        else:
            HUC8_Boundary = os.path.join(HUC8_folder, "HUC8_{0}.shp".format(HUC8))

        # Create FVA_feature layer 
        FVA_feature_name = "FVA_{}_{}.shp".format(feature_type, HUC8)
        FVA_feature = os.path.join(HUC8_folder, FVA_feature_name)
        arcpy.AddMessage("Adding {0} to handy folder for HUC {1}".format(FVA_feature_name, HUC8))

        #Select by location using feature layer
        arcpy.management.MakeFeatureLayer(NFHL_File, "FVA_feature_layer")
        arcpy.management.SelectLayerByLocation(in_layer="FVA_feature_layer", overlap_type="INTERSECT", 
                                               select_features=HUC8_Boundary, selection_type="NEW_SELECTION")
        arcpy.management.CopyFeatures(in_features="FVA_feature_layer", out_feature_class=FVA_feature)

        #Check to see if the feature is empty:
        if arcpy.management.GetCount(FVA_feature)[0] == "0":
            arcpy.AddMessage("No {0} data found for HUC {1}".format(feature_type, HUC8))
            arcpy.AddMessage("Deleting {0} from handy folder".format(FVA_feature_name))
            arcpy.management.Delete(FVA_feature)
            continue
        
        #if feature_type is "S_XS", use update cursor to loop through WSEL_REG and delete any values with -9999, -8888, or 9999
        if feature_type == "S_XS":
            deleted_rows = 0
            with arcpy.da.UpdateCursor(FVA_feature, "WSEL_REG") as cursor:
                for row in cursor:
                    if row[0] in [-9999, -8888, 9999]:
                        cursor.deleteRow()
                        deleted_rows += 1
            if deleted_rows > 0:
                arcpy.AddMessage("Deleted {0} XS features with bad WSEL (i.e. -9999, -8888, 9999) from {1} feature".format(deleted_rows, FVA_feature_name))
                        
        #Delete any new fields that were added to S_Profil_Basln during the merge
        delete_fields = ["BW", "INTER_ZONE"]
        for field in delete_fields:
            if field in [f.name for f in arcpy.ListFields(FVA_feature)]:
                try:
                    arcpy.management.DeleteField(in_table=FVA_feature, drop_field=field)
                except:
                    pass

        #Check Vertical Datum of feature   
        NGVD29 = Check_Elev_Datum(FVA_feature, FVA_feature_name)

        #If there are NGVD29 values, move feature to Convert_elevations_in_these_files_from_NGVD29_to_NAVD88 folder
        if NGVD29 == True:
            move_to_convert_folder(FVA_feature, HUC8_folder)

def Create_S_Fld_Haz_Ar_Static_BFE(input_feature, static_bfe_name):
    if input_feature is not None:
        
        #Make feature layer
        arcpy.management.MakeFeatureLayer(input_feature, "features_layer")

        #Select based on query
        query = "STATIC_BFE IS NOT NULL And STATIC_BFE > 0 and (FLD_ZONE = 'AE' or FLD_ZONE = 'AH')"
        arcpy.management.SelectLayerByAttribute(in_layer_or_view="features_layer", selection_type="NEW_SELECTION", where_clause=query)

        #Copy selected features to new in_memory feature class
        S_Fld_Haz_Ar_Static_BFE = os.path.join("in_memory", static_bfe_name)
        arcpy.management.CopyFeatures(in_features="features_layer", out_feature_class=S_Fld_Haz_Ar_Static_BFE)

        return S_Fld_Haz_Ar_Static_BFE
        
def Check_Elev_Datum(Feature_Class, Feature_Type):
    #Check if feature has any NGVD29 values
    #If so, flag warning and stop running
    if Feature_Class is None:
        return

    if "V_DATUM" in [f.name for f in arcpy.ListFields(Feature_Class)]:
        with arcpy.da.SearchCursor(Feature_Class, "V_DATUM") as cursor:
            for row in cursor:
                if row[0] == "NGVD29":
                    arcpy.AddWarning("{0} data has NGVD29 values".format(Feature_Type))
                    return True
    return False

def subset_L_XS_Elev_by_XS_LN_ID(L_XS_Elev_table, HUC8_FVA_S_XS, Output_df, feature_type):
    #Create list of XS_LN_IDs from FVA_S_XS
    XS_LN_ID_list = []
    with arcpy.da.SearchCursor(HUC8_FVA_S_XS, "XS_LN_ID") as cursor:
        for row in cursor:
            XS_LN_ID_list.append(row[0])

    #Get unique values for XS_LN_ID_List
    XS_LN_ID_list = list(set(XS_LN_ID_list))
    if feature_type == "NFHL":
        arcpy.AddMessage("There are {0} cross sections in S_XS for this HUC8".format(len(XS_LN_ID_list)))

    #Export Table using query XS_LN_ID is in XS_LN_ID_list
    if XS_LN_ID_list == [] or XS_LN_ID_list == None:
        arcpy.AddWarning("No {0} cross sections found in S_XS for this HUC8".format(feature_type))
    else:
        arcpy.conversion.ExportTable(in_table=L_XS_Elev_table, out_table=Output_df, where_clause="XS_LN_ID IN {0}".format(tuple(XS_LN_ID_list)))
        arcpy.AddMessage("There are {0} matching entries in {1} L_XS_Elev table".format(arcpy.management.GetCount(Output_df)[0], feature_type))

def Create_L_XS_Tables(HUC8_list, L_XS_Elev):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Creating L_XS_Elev files #####")
    
    for HUC8 in HUC8_list:
        arcpy.AddMessage("HUC8 {0}".format(HUC8))
        HUC8_folder = os.path.join(handy_folder, HUC8, "inputs", "{0}_a".format(HUC8))

        #Check that FVA_S_XS exists in HUC8 folder
        HUC8_FVA_S_XS = os.path.join(HUC8_folder, "FVA_S_XS_{0}.shp".format(HUC8))
        if not arcpy.Exists(HUC8_FVA_S_XS):
            arcpy.AddMessage("No FVA_S_XS_{0}.shp found in HUC8 folder. L_XS_Elev will not be generated.".format(HUC8))
            continue
        
        #Set paths for output L_XS_Elev files
        NFHL_output_dbf = os.path.join("in_memory","NFHL_L_XS_Elev")
        FVA_output_dbf = os.path.join(HUC8_folder,"FVA_L_XS_Elev.dbf")

        #Subset NFHL L_XS_Elev using S_XS
        try:
            subset_L_XS_Elev_by_XS_LN_ID(L_XS_Elev, HUC8_FVA_S_XS, NFHL_output_dbf, "NFHL")
        except:
            arcpy.AddMessage("No matching NFHL L_XS_Elev found")
            continue

        #Export MIP to .dbf file
        arcpy.AddMessage("Copying NFHL L_XS_Elev to FVA_L_XS_Elev")
        arcpy.conversion.ExportTable(in_table=NFHL_output_dbf,out_table=FVA_output_dbf)
        
        #Check to see if feature is empty
        if arcpy.management.GetCount(FVA_output_dbf)[0] == "0":
            arcpy.AddMessage("No L_XS_Elev data found for HUC {0}".format(HUC8))
            arcpy.AddMessage("Deleting L_XS_Elev from HUC8 folder")
            arcpy.management.Delete(FVA_output_dbf)
            continue
        
        #Check vertical datum for FVA L_XS_Elev
        NGVD29 = Check_Elev_Datum(FVA_output_dbf, "FVA_L_XS_Elev")
        if NGVD29 == True:
            move_to_convert_folder(FVA_output_dbf, HUC8_folder)

def Get_Stantec_County_HUC8_Scope(Stantec_HUC_Tracker, county_name, state_abrv, county_field):
#use cursor to loop through HUC tracker, looking at county field and huc8 field
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("#### Looking through Stantec HUC Scope file to determine which HUC8s to process ####")
    arcpy.AddMessage("Searching for {0}, {1}".format(county_name, state_abrv))

    county_name = county_name.replace(" ", "").replace("_","").lower()
    county_name = county_name.replace("county", "")
    county_name = county_name + state_abrv.lower()
                        
    Scope_HUCs = []
    with arcpy.da.SearchCursor(Stantec_HUC_Tracker, [county_field, "huc8"]) as cursor:
        for row in cursor:
            county = row[0].replace(" ", "").replace("_","").lower()
            if county_name in county:
                Scope_HUCs.append(row[1])

    arcpy.AddMessage("HUC8s according to Stantec Scope File: {0}".format(Scope_HUCs))
    arcpy.AddMessage("Please double check assigned HUC8s within Scope File, and only process the HUC8s that are in the given scope")
    arcpy.AddMessage("Delete HUC8 folders that will not be processed by you")

def Copy_AOI_Erase_GDB(HUC8_list, HUC_AOI_Erase_gdb):
    #Loop through HUC8 folders and copy the HUC_Erase_AOI_gdb to the HUC8 folder, rename to match HUC

    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Creating HUC-level S_AOI_Ar and Erase Areas GDBs for Development and QC #####")

    if not os.path.exists(HUC_AOI_Erase_gdb):
        arcpy.AddWarning("Can't find HUC-level Erase Areas and AOI geodatabase. Please manually copy the HUC_AOIs_Erase_Areas_XXXXXXXX.gdb to the handy folder for each HUC you will process")
        return
        
    for HUC8 in HUC8_list:

        arcpy.AddMessage("Creating gdb for HUC8 {0}".format(HUC8))
        gdb_name = "AOIs_Erase_Areas_{0}.gdb".format(HUC8)
        HUC8_folder = os.path.join(handy_folder, HUC8)
        HUC8_AOI_Erase_gdb = os.path.join(HUC8_folder, gdb_name)
        
        #Copy Template GDB
        if os.path.exists(HUC8_AOI_Erase_gdb):
            arcpy.AddMessage("HUC8 AOI and Erase Area GDBs already exist")
        else:
            #Copy GDB
            shutil.copytree(HUC_AOI_Erase_gdb, HUC8_AOI_Erase_gdb)

            #rename Erase_Areas_XXXXXXXX to Erase_Areas_HUC8
            arcpy.AddMessage("Renaming Files")
            arcpy.env.workspace = HUC8_AOI_Erase_gdb
            in_data =  "Erase_Areas_XXXXXXXX"
            out_data = "Erase_Areas_{0}".format(HUC8)
            data_type = "FeatureClass"
            arcpy.management.Rename(in_data, out_data, data_type)

            #rename S_AOI_Ar_XXXXXXXX to S_AOI_Ar_HUC8
            arcpy.env.workspace = os.path.join(HUC8_AOI_Erase_gdb, "FFRMS_Spatial_Layers")
            in_data =  "S_AOI_Ar_XXXXXXXX"
            out_data = "S_AOI_Ar_{0}".format(HUC8)
            data_type = "FeatureClass"
            arcpy.management.Rename(in_data, out_data, data_type)

def Create_Backup_Files(HUC8_list):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Creating Backup Files #####")
    for HUC8 in HUC8_list:
        HUC8_folder = os.path.join(handy_folder, HUC8)
        HUC8_input_folder = os.path.join(HUC8_folder, "inputs")
        HUC8_backup_folder = os.path.join(HUC8_input_folder, "{0}_backup_files".format(HUC8))
        HUC8_input_a_folder = os.path.join(HUC8_input_folder, "{0}_a".format(HUC8))

        arcpy.AddMessage("Creating backup files for HUC8 {0}".format(HUC8))

        if not os.path.exists(HUC8_backup_folder):
            shutil.copytree(HUC8_input_a_folder, HUC8_backup_folder)
            
if __name__ == '__main__':

    # Gather Parameter inputs from tool
    County_Folder = arcpy.GetParameterAsText(0)
    FIPS_Code = arcpy.GetParameterAsText(1)[:5]
    Tool_Template_Folder = arcpy.GetParameterAsText(2) #Assuming this is already cleaned up in a file folder

    #Set environment variables
    arcpy.env.workspace = County_Folder
    arcpy.env.overwriteOutput = True

    #Check inputs - verify county boundary, HUC8s location - Get County Boundary and HUC8 features
    NFHL_data, county_shapefile, HUC8_Shapefile, HUC_AOI_Erase_gdb = Check_Source_Data(Tool_Template_Folder)

    #Create handy folder within County Production Folder
    handy_folder = Create_Handy_Folder(County_Folder)

    #Get County Boundary from Shapefile
    county_boundary, county_name, state_name, state_abrv = Get_County_Info(FIPS_Code, county_shapefile)
    
    #Get HUC8s features in County
    County_HUC8s, HUC8_list = Get_All_HUC8s_in_County(county_boundary, HUC8_Shapefile)

    #Create HUC8_folders in handy_folder
    HUC8_list = Create_HUC8_folders(HUC8_list)

    if len(HUC8_list) == 0:
        arcpy.AddMessage(u"\u200B")
        arcpy.AddMessage("#### All HANDy INPUTS ALREADY CREATED FOR THIS COUNTY ####")
        arcpy.AddWarning("This tool will not overwrite existing inputs")
        arcpy.AddWarning("If you want to re-create a HUC8's inputs, move or delete the HUC8_a folder and try again")
        sys.exit()

    #Buffer HUC8s in handy_folder by 1km
    Create_HUC8_Shapefiles(HUC8_list, County_HUC8s)

    #Get Filenames for NFHL data
    S_Profil_Basln, S_BFE, S_XS, L_XS_Elev, S_Fld_Haz_Ar = find_NFHL_files(NFHL_data)

    #Prepare S_Fld_Haz_Ar_Static_BFE
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("Finding static BFEs in S_Fld_Haz_Ar files")
    S_Fld_Haz_Ar_Static_BFE = Create_S_Fld_Haz_Ar_Static_BFE(S_Fld_Haz_Ar, "S_Fld_Haz_Ar_Static_BFE")
    S_Fld_Haz_Ar_Static_BFE_MIP = None

    #Select NFHL data by HUC8 for each FVA feature 
    Select_NFHL_by_HUC("S_Profil_Basln", S_Profil_Basln, HUC8_list, True)
    Select_NFHL_by_HUC("S_BFE", S_BFE, HUC8_list, False)
    Select_NFHL_by_HUC("S_Fld_Haz_Ar_Static_BFE", S_Fld_Haz_Ar_Static_BFE, HUC8_list, False)
    Select_NFHL_by_HUC("S_XS", S_XS, HUC8_list, False)

    #loop through all HUC8 folders and select L_XS_Elev based on XS values
    Create_L_XS_Tables(HUC8_list, L_XS_Elev)

    #Copy HUC_AOI_Erase_gdb to each HUC8 folder
    Copy_AOI_Erase_GDB(HUC8_list, HUC_AOI_Erase_gdb)

    #Loop through HUC8 folders and copy the _a folder to _backup_files folder
    Create_Backup_Files(HUC8_list)

    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### FVA Input Processing Complete #####")
