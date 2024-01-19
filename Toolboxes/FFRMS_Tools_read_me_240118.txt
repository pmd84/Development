FFRMS GIS Tools

This toolbox has the following six (6) tools:

0 - Prepare FVA Inputs (HUC8 or Countywide)

User Inputs (HUC8):
-	Production Folder: Location where you will produce FVA inputs
-	HUC8 Number: 8-digit HUC8

User Inputs (Countywide):
-	County Production Folder: Highest-level folder housing all data for the county.
-	FIPS Code: 5-number State & County code. 

User Inputs (Both):
-	Tool Template Files Folder (non-Stantec users) – included in toolbox zip folder, and contains necessary template files, including:
	-	FFRMS_Coastal_DB_20231020.gdb
	-	FFRMS_Riverine_DB_20231020.gdb
	-	HUC_AOIs_Erase_Areas_XXXXXXXX.gdb
	-	rFHL_20230630.gdb
	-	FFRMS_Counties.shp
	-	STARRII_FFRMS_HUC8s_Scope.shp

Outputs:
-	“FVA_Inputs” folder, located within County Folder chosen by user
-	Individual HUC8 Folders. HUC8s are determined by spatially intersecting county boundary with HUC8 scope file
-	HUC8_XXXXXXXX.shp: HUC8 boundary, pulled from HUC8 scope file
-	HUC8_XXXXXXXX_buffer.shp: HUC8 boundary, buffered by 1km
-	FVA_S_BFE_XXXXXXXX.shp: NFHL S_BFE lines (with additional MIP data, if available) selected using HUC8 boundary 
-	FVA_S_Profil_Basln_XXXXXXXX.shp: NFHL S_Profil_Basln lines (with MIP data) selected using HUC8 1km buffer 
-	FVA_S_Fld_Haz_Ar_Static_BFE_XXXXXXXX.shp: NFHL S_Fld_Haz_Ar polygons (with MIP data) where FLD_ZONE = “AE” or “AH”, and STATIC_BFE > 0 and selected using HUC8 boundary 
-	FVA_S_XS_XXXXXXXX.shp: NFHL S_XS lines (with MIP data) selected using HUC8 boundary 
-	FVA_L_XS_Elev_XXXXXXXX.shp: NFHL L_XS_Elev table (with MIP data) subset based on S_XS within HUC8 boundary
-	AOIs_Erase_Areas_XXXXXXXX.gdb: Geodatabase for creating erase areas and AOIs on a HUC8 level

Tool Process:
- 	Tool gets county info using FIPS code and counties shapefile
-	NFHL data and MIP data are validated
- 	FVA_Input and HUC8 folders are created
-	HUC8 features are selected using county boundary and buffered.
-	MIP data is checked for proper vertical datums (if NGVD29 values are found, the tool is exited and manual conversion is required)
-	Static BFEs are extracted from S_Fld_Haz_Ar if the STATIC_BFE field is greater than 0, and FLD_ZONE is AE or AH
-	S_XS, S_Profil_Basln, S_Fld_Haz_Ar_Static_BFE, and S_BFE are merged with MIP data (if available), and selected by HUC8 boundaries
-	L_XS_Elev tables are created based on XS_LN_ID in S_XS (both NFHL and MIP data)
-	Tool formats and copies AOIs_Erase_Areas_XXXXXXXX.gdb for each HUC8

1 - Create County FFRMS Geodatabase:

User Inputs:
-	County Production Folder: Location of production folder for current. Deliverables subfolders will be created by this tool.
-	FIPS Code: 5 numbers
-	UTM Zone: Pick number from drop-down list.
-	Riverine or Coastal: Type of FFRMS analysis performed.
-	Tool Template Files Folder (non-Stantec users) – included in toolbox zip folder, and contains necessary template files.

Outputs:
-	Configured County FFRMS Geodatabase

