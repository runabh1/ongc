--------------------------------------------------------
--  File created - Monday-January-05-2026   
--------------------------------------------------------
--------------------------------------------------------
--  DDL for Table WCR_WELLHEAD
--------------------------------------------------------

  CREATE TABLE "WCR_WELLHEAD" 
   (	"UWI" VARCHAR2(64 BYTE), 
	"WELL_NAME" VARCHAR2(255 BYTE), 
	"FIELD" VARCHAR2(255 BYTE), 
	"RELEASE_NAME" VARCHAR2(255 BYTE), 
	"LOCATION_TYPE" VARCHAR2(128 BYTE), 
	"BOTTOM_LONG" NUMBER, 
	"BOTTOM_LAT" NUMBER, 
	"SURFACE_LONG" NUMBER, 
	"SURFACE_LAT" NUMBER, 
	"CATEGORY" VARCHAR2(255 BYTE), 
	"WELL_PROFILE" VARCHAR2(64 BYTE), 
	"TARGET_DEPTH" NUMBER, 
	"DRILLED_DEPTH" NUMBER, 
	"LOGGERS_DEPTH" NUMBER, 
	"K_B" NUMBER, 
	"G_L" NUMBER, 
	"RIG" VARCHAR2(255 BYTE), 
	"SPUD_DATE" VARCHAR2(11 BYTE), 
	"HERMETICAL_TEST_DATE" VARCHAR2(11 BYTE), 
	"DRILLING_COMPLETED_DATE" VARCHAR2(11 BYTE), 
	"RIG_RELEASED_DATE" VARCHAR2(11 BYTE), 
	"FORMATION_AT_TD" VARCHAR2(255 BYTE), 
	"RELEASE_ORDER_NO" VARCHAR2(255 BYTE), 
	"OBJECTIVE" VARCHAR2(2000 BYTE), 
	"STATUS" VARCHAR2(2000 BYTE), 
	"ID" NUMBER(38,0), 
	"MODEL" VARCHAR2(25 BYTE), 
	"INSERT_DATE" DATE, 
	"MATCH_PERCENT" NUMBER, 
	"VECTOR_IDS" VARCHAR2(100 BYTE), 
	"PAGE_NUMBERS" VARCHAR2(100 BYTE)
   )  ;
--------------------------------------------------------
--  DDL for Table WCR_SWC
--------------------------------------------------------

  CREATE TABLE "WCR_SWC" 
   (	"ID" NUMBER(38,0), 
	"UWI" VARCHAR2(64 BYTE), 
	"DEPTH" NUMBER, 
	"RECOVERED_LENGTH" NUMBER, 
	"LITHOLOGY" VARCHAR2(255 BYTE), 
	"LITHOLOGY_DESCRIPTION" VARCHAR2(1000 BYTE), 
	"HCSHOW" VARCHAR2(255 BYTE), 
	"REMARKS" VARCHAR2(255 BYTE), 
	"MODEL" VARCHAR2(25 BYTE), 
	"INSERT_DATE" DATE, 
	"MATCH_PERCENT" NUMBER, 
	"VECTOR_IDS" VARCHAR2(100 BYTE), 
	"PAGE_NUMBERS" VARCHAR2(100 BYTE), 
	"MATCH_ID" NUMBER(38,0)
   )  ;
--------------------------------------------------------
--  DDL for Table WCR_LOGSRECORD
--------------------------------------------------------

  CREATE TABLE "WCR_LOGSRECORD" 
   (	"UWI" VARCHAR2(64 BYTE), 
	"TOP" NUMBER, 
	"BOTTOM" NUMBER, 
	"LOG_RECORDED" VARCHAR2(255 BYTE), 
	"LOG_DATE" VARCHAR2(11 BYTE), 
	"LOGGED_BY" VARCHAR2(64 BYTE), 
	"ID" NUMBER(38,0), 
	"MODEL" VARCHAR2(25 BYTE), 
	"INSERT_DATE" DATE, 
	"MATCH_PERCENT" NUMBER, 
	"VECTOR_IDS" VARCHAR2(100 BYTE), 
	"PAGE_NUMBERS" VARCHAR2(100 BYTE), 
	"MATCH_ID" NUMBER(38,0)
   )  ;
