
/*
* This program is largely based on the TelemFFB distribution (https://github.com/walmis/TelemFFB).

* This program is free software : you can redistribute it and /or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, version 3.

* This program is distributed in the hope that it will be useful, but
* WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.See the GNU
* General Public License for more details.

* You should have received a copy of the GNU General Public License
* along with this program.If not, see < http://www.gnu.org/licenses/>.
*/

#define NOMINMAX
#include <stdio.h>
#include <string.h>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <cstdarg>
#include <string>
#include <vector>
#include <map>
#include <cstring>
#include <winsock2.h>
#include <thread>
#include <mutex>
#include <fstream>
#include <chrono>
#include <Windows.h>
#include <algorithm>
#include "XPLMProcessing.h"
#include "XPLMDataAccess.h"
#include "XPLMUtilities.h"
#include "XPLMPlugin.h"
#include "XPLMPlanes.h"



/* UDP socket variables */
SOCKET udpSocket_tx;
struct sockaddr_in serverAddr_tx;
SOCKET udpSocket_rx;
struct sockaddr_in serverAddr_rx;
bool gTerminateReceiveThread = false;

std::mutex axisDataMutex;
std::mutex logMutex;


std::ofstream debugLogFile;


struct DataRefSubscription {
    XPLMDataRef dataRef;
    std::string key;         // Key in telemetryData
    std::string type;        // Data type (int, float, double, etc.)
    int precision;           // Precision for floats
    float conversionFactor;  // Conversion factor (default 1.0)
};




std::vector<DataRefSubscription> subscribedDataRefs;


/* Data refs we will record. */

char gAircraftName[250];
char gPrevAircraftName[250];

int gActiveNumGear = 3;
int gActiveRetractable;
float gActiveWarnAlpha;
int gActiveNumEngines;
float gActiveVne;
float gActiveVso;
float gActiveVfe;
float gActiveVle;
float gActiveGearXNode;
float gActiveGearYNode;
float gActiveGearZNode;

bool simPaused = false;