Tool Process:
1.	Reads user inputs.
2.	Checks the source data locations and ensures valid files. 
3.	Sets the spatial reference of the county geodatabase to the appropriate UTM zone (if no UTM zone provided, uses NRCS API to get UTM # based on the FIPS code) 
4.	Copies template geodatabase to output location and projects all spatial feature classes to the appropriate UTM zone.
	b.	Template files start in UTM zone 19.
	a. 	For cases where target UTM zones are 4 or lower, spatial files are reprojected twice, as UTM zones can only be projected 15 zones (90 degrees) at a time. 
5.	Populates S_FFRMS_Proj_Ar with county boundary and populates all fields.
	a.	EFF_DATE is “FEMA” date from counties shapefile.
	b.	PROD_DATE is set to be equal to the date the tool is run, or the FEMA_DATE in the FFRMS Counties Shapefile, whichever comes first.
6.	Populates S_Eff_0_2pct_Ar with appropriate NFHL data.
	a.	Uses the query: "SFHA_TF = 'T' OR ZONE_SUBTY = '0.2 PCT ANNUAL CHANCE FLOOD HAZARD"
7.	Configures A_AOI_Ar attribute table to follow same contingent attribute rules as in template gdb
8.	Populates the L_Source_Cit table in the county geodatabase with county info.


2 – Combine FVA Rasters:

User Inputs:
-	Tool Output Folders (by HUC8) – the user points to each of the HUC8 output folders created by the HANDy tool. Folders should contain all available FVA rasters (i.e. "wsel_grid_0.tif", "wsel_grid_1.tif"...)
-	HUC8 Erase Area AOI geodatabases - HUC8-level geodatabases with completed Erase_Areas_XXXXXXXX and S_AOI_Ar_XXXXXXXX 
-	County FFRMS Geodatabase – must be configured with first tool.
-	FVAs to Process: Choose which FVAs to process. Tool will find the appropriate rasters to stitch from each output folder.
-	Append AOIs to Geodatabase - Yes/No option of whether or not to append S_AOI_Ar features from HUC8-level geodatabases to county geodatabase
-	Tool Template Files Folder (non-Stantec users) – included in toolbox zip folder, and contains necessary template files.

Outputs:
-	FFRMS Geodatabase with FVA Rasters stitched together, clipped to county, and with areas removed.
-	S_AOI_Ar populated, if option is chosen

Tool Process:
1.	Reads user inputs, verifies naming convention, and checks validity of input files.
2.	Determines which FVAs will be processed and loops through the tool folders to gather the necessary rasters.
3.	Erases Erase_Areas on a HUC8 level and clips to county boundary
	- Erases areas determined from Y/N coded values in attribute table. 
	- If “Erase_All_FVAs” field is "Yes" for a given shape, then that shape will be clipped out for all FVAs. "NULL" or "No" will be ignored.
	- If an FVA feature is labeled "Yes", all lower FVA rasters will be erased for that feature (i.e., if FVA02 = "Yes", then FVA01 and FVA00 will also be erased)
4.	Creates empty raster dataset and mosaics all FVA rasters together.
5.	Rounds all values to the nearest tenth of a foot.
6.	Ensures values are in 32-bit float.
7.	Appends AOI features to county-wide S_AOI_Ar if option is chosen.

3 – Fix Countywide Raster Issues:

User inputs:
- 	FFRMS Geodatabase

Outputs:
- 	FFRMS Geodatabase with fixed rasters

Tool Process:
-	Identifies rasters in county geodatabase - ignores 0.2% raster
-	Creates polygons of raster extents
-	Compares floodplain extents between adjacent FVAs (compares 00 to 01, 01 to 02, 02 to 03)
-	If extent of lower FVA is greater than higher FVA, the difference is rasterized, made equal to lower FVA +1, and added to higher FVA
-	Compares cell values between adjacent FVAs
-	If cell values of lower FVA are greater than higher FVA, the FVA00 is used as a reference and 1, 2, and 3 are added to FVA01, FVA02, and FVA03, respectively. 
-	Any remaining issues are fixed using median raster values to fill in discrepancy areas where FVA00 is not available

4 – Post-Process FFRMS Geodatabase Tool:

User inputs:
-	FFRMS County Geodatabase – the gdb created in step 1 and populated with the stitched rasters in step 2.
-	HANDy Output Folders (by HUC8) – the user points to each of the HUC8 output folders created by the HANDy tool.
-	Tool Template Files Folder (non-Stantec users) – included in toolbox zip folder, and contains necessary template files.

Outputs:
-	S_Raster_QC_pt with qc points from each HUC8 folder and clipped to county boundary.
-	S_AOI_Ar with 2 polygons showing difference between FVA00 and NFHL 100-year floodplains.
-	S_AOI_Ar with Levees added based on NLD; AO and AH polygons added based on S_Fld_Haz_Ar. MIP Search polygons added based on CNMS Scope file (Stantec Only).
-	S_FFRMS_Ar with unioned county boundary and FVA03 polygon, with “T” and “F” fields populated for FFRMS availability
-	QC Pass rate based on HANDy QC Centerline Points (output message only)

Tool Process:
1.	Reads user input.
2.	Selects 100-year floodplain polygons from NFHL dataset, dissolves them into a single multipart feature, and clips it to the county boundary.
3.	Converts FVA00 and FVA03 rasters to integer, then to polygon, dissolves each into a single multipart feature.
4.	Clips and unions the county boundary and FVA03 polygons, and appends features S_FFRMS_Ar. The field “FFRMS_AVL” is given the value “T” for the FVA03 boundary, and “F” for the rest of the county.
5.	Creates 2 polygons by clipping the FVA00 polygon to the NFHL 100-year floodplain, and then vice-versa. These polygons are appended to S_AOI_Ar, and the “AOI_INFO” field is populated with an explanation.
6.	Loops through each of the HUC8 tool output folders from HANDy tool, searches for the qc points shapefiles for 01PCT FVA values
7.	Selects only QC points that intersect (within 1 meter) NFHL S_XS lines and are within county boundary.
8.	Appends selected QC points to S_Raster_QC_pt, populating all relevant fields.
9.	Determines the percentage of QC centerline points with a WSEL_DIFF value less than 0.5. If percentage is greater than 90%, the county passes QC.

5 – Export FFRMS Geodatabase Files:

User inputs:
-	County FFRMS Geodatabase – the gdb created in step 1, populated with the stitched rasters in step 2, and post-processed in step 3.
-	Features to Export - drop down to pick whether to export rasters, shapefiles, or both.

Outputs:
-	Raster folder with exported geotiff (.tif) versions of each FVA raster (RIV and/or CST)
-	Shapefiles saved to respective Riverine or Coastal folder with the following exported shapefiles:
	o	S_AOI_Ar
	o	S_FFRMS_Proj_Ar
	o	S_FFRMS_Ar
	o	S_Eff_0_2pct_Ar
	o	S_Raster_QC_pt
	o	L_Source_Cit (.dbf format)

Tool Process:
1.	Reads user input and checks validity of data sources
2.	Gathers FIPS_code, county, and state information from FFRMS features
3.	Creates "Rasters" and "Shapefiles" folders, and creates either "Riverine" or "Coastal" folder within Shapefiles folder
4.	Exports Rasters to geotiff format within "Rasters" folder
5.	Exports Spatial Layers to shapefile format within "Shapefiles" folder.
6.	Exports L_Source_Cit to .dbf format within "Shapefiles" folder.

6 – Create County FFRMS Metadata (XML):

User inputs:
-	County FFRMS Geodatabase – the gdb created in step 1, populated with the stitched rasters in step 2, and post-processed in step 3.
-	Tool Template Files Folder (non-Stantec users) – included in toolbox zip folder, and contains necessary template files.

Outputs:
-	Formatted and populated metadata (XML) file within the same folder as the geodatabase

Tool Process:
1.	Reads user input and checks validity of data sources
2.	Copies template XML to county folder
3.	Determines project extents in decimal degrees
4.	Gathers the names and numbers of all HUC8 watersheds that are within or intersect the county boundary
5.	Determines county info from feature classes, and creates a dictionary of values to replace within the metadata XML
6.	Determines which rasters are available, and deletes references to the 0.2% Annual Chance raster if not available
7.	Updates all variable values within the metadata XML

