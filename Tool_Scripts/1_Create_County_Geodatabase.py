import arcpy
import sys
from sys import argv
import os
import json
import requests
from arcpy import env
from arcpy.sa import *
import datetime
import shutil

def Check_Source_Data(Tool_Template_Folder, Riv_or_Cst):
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

    #Set File Paths
    if Riv_or_Cst == "Riverine":
        Template_FFRMS_gdb = os.path.join(Tool_Template_Folder, "FFRMS_Riverine_DB_20231020.gdb")
    else:
        Template_FFRMS_gdb = os.path.join(Tool_Template_Folder, "FFRMS_Coastal_DB_20231020.gdb")
    NFHL_data = os.path.join(Tool_Template_Folder, "rFHL_20230630.gdb")
    county_shapefile = os.path.join(Tool_Template_Folder, "FFRMS_Counties.shp")

    #Check or existence of template data
    for files in [NFHL_data, county_shapefile, Template_FFRMS_gdb]:
        if not os.path.exists(files):
            arcpy.AddError("No {0} found in Tool Template Files folder. Please manually add {0} to Tool Template Files folder and try again".format(os.path.basename(files)))
            sys.exit()
        else:
            arcpy.AddMessage("{0} found".format(os.path.basename(files)))

    return Template_FFRMS_gdb, NFHL_data, county_shapefile