static XPLMDataRef gAircraftDescr;
static XPLMDataRef gPaused = XPLMFindDataRef("sim/time/paused");                                        // boolean � int � v6.60+
static XPLMDataRef gOnGround = XPLMFindDataRef("sim/flightmodel/failures/onground_all");                // int � v6.60+
static XPLMDataRef gRetractable = XPLMFindDataRef("sim/aircraft/gear/acf_gear_retract");                // boolean � int � v6.60+
static XPLMDataRef gFlaps = XPLMFindDataRef("sim/cockpit2/controls/flap_system_deploy_ratio");          // [0..1] � float � v6.60
static XPLMDataRef gGear = XPLMFindDataRef("sim/flightmodel2/gear/deploy_ratio");                       // ratio � float[gear] � v9.00 +
static XPLMDataRef gGs_axil = XPLMFindDataRef("sim/flightmodel/forces/g_axil");                         // Gs � float � v6.60+
static XPLMDataRef gGs_nrml = XPLMFindDataRef("sim/flightmodel/forces/g_nrml");                         // Gs � float � v6.60+
static XPLMDataRef gGs_side = XPLMFindDataRef("sim/flightmodel/forces/g_side");                         // Gs � float � v6.60+
static XPLMDataRef gAccLocal_x = XPLMFindDataRef("sim/flightmodel/position/local_ax");                  // mtr/sec2 � float � v6.60+
static XPLMDataRef gAccLocal_y = XPLMFindDataRef("sim/flightmodel/position/local_ay");                  // mtr/sec2 � float � v6.60+
static XPLMDataRef gAccLocal_z = XPLMFindDataRef("sim/flightmodel/position/local_az");                  // mtr/sec2 � float � v6.60+
static XPLMDataRef gVelAcf_x = XPLMFindDataRef("sim/flightmodel/forces/vx_acf_axis");                   // m/s � float � v6.60+
static XPLMDataRef gVelAcf_y = XPLMFindDataRef("sim/flightmodel/forces/vy_acf_axis");                   // m/s � float � v6.60+
static XPLMDataRef gVelAcf_z = XPLMFindDataRef("sim/flightmodel/forces/vz_acf_axis");                   // m/s � float � v6.60+
static XPLMDataRef gTAS = XPLMFindDataRef("sim/flightmodel/position/true_airspeed");                    // m/s � float � v6.60+
static XPLMDataRef gIAS = XPLMFindDataRef("sim/flightmodel/position/indicated_airspeed");               // m/s � float � v6.60+
static XPLMDataRef gAirDensity = XPLMFindDataRef("sim/weather/rho");                                    // kg/cu m float � v6.60+
static XPLMDataRef gDynPress = XPLMFindDataRef("sim/flightmodel/misc/Qstatic");                         // psf � float � v6.60+
static XPLMDataRef gPropThrust = XPLMFindDataRef("sim/flightmodel/engine/POINT_thrust");                // newtons � float[16] � v6.60+
static XPLMDataRef gAoA = XPLMFindDataRef("sim/flightmodel/position/alpha");                            // degrees � float � v6.60+
static XPLMDataRef gWarnAlpha = XPLMFindDataRef("sim/aircraft/overflow/acf_stall_warn_alpha");          // degrees � float � v6.60+
static XPLMDataRef gSlip = XPLMFindDataRef("sim/flightmodel/position/beta");                            // degrees � float � v6.60+
static XPLMDataRef gWoW = XPLMFindDataRef("sim/flightmodel2/gear/tire_vertical_deflection_mtr");        // meters � float[gear] � v9.00+
static XPLMDataRef gNumEngines = XPLMFindDataRef("sim/aircraft/engine/acf_num_engines");                // int � v6.60+
static XPLMDataRef gEngRPM = XPLMFindDataRef("sim/flightmodel/engine/ENGN_tacrad");                     // rad/sec � float[16] � v6.60+
static XPLMDataRef gEngPCT = XPLMFindDataRef("sim/flightmodel/engine/ENGN_N1_");                        // percent � float[16] � v6.60+
static XPLMDataRef gAfterburner = XPLMFindDataRef("sim/flightmodel2/engines/afterburner_ratio");        // ratio � float[engine] � v9.00+
static XPLMDataRef gPropRPM = XPLMFindDataRef("sim/flightmodel/engine/POINT_tacrad");                   // rad/sec � float[16] � v6.60+
static XPLMDataRef gRudDefl_l = XPLMFindDataRef("sim/flightmodel/controls/ldruddef");                   // degrees � float � v6.60+
static XPLMDataRef gRudDefl_r = XPLMFindDataRef("sim/flightmodel/controls/rdruddef");                   // degrees � float � v6.60+
static XPLMDataRef gVne = XPLMFindDataRef("sim/aircraft/view/acf_Vne");                                 // kias � float � v6.60+
static XPLMDataRef gVso = XPLMFindDataRef("sim/aircraft/view/acf_Vso");                                 // kias � float � v6.60+
static XPLMDataRef gVfe = XPLMFindDataRef("sim/aircraft/view/acf_Vfe");                                 // kias � float � v6.60+
static XPLMDataRef gVle = XPLMFindDataRef("sim/aircraft/overflow/acf_Vle");                             // kias  float � v6.60 +


static XPLMDataRef gCollectiveOvd = XPLMFindDataRef("sim/operation/override/override_prop_pitch");
static XPLMDataRef gRollOvd = XPLMFindDataRef("sim/operation/override/override_joystick_roll");
static XPLMDataRef gPitchOvd = XPLMFindDataRef("sim/operation/override/override_joystick_pitch");
static XPLMDataRef gYawOvd = XPLMFindDataRef("sim/operation/override/override_joystick_heading");

static XPLMDataRef gRollCenter = XPLMFindDataRef("sim/joystick/joystick_roll_center");
static XPLMDataRef gPitchCenter = XPLMFindDataRef("sim/joystick/joystick_pitch_center");
static XPLMDataRef gYawCenter = XPLMFindDataRef("sim/joystick/joystick_heading_center");

static XPLMDataRef gCollectiveRatio = XPLMFindDataRef("sim/cockpit2/engine/actuators/prop_ratio_all");
static XPLMDataRef gRollRatio = XPLMFindDataRef("sim/joystick/yoke_roll_ratio");
static XPLMDataRef gPitchRatio = XPLMFindDataRef("sim/joystick/yoke_pitch_ratio");
static XPLMDataRef gYawRatio = XPLMFindDataRef("sim/joystick/yoke_heading_ratio");

static XPLMDataRef gElevTrim = XPLMFindDataRef("sim/flightmodel2/controls/elevator_trim");
static XPLMDataRef gAilerTrim = XPLMFindDataRef("sim/flightmodel2/controls/aileron_trim");
static XPLMDataRef gRudderTrim = XPLMFindDataRef("sim/flightmodel2/controls/rudder_trim");