--------------------------------------------------------
--  DDL for Table WCR_HCSHOWS
--------------------------------------------------------

  CREATE TABLE "WCR_HCSHOWS" 
   (	"ID" NUMBER(38,0), 
	"UWI" VARCHAR2(64 BYTE), 
	"TOP_DEPTH" NUMBER, 
	"BOTTOM_DEPTH" NUMBER, 
	"TOTAL_GAS" VARCHAR2(255 BYTE), 
	"LITHOLOGY" VARCHAR2(255 BYTE), 
	"HCSHOW" VARCHAR2(255 BYTE), 
	"MODEL" VARCHAR2(25 BYTE), 
	"INSERT_DATE" DATE, 
	"MATCH_PERCENT" NUMBER, 
	"VECTOR_IDS" VARCHAR2(100 BYTE), 
	"PAGE_NUMBERS" VARCHAR2(100 BYTE), 
	"MATCH_ID" NUMBER(38,0)
   )  ;
--------------------------------------------------------
--  DDL for Table WCR_DIRSRVY
--------------------------------------------------------

  CREATE TABLE "WCR_DIRSRVY" 
   (	"ID" NUMBER(38,0), 
	"UWI" VARCHAR2(64 BYTE), 
	"MD" NUMBER, 
	"ANGLE_INCLINATION" NUMBER, 
	"AZIMUTH" NUMBER, 
	"NS" NUMBER, 
	"EW" NUMBER, 
	"NET_DRIFT" NUMBER, 
	"NET_DIRECTION_ANGLE" NUMBER, 
	"VERTICAL_SHORTENING" NUMBER, 
	"MODEL" VARCHAR2(25 BYTE), 
	"INSERT_DATE" DATE, 
	"MATCH_PERCENT" NUMBER, 
	"VECTOR_IDS" VARCHAR2(100 BYTE), 
	"PAGE_NUMBERS" VARCHAR2(100 BYTE), 
	"MATCH_ID" VARCHAR2(100 BYTE)
   )  ;
--------------------------------------------------------
--  DDL for Table WCR_CASING
--------------------------------------------------------

  CREATE TABLE "WCR_CASING" 
   (	"UWI" VARCHAR2(64 BYTE), 
	"CASING_TYPE" VARCHAR2(255 BYTE), 
	"CASING_LINER_NAME" VARCHAR2(255 BYTE), 
	"CASING_START_DATE" DATE, 
	"CASING_TOP" NUMBER, 
	"CASING_BOTTOM" NUMBER, 
	"OUTER_DIAMETER" NUMBER, 
	"CASING_SHOE_LENGTH" NUMBER, 
	"FLOAT_COLLAR" NUMBER, 
	"MATERIAL_TYPE" VARCHAR2(64 BYTE), 
	"WEIGHT" VARCHAR2(64 BYTE), 
	"STEEL_GRADE" VARCHAR2(64 BYTE), 
	"REMARKS" VARCHAR2(2000 BYTE), 
	"ID" NUMBER(38,0), 
	"MODEL" VARCHAR2(25 BYTE), 
	"INSERT_DATE" DATE, 
	"MATCH_PERCENT" NUMBER, 
	"VECTOR_IDS" VARCHAR2(100 BYTE), 
	"PAGE_NUMBERS" VARCHAR2(100 BYTE), 
	"MATCH_ID" NUMBER(38,0)
   )  ;
--------------------------------------------------------
--  Constraints for Table WCR_WELLHEAD
--------------------------------------------------------

  ALTER TABLE "WCR_WELLHEAD" MODIFY ("UWI" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table WCR_LOGSRECORD
--------------------------------------------------------

  ALTER TABLE "WCR_LOGSRECORD" MODIFY ("UWI" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table WCR_CASING
--------------------------------------------------------

  ALTER TABLE "WCR_CASING" MODIFY ("UWI" NOT NULL ENABLE);