def Copy_Template_FFRMS_Geodatabase(Template_FFRMS_gdb, geodatabase_dir, county_name, state_abrv, Riv_or_Cst):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Copying Template FFRMS Geodatabase #####")

    #make county and state abrv all caps
    county = county_name.upper()
    county = county.replace(" COUNTY", "").replace(" ", "_")
    state = state_abrv.upper()

    if Riv_or_Cst == "Riverine":
        wtr_type = "RIV"
    elif Riv_or_Cst == "Coastal":
        wtr_type = "CST"
    else:
        arcpy.AddError("Please select Riverine or Coastal and try again")
        sys.exit()

    gdb_name = "{0}_{1}_FFRMS_{2}.gdb".format(county, state, wtr_type)
    FFRMS_Geodatabase = os.path.join(geodatabase_dir, gdb_name)

    #Do not overwrite existing geodatabase
    if arcpy.Exists(FFRMS_Geodatabase):
        arcpy.AddWarning("Geodatabase already exists at {0}".format(FFRMS_Geodatabase))
        arcpy.AddError("County FFRMS Geodatabase already exists - if you wish to overwrite, please manually delete it try again".format(FFRMS_Geodatabase))
        sys.exit()

    #Copy template to new county geodatabase
    arcpy.AddMessage("Copying template FFRMS geodatabase to output location: {0}".format(FFRMS_Geodatabase))
    shutil.copytree(Template_FFRMS_gdb, FFRMS_Geodatabase)
        
    arcpy.env.workspace = FFRMS_Geodatabase

    #loop through feature classes in new geodatabase feature dataset and delete any existing rows
    for fc in arcpy.ListFeatureClasses(os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers")):
        arcpy.management.DeleteRows(in_rows=os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers", fc))
    arcpy.management.DeleteRows(in_rows = os.path.join(FFRMS_Geodatabase, "L_Source_Cit"))

    #If there are any rasters in the GDB template, delete them from county FFRMS geodatabase
    for raster in arcpy.ListRasters():
        arcpy.management.Delete(in_data=os.path.join(FFRMS_Geodatabase, raster))

    arcpy.AddMessage("County FFRMS geodatabase created")
    return FFRMS_Geodatabase

def Get_UTM_Zone_from_API(fips_code):
    #If no UTM zone is give, get if from NRCS API
    fips_code = fips_code[:5]
    arcpy.AddMessage("No UTM Code provided - Determining UTM code from API using FIPS code {0}".format(fips_code))

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
            utm_code_str = str(int(utm_designation))
            arcpy.AddMessage("UTM designation for county " + fips_code + " is " + utm_code_str)
            return utm_code_str
        else:
            raise Exception("Failed to retrieve UTM designation from API - please provided UTM code or try again later")
    else:
        raise Exception("Failed to retrieve UTM designation from API - please provided UTM code or try again later")  
    
def Set_Spatial_Reference(UTM_zone, FIPS_code):
    #Determine UTM Spatial Reference based on FIPS code
    if UTM_zone == "" or UTM_zone == None:
        UTM_zone = Get_UTM_Zone_from_API(FIPS_code)

    if UTM_zone == "55":
        #GUAM spatial reference must be set differently
        arcpy.AddMessage("Setting spatial reference for Guam using projection file")
        Spatial_Reference_String = "NAD 1983 (MA11) UTM Zone 55N"
        vertical_datum = "Guam Vertical Datum of 2004"

        Spatial_Reference_file = r"\\us0525-ppfss01\shared_projects\203432303012\FFRMS_Zone3\production\source_data\projection_files\Guam.prj"
        
        Output_Spatial_Reference = arcpy.SpatialReference(Spatial_Reference_file)
    else:
        vertical_datum = "NAVD88 height (ftUS)"
        Spatial_Reference_String = "NAD 1983 UTM Zone "+ UTM_zone +"N"
        arcpy.AddMessage("Spatial Reference is " + Spatial_Reference_String)
        Output_Spatial_Reference = arcpy.SpatialReference(Spatial_Reference_String, vertical_datum)

    return Output_Spatial_Reference, Spatial_Reference_String, UTM_zone 

def Get_County_Boundary_from_API(fips_code, County_Deliverables_Folder):
    arcpy.AddMessage("Downloading county boundary data from API")
    #Take first 5 characteris of FIPS code
    fips_code = fips_code[:5]

     # ArcGIS REST Endpoint for County Boundaries
    endpoint = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2019/MapServer/84/query"

    # Parameters for the API request
    params = {
        'where': "STATE='" + fips_code[:2] + "' AND COUNTY='" + fips_code[2:] + "'",
        'outFields': '*',
        'returnGeometry': 'true',
        'f': 'geojson'
    }
    
    # Make the API request
    response = requests.get(endpoint, params=params)
    if response.status_code == 200:
        geojson_data = response.json()

        # Save the JSON data to a file
        json_file = os.path.join(County_Deliverables_Folder, "{0}_county_boundary.json".format(fips_code))
        
        # Save the JSON data to file
        json_file = os.path.join(County_Deliverables_Folder, "{0}_county_boundary.json".format(fips_code))
        with open(json_file, 'w') as f:
            json.dump(geojson_data, f)

        # Create an output path to save the county boundary
        county_boundary = r"in_memory\county_boundary"

        # Use arcpy's JSONToFeatures_conversion method to convert JSON to a shapefile
        arcpy.conversion.JSONToFeatures(in_json_file=json_file, out_features=county_boundary)

        #Delete JSON file
        os.remove(json_file)

        arcpy.AddMessage("Downloaded shapefile for county " + fips_code + " to " + county_boundary)
    else:
        arcpy.AddError("Failed to download country boundary data using API. Please provide UTM code manually, or try again later.")
    return county_boundary

def Get_County_Info(fips_code, county_shapefile):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting County Boundary Geometry and Information #####")
    
    # if not arcpy.Exists(county_shapefile):
    #     arcpy.AddWarning("County server shapefile does not exist at {0}".format(county_shapefile))
        # arcpy.AddWarning("Attempting to download county shapefile from NRCS API")
        # county_boundary = Get_County_Boundary_from_API(fips_code, County_Deliverables_Folder)
        
    #Select county boundary from server shapefile based on the field CO_FIPS and export to new county shapefile
    fips_code = fips_code[:5]
    arcpy.management.MakeFeatureLayer(county_shapefile, "county_layer")

    arcpy.management.SelectLayerByAttribute(in_layer_or_view="county_layer", selection_type="NEW_SELECTION", 
                                            where_clause="CO_FIPS = '{0}'".format(fips_code))
    
    #Export county boundary to new shapefile (in memory)
    arcpy.AddMessage("Exporting county boundary")
    county_boundary = r"in_memory\county_boundary"
    arcpy.management.CopyFeatures(in_features="county_layer", out_feature_class=county_boundary)

    #Get county name from county boundary shapefile
    county_name = arcpy.da.SearchCursor(county_boundary, "CO_FNAME").next()[0]
    arcpy.AddMessage("County is {0}".format(county_name))

    state_name = arcpy.da.SearchCursor(county_boundary, "ST_NAME").next()[0]
    arcpy.AddMessage("State is {0}".format(state_name))

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
                            "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC", 
                            "Guam": "GU", "Puerto Rico": "PR", "Virgin Islands": "VI", "American Samoa": "AS", 
                            "Northern Mariana Islands": "MP", "Federated States of Micronesia": "FM"}
    
    state_abrv = state_name_abrv_dict[state_name]

    try:
        pub_date = arcpy.da.SearchCursor(county_boundary, "FEMA").next()[0]
        pub_date = pub_date.strftime("%m/%d/%Y")
    except:
        pub_date = ""
        arcpy.AddWarning("FEMA publication date not found in county boundary shapefile - please add manually to L_Source_Cit")

    return county_boundary, county_name, state_name, state_abrv, pub_date

def Reproject_FFRMS_gdb_Feature_Classes(Output_Spatial_Reference, FFRMS_Geodatabase, UTM_zone):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Reprojecting FFRMS Geodatabase Feature Classes to UTM zone {} #####".format(UTM_zone))

    #Project entire feature dataset to UTM zone

    feature_dataset = os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers")
    feature_dataset_projected = os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers_projected")
    arcpy.management.Project(feature_dataset, feature_dataset_projected, Output_Spatial_Reference)
    arcpy.management.Delete(feature_dataset)
    arcpy.management.Rename(feature_dataset_projected, "FFRMS_Spatial_Layers")

    arcpy.env.workspace = feature_dataset
    #Files may have wrong name from projecting - rename to remove _1
    for fc in arcpy.ListFeatureClasses():
        if fc.endswith("_1"):
            arcpy.management.Rename(fc, fc[:-2])

def Add_County_Info_to_S_FFRMS_Proj_Ar(FFRMS_Geodatabase, county_boundary, FIPS_code, county_name, UTM_zone, pub_date):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Adding County Information to S_FFRMS_Proj_Ar feature class #####")
    
    S_FFRMS_Proj_Ar = os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers\S_FFRMS_Proj_Ar")  
    
    arcpy.management.Append(inputs=county_boundary, target=S_FFRMS_Proj_Ar, schema_type="NO_TEST")

    #Get today's data in form MM/DD/YYYY
    today_date = datetime.datetime.now()
    today_date = today_date.strftime("%m/%d/%Y")

    with arcpy.da.UpdateCursor(S_FFRMS_Proj_Ar, ["FIPS", "POL_NAME1", "EFF_DATE", "PROD_DATE", "LIDAR_DATE", "SOURCE_CIT", "PROJECTION", "PROJ_ZONE", "PROJ_UNIT", "CASE_NO", "NOTES"]) as cursor:
        for row in cursor:
            row[0] = FIPS_code[:5]
            row[1] = county_name
            row[2] = r"6/30/2023"
            row[3] = today_date
            row[4] = r"8/8/8888"
            row[5] = "STUDY1"
            row[6] = "UNIVERSAL TRANSVERSE MERCATOR"
            row[7] = UTM_zone
            row[8] = "Meters"
            row[9] = "NP"
            row[10] = "NP"
            cursor.updateRow(row)

    return S_FFRMS_Proj_Ar
    
def Add_NFHL_data_to_S_Eff_0_2_pct_Ar(FFRMS_Geodatabase, NFHL_data, FIPS_code, county_name, UTM_zone):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Adding NFHL data to S_Eff_0_2_pct_Ar feature class #####")

    S_Eff_0_2_pct_Ar = os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers\S_Eff_0_2pct_Ar")  
    if not arcpy.Exists(S_Eff_0_2_pct_Ar):
        arcpy.AddWarning("S_Eff_0_2_pct_Ar feature class does not exist in geodatabase")

    S_Fld_Haz_AR = os.path.join(NFHL_data, "S_Fld_Haz_AR")
    #query = "FLD_ZONE NOT IN ('AREA NOT INCLUDED', 'D', 'NP', 'OPEN WATER') AND ZONE_SUBTY NOT IN ('AREA OF MINIMAL FLOOD HAZARD')"
    query = "SFHA_TF = 'T' OR ZONE_SUBTY = '0.2 PCT ANNUAL CHANCE FLOOD HAZARD'"
    arcpy.management.MakeFeatureLayer(S_Fld_Haz_AR, "NFHL_layer", query)

    #clip to county boundary
    arcpy.analysis.Clip("NFHL_layer", county_boundary, r"in_memory/NFHL_layer_clip")

    #dissolve all features
    arcpy.management.Dissolve(in_features=r"in_memory/NFHL_layer_clip", out_feature_class= r"in_memory/NFHL_layer_clip_merge")
                                
    #append to S_Eff_0_2_pct_AR
    arcpy.management.Append(inputs=r"in_memory/NFHL_layer_clip_merge", target=S_Eff_0_2_pct_Ar, schema_type="NO_TEST")

    return S_Eff_0_2_pct_Ar

def Populate_L_Source_Cit(FFRMS_Geodatabase, county_name, state_name, state_abrv, pub_date, FIPS_code):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Populating L_Source_Cit table #####")

    L_Source_Cit = os.path.join(FFRMS_Geodatabase, "L_Source_Cit")
    
    #delete any existing entries
    arcpy.management.DeleteRows(in_rows=L_Source_Cit)
    
    arcpy.AddMessage("Populating L_Source_Cit table")
    entries = [
    {   "SOURCE_CIT": "BASE1",
        "CID": FIPS_code[:5]+"C",
        "CITATION": "USGS WBD, 2023",
        "PUBLISHER": "United States Geological Survey",
        "TITLE": "HUC8 Boundaries Hydrographic features for water bodies and rivers/streams",
        "AUTHOR": "USGS",
        "PUB_PLACE": "Reston, VA",
        "PUB_DATE": r"05/08/2023",
        "WEBLINK": "https://www.usgs.gov/national-hydrography/access-national-hydrography-products",
        "MEDIA": "Digital",
        "VERSION_ID": "2.6.5.6",
        "CASE_NO": "NP",
        "MIP_CASE_N": "NP"
    },
    {
        "SOURCE_CIT": "FIRM1",
        "CID": FIPS_code[:5]+"C",
        "CITATION": "FEMA NFHL, 2023",
        "PUBLISHER": "Federal Emergency Management Agency",
        "TITLE": "Effective Flood Risk Data {0}, {1}".format(county_name, state_name),
        "AUTHOR": "FEMA",
        "PUB_PLACE": "Washington, DC",
        "PUB_DATE": r"06/30/2023",
        "WEBLINK": r"https://hazards.fema.gov/",
        "MEDIA": "Digital",
        "VERSION_ID": "2.6.5.6",
        "CASE_NO": "NP",
        "MIP_CASE_N": "NP"
    },
    {   "SOURCE_CIT": "STUDY1",
        "CID": FIPS_code[:5]+"C",
        "CITATION": "STARR II FFRMS, 2023",
        "PUBLISHER": "Federal Emergency Management Agency",
        "TITLE": "FFRMS for {0}, {1}".format(county_name, state_abrv),
        "AUTHOR": "STARR II",
        "PUB_PLACE": "Washington, DC",
        "PUB_DATE": "{0}".format(pub_date),
        "WEBLINK": r"https://hazards.fema.gov/",
        "MEDIA": "Digital",
        "VERSION_ID": "2.6.5.6",
        "CASE_NO": "NP",
        "MIP_CASE_N": "NP"
    }
]
    with arcpy.da.InsertCursor(L_Source_Cit, ["SOURCE_CIT", "CID", "CITATION", "PUBLISHER", "TITLE", "AUTHOR", "PUB_PLACE", "PUB_DATE", "WEBLINK", "MEDIA", "VERSION_ID", "CASE_NO", "MIP_CASE_NO"]) as cursor:
        for entry in entries:
            cursor.insertRow([entry["SOURCE_CIT"], entry["CID"], entry["CITATION"], entry["PUBLISHER"], entry["TITLE"], entry["AUTHOR"], entry["PUB_PLACE"], entry["PUB_DATE"], entry["WEBLINK"], entry["MEDIA"], entry["VERSION_ID"], entry["CASE_NO"], entry["MIP_CASE_N"]])

def Configure_Attribute_Domains(FFRMS_Geodatabase, Template_FFRMS_gdb, County_Deliverables_Folder):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Configuring S_AOI_Ar Attributes #####")

    target_S_AOI_Ar = os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers\S_AOI_Ar")
    template_S_AOI_Ar = os.path.join(Template_FFRMS_gdb, "FFRMS_Spatial_Layers\S_AOI_Ar")
    field_groups_csv = os.path.join(County_Deliverables_Folder, "AOI_Field_Groups.csv")
    contingent_values_csv = os.path.join(County_Deliverables_Folder, "AOI_Contingent_Values.csv")

    arcpy.AddMessage("Exporting field groups and contingent values from template geodatabase")    
    arcpy.management.ExportContingentValues(target_table=template_S_AOI_Ar, 
                                            field_groups_file=field_groups_csv, 
                                            contingent_values_file=contingent_values_csv)

    arcpy.AddMessage("Importing field groups and contingent values to county geodatabase")
    arcpy.management.ImportContingentValues(target_table=target_S_AOI_Ar, 
                                            field_group_file=field_groups_csv, 
                                            contingent_value_file=contingent_values_csv, 
                                            import_type="REPLACE")

    arcpy.AddMessage("Deleting temporary files")
    os.remove(field_groups_csv)
    os.remove(contingent_values_csv)
    os.remove(os.path.join(County_Deliverables_Folder, "AOI_Field_Groups.csv.xml"))
    os.remove(os.path.join(County_Deliverables_Folder, "AOI_Contingent_Values.csv.xml"))
    os.remove(os.path.join(County_Deliverables_Folder, "schema.ini"))

def getDirectories(County_Production_Folder, state_abrv, FIPS_Code, Riv_or_Cst):
    #Get/Set directory variables
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Creating County Deliverables Folder and Subfolders #####")

    #Create County Deliverables folder if not already existing
    County_Deliverables_Folder = os.path.join(County_Production_Folder, state_abrv + "_" + FIPS_Code)
    if not os.path.exists(County_Deliverables_Folder):
        arcpy.AddMessage("Creating {0} directory ".format(os.path.basename(County_Deliverables_Folder)))
        os.makedirs(County_Deliverables_Folder)
    else:
        arcpy.AddMessage("County Deliverables Folder already exists at {0}".format(County_Deliverables_Folder))

    #Name of folder locations
    raster_dir_name = state_abrv + "_" + FIPS_Code + "_Rasters"
    shapefile_dir_name = state_abrv + "_" + FIPS_Code + "_Shapefiles"
    geodatabase_dir_name = state_abrv + "_" + FIPS_Code + "_Geodatabase"
    shapefile_subdir_name = Riv_or_Cst

    #Folder Paths
    raster_dir = os.path.join(County_Deliverables_Folder, raster_dir_name)
    shapefile_dir = os.path.join(County_Deliverables_Folder, shapefile_dir_name)
    shapefile_subdir = os.path.join(shapefile_dir, shapefile_subdir_name)
    geodatabase_dir = os.path.join(County_Deliverables_Folder, geodatabase_dir_name)
    
    #Create if not already existing
    for directory in [raster_dir, shapefile_dir, shapefile_subdir, geodatabase_dir]:
        if not os.path.exists(directory):
            arcpy.AddMessage("Creating {0} directory ".format(os.path.basename(directory)))
            os.makedirs(directory)

    return County_Deliverables_Folder, raster_dir, shapefile_dir, shapefile_subdir, geodatabase_dir

def checkFinalSpatialReference(FFRMS_Geodatabase, Spatial_Reference_String):
    arcpy.env.workspace = FFRMS_Geodatabase
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Final Spatial Reference Check #####")
    arcpy.AddMessage("Spatial reference of FFRMS Feature Classes should be: {0}".format(Spatial_Reference_String))
    actual_sr = arcpy.Describe("FFRMS_Spatial_Layers").spatialReference.name
    actual_sr = actual_sr.replace("_", " ")
    arcpy.AddMessage("Spatial reference is: {0}".format(actual_sr))
    if actual_sr == Spatial_Reference_String:
        arcpy.AddMessage("Spatial reference is correct")
    else:
        arcpy.AddWarning("Spatial reference may be incorrect - please check spatial reference of FFRMS Spatial Layers. Delete geodatabase and try again if needed.")
        
if __name__ == '__main__':

    # Gather Parameter inputs from tool
    County_Production_Folder = arcpy.GetParameterAsText(0)
    FIPS_code = arcpy.GetParameterAsText(1)[:5]
    Riv_or_Cst = arcpy.GetParameterAsText(2)
    UTM_zone = arcpy.GetParameterAsText(3)
    Tool_Template_Folder = arcpy.GetParameterAsText(4)

    arcpy.env.workspace = County_Production_Folder
    arcpy.env.overwriteOutput = True

    #Validate source data
    Template_FFRMS_gdb, NFHL_data, county_shapefile = Check_Source_Data(Tool_Template_Folder, Riv_or_Cst)

    State_code = FIPS_code[:2]
    County_code = FIPS_code[2:5]

    #Create County Boundary shapefile
    county_boundary, county_name, state_name, state_abrv, pub_date = Get_County_Info(FIPS_code, county_shapefile)
    
    #Create spatial reference and get UTM zone
    Output_Spatial_Reference, Spatial_Reference_String, UTM_zone  = Set_Spatial_Reference(UTM_zone, FIPS_code)

    #Get project folder locations
    County_Deliverables_Folder, raster_dir, shapefile_dir, shapefile_subdir, geodatabase_dir = getDirectories(County_Production_Folder, state_abrv, FIPS_code, Riv_or_Cst)

    #copy template geodatabase
    FFRMS_Geodatabase = Copy_Template_FFRMS_Geodatabase(Template_FFRMS_gdb, geodatabase_dir, county_name, state_abrv, Riv_or_Cst)

    arcpy.env.workspace = os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers")

    #loop through feature classes in template geodatabase feature dataset and project to UTM zone
    Reproject_FFRMS_gdb_Feature_Classes(Output_Spatial_Reference, FFRMS_Geodatabase, UTM_zone)

    #Add county boundary to S_FFRMS_Proj_AR feature class
    S_FFRMS_Proj_Ar = Add_County_Info_to_S_FFRMS_Proj_Ar(FFRMS_Geodatabase, county_boundary, FIPS_code, 
                                                         county_name, UTM_zone, pub_date)

    #Add 0.2% FEMA floodplain to S_Eff_0_2_pct_Ar feature class in geodatabase
    S_Eff_0_2_pct_Ar = Add_NFHL_data_to_S_Eff_0_2_pct_Ar(FFRMS_Geodatabase, NFHL_data, FIPS_code, 
                                                         county_name, UTM_zone)
  
    #Configure attribute domains for S_AOI_Ar
    Configure_Attribute_Domains(FFRMS_Geodatabase, Template_FFRMS_gdb, County_Deliverables_Folder)
    
    #Populate L_Source_Cit
    Populate_L_Source_Cit(FFRMS_Geodatabase, county_name, state_name, state_abrv, pub_date, FIPS_code)

    #Final check of spatial reference for feature dataset in geodatabase
    checkFinalSpatialReference(FFRMS_Geodatabase, Spatial_Reference_String)