static XPLMDataRef gAPMode = XPLMFindDataRef("sim/cockpit/autopilot/autopilot_mode");
static XPLMDataRef gAPServos = XPLMFindDataRef("sim/cockpit2/autopilot/servos_on");
static XPLMDataRef gYawServo = XPLMFindDataRef("sim/joystick/servo_heading_ratio");
static XPLMDataRef gPitchServo = XPLMFindDataRef("sim/joystick/servo_pitch_ratio");
static XPLMDataRef gRollServo = XPLMFindDataRef("sim/joystick/servo_roll_ratio");

static XPLMDataRef gCanopyPos = XPLMFindDataRef("sim/flightmodel/controls/canopy_ratio");
static XPLMDataRef gSpeedbrakePos = XPLMFindDataRef("sim/flightmodel2/controls/speedbrake_ratio");

static XPLMDataRef gGearXNode = XPLMFindDataRef("sim/aircraft/parts/acf_gear_xnodef");
static XPLMDataRef gGearYNode = XPLMFindDataRef("sim/aircraft/parts/acf_gear_ynodef");
static XPLMDataRef gGearZNode = XPLMFindDataRef("sim/aircraft/parts/acf_gear_znodef");

// Stick force DataRefs
static XPLMDataRef gStickForcePitch = XPLMFindDataRef("sim/flightmodel/misc/act_frc_ptch_lb");
static XPLMDataRef gStickForceRoll = XPLMFindDataRef("sim/flightmodel/misc/act_frc_roll_lb");
static XPLMDataRef gStickForceYaw = XPLMFindDataRef("sim/flightmodel/misc/act_frc_hdgn_lb");




std::map<std::string, std::string> telemetryData;
std::map<std::string, float> axisDataMap = { {"jx", 0.0}, {"jy", 0.0}, {"px", 0.0}, {"cy", 0.0} };

bool overrideJoystick = false;
bool overridePedals = false;
bool overrideCollective = false;

static bool DEBUG = true;


static float MyFlightLoopCallback(float inElapsedSinceLastCall, float inElapsedTimeSinceLastFlightLoop, int inCounter, void* inRefcon);

const float kt_2_mps = 0.51444f; // convert knots to meters per second
const float radps_2_rpm = 9.5493f; // convert rad/sec to rev/min
const float fps_2_g = 0.031081f; // convert feet per second to g
const float no_convert = 1.0; // dummy value for no conversion factor


std::string GetTimestamp() {
    SYSTEMTIME systemTime;
    GetSystemTime(&systemTime);

    FILETIME fileTime;
    SystemTimeToFileTime(&systemTime, &fileTime);

    ULARGE_INTEGER uli;
    uli.LowPart = fileTime.dwLowDateTime;
    uli.HighPart = fileTime.dwHighDateTime;

    auto milliseconds = uli.QuadPart % 10000000 / 10000;  // Convert 100-nanoseconds to milliseconds

    std::ostringstream oss;
    oss << std::setfill('0') << std::setw(3) << milliseconds;

    return
        std::to_string(systemTime.wMonth) + ":" +
        std::to_string(systemTime.wDay) + ":" +
        std::to_string(systemTime.wHour) + ":" +
        std::to_string(systemTime.wMinute) + ":" +
        std::to_string(systemTime.wSecond) + "." +
        oss.str() + " - ";
}

// Function to write a log message with timestamp to the debug log
void DebugLog(const std::string& message) {
    std::lock_guard<std::mutex> lock(logMutex);  // Lock the mutex

    if (debugLogFile.is_open()) {
        debugLogFile << GetTimestamp() << message << std::endl;
        debugLogFile.flush();
    }
}

void InitializeDebugLog() {
    if (DEBUG) {
        debugLogFile.open("FSFFB_DebugLog.txt", std::ios::out);
    }
}

void RegisterDataRef(const std::string& datarefPath, const std::string& key, const std::string& type, int precision = 3, float conversionFactor = 1.0f) {
    // Find the dataref
    XPLMDataRef dataRef = XPLMFindDataRef(datarefPath.c_str());
    if (dataRef != nullptr) {
        // Store the dataref in the vector with precision and conversion factor
        DataRefSubscription sub = { dataRef, key, type, precision, conversionFactor };
        subscribedDataRefs.push_back(sub);
        DebugLog("Subscribed to DataRef: " + datarefPath + " as " + type + " with key " + key + ", precision " + std::to_string(precision) + ", conversion factor " + std::to_string(conversionFactor));
    }
    else {
        DebugLog("Failed to subscribe to DataRef: " + datarefPath);
    }
}



// Function to get a timestamp string
// Function to get a timestamp string with millisecond resolution


void InitializeAW109DataRefs() {
    RegisterDataRef("aw109/controls/aileron_trim_req", "gAW109_aileron_trim_req", "float");
    RegisterDataRef("aw109/controls/elevator_trim_req", "gAW109_elevator_trim_req", "float");
    RegisterDataRef("aw109/controls/rudder_trim_req", "gAW109_rudder_trim_req", "float");
    RegisterDataRef("aw109/autopilot/cyc_force_trim_release_pressed", "gAW109_cyc_force_trim_release_pressed", "int");
    RegisterDataRef("aw109/servo/aileron_trim_rate", "gAW109_aileron_trim_rate", "float");
    // Continue for other datarefs...
}




std::string FloatToString(float value, int precision, float conversionFactor = 1.0) {
    value *= conversionFactor; // Apply the conversion factor
    std::ostringstream stream;
    stream << std::fixed << std::setprecision(precision) << value;
    return stream.str();
}

// Function to convert an array of floats to a formatted string with an optional conversion factor
// If fixed size is passed, that many elements (including trailiing zero vaues) will be returned
// Otherwise, the size is calculated, result formatted and any trailing 0 values are trimmed from the result
std::string FloatArrayToString(XPLMDataRef dataRef, float conversionFactor = 1.0, int fixed_size = -1, int precision = 3) {
    // Determine the size of the array
    int size = XPLMGetDatavf(dataRef, nullptr, 0, 0);

    // Override the size if fixed_size is provided and is less than the dynamically determined size
    // This is needed for some datarefs where values may be zero but are needed (eng rpm for example) and we don't want those values stripped of after formatting
    if (fixed_size > 0 && fixed_size <= size) {
        size = fixed_size;
    }


    // Use std::vector for dynamic memory allocation
    std::vector<float> dataArray(size);

    // Retrieve the entire array of values
    XPLMGetDatavf(dataRef, dataArray.data(), 0, size);

    std::ostringstream formattedString;

    // Set precision for floating-point values
    formattedString << std::fixed << std::setprecision(precision);

    for (int i = 0; i < size; ++i) {
        // Convert each value with specified precision before applying conversion factor
        float value = dataArray[i] * conversionFactor;

        formattedString << std::setprecision(precision) << value;

        //if (dataRef == gPropRPM) {
        //    DebugLog("PropRPM:" + formattedString.str());
        //}

        if (i < size - 1) {
            formattedString << "~";  // Add tilde separator between values, except for the last one
        }
    }

    if (fixed_size > 0) {
        // if fixed size was passed, return whole formatted string, including trailing 0.000 values
        return formattedString.str();
    }

    // Trim instances of "~0" from the right side of the string
    std::string result = formattedString.str();
    size_t pos = result.find_last_not_of("~0.000");
    if (pos != std::string::npos) {
        result = result.substr(0, pos + 1);
    }

    return result;
}


int GetNumGear() {
    // Use std::vector for dynamic memory allocation
    int size = 10;
    std::vector<float> arrayX(size);
    std::vector<float> arrayY(size);
    std::vector<float> arrayZ(size);

    // Retrieve the entire arrays of values
    XPLMGetDatavf(gGearXNode, arrayX.data(), 0, size);
    XPLMGetDatavf(gGearYNode, arrayY.data(), 0, size);
    XPLMGetDatavf(gGearZNode, arrayZ.data(), 0, size);

    int maxNonZero = 0;

    for (int i = 0; i < size; ++i) {
        int nonZeroCount = std::count_if(arrayX.begin() + i, arrayX.begin() + i + 1, [](float value) { return value != 0.0f; }) +
            std::count_if(arrayY.begin() + i, arrayY.begin() + i + 1, [](float value) { return value != 0.0f; }) +
            std::count_if(arrayZ.begin() + i, arrayZ.begin() + i + 1, [](float value) { return value != 0.0f; });

        maxNonZero = std::max(maxNonZero, nonZeroCount);
    }

    return maxNonZero;
}

void GetACDetails(const std::string& aircraftName) {
    // Stuff we only need to get once when the aircraft is loaded
    DebugLog("Aircraft Changed to: >" + aircraftName + "< - getting new aircraft details...");
    gActiveNumEngines = XPLMGetDatai(gNumEngines);
    gActiveNumGear = GetNumGear();

    telemetryData["RetractableGear"] = std::to_string(XPLMGetDatai(gRetractable));
    telemetryData["NumberEngines"] = std::to_string(gActiveNumEngines);
    telemetryData["NumberGear"] = std::to_string(gActiveNumGear);
    telemetryData["WarnAlpha"] = FloatToString(XPLMGetDataf(gWarnAlpha), 3);
    telemetryData["Vne"] = FloatToString(XPLMGetDataf(gVne) * kt_2_mps, 3);
    telemetryData["Vso"] = FloatToString(XPLMGetDataf(gVso) * kt_2_mps, 3);
    telemetryData["Vfe"] = FloatToString(XPLMGetDataf(gVfe) * kt_2_mps, 3);
    telemetryData["Vle"] = FloatToString(XPLMGetDataf(gVle) * kt_2_mps, 3);

    telemetryData["GearXNode"] = FloatArrayToString(gGearXNode, no_convert, gActiveNumGear);
    telemetryData["GearYNode"] = FloatArrayToString(gGearYNode, no_convert, gActiveNumGear);
    telemetryData["GearZNode"] = FloatArrayToString(gGearZNode, no_convert, gActiveNumGear);

    //InitializeAW109DataRefs();

}

void CollectTelemetryData()
{

    // Get the aircraft name
    XPLMGetDatab(gAircraftDescr, gAircraftName, 0, 250);

    if (strlen(gAircraftName) == 0) {
        //If the aircraft description is blank.. use the aircraft model file name
        char aircraftPath[256];
        XPLMGetNthAircraftModel(0, gAircraftName, aircraftPath);
    }

    // Check if the aircraft name has changed
    if (std::strcmp(gAircraftName, gPrevAircraftName) != 0) {
        GetACDetails(gAircraftName);
        std::strcpy(gPrevAircraftName, gAircraftName);
    }

    for (const auto& sub : subscribedDataRefs) {
        if (sub.type == "int") {
            int value = XPLMGetDatai(sub.dataRef);
            telemetryData[sub.key] = std::to_string(value);  // Store in telemetryData map
        }
        else if (sub.type == "float") {
            float value = XPLMGetDataf(sub.dataRef) * sub.conversionFactor;  // Apply conversion factor
            telemetryData[sub.key] = FloatToString(value, sub.precision);    // Use custom precision
        }
        else if (sub.type == "double") {
            double value = XPLMGetDatad(sub.dataRef) * sub.conversionFactor;  // Apply conversion factor
            telemetryData[sub.key] = FloatToString(static_cast<float>(value), sub.precision);  // Store in telemetryData map
        }
        else {
            DebugLog("Unsupported dataref type: " + sub.type);
        }
    }

    telemetryData["src"] = "XPLANE";
    telemetryData["N"] = gAircraftName;
    telemetryData["STOP"] = std::to_string(XPLMGetDatai(gPaused));

    simPaused = XPLMGetDatai(gPaused) == 1;

    telemetryData["SimPaused"] = std::to_string(simPaused);  // Store as string for telemetry

    telemetryData["SimOnGround"] = std::to_string(XPLMGetDatai(gOnGround));

    telemetryData["T"] = FloatToString(XPLMGetElapsedTime(), 3);
    telemetryData["G"] = FloatToString(XPLMGetDataf(gGs_nrml), 3);
    telemetryData["Gaxil"] = FloatToString(XPLMGetDataf(gGs_axil), 3);
    telemetryData["Gside"] = FloatToString(XPLMGetDataf(gGs_side), 3);

    telemetryData["TAS"] = FloatToString(XPLMGetDataf(gTAS), 3);
    telemetryData["IAS"] = FloatToString(XPLMGetDataf(gIAS) * kt_2_mps, 3); //convert from kt t m/s to match with gTAS
    telemetryData["AirDensity"] = FloatToString(XPLMGetDataf(gAirDensity), 3);
    telemetryData["DynPressure"] = FloatToString(XPLMGetDataf(gDynPress), 3);
    telemetryData["AoA"] = FloatToString(XPLMGetDataf(gAoA), 3);

    telemetryData["SideSlip"] = FloatToString(XPLMGetDataf(gSlip), 3);


    telemetryData["WeightOnWheels"] = FloatArrayToString(gWoW, no_convert, 3);
    telemetryData["EngRPM"] = FloatArrayToString(gEngRPM, radps_2_rpm, gActiveNumEngines, 2);
    telemetryData["EngPCT"] = FloatArrayToString(gEngPCT, no_convert, gActiveNumEngines, 3);
    telemetryData["PropRPM"] = FloatArrayToString(gPropRPM, radps_2_rpm, gActiveNumEngines, 2);
    telemetryData["PropThrust"] = FloatArrayToString(gPropThrust,no_convert, gActiveNumEngines, 2);
    telemetryData["Afterburner"] = FloatArrayToString(gAfterburner,no_convert, gActiveNumEngines, 2);


    telemetryData["RudderDefl"] = FloatToString(XPLMGetDataf(gRudDefl_l), 3);
    telemetryData["RudderDefl_l"] = FloatToString(XPLMGetDataf(gRudDefl_l), 3);
    telemetryData["RudderDefl_r"] = FloatToString(XPLMGetDataf(gRudDefl_r), 3);

    // Stick Force data from X-Plane
    telemetryData["StickForcePitch"] = FloatToString(XPLMGetDataf(gStickForcePitch), 3);
    telemetryData["StickForceRoll"] = FloatToString(XPLMGetDataf(gStickForceRoll), 3);
    telemetryData["StickForceYaw"] = FloatToString(XPLMGetDataf(gStickForceYaw), 3);

    telemetryData["AccBody"] =  FloatToString(XPLMGetDataf(gAccLocal_x) * fps_2_g, 3) + "~" + FloatToString(XPLMGetDataf(gAccLocal_y) * fps_2_g, 3) + "~" + FloatToString(XPLMGetDataf(gAccLocal_z) * fps_2_g, 3);
    telemetryData["VelAcf"] =  FloatToString(XPLMGetDataf(gVelAcf_x), 3) + "~" + FloatToString(XPLMGetDataf(gVelAcf_y), 3) + "~" + FloatToString(-XPLMGetDataf(gVelAcf_z), 3);
    telemetryData["Flaps"] = FloatToString(XPLMGetDataf(gFlaps), 3);
    telemetryData["Gear"] = FloatArrayToString(gGear, no_convert, 3);

    telemetryData["APMode"] = std::to_string(XPLMGetDatai(gAPMode));
    telemetryData["APServos"] = std::to_string(XPLMGetDatai(gAPServos));
    telemetryData["APYawServo"] = FloatToString(XPLMGetDataf(gYawServo), 3);
    telemetryData["APPitchServo"] = FloatToString(XPLMGetDataf(gPitchServo), 3);
    telemetryData["APRollServo"] = FloatToString(XPLMGetDataf(gRollServo), 3);
    telemetryData["ElevTrimPct"] = FloatToString(XPLMGetDataf(gElevTrim), 3);
    telemetryData["AileronTrimPct"] = FloatToString(XPLMGetDataf(gAilerTrim), 3);
    telemetryData["RudderTrimPct"] = FloatToString(XPLMGetDataf(gRudderTrim), 3);

    telemetryData["CanopyPos"] = FloatToString(XPLMGetDataf(gCanopyPos), 3);
    telemetryData["SpeedbrakePos"] = FloatToString(XPLMGetDataf(gSpeedbrakePos), 3);


    telemetryData["cOvrd"] = std::to_string(overrideCollective);
    telemetryData["jOvrd"] = std::to_string(overrideJoystick);
    telemetryData["pOvrd"] = std::to_string(overridePedals);



}



void FormatAndSendTelemetryData()
{
    // Create a string with the data for UDP transmission
    std::string dataString;

    for (const auto& entry : telemetryData) {
        dataString += entry.first + "=" + entry.second + ";";
    }

    // Send the data over the UDP socket
    sendto(udpSocket_tx, dataString.c_str(), dataString.length(), 0, (struct sockaddr*)&serverAddr_tx, sizeof(serverAddr_tx));
}

void ProcessReceivedData(const std::string& dataType, const std::string& payload) {
    // Handle different data types here
    if (dataType == "AXIS") {
        // Parse and update AXIS data map
        std::istringstream iss(payload);
        std::string token;
        while (std::getline(iss, token, ',')) {
            size_t equalsPos = token.find('=');
            if (equalsPos != std::string::npos) {
                std::string key = token.substr(0, equalsPos);
                float value = std::stof(token.substr(equalsPos + 1));
                axisDataMap[key] = value;
            }
        }

        // Perform actions based on AXIS data
        // ...
    }
    else if (dataType == "OVERRIDE") {
        // Parse the payload for keyword and value
        DebugLog("Inside the Override block");
        std::istringstream iss(payload);
        std::string keyValuePair;

        // Assuming payload is in the form "keyword=value"
        if (std::getline(iss, keyValuePair, '=')) {
            std::string keyword = keyValuePair;
            bool overrideValue;
            iss >> std::boolalpha >> overrideValue;
            DebugLog("Received Keyword: " + keyword);
            DebugLog("Stream Content: " + payload);
            DebugLog("Parsed overrideValue: " + std::to_string(overrideValue));
            // Handle "OVERRIDE" data type based on keywords
            if (keyword == "joystick") {
                //DebugLog("Inside the joystick block");

                XPLMSetDatai(gRollOvd, overrideValue ? 1 : 0);
                XPLMSetDatai(gPitchOvd, overrideValue ? 1 : 0);

                overrideJoystick = overrideValue;
            }
            else if (keyword == "pedals") {
                XPLMSetDatai(gYawOvd, overrideValue ? 1 : 0);
                overridePedals = overrideValue;

            }
            else if (keyword == "collective") {
                XPLMSetDatai(gCollectiveOvd, overrideValue ? 1 : 0);
                overrideCollective = overrideValue;
            }
            else {
                // Unknown or unsupported keyword
                // Handle accordingly or log a warning
            }
        }
    }
    else if (dataType == "SUBSCRIBE") {
        // Example payload format: "dataref=sim/flightmodel/position/latitude,type=float,tag=Latitude,precision=6,conversion=0.51444"
        std::istringstream iss(payload);
        std::string key, value;
        std::map<std::string, std::string> parameters;

        // Parse key-value pairs (dataref, type, tag, precision, conversion)
        while (std::getline(iss, key, '=')) {
            std::getline(iss, value, ',');
            parameters[key] = value;
        }

        // Extract mandatory parameters
        std::string datarefStr = parameters["dataref"];
        std::string typeStr = parameters["type"];
        std::string tagStr = parameters["tag"];

        // Extract optional parameters with default values
        int precision = parameters.find("precision") != parameters.end() ? std::stoi(parameters["precision"]) : 3;
        float conversionFactor = parameters.find("conversion") != parameters.end() ? std::stof(parameters["conversion"]) : 1.0f;

        // Register the dataref with the provided or default precision and conversion factor
        RegisterDataRef(datarefStr, tagStr, typeStr, precision, conversionFactor);
    }
    else {
        DebugLog("Unknown Packet: " + payload);
        // Unknown or unsupported data type
        // Handle accordingly or log a warning
    }
}

void ReceiveData() {
    char buffer[1024];
    int recvlen;
    struct sockaddr_in senderAddr;
    int senderAddrSize = sizeof(senderAddr);

    recvlen = recvfrom(udpSocket_rx, buffer, sizeof(buffer), 0, (struct sockaddr*)&senderAddr, &senderAddrSize);
    if (recvlen > 0) {
        // Process the received message
        buffer[recvlen] = 0; // Null-terminate the received data

        // Parse the received data for data type and payload
        std::istringstream iss(buffer);
        std::string dataType;
        std::getline(iss, dataType, ':');  // Extract data type
        std::string payload;
        std::getline(iss, payload);  // Extract payload

        {
            std::lock_guard<std::mutex> lock(axisDataMutex);

            // Call the processing function with the parsed data
            ProcessReceivedData(dataType, payload);

            //DebugLog("Received Data - Type: " + dataType + ", Payload: " + payload);
        }
    }
}

void ReceiveThread() {
    while (!gTerminateReceiveThread) {
        ReceiveData();
        //std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}

void SendAxisPosition() {
    std::lock_guard<std::mutex> lock(axisDataMutex);
    if (overrideJoystick) {
        float jx = axisDataMap["jx"];
        float jy = axisDataMap["jy"];
 
        XPLMSetDataf(gRollRatio, jx);
        XPLMSetDataf(gPitchRatio, jy);
        //DebugLog("Send Axis: x=" + FloatToString(jx, 4) + ", y=" + FloatToString(jy, 4));
    }
    if (overridePedals) {
        float px = axisDataMap["px"];
 
        XPLMSetDataf(gYawRatio, px);
    }
    if (overrideCollective) {
        float cy = axisDataMap["cy"];
        XPLMSetDataf(gCollectiveRatio, cy);
    }
}

bool IsXPlane12OrNewer() {
    // Get the X-Plane version as an integer
    static XPLMDataRef gXplaneVers = XPLMFindDataRef("sim/version/xplane_internal_version");
    int XPVersion = XPLMGetDatai(gXplaneVers);

    // Convert the version to a string
    std::string versionString = std::to_string(XPVersion);

    // Extract the first two characters
    std::string firstTwoDigits = versionString.substr(0, 2);

    // Check if the first two digits are '12'
    return firstTwoDigits == "12";
}



PLUGIN_API int XPluginStart(char* outName, char* outSig, char* outDesc)
{
    if (DEBUG) {
        InitializeDebugLog();
    }

    strcpy(outName, "FSFFB-XPP");
    strcpy(outSig, "vpforce.fsffb.xpplugin");
    strcpy(outDesc, "Collect and send Telemetry for FFB processing");

    if (IsXPlane12OrNewer()) {
        gAircraftDescr = XPLMFindDataRef("sim/aircraft/view/acf_ui_name");                   // string bytes[250]
    }
    else {
        gAircraftDescr = XPLMFindDataRef("sim/aircraft/view/acf_descrip");                   // string bytes[250]
    }

    /* Find the data refs we want to record. */

    // Initialize Winsock
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0)
    {
        XPLMDebugString("Failed to initialize Winsock\n");
        return 0;
    }

    // Create a UDP socket
    udpSocket_tx = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);

    if (udpSocket_tx == INVALID_SOCKET)
    {
        XPLMDebugString("Failed to create UDP socket\n");
        WSACleanup();
        return 0;
    }

    // Set up server address information
    memset(&serverAddr_tx, 0, sizeof(serverAddr_tx));
    serverAddr_tx.sin_family = AF_INET;
    serverAddr_tx.sin_port = htons(34390); // Set the desired port number
    serverAddr_tx.sin_addr.s_addr = inet_addr("127.255.255.255"); // Send to localhost (127.0.0.1)


    udpSocket_rx = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);

    if (udpSocket_rx == INVALID_SOCKET)
    {
        XPLMDebugString("Failed to create receive UDP socket\n");
        WSACleanup();
        return 0;
    }

    // Set up server address information for the receive socket
    memset(&serverAddr_rx, 0, sizeof(serverAddr_rx));
    serverAddr_rx.sin_family = AF_INET;
    serverAddr_rx.sin_port = htons(34391);  // Set the desired port number for receiving
    serverAddr_rx.sin_addr.s_addr = inet_addr("127.0.0.1");
    bind(udpSocket_rx, (struct sockaddr*)&serverAddr_rx, sizeof(serverAddr_rx));


    /* Register our callback for once a second.  Positive intervals
     * are in seconds, negative are the negative of sim frames.  Zero
     * registers but does not schedule a callback for time. */
    XPLMRegisterFlightLoopCallback(
        MyFlightLoopCallback, /* Callback */
        -1,                  /* Interval */
        NULL);                /* refcon not used. */

    std::thread receiveThread(ReceiveThread);
    receiveThread.detach();  // Detach the thread to allow it to run independently

    //XPLMSetDatai(gRollOvd, 1);
    //XPLMSetDatai(gPitchOvd, 1);
    return 1;
}

PLUGIN_API void XPluginStop(void)
{
    /* Unregister the callback */
    XPLMUnregisterFlightLoopCallback(MyFlightLoopCallback, NULL);

    gTerminateReceiveThread = true;

    // Close the UDP socket
    closesocket(udpSocket_tx);
    closesocket(udpSocket_rx);
    WSACleanup();
}

PLUGIN_API void XPluginDisable(void)
{
    /* do any clean up here */
}

PLUGIN_API int XPluginEnable(void)
{
    return 1;
}

PLUGIN_API void XPluginReceiveMessage(XPLMPluginID inFromWho, int inMessage, void* inParam)
{

}

float MyFlightLoopCallback(float inElapsedSinceLastCall, float inElapsedTimeSinceLastFlightLoop, int inCounter, void* inRefcon)
{
    SendAxisPosition();

    // Collect telemetry data
    CollectTelemetryData();

    // Format and send telemetry data
    if (!simPaused) {
        FormatAndSendTelemetryData();
    }



    // Return -1 to indicate we want to be called on next opportunity
    return -1;
}
