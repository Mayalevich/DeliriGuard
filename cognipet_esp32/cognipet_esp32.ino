/*
 * CogniPet: Hospital-Induced Delirium Detection Device
 * 
 * Hardware:
 * - ESP32-S3
 * - Grove LCD RGB Backlight (16x2 character LCD)
 * - 3 buttons (BTN1, BTN2, BTN3)
 * - LED for feedback
 * 
 * Features:
 * - Cognitive assessment tests (orientation, memory, attention, executive function)
 * - Virtual pet interactions (feed, play, clean)
 * - LED feedback for correct/incorrect answers
 * - RGB backlight color changes for mood/status
 * - BLE data transmission to backend
 * 
 * Libraries Required (install via Arduino Library Manager):
 * - ESP32 BLE Arduino (built-in with ESP32 board support)
 * - Preferences (built-in with ESP32)
 * 
 * Setup Instructions:
 * 1. Install ESP32 board support in Arduino IDE:
 *    - File > Preferences > Additional Board Manager URLs
 *    - Add: https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
 *    - Tools > Board > Boards Manager > Search "ESP32" > Install
 * 2. Select board: Tools > Board > ESP32 Arduino > ESP32S3 Dev Module
 * 3. Select port: Tools > Port > (your ESP32-S3 port)
 * 4. Upload this sketch
 */

#include <Wire.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <Preferences.h>
#include <WiFi.h>
#include <time.h>

// ==== Pin Definitions ====
// ESP32-S3 I2C pins - try these common configurations:
// Option 1: GPIO 8/9 (common for ESP32-S3)
// Option 2: GPIO 21/22 (Arduino default, but may not work on S3)
// Option 3: GPIO 1/2 (your current setting)
#define SDA_PIN   8   // Changed from 1 - try GPIO 8
#define SCL_PIN   9   // Changed from 2 - try GPIO 9
#define LED_PIN   11
#define BTN1_PIN  12  // Button A / Feed
#define BTN2_PIN  13  // Button B / Play
#define BTN3_PIN  14  // Button C / Clean / Select

// ==== Grove LCD RGB Backlight Addresses ====
#define LCD_ADDR  0x3E   // text controller
#define RGB_ADDR  0x62   // backlight (PCA9633)

// ==== BLE Configuration ====
#define BLE_DEVICE_NAME "CogniPet"
#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define ASSESSMENT_UUID     "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define INTERACTION_UUID    "1c95d5e3-d8f7-413a-bf3d-7a2e5d7be87e"

#define WIFI_CONNECT_TIMEOUT_MS 15000
#define TIME_RESYNC_INTERVAL_MS (6UL * 60UL * 60UL * 1000UL)  // every 6 hours
#define TIME_CHECK_INTERVAL_MS 60000

const char* WIFI_SSID = "Huawei mate60 5G";
const char* WIFI_PASSWORD = "123456789";
const char* TZ_INFO = "EST5EDT,M3.2.0,M11.1.0";
const char* NTP_PRIMARY = "ca.pool.ntp.org";
const char* NTP_SECONDARY = "pool.ntp.org";
const char* NTP_TERTIARY = "time.nist.gov";

bool wifiConnectedFlag = false;
bool timeSynced = false;
unsigned long lastTimeSyncAttempt = 0;
unsigned long lastTimeMaintenance = 0;
bool wifiEverConnected = false;
unsigned long lastWifiSuccessMs = 0;
unsigned long lastNtpSyncMs = 0;
char lastWifiIp[20] = "--";

const char* DAY_SHORT[7] = {"Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"};
const char* PERIOD_SHORT[3] = {"AM", "PM", "EVE"};

// ==== Device States ====
enum DeviceState {
  STATE_FIRST_BOOT,
  STATE_ASSESSMENT,
  STATE_PET_NORMAL,
  STATE_PET_MENU,
  STATE_PET_STATS,
  STATE_PET_MOOD,
  STATE_PET_GAME,
  STATE_DIAGNOSTICS,
  STATE_REMINDER,
  STATE_HISTORY_VIEWER
};

enum PetMenu {
  MENU_MAIN,
  MENU_STATS,
  MENU_MOOD,
  MENU_GAMES
};

enum AssessmentPhase {
  PHASE_ORIENTATION,
  PHASE_MEMORY,
  PHASE_ATTENTION,
  PHASE_EXECUTIVE,
  PHASE_COMPLETE
};

// ==== Data Structures ====
struct AssessmentResult {
  uint32_t timestamp;
  uint8_t orientation_score;    // 0-3
  uint8_t memory_score;         // 0-3
  uint8_t attention_score;      // 0-3
  uint8_t executive_score;      // 0-3
  uint8_t total_score;          // 0-12
  uint16_t avg_response_time_ms;
  uint8_t alert_level;          // 0=green, 1=yellow, 2=orange, 3=red
};

struct PetState {
  uint8_t happiness;   // 0-100
  uint8_t hunger;      // 0-100 (100 = very hungry)
  uint8_t cleanliness; // 0-100
  unsigned long lastFed;
  unsigned long lastPlayed;
  unsigned long lastCleaned;
};

struct InteractionLog {
  uint32_t timestamp;
  uint8_t interaction_type;  // 0=feed, 1=play, 2=clean, 3=game
  uint16_t response_time_ms;
  uint8_t success;           // 1=success, 0=fail
  int8_t mood_selected;      // -1 if not mood check
};

// ==== Adaptive Difficulty System ====
struct DifficultyLevel {
  uint8_t memory_sequence_length;    // 2-5 (default 3)
  uint16_t memory_display_time_ms;   // 400-1200 (default 800)
  uint8_t attention_trials;          // 3-7 (default 5)
  uint16_t attention_min_delay_ms;   // 1000-3000 (default 2000)
  uint16_t attention_max_delay_ms;   // 3000-8000 (default 5000)
  uint8_t executive_sequence_length; // 3-5 (default 4)
};

// ==== Assessment Scheduling ====
struct ScheduleConfig {
  uint8_t interval_hours;      // 4, 6, or 8 hours
  unsigned long lastAssessmentTime; // millis() timestamp
  bool remindersEnabled;       // true if reminders should show
  bool assessmentOverdue;      // true if past due
};

// ==== Data Persistence ====
struct StoredAssessment {
  uint32_t timestamp;          // Unix epoch or millis()
  uint8_t orientation_score;
  uint8_t memory_score;
  uint8_t attention_score;
  uint8_t executive_score;
  uint8_t total_score;
  uint16_t avg_response_time_ms;
  uint8_t alert_level;
  bool synced;                 // true if successfully sent via BLE
};

struct PendingInteraction {
  uint32_t timestamp;
  uint8_t interaction_type;
  uint16_t response_time_ms;
  uint8_t success;
  int8_t mood_selected;
  bool synced;
};

// ==== Global Variables ====
DeviceState currentState = STATE_FIRST_BOOT;
AssessmentPhase assessmentPhase = PHASE_ORIENTATION;
AssessmentResult lastAssessment;
PetState pet;
Preferences prefs;

// BLE
BLEServer* pServer = nullptr;
BLECharacteristic* pAssessmentChar = nullptr;
BLECharacteristic* pInteractionChar = nullptr;
bool deviceConnected = false;
bool oldDeviceConnected = false;

// Button state
bool btn1Pressed = false;
bool btn2Pressed = false;
bool btn3Pressed = false;
bool btn1Last = false;
bool btn2Last = false;
bool btn3Last = false;
unsigned long btn1PressTime = 0;
unsigned long btn2PressTime = 0;
unsigned long btn3PressTime = 0;

// Assessment state
uint8_t currentQuestion = 0;
uint8_t selectedAnswer = 0;
unsigned long questionStartTime = 0;
uint16_t totalResponseTime = 0;
uint8_t responseCount = 0;

// Memory test (support up to 5 items for adaptive difficulty)
uint8_t memorySequence[5];
uint8_t userSequence[5];
uint8_t memoryStep = 0;

// Attention test
uint8_t attentionTrials = 0;
uint8_t attentionCorrect = 0;
unsigned long attentionStartTime = 0;
bool waitingForAttention = false;

// Executive function test
uint8_t sequenceStep = 0;
uint8_t correctSequence[4] = {1, 0, 2, 3}; // Dinner, Shower, Brush, Sleep

// Interaction queue
InteractionLog interactionQueue[20];
uint8_t queueHead = 0;
uint8_t queueTail = 0;

// RGB state tracking
uint8_t lastR = 255, lastG = 255, lastB = 255; // Track last color to avoid unnecessary updates

// Menu state
PetMenu currentMenu = MENU_MAIN;
uint8_t menuSelection = 0;
unsigned long lastMenuChange = 0;
uint8_t diagnosticsPage = 0;
unsigned long lastDiagnosticsRefresh = 0;
bool diagnosticsActive = false;
const uint8_t DIAGNOSTIC_PAGE_COUNT = 4;

// Assessment scheduling
ScheduleConfig schedule;
unsigned long lastReminderCheck = 0;
unsigned long reminderBlinkTime = 0;
bool reminderBlinkState = false;
bool overdueReminderShown = false;  // Track if overdue reminder has been shown
unsigned long reminderCooldownUntil = 0;  // Cooldown period after skip/postpone
const unsigned long REMINDER_CHECK_INTERVAL_MS = 60000; // Check every minute
const unsigned long REMINDER_BLINK_INTERVAL_MS = 500;   // Blink every 500ms
const unsigned long REMINDER_COOLDOWN_MS = 300000;      // 5 minute cooldown after skip/postpone

// Adaptive difficulty
DifficultyLevel currentDifficulty;
uint8_t recentScores[5];  // Last 5 total scores for trend analysis
uint8_t recentScoreIndex = 0;
bool difficultyInitialized = false;

// Data persistence
StoredAssessment assessmentHistory[50];  // Store last 50 assessments
uint8_t assessmentHistoryCount = 0;
uint8_t assessmentHistoryIndex = 0;  // Circular buffer index
PendingInteraction pendingInteractions[30];  // Queue for interactions when BLE is down
uint8_t pendingInteractionCount = 0;
uint8_t pendingInteractionHead = 0;
uint8_t pendingInteractionTail = 0;
unsigned long lastRetryAttempt = 0;
const unsigned long RETRY_INTERVAL_MS = 5000;  // Retry every 5 seconds when BLE reconnects

// History viewer
uint8_t historyViewerIndex = 0;  // Currently viewing assessment index
bool historyViewerActive = false;

// ==== Timekeeping Helpers ====
bool hasWiFiCredentials() {
  return strlen(WIFI_SSID) > 0 &&
         strcmp(WIFI_SSID, "YOUR_WIFI") != 0 &&
         strlen(WIFI_PASSWORD) > 0 &&
         strcmp(WIFI_PASSWORD, "YOUR_PASSWORD") != 0;
}

bool connectToWiFi() {
  if (!hasWiFiCredentials()) {
    Serial.println("WiFi credentials not configured; skipping real-time sync.");
    return false;
  }

  if (WiFi.status() == WL_CONNECTED) {
    wifiConnectedFlag = true;
    return true;
  }

  Serial.print("Connecting to WiFi");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_CONNECT_TIMEOUT_MS) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    wifiConnectedFlag = true;
    wifiEverConnected = true;
    lastWifiSuccessMs = millis();
    IPAddress ip = WiFi.localIP();
    Serial.print("WiFi connected, IP: ");
    Serial.println(ip);
    snprintf(lastWifiIp, sizeof(lastWifiIp), "%u.%u.%u.%u", ip[0], ip[1], ip[2], ip[3]);
    return true;
  }

  wifiConnectedFlag = false;
  snprintf(lastWifiIp, sizeof(lastWifiIp), "--");
  Serial.println("WiFi connection failed.");
  return false;
}

void shutdownWiFi() {
  if (WiFi.getMode() != WIFI_OFF) {
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
  }
  wifiConnectedFlag = false;
}

bool syncTimeFromNTP() {
  lastTimeSyncAttempt = millis();
  if (!connectToWiFi()) {
    timeSynced = false;
    return false;
  }

  Serial.println("Syncing time via NTP...");
  configTzTime(TZ_INFO, NTP_PRIMARY, NTP_SECONDARY, NTP_TERTIARY);

  struct tm timeinfo;
  bool success = false;
  for (int i = 0; i < 10; i++) {
    if (getLocalTime(&timeinfo, 1000)) {
      success = true;
      break;
    }
    delay(250);
  }

  if (success) {
    timeSynced = true;
    lastNtpSyncMs = millis();
    char buf[32];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M", &timeinfo);
    Serial.print("Time sync OK: ");
    Serial.println(buf);
  } else {
    Serial.println("Failed to obtain time from NTP.");
    timeSynced = false;
  }

  shutdownWiFi();  // conserve power once time is fetched
  return success;
}

void ensureTimeSync() {
  if (!hasWiFiCredentials()) {
    timeSynced = false;
    return;
  }

  if (!timeSynced) {
    syncTimeFromNTP();
    return;
  }

  if (millis() - lastTimeSyncAttempt > TIME_RESYNC_INTERVAL_MS) {
    syncTimeFromNTP();
  }
}

bool getLocalTimeSafe(struct tm* info) {
  if (!timeSynced) {
    ensureTimeSync();
    if (!timeSynced) {
      return false;
    }
  }

  if (!getLocalTime(info, 1000)) {
    Serial.println("RTC read failed; will attempt to resync.");
    timeSynced = false;
    return false;
  }

  return true;
}

uint32_t getCurrentTimestamp() {
  if (timeSynced) {
    time_t now = time(nullptr);
    if (now > 0) {
      return static_cast<uint32_t>(now);
    }
  }
  return millis();
}

void maintainTimeService() {
  if (!hasWiFiCredentials()) {
    return;
  }

  if (millis() - lastTimeMaintenance > TIME_CHECK_INTERVAL_MS) {
    ensureTimeSync();
    lastTimeMaintenance = millis();
  }
}

void initializeTimeService() {
  if (!hasWiFiCredentials()) {
    Serial.println("Skipping time sync (WiFi credentials not set).");
    return;
  }
  syncTimeFromNTP();
}

void rotateOptions(uint8_t* arr, uint8_t shift) {
  shift %= 3;
  while (shift--) {
    uint8_t tmp = arr[0];
    arr[0] = arr[1];
    arr[1] = arr[2];
    arr[2] = tmp;
  }
}

// ==== Assessment Scheduling Functions ====
void initializeSchedule() {
  prefs.begin("cognipet", true);
  schedule.interval_hours = prefs.getUChar("sched_interval", 6); // Default 6 hours
  schedule.lastAssessmentTime = prefs.getULong64("last_assess", 0);
  schedule.remindersEnabled = prefs.getBool("remind_en", true);
  prefs.end();
  
  // If no previous assessment, set to now (will trigger after interval)
  if (schedule.lastAssessmentTime == 0) {
    schedule.lastAssessmentTime = millis();
  }
  
  schedule.assessmentOverdue = false;
  Serial.print("Schedule initialized: interval=");
  Serial.print(schedule.interval_hours);
  Serial.print("h, last=");
  Serial.println(schedule.lastAssessmentTime);
}

void saveSchedule() {
  prefs.begin("cognipet", false);
  prefs.putUChar("sched_interval", schedule.interval_hours);
  prefs.putULong64("last_assess", schedule.lastAssessmentTime);
  prefs.putBool("remind_en", schedule.remindersEnabled);
  prefs.end();
}

void updateSchedule() {
  unsigned long now = millis();
  unsigned long intervalMs = schedule.interval_hours * 3600000UL; // Convert hours to ms
  unsigned long timeSinceLast = now - schedule.lastAssessmentTime;
  
  // Check if assessment is due
  if (timeSinceLast >= intervalMs) {
    // Only mark as overdue if we haven't shown the overdue reminder yet
    // This prevents overdue from accumulating - show it once, then treat as regular "due"
    if (!overdueReminderShown) {
      schedule.assessmentOverdue = true;
    } else {
      // Already showed overdue reminder once - treat as regular "due" (not overdue)
      schedule.assessmentOverdue = false;
    }
  } else {
    // Not due yet - reset flags
    schedule.assessmentOverdue = false;
    overdueReminderShown = false;  // Reset flag when not overdue
  }
}

bool isAssessmentDue() {
  updateSchedule();
  // Check if assessment is due (either overdue or just due)
  unsigned long now = millis();
  unsigned long intervalMs = schedule.interval_hours * 3600000UL;
  unsigned long timeSinceLast = now - schedule.lastAssessmentTime;
  bool isDue = timeSinceLast >= intervalMs;
  
  return isDue && schedule.remindersEnabled;
}

unsigned long getTimeUntilNextAssessment() {
  updateSchedule();
  unsigned long intervalMs = schedule.interval_hours * 3600000UL;
  unsigned long timeSinceLast = millis() - schedule.lastAssessmentTime;
  
  if (timeSinceLast >= intervalMs) {
    return 0; // Overdue
  }
  return intervalMs - timeSinceLast;
}

void markAssessmentComplete() {
  schedule.lastAssessmentTime = millis();
  schedule.assessmentOverdue = false;
  overdueReminderShown = false;  // Reset overdue reminder flag
  reminderCooldownUntil = 0;  // Reset cooldown so reminders can show again
  saveSchedule();
  Serial.println("Assessment marked complete, schedule updated");
}

void setScheduleInterval(uint8_t hours) {
  if (hours == 4 || hours == 6 || hours == 8) {
    schedule.interval_hours = hours;
    saveSchedule();
    Serial.print("Schedule interval set to ");
    Serial.print(hours);
    Serial.println(" hours");
  }
}

// ==== Adaptive Difficulty Functions ====
void initializeDifficulty() {
  if (difficultyInitialized) return;
  
  // Load difficulty from preferences
  prefs.begin("cognipet", true);
  currentDifficulty.memory_sequence_length = prefs.getUChar("diff_mem_len", 3);
  currentDifficulty.memory_display_time_ms = prefs.getUShort("diff_mem_time", 800);
  currentDifficulty.attention_trials = prefs.getUChar("diff_att_trials", 5);
  currentDifficulty.attention_min_delay_ms = prefs.getUShort("diff_att_min", 2000);
  currentDifficulty.attention_max_delay_ms = prefs.getUShort("diff_att_max", 5000);
  currentDifficulty.executive_sequence_length = prefs.getUChar("diff_exec_len", 4);
  prefs.end();
  
  // Initialize recent scores array
  for (int i = 0; i < 5; i++) {
    recentScores[i] = 6; // Neutral starting point
  }
  recentScoreIndex = 0;
  
  difficultyInitialized = true;
  Serial.println("Adaptive difficulty initialized");
}

void saveDifficulty() {
  prefs.begin("cognipet", false);
  prefs.putUChar("diff_mem_len", currentDifficulty.memory_sequence_length);
  prefs.putUShort("diff_mem_time", currentDifficulty.memory_display_time_ms);
  prefs.putUChar("diff_att_trials", currentDifficulty.attention_trials);
  prefs.putUShort("diff_att_min", currentDifficulty.attention_min_delay_ms);
  prefs.putUShort("diff_att_max", currentDifficulty.attention_max_delay_ms);
  prefs.putUChar("diff_exec_len", currentDifficulty.executive_sequence_length);
  prefs.end();
}

void addScoreToHistory(uint8_t totalScore) {
  recentScores[recentScoreIndex] = totalScore;
  recentScoreIndex = (recentScoreIndex + 1) % 5;
}

float getAverageRecentScore() {
  uint16_t sum = 0;
  for (int i = 0; i < 5; i++) {
    sum += recentScores[i];
  }
  return sum / 5.0f;
}

void adjustDifficultyBasedOnPerformance(uint8_t totalScore) {
  addScoreToHistory(totalScore);
  float avgScore = getAverageRecentScore();
  
  Serial.print("Adjusting difficulty: score=");
  Serial.print(totalScore);
  Serial.print(", avg=");
  Serial.println(avgScore);
  
  // Adjust memory test difficulty
  if (avgScore >= 9.0f) {
    // High performance: increase difficulty
    if (currentDifficulty.memory_sequence_length < 5) {
      currentDifficulty.memory_sequence_length++;
    }
    if (currentDifficulty.memory_display_time_ms > 400) {
      currentDifficulty.memory_display_time_ms -= 100;
    }
  } else if (avgScore <= 5.0f) {
    // Low performance: decrease difficulty
    if (currentDifficulty.memory_sequence_length > 2) {
      currentDifficulty.memory_sequence_length--;
    }
    if (currentDifficulty.memory_display_time_ms < 1200) {
      currentDifficulty.memory_display_time_ms += 100;
    }
  }
  
  // Adjust attention test difficulty
  if (avgScore >= 9.0f) {
    // Increase trials and delay range
    if (currentDifficulty.attention_trials < 7) {
      currentDifficulty.attention_trials++;
    }
    if (currentDifficulty.attention_min_delay_ms < 3000) {
      currentDifficulty.attention_min_delay_ms += 200;
    }
    if (currentDifficulty.attention_max_delay_ms < 8000) {
      currentDifficulty.attention_max_delay_ms += 300;
    }
  } else if (avgScore <= 5.0f) {
    // Decrease trials and delay range
    if (currentDifficulty.attention_trials > 3) {
      currentDifficulty.attention_trials--;
    }
    if (currentDifficulty.attention_min_delay_ms > 1000) {
      currentDifficulty.attention_min_delay_ms -= 200;
    }
    if (currentDifficulty.attention_max_delay_ms > 3000) {
      currentDifficulty.attention_max_delay_ms -= 300;
    }
  }
  
  // Adjust executive function test difficulty
  if (avgScore >= 9.0f) {
    if (currentDifficulty.executive_sequence_length < 5) {
      currentDifficulty.executive_sequence_length++;
    }
  } else if (avgScore <= 5.0f) {
    if (currentDifficulty.executive_sequence_length > 3) {
      currentDifficulty.executive_sequence_length--;
    }
  }
  
  // Clamp values to valid ranges
  currentDifficulty.memory_sequence_length = constrain(currentDifficulty.memory_sequence_length, 2, 5);
  currentDifficulty.memory_display_time_ms = constrain(currentDifficulty.memory_display_time_ms, 400, 1200);
  currentDifficulty.attention_trials = constrain(currentDifficulty.attention_trials, 3, 7);
  currentDifficulty.attention_min_delay_ms = constrain(currentDifficulty.attention_min_delay_ms, 1000, 3000);
  currentDifficulty.attention_max_delay_ms = constrain(currentDifficulty.attention_max_delay_ms, 3000, 8000);
  currentDifficulty.executive_sequence_length = constrain(currentDifficulty.executive_sequence_length, 3, 5);
  
  saveDifficulty();
  
  Serial.print("New difficulty: mem_len=");
  Serial.print(currentDifficulty.memory_sequence_length);
  Serial.print(", mem_time=");
  Serial.print(currentDifficulty.memory_display_time_ms);
  Serial.print(", att_trials=");
  Serial.print(currentDifficulty.attention_trials);
  Serial.print(", exec_len=");
  Serial.println(currentDifficulty.executive_sequence_length);
}

// ==== Data Persistence Functions ====
void storeAssessmentToHistory(const AssessmentResult& assessment) {
  StoredAssessment stored;
  stored.timestamp = assessment.timestamp;
  stored.orientation_score = assessment.orientation_score;
  stored.memory_score = assessment.memory_score;
  stored.attention_score = assessment.attention_score;
  stored.executive_score = assessment.executive_score;
  stored.total_score = assessment.total_score;
  stored.avg_response_time_ms = assessment.avg_response_time_ms;
  stored.alert_level = assessment.alert_level;
  stored.synced = deviceConnected;  // Mark as synced if BLE is connected
  
  // Use circular buffer
  assessmentHistory[assessmentHistoryIndex] = stored;
  assessmentHistoryIndex = (assessmentHistoryIndex + 1) % 50;
  
  if (assessmentHistoryCount < 50) {
    assessmentHistoryCount++;
  }
  
  // Save to NVS (store last 10 in NVS for persistence across reboots)
  prefs.begin("cognipet", false);
  uint8_t nvsIndex = assessmentHistoryIndex >= 10 ? (assessmentHistoryIndex - 10) % 10 : 0;
  char key[20];
  snprintf(key, sizeof(key), "assess_%d_ts", nvsIndex);
  prefs.putULong64(key, stored.timestamp);
  snprintf(key, sizeof(key), "assess_%d_score", nvsIndex);
  prefs.putUChar(key, stored.total_score);
  snprintf(key, sizeof(key), "assess_%d_alert", nvsIndex);
  prefs.putUChar(key, stored.alert_level);
  prefs.end();
  
  Serial.print("Stored assessment to history (index ");
  Serial.print(assessmentHistoryIndex);
  Serial.print(", count ");
  Serial.print(assessmentHistoryCount);
  Serial.println(")");
}

void loadAssessmentHistory() {
  prefs.begin("cognipet", true);
  assessmentHistoryCount = 0;
  
  // Load last 10 assessments from NVS
  for (uint8_t i = 0; i < 10; i++) {
    char key[20];
    snprintf(key, sizeof(key), "assess_%d_ts", i);
    uint64_t ts = prefs.getULong64(key, 0);
    
    if (ts == 0) break;  // No more stored assessments
    
    StoredAssessment stored;
    stored.timestamp = (uint32_t)ts;
    snprintf(key, sizeof(key), "assess_%d_score", i);
    stored.total_score = prefs.getUChar(key, 0);
    snprintf(key, sizeof(key), "assess_%d_alert", i);
    stored.alert_level = prefs.getUChar(key, 0);
    stored.synced = true;  // Assume synced if stored
    
    assessmentHistory[assessmentHistoryCount] = stored;
    assessmentHistoryCount++;
  }
  
  assessmentHistoryIndex = assessmentHistoryCount % 50;
  prefs.end();
  
  Serial.print("Loaded ");
  Serial.print(assessmentHistoryCount);
  Serial.println(" assessments from NVS");
}

void queueInteraction(const InteractionLog& interaction) {
  if (pendingInteractionCount >= 30) {
    Serial.println("WARNING: Interaction queue full, dropping oldest");
    pendingInteractionHead = (pendingInteractionHead + 1) % 30;
    pendingInteractionCount--;
  }
  
  PendingInteraction pending;
  pending.timestamp = interaction.timestamp;
  pending.interaction_type = interaction.interaction_type;
  pending.response_time_ms = interaction.response_time_ms;
  pending.success = interaction.success;
  pending.mood_selected = interaction.mood_selected;
  pending.synced = false;
  
  pendingInteractions[pendingInteractionTail] = pending;
  pendingInteractionTail = (pendingInteractionTail + 1) % 30;
  pendingInteractionCount++;
  
  Serial.print("Queued interaction (count: ");
  Serial.print(pendingInteractionCount);
  Serial.println(")");
}

void retryPendingData() {
  if (!deviceConnected || pendingInteractionCount == 0) {
    return;
  }
  
  unsigned long now = millis();
  if (now - lastRetryAttempt < RETRY_INTERVAL_MS) {
    return;
  }
  lastRetryAttempt = now;
  
  // Retry sending pending interactions
  uint8_t retried = 0;
  while (pendingInteractionCount > 0 && deviceConnected && retried < 5) {
    PendingInteraction& pending = pendingInteractions[pendingInteractionHead];
    
    if (!pending.synced) {
      // Reconstruct InteractionLog
      InteractionLog log;
      log.timestamp = pending.timestamp;
      log.interaction_type = pending.interaction_type;
      log.response_time_ms = pending.response_time_ms;
      log.success = pending.success;
      log.mood_selected = pending.mood_selected;
      
      // Try to send
      if (deviceConnected && pInteractionChar) {
        uint8_t data[sizeof(InteractionLog)];
        memcpy(data, &log, sizeof(InteractionLog));
        pInteractionChar->setValue(data, sizeof(InteractionLog));
        pInteractionChar->notify();
        pending.synced = true;
        Serial.print("Retried and sent pending interaction (timestamp: ");
        Serial.print(pending.timestamp);
        Serial.println(")");
      } else {
        Serial.println("Failed to send pending interaction, will retry later");
        break;  // Stop retrying if send fails
      }
    }
    
    // Remove from queue if synced
    if (pending.synced) {
      pendingInteractionHead = (pendingInteractionHead + 1) % 30;
      pendingInteractionCount--;
      retried++;
    }
  }
  
  // Retry unsynced assessments (check last 10)
  uint8_t startIdx = assessmentHistoryCount >= 10 ? (assessmentHistoryIndex - 10 + 50) % 50 : 0;
  uint8_t checkCount = assessmentHistoryCount < 10 ? assessmentHistoryCount : 10;
  for (uint8_t i = 0; i < checkCount; i++) {
    uint8_t idx = (startIdx + i) % 50;
    StoredAssessment& stored = assessmentHistory[idx];
    
    if (!stored.synced && deviceConnected) {
      // Temporarily set global lastAssessment and send
      AssessmentResult saved = lastAssessment;
      lastAssessment.timestamp = stored.timestamp;
      lastAssessment.orientation_score = stored.orientation_score;
      lastAssessment.memory_score = stored.memory_score;
      lastAssessment.attention_score = stored.attention_score;
      lastAssessment.executive_score = stored.executive_score;
      lastAssessment.total_score = stored.total_score;
      lastAssessment.avg_response_time_ms = stored.avg_response_time_ms;
      lastAssessment.alert_level = stored.alert_level;
      
      if (deviceConnected && pAssessmentChar) {
        uint8_t data[32];
        memcpy(data, &lastAssessment, sizeof(AssessmentResult));
        pAssessmentChar->setValue(data, sizeof(AssessmentResult));
        pAssessmentChar->notify();
        stored.synced = true;
        Serial.print("Retried and sent pending assessment (timestamp: ");
        Serial.print(stored.timestamp);
        Serial.println(")");
      }
      
      lastAssessment = saved;  // Restore
    }
  }
}

void exportHistoryToSerial() {
  Serial.println("=== ASSESSMENT HISTORY EXPORT ===");
  Serial.println("Format: timestamp,orientation,memory,attention,executive,total,avg_time_ms,alert_level,synced");
  
  if (assessmentHistoryCount == 0) {
    Serial.println("No assessment history available");
    return;
  }
  
  // Export in chronological order (oldest first)
  uint8_t startIdx = assessmentHistoryCount >= 50 ? assessmentHistoryIndex : 0;
  uint8_t count = assessmentHistoryCount;
  
  for (uint8_t i = 0; i < count; i++) {
    uint8_t idx = (startIdx + i) % 50;
    StoredAssessment& stored = assessmentHistory[idx];
    
    Serial.print(stored.timestamp);
    Serial.print(",");
    Serial.print(stored.orientation_score);
    Serial.print(",");
    Serial.print(stored.memory_score);
    Serial.print(",");
    Serial.print(stored.attention_score);
    Serial.print(",");
    Serial.print(stored.executive_score);
    Serial.print(",");
    Serial.print(stored.total_score);
    Serial.print(",");
    Serial.print(stored.avg_response_time_ms);
    Serial.print(",");
    Serial.print(stored.alert_level);
    Serial.print(",");
    Serial.println(stored.synced ? "1" : "0");
  }
  
  Serial.println("=== END EXPORT ===");
  Serial.print("Total assessments: ");
  Serial.println(assessmentHistoryCount);
  Serial.print("Pending interactions: ");
  Serial.println(pendingInteractionCount);
}

// ==== History Viewer Functions ====
void drawHistoryViewer() {
  if (assessmentHistoryCount == 0) {
    lcdClear();
    lcdSetCursor(0, 0);
    lcdPrint("No history yet");
    lcdSetCursor(0, 1);
    lcdPrint("Complete tests!");
    return;
  }
  
  // Get the assessment to display (most recent first)
  uint8_t displayCount = assessmentHistoryCount < 10 ? assessmentHistoryCount : 10;
  uint8_t idx = (assessmentHistoryIndex - 1 - historyViewerIndex + 50) % 50;
  StoredAssessment& stored = assessmentHistory[idx];
  
  // Line 1: Score and alert level
  char line1[17];
  snprintf(line1, sizeof(line1), "#%d Score:%d/12", historyViewerIndex + 1, stored.total_score);
  lcdSetCursor(0, 0);
  lcdPrintPadded(line1, 16);
  
  // Line 2: Breakdown or trend
  char line2[17];
  if (historyViewerIndex < displayCount - 1) {
    // Show trend arrow
    uint8_t prevIdx = (assessmentHistoryIndex - 1 - historyViewerIndex - 1 + 50) % 50;
    StoredAssessment& prev = assessmentHistory[prevIdx];
    char trend = '=';
    if (stored.total_score > prev.total_score) trend = '^';
    else if (stored.total_score < prev.total_score) trend = 'v';
    
    snprintf(line2, sizeof(line2), "%c O:%d M:%d A:%d", trend,
             stored.orientation_score, stored.memory_score, stored.attention_score);
  } else {
    // Show breakdown
    snprintf(line2, sizeof(line2), "O:%d M:%d A:%d E:%d",
             stored.orientation_score, stored.memory_score,
             stored.attention_score, stored.executive_score);
  }
  lcdSetCursor(0, 1);
  lcdPrintPadded(line2, 16);
}

void drawHistoryGraph() {
  if (assessmentHistoryCount < 2) {
    lcdClear();
    lcdSetCursor(0, 0);
    lcdPrint("Need 2+ tests");
    lcdSetCursor(0, 1);
    lcdPrint("for graph");
    return;
  }
  
  // First, flash the title for 1 second
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Trend Graph:");
  lcdSetCursor(0, 1);
  lcdPrint("Loading...");
  delay(1000);
  
  // Now show the graph using both lines (32 characters total)
  // Show last 16 assessments (8 per line)
  uint8_t displayCount = assessmentHistoryCount < 16 ? assessmentHistoryCount : 16;
  lcdClear();
  
  // Line 1: Show first 8 assessments (oldest to newest of the 16)
  for (uint8_t i = 0; i < 8 && i < displayCount; i++) {
    uint8_t idx = (assessmentHistoryIndex - 1 - (displayCount - 1 - i) + 50) % 50;
    StoredAssessment& stored = assessmentHistory[idx];
    
    // Map score (0-12) to visual representation
    char barChar = ' ';
    if (stored.total_score >= 10) barChar = '|';  // High score (10-12)
    else if (stored.total_score >= 7) barChar = '=';  // Medium-high (7-9)
    else if (stored.total_score >= 4) barChar = '-';  // Medium-low (4-6)
    else barChar = '.';  // Low score (0-3)
    
    lcdSetCursor(i, 0);
    lcdData(barChar);
  }
  
  // Line 2: Show next 8 assessments (newest 8 of the 16)
  for (uint8_t i = 8; i < displayCount && i < 16; i++) {
    uint8_t idx = (assessmentHistoryIndex - 1 - (displayCount - 1 - i) + 50) % 50;
    StoredAssessment& stored = assessmentHistory[idx];
    
    // Map score (0-12) to visual representation
    char barChar = ' ';
    if (stored.total_score >= 10) barChar = '|';  // High score
    else if (stored.total_score >= 7) barChar = '=';  // Medium-high
    else if (stored.total_score >= 4) barChar = '-';  // Medium-low
    else barChar = '.';  // Low score
    
    lcdSetCursor(i - 8, 1);
    lcdData(barChar);
  }
  
  // If we have less than 8 assessments, fill remaining with spaces
  if (displayCount < 8) {
    for (uint8_t i = displayCount; i < 8; i++) {
      lcdSetCursor(i, 0);
      lcdData(' ');
    }
  }
}

void handleHistoryViewer() {
  static unsigned long lastScrollTime = 0;
  const unsigned long SCROLL_DELAY_MS = 300;
  
  updateButtons();
  
  uint8_t maxIndex = (assessmentHistoryCount < 10 ? assessmentHistoryCount : 10) - 1;
  
  // Button 1: Previous assessment (older)
  if (buttonPressed(1)) {
    if (historyViewerIndex < maxIndex) {
      historyViewerIndex++;
    }
    lastScrollTime = millis();
  }
  
  // Button 2: Next assessment (newer) or toggle graph view
  if (buttonPressed(2)) {
    if (historyViewerIndex > 0) {
      historyViewerIndex--;
    } else {
      // Toggle to graph view when at most recent
      static bool showGraph = false;
      showGraph = !showGraph;
      if (showGraph) {
        drawHistoryGraph();  // This includes 1 second title flash + graph display
        delay(4000);  // Show graph for 4 seconds (title already took 1 second)
        return;
      }
    }
    lastScrollTime = millis();
  }
  
  // Button 3: Exit
  if (buttonPressed(3)) {
    historyViewerActive = false;
    historyViewerIndex = 0;
    currentState = STATE_PET_NORMAL;
    return;
  }
  
  // Auto-scroll every 5 seconds
  if (millis() - lastScrollTime > 5000 && historyViewerIndex < maxIndex) {
    historyViewerIndex++;
    lastScrollTime = millis();
  }
  
  drawHistoryViewer();
}

// ==== LCD Functions ====
void lcdCommand(uint8_t cmd) {
  Wire.beginTransmission(LCD_ADDR);
  Wire.write((uint8_t)0x80);  // Command mode
  Wire.write(cmd);
  uint8_t error = Wire.endTransmission();
  if (error != 0) {
    Serial.print("LCD command error: ");
    Serial.println(error);
  }
  delayMicroseconds(100); // Small delay for command processing
}

void lcdData(uint8_t data) {
  Wire.beginTransmission(LCD_ADDR);
  Wire.write((uint8_t)0x40);  // Data mode
  Wire.write(data);
  uint8_t error = Wire.endTransmission();
  if (error != 0) {
    Serial.print("LCD data error: ");
    Serial.println(error);
  }
  delayMicroseconds(50);
}

void lcdSetRGB(uint8_t r, uint8_t g, uint8_t b) {
  // Only update if color changed
  if (r == lastR && g == lastG && b == lastB) {
    return;
  }
  lastR = r;
  lastG = g;
  lastB = b;
  
  // Check if RGB device responds
  Wire.beginTransmission(RGB_ADDR);
  uint8_t error = Wire.endTransmission();
  if (error != 0) {
    Serial.print("RGB I2C error: ");
    Serial.println(error);
    return;
  }
  
  // PCA9633 initialization - reset first
  Wire.beginTransmission(RGB_ADDR);
  Wire.write(0x00);  // MODE1 register
  Wire.write(0x00);  // Normal mode, no sleep
  error = Wire.endTransmission();
  if (error != 0) {
    Serial.println("RGB MODE1 error");
    return;
  }
  delay(2);

  Wire.beginTransmission(RGB_ADDR);
  Wire.write(0x08);  // MODE2 register
  Wire.write(0x04);  // Open-drain, non-inverted
  error = Wire.endTransmission();
  if (error != 0) {
    Serial.println("RGB MODE2 error");
    return;
  }
  delay(2);

  // IMPORTANT: Set LEDOUT registers FIRST to enable PWM mode
  // LEDOUT0 (0x14) controls LEDs 0-3, LEDOUT1 (0x15) controls LEDs 4-7
  Wire.beginTransmission(RGB_ADDR);
  Wire.write(0x14);  // LEDOUT0 register
  Wire.write(0xAA);  // 0xAA = PWM mode for all 4 LEDs (10101010)
  error = Wire.endTransmission();
  if (error != 0) {
    Serial.println("RGB LEDOUT0 error");
    return;
  }
  delay(2);
  
  Wire.beginTransmission(RGB_ADDR);
  Wire.write(0x15);  // LEDOUT1 register  
  Wire.write(0xAA);  // PWM mode for LEDs 4-7
  error = Wire.endTransmission();
  if (error != 0) {
    Serial.println("RGB LEDOUT1 error");
    return;
  }
  delay(2);

  // Now set PWM values - PCA9633 PWM registers start at 0x02
  // Register mapping: 0x02=PWM0, 0x03=PWM1, 0x04=PWM2, etc.
  // Grove LCD typically uses: PWM2=Red, PWM3=Green, PWM4=Blue
  Wire.beginTransmission(RGB_ADDR);
  Wire.write(0x04);  // PWM2 (Red)
  Wire.write(r);
  error = Wire.endTransmission();
  if (error != 0) {
    Serial.println("RGB PWM2 (Red) error");
    return;
  }
  delay(2);
  
  Wire.beginTransmission(RGB_ADDR);
  Wire.write(0x05);  // PWM3 (Green)
  Wire.write(g);
  error = Wire.endTransmission();
  if (error != 0) {
    Serial.println("RGB PWM3 (Green) error");
    return;
  }
  delay(2);
  
  Wire.beginTransmission(RGB_ADDR);
  Wire.write(0x06);  // PWM4 (Blue)
  Wire.write(b);
  error = Wire.endTransmission();
  if (error != 0) {
    Serial.println("RGB PWM4 (Blue) error");
    return;
  }
  
  Serial.print("RGB set: R=");
  Serial.print(r);
  Serial.print(" G=");
  Serial.print(g);
  Serial.print(" B=");
  Serial.print(b);
  Serial.print(" (error=");
  Serial.print(error);
  Serial.println(")");
}

void lcdClear() {
  lcdCommand(0x01);
  delay(2);
}

void lcdHome() {
  lcdCommand(0x02);
  delay(2);
}

void lcdDisplayOn() {
  lcdCommand(0x0C);
}

void lcdSetCursor(uint8_t col, uint8_t row) {
  static const uint8_t row_offsets[] = {0x00, 0x40};
  lcdCommand(0x80 | (row_offsets[row] + col));
}

void lcdInit() {
  Serial.println("Initializing LCD...");
  
  // Check if LCD responds
  Wire.beginTransmission(LCD_ADDR);
  uint8_t error = Wire.endTransmission();
  if (error != 0) {
    Serial.print("ERROR: LCD not responding! Error code: ");
    Serial.println(error);
    Serial.println("Check I2C wiring and address (should be 0x3E)");
    return;
  }
  Serial.println("LCD responds to I2C");
  
  // Reset sequence - try multiple times
  for (int i = 0; i < 3; i++) {
    delay(100); // Longer delay for ESP32-S3
    
    // Function set: 8-bit, 2-line, 5x8 dots
  lcdCommand(0x38);
    delay(10);
    
    // Extended function set (some Grove LCDs need this)
    lcdCommand(0x39);
    delay(10);

  // Return to normal instruction set
  lcdCommand(0x38);
    delay(10);
    
    // Display on, cursor off, blink off
    lcdCommand(0x0C);
    delay(10);
    
    // Clear display
    lcdCommand(0x01);
    delay(10);

  // Entry mode: increment, no shift
  lcdCommand(0x06);
    delay(10);
  }
  
  // Test: Try to write something
  lcdSetCursor(0, 0);
  lcdPrint("Test 123");
  delay(500);
  
  Serial.println("LCD init complete - check if 'Test 123' appears");
}

void lcdPrint(const char* s) {
  uint8_t count = 0;
  while (*s && count < 16) {  // Limit to 16 chars per line
    lcdData(*s++);
    count++;
  }
}

void lcdPrintPadded(const char* s, uint8_t width) {
  uint8_t len = 0;
  const char* p = s;
  while (*p && len < width) {
    len++;
    p++;
  }
  
  // Print text
  lcdPrint(s);
  
  // Pad with spaces
  for (uint8_t i = len; i < width; i++) {
    lcdData(' ');
  }
}

void lcdPrintNum(int num) {
  char buf[10];
  snprintf(buf, sizeof(buf), "%d", num);
  lcdPrint(buf);
}

void i2cScan() {
  Serial.println("\n=== I2C Scan ===");
  uint8_t found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t error = Wire.endTransmission();
    if (error == 0) {
      Serial.print("Found device at 0x");
      if (addr < 16) Serial.print("0");
      Serial.print(addr, HEX);
      if (addr == LCD_ADDR) Serial.print(" (LCD)");
      if (addr == RGB_ADDR) Serial.print(" (RGB)");
      Serial.println();
      found++;
    } else if (error == 4) {
      Serial.print("Unknown error at 0x");
      if (addr < 16) Serial.print("0");
      Serial.println(addr, HEX);
    }
  }
  if (!found) {
    Serial.println("No I2C devices found!");
    Serial.println("Check wiring: SDA=pin 1, SCL=pin 2");
  } else {
    Serial.print("Found ");
    Serial.print(found);
    Serial.println(" device(s)");
  }
  Serial.println("================\n");
}

// ==== LED Feedback ====
void ledFlash(uint8_t times, uint16_t duration) {
  for (uint8_t i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(duration);
    digitalWrite(LED_PIN, LOW);
    if (i < times - 1) delay(duration);
  }
}

void ledCorrect() {
  // Green flash pattern (3 quick flashes)
  ledFlash(3, 100);
}

void ledIncorrect() {
  // Red flash pattern (1 long flash)
  digitalWrite(LED_PIN, HIGH);
  delay(500);
  digitalWrite(LED_PIN, LOW);
}

// ==== Button Handling ====
void updateButtons() {
  btn1Last = btn1Pressed;
  btn2Last = btn2Pressed;
  btn3Last = btn3Pressed;
  
  btn1Pressed = (digitalRead(BTN1_PIN) == LOW);
  btn2Pressed = (digitalRead(BTN2_PIN) == LOW);
  btn3Pressed = (digitalRead(BTN3_PIN) == LOW);
  
  if (btn1Pressed && !btn1Last) {
    btn1PressTime = millis();
  }
  if (btn2Pressed && !btn2Last) {
    btn2PressTime = millis();
  }
  if (btn3Pressed && !btn3Last) {
    btn3PressTime = millis();
  }
}

bool buttonPressed(uint8_t btn) {
  switch(btn) {
    case 1: return btn1Pressed && !btn1Last;
    case 2: return btn2Pressed && !btn2Last;
    case 3: return btn3Pressed && !btn3Last;
    default: return false;
  }
}

// ==== Persistence ====
bool isFirstBoot() {
  prefs.begin("cognipet", true);
  bool firstBoot = prefs.getBool("firstBoot", true);
  prefs.end();
  return firstBoot;
}

void markBootComplete() {
  prefs.begin("cognipet", false);
  prefs.putBool("firstBoot", false);
  prefs.end();
}

// ==== BLE Setup ====
class MyServerCallbacks: public BLEServerCallbacks {
  void onConnect(BLEServer* pServer) {
    deviceConnected = true;
    Serial.println("BLE Client connected");
  }

  void onDisconnect(BLEServer* pServer) {
    deviceConnected = false;
    Serial.println("BLE Client disconnected");
  }
};

void setupBLE() {
  BLEDevice::init(BLE_DEVICE_NAME);
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());

  BLEService* pService = pServer->createService(SERVICE_UUID);

  pAssessmentChar = pService->createCharacteristic(
    ASSESSMENT_UUID,
    BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
  );
  pAssessmentChar->addDescriptor(new BLE2902());

  pInteractionChar = pService->createCharacteristic(
    INTERACTION_UUID,
    BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
  );
  pInteractionChar->addDescriptor(new BLE2902());

  pService->start();

  BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(false);
  pAdvertising->setMinPreferred(0x0);
  BLEDevice::startAdvertising();
  
  Serial.println("BLE advertising started");
}

void sendAssessmentViaBLE() {
  Serial.print("Attempting to send assessment via BLE... ");
  Serial.print("deviceConnected=");
  Serial.print(deviceConnected);
  Serial.print(", pAssessmentChar=");
  Serial.println(pAssessmentChar ? "OK" : "NULL");
  
  if (deviceConnected && pAssessmentChar) {
    uint8_t data[32];
    memcpy(data, &lastAssessment, sizeof(AssessmentResult));
    pAssessmentChar->setValue(data, sizeof(AssessmentResult));
    pAssessmentChar->notify();
    Serial.println("✓ Assessment sent via BLE");
    Serial.print("  Score: ");
    Serial.print(lastAssessment.total_score);
    Serial.print("/12, Alert: ");
    Serial.println(lastAssessment.alert_level);
  } else {
    Serial.println("✗ Cannot send: device not connected or characteristic not available");
  }
}

void logInteraction(uint8_t type, uint16_t responseTime, uint8_t success, int8_t mood = -1) {
  InteractionLog log;
  log.timestamp = getCurrentTimestamp();
  log.interaction_type = type;
  log.response_time_ms = responseTime;
  log.success = success;
  log.mood_selected = mood;
  
  interactionQueue[queueTail] = log;
  queueTail = (queueTail + 1) % 20;
  
  // Send via BLE if connected
  if (deviceConnected && pInteractionChar) {
    uint8_t data[sizeof(InteractionLog)];
    memcpy(data, &log, sizeof(InteractionLog));
    pInteractionChar->setValue(data, sizeof(InteractionLog));
    pInteractionChar->notify();
  } else {
    // Queue for later if BLE is down
    queueInteraction(log);
  }
  
  Serial.print("Interaction logged: type=");
  Serial.print(type);
  Serial.print(" time=");
  Serial.print(responseTime);
  Serial.print(" success=");
  Serial.println(success);
}

// ==== Cognitive Assessment Tests ====
uint8_t testOrientation() {
  uint8_t score = 0;
  struct tm now;
  if (!getLocalTimeSafe(&now)) {
    Serial.println("Orientation test requires valid real-time clock. Prompting user to sync.");
    lcdClear();
    lcdSetCursor(0, 0);
    lcdPrint("Sync clock first");
    lcdSetCursor(0, 1);
    lcdPrint("Hold BTN1+BTN2");
    delay(2500);
    return 0;
  }
  
  // Question 1: Day of week
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Today is?");
  lcdSetCursor(0, 1);

  uint8_t dayOptions[3];
  uint8_t correctDaySlot = 0;
  uint8_t today = now.tm_wday % 7;
  dayOptions[0] = today;
  dayOptions[1] = (today + 6) % 7;
  dayOptions[2] = (today + 1) % 7;
  rotateOptions(dayOptions, now.tm_mday % 3);
  for (uint8_t i = 0; i < 3; i++) {
    if (dayOptions[i] == today) {
      correctDaySlot = i;
      break;
    }
  }

  char dayLine[17];
  snprintf(dayLine, sizeof(dayLine), "A:%-2sB:%-2sC:%-2s",
           DAY_SHORT[dayOptions[0]],
           DAY_SHORT[dayOptions[1]],
           DAY_SHORT[dayOptions[2]]);
  lcdPrint(dayLine);
  delay(1000);
  
  questionStartTime = millis();
  selectedAnswer = 255;
  
  while (selectedAnswer == 255) {
    updateButtons();
    if (buttonPressed(1)) {
      selectedAnswer = 0; // Monday
      break;
    }
    if (buttonPressed(2)) {
      selectedAnswer = 1; // Tuesday
      break;
    }
    if (buttonPressed(3)) {
      selectedAnswer = 2; // Wednesday
      break;
    }
    delay(50);
  }
  
  uint16_t responseTime = millis() - questionStartTime;
  totalResponseTime += responseTime;
  responseCount++;
  
  if (selectedAnswer == correctDaySlot) {
    score++;
    ledCorrect();
    lcdClear();
    lcdSetCursor(4, 0);
    lcdPrint("Correct!");
    delay(1500);
  } else {
    ledIncorrect();
    lcdClear();
    lcdSetCursor(5, 0);
    lcdPrint("Oops!");
    delay(1500);
  }
  
  // Question 2: Time of day
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Time of day?");
  lcdSetCursor(0, 1);

  uint8_t periodOptions[3] = {0, 1, 2};  // morning, afternoon, evening
  uint8_t epochHour = now.tm_hour;
  uint8_t correctPeriod = 0;
  if (epochHour >= 5 && epochHour < 12) {
    correctPeriod = 0; // morning
  } else if (epochHour >= 12 && epochHour < 18) {
    correctPeriod = 1; // afternoon
  } else {
    correctPeriod = 2; // evening/night
  }
  rotateOptions(periodOptions, now.tm_min % 3);
  uint8_t correctPeriodSlot = 0;
  for (uint8_t i = 0; i < 3; i++) {
    if (periodOptions[i] == correctPeriod) {
      correctPeriodSlot = i;
      break;
    }
  }

  char timeLine[17];
  snprintf(timeLine, sizeof(timeLine), "A:%-3sB:%-3sC:%-3s",
           PERIOD_SHORT[periodOptions[0]],
           PERIOD_SHORT[periodOptions[1]],
           PERIOD_SHORT[periodOptions[2]]);
  lcdPrint(timeLine);
  delay(1000);
  
  questionStartTime = millis();
  selectedAnswer = 255;
  
  while (selectedAnswer == 255) {
    updateButtons();
    if (buttonPressed(1)) {
      selectedAnswer = 0;
      break;
    }
    if (buttonPressed(2)) {
      selectedAnswer = 1;
      break;
    }
    if (buttonPressed(3)) {
      selectedAnswer = 2;
      break;
    }
    delay(50);
  }
  
  responseTime = millis() - questionStartTime;
  totalResponseTime += responseTime;
  responseCount++;
  
  if (selectedAnswer == correctPeriodSlot) {
    score++;
    ledCorrect();
    lcdClear();
    lcdSetCursor(4, 0);
    lcdPrint("Correct!");
    delay(1500);
  } else {
    ledIncorrect();
    lcdClear();
    lcdSetCursor(5, 0);
    lcdPrint("Oops!");
    delay(1500);
  }
  
  // Question 3: Location
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Where are you?");
  lcdSetCursor(0, 1);
  lcdPrint("A:Hosp B:Home  ");  // Pad to 16 chars
  delay(1000);
  
  questionStartTime = millis();
  selectedAnswer = 255;
  
  while (selectedAnswer == 255) {
    updateButtons();
    if (buttonPressed(1)) {
      selectedAnswer = 0; // Hospital
      break;
    }
    if (buttonPressed(2)) {
      selectedAnswer = 1; // Home
      break;
    }
    delay(50);
  }
  
  responseTime = millis() - questionStartTime;
  totalResponseTime += responseTime;
  responseCount++;
  
  if (selectedAnswer == 0) {
    score++;
    ledCorrect();
    lcdClear();
    lcdSetCursor(4, 0);
    lcdPrint("Correct!");
    delay(1500);
  } else {
    ledIncorrect();
    lcdClear();
    lcdSetCursor(5, 0);
    lcdPrint("Oops!");
    delay(1500);
  }
  
  return score; // 0-3
}

uint8_t testMemory() {
  // Use adaptive difficulty for sequence length
  uint8_t seqLen = currentDifficulty.memory_sequence_length;
  uint16_t displayTime = currentDifficulty.memory_display_time_ms;
  
  // Generate random sequence with adaptive length
  for (int i = 0; i < seqLen; i++) {
    memorySequence[i] = random(0, 3); // 0=A, 1=B, 2=C
  }
  
  // Show sequence
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Remember:");
  delay(1500);
  
  for (int i = 0; i < seqLen; i++) {
    lcdClear();
    lcdSetCursor(7, 0);
    lcdData('A' + memorySequence[i]);
    delay(displayTime);
    lcdClear();
    delay(200);
  }
  
  // Get user input
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Repeat it:");
  lcdSetCursor(0, 1);
  char prompt[17];
  snprintf(prompt, sizeof(prompt), "Press A/B/C   ");
  lcdPrintPadded(prompt, 16);
  delay(1000);
  
  questionStartTime = millis();
  memoryStep = 0;
  
  while (memoryStep < seqLen) {
    updateButtons();
    if (buttonPressed(1)) {
      userSequence[memoryStep] = 0;
      memoryStep++;
      lcdSetCursor(memoryStep - 1, 1);
      lcdData('A');
      delay(300);
    }
    if (buttonPressed(2)) {
      userSequence[memoryStep] = 1;
      memoryStep++;
      lcdSetCursor(memoryStep - 1, 1);
      lcdData('B');
      delay(300);
    }
    if (buttonPressed(3)) {
      userSequence[memoryStep] = 2;
      memoryStep++;
      lcdSetCursor(memoryStep - 1, 1);
      lcdData('C');
      delay(300);
    }
    delay(50);
  }
  
  uint16_t responseTime = millis() - questionStartTime;
  totalResponseTime += responseTime;
  responseCount++;
  
  // Check correctness - scale score to 0-3 based on sequence length
  uint8_t correct = 0;
  for (int i = 0; i < seqLen; i++) {
    if (memorySequence[i] == userSequence[i]) correct++;
  }
  
  // Normalize score to 0-3 scale
  uint8_t normalizedScore = (correct * 3) / seqLen;
  
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Score:");
  lcdSetCursor(0, 1);
  char buf[17];
  snprintf(buf, sizeof(buf), "%d/%d -> %d/3", correct, seqLen, normalizedScore);
  lcdPrintPadded(buf, 16);
  delay(2000);
  
  if (normalizedScore == 3) {
    ledCorrect();
  } else {
    ledIncorrect();
  }
  
  return normalizedScore; // 0-3
}

uint8_t testAttention() {
  // Use adaptive difficulty
  uint8_t numTrials = currentDifficulty.attention_trials;
  uint16_t minDelay = currentDifficulty.attention_min_delay_ms;
  uint16_t maxDelay = currentDifficulty.attention_max_delay_ms;
  uint16_t timeoutMs = 2000; // Fixed timeout for reaction
  
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Press A when");
  lcdSetCursor(2, 1);
  lcdPrint("you see *");
  delay(2000);
  
  attentionTrials = 0;
  attentionCorrect = 0;
  
  for (int i = 0; i < numTrials; i++) {
    // Random wait with adaptive range
    delay(random(minDelay, maxDelay));
    
    // Show star
    lcdClear();
    lcdSetCursor(7, 0);
    lcdData('*');
    lcdSetCursor(7, 1);
    lcdData('*');
    
    attentionStartTime = millis();
    waitingForAttention = true;
    bool pressed = false;
    
    while (millis() - attentionStartTime < timeoutMs) {
      updateButtons();
      if (buttonPressed(1)) { // Button A
        pressed = true;
        uint16_t reactionTime = millis() - attentionStartTime;
        totalResponseTime += reactionTime;
        responseCount++;
        attentionCorrect++;
        
        lcdClear();
        lcdSetCursor(0, 0);
        lcdPrint("Good!");
        lcdSetCursor(0, 1);
        lcdPrintNum(reactionTime);
        lcdPrint(" ms");
        delay(1000);
        break;
      }
      delay(10);
    }
    
    if (!pressed) {
      lcdClear();
      lcdSetCursor(5, 0);
      lcdPrint("Too slow!");
      delay(1000);
    }
    
    attentionTrials++;
  }
  
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Score:");
  lcdSetCursor(0, 1);
  char buf[17];
  snprintf(buf, sizeof(buf), "%d/%d", attentionCorrect, numTrials);
  lcdPrintPadded(buf, 16);
  delay(2000);
  
  // Return 0-3 score, normalized based on trials
  uint8_t threshold1 = (numTrials * 3) / 4; // 75%
  uint8_t threshold2 = (numTrials * 2) / 3; // 67%
  uint8_t threshold3 = numTrials / 2;       // 50%
  
  if (attentionCorrect >= threshold1) {
    ledCorrect();
    return 3;
  } else if (attentionCorrect >= threshold2) {
    return 2;
  } else if (attentionCorrect >= threshold3) {
    return 1;
  } else {
    ledIncorrect();
    return 0;
  }
}

uint8_t testExecutiveFunction() {
  // Use adaptive difficulty for sequence length
  uint8_t seqLen = currentDifficulty.executive_sequence_length;
  uint8_t userSeq[5] = {255, 255, 255, 255, 255}; // Max 5
  uint8_t correctSeq[5];
  
  // Generate correct sequence based on length (simplified: A->B->C pattern)
  for (int i = 0; i < seqLen; i++) {
    correctSeq[i] = i % 3; // Pattern: 0,1,2,0,1...
  }
  
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Order actions:");
  lcdSetCursor(0, 1);
  lcdPrint("A:Eat B:Shwr    ");  // Pad to 16 chars
  delay(2000);
  
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Select order:");
  lcdSetCursor(0, 1);
  lcdPrint("Press A/B/C    ");  // Pad to 16 chars
  
  sequenceStep = 0;
  questionStartTime = millis();
  
  while (sequenceStep < seqLen) {
    updateButtons();
    if (buttonPressed(1)) {
      userSeq[sequenceStep] = 0;
      sequenceStep++;
      lcdSetCursor(sequenceStep * 2 - 2, 1);
      lcdData('A');
      delay(300);
    }
    if (buttonPressed(2)) {
      userSeq[sequenceStep] = 1;
      sequenceStep++;
      lcdSetCursor(sequenceStep * 2 - 2, 1);
      lcdData('B');
      delay(300);
    }
    if (buttonPressed(3)) {
      userSeq[sequenceStep] = 2;
      sequenceStep++;
      lcdSetCursor(sequenceStep * 2 - 2, 1);
      lcdData('C');
      delay(300);
    }
    delay(50);
  }
  
  uint16_t responseTime = millis() - questionStartTime;
  totalResponseTime += responseTime;
  responseCount++;
  
  // Check if sequence is correct
  uint8_t correct = 0;
  for (int i = 0; i < seqLen; i++) {
    if (userSeq[i] == correctSeq[i]) correct++;
  }
  
  // Normalize score to 0-3
  uint8_t normalizedScore = (correct * 3) / seqLen;
  
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Score:");
  lcdSetCursor(0, 1);
  char buf[17];
  snprintf(buf, sizeof(buf), "%d/%d -> %d/3", correct, seqLen, normalizedScore);
  lcdPrintPadded(buf, 16);
  delay(2000);
  
  if (normalizedScore == 3) {
    ledCorrect();
    return 3;
  } else if (normalizedScore >= 2) {
    return 2;
  } else {
    ledIncorrect();
    return 0;
  }
}

void runCognitiveAssessment() {
  lcdClear();
  lcdSetCursor(3, 0);
  lcdPrint("CogniPet");
  lcdSetCursor(0, 1);
  lcdPrint("Assessment...");
  lastR = 255; lastG = 255; lastB = 255; // Force update
  lcdSetRGB(0, 10, 30); // Very dim blue
  delay(2000);
  
  Serial.println("=== Starting Cognitive Assessment ===");

  ensureTimeSync();
  
  // Reset assessment
  memset(&lastAssessment, 0, sizeof(AssessmentResult));
  totalResponseTime = 0;
  responseCount = 0;
  
  // Test 1: Orientation
  lastAssessment.orientation_score = testOrientation();
  
  // Test 2: Memory
  lastAssessment.memory_score = testMemory();
  
  // Test 3: Attention
  lastAssessment.attention_score = testAttention();
  
  // Test 4: Executive function
  lastAssessment.executive_score = testExecutiveFunction();
  
  // Calculate totals
  lastAssessment.total_score = 
    lastAssessment.orientation_score +
    lastAssessment.memory_score +
    lastAssessment.attention_score +
    lastAssessment.executive_score;
  
  lastAssessment.avg_response_time_ms = totalResponseTime / responseCount;
  lastAssessment.timestamp = getCurrentTimestamp();
  
  // Determine alert level
  if (lastAssessment.total_score >= 10) {
    lastAssessment.alert_level = 0; // Green
  } else if (lastAssessment.total_score >= 7) {
    lastAssessment.alert_level = 1; // Yellow
  } else if (lastAssessment.total_score >= 4) {
    lastAssessment.alert_level = 2; // Orange
  } else {
    lastAssessment.alert_level = 3; // Red
  }
  
  // Show results
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Done! Score:");
  lcdSetCursor(0, 1);
  char scoreBuf[17];
  snprintf(scoreBuf, sizeof(scoreBuf), "%d/12", lastAssessment.total_score);
  lcdPrint(scoreBuf);
  delay(3000);
  
  // Store to history (before sending, so we can mark as synced if successful)
  storeAssessmentToHistory(lastAssessment);
  
  // Send via BLE
  sendAssessmentViaBLE();
  
  // Mark as synced in history if BLE send was successful
  if (deviceConnected && pAssessmentChar) {
    uint8_t idx = (assessmentHistoryIndex - 1 + 50) % 50;
    assessmentHistory[idx].synced = true;
  }
  
  // Update adaptive difficulty based on performance
  adjustDifficultyBasedOnPerformance(lastAssessment.total_score);
  
  // Mark assessment as complete (updates schedule)
  markAssessmentComplete();
  
  // Transition to pet mode
  initializePet();
  currentState = STATE_PET_NORMAL;
  currentMenu = MENU_MAIN;  // Reset menu
  
  Serial.println("=== Assessment Complete ===");
  Serial.print("Total Score: ");
  Serial.print(lastAssessment.total_score);
  Serial.print("/12, Alert Level: ");
  Serial.println(lastAssessment.alert_level);
}

// ==== Virtual Pet Functions ====
void initializePet() {
  pet.happiness = 60;  // Start at neutral (not always green)
  pet.hunger = 50;     // Start a bit hungry
  pet.cleanliness = 70; // Start a bit dirty
  pet.lastFed = millis();
  pet.lastPlayed = millis();
  pet.lastCleaned = millis();
  
  // Reset RGB tracking to force update
  lastR = 255; lastG = 255; lastB = 255;
}

void updatePetStats() {
  unsigned long now = millis();
  if (now - pet.lastFed > 60000) { // Every minute
    pet.hunger = min(100, pet.hunger + 2);
    pet.cleanliness = max(0, pet.cleanliness - 1);
    
    // Intelligent happiness decay
    if (pet.hunger > 80) {
      pet.happiness = max(0, pet.happiness - 3);
    } else if (pet.hunger > 60) {
      pet.happiness = max(0, pet.happiness - 1);
    }
    
    if (pet.cleanliness < 20) {
      pet.happiness = max(0, pet.happiness - 2);
    }
    
    // Gradual happiness recovery if needs are met
    if (pet.hunger < 50 && pet.cleanliness > 50 && pet.happiness < 80) {
      pet.happiness = min(100, pet.happiness + 1);
    }
    
    pet.lastFed = now;
  }
}

void drawPetScreen() {
  static unsigned long lastDraw = 0;
  static uint8_t lastHappiness = 255;
  
  // Only redraw every 500ms to avoid flickering
  unsigned long now = millis();
  if (now - lastDraw < 500 && pet.happiness == lastHappiness && currentMenu == MENU_MAIN) {
    return;
  }
  lastDraw = now;
  lastHappiness = pet.happiness;
  
  lcdClear();
  
  if (currentMenu == MENU_MAIN) {
    // Line 1: Pet status (16 chars max)
    lcdSetCursor(0, 0);
    if (pet.happiness > 70) {
      lcdPrint("^_^ Buddy");
    } else if (pet.happiness > 40) {
      lcdPrint("-_- Buddy");
    } else {
      lcdPrint("T_T Buddy");
    }
    
    // Show status indicator (fit in remaining space)
    lcdSetCursor(10, 0);
    if (pet.hunger > 70) {
      lcdPrint("HUN");
    } else if (pet.cleanliness < 30) {
      lcdPrint("DRT");
    } else {
      lcdPrint("OK");
    }
    
    // Line 2: Menu (16 chars max) - Use all 3 buttons
    lcdSetCursor(0, 1);
    lcdPrint("A:Feed B:Play C:Cln");  // C: Clean (hold for menu)
    
  } else if (currentMenu == MENU_STATS) {
    // Stats screen
    lcdSetCursor(0, 0);
    lcdPrint("Stats:");
    lcdSetCursor(0, 1);
    char buf[17];
    snprintf(buf, sizeof(buf), "HP:%d%% H:%d%%", pet.happiness, pet.hunger);
    lcdPrint(buf);
    
  } else if (currentMenu == MENU_MOOD) {
    // Mood check screen
    lcdSetCursor(0, 0);
    lcdPrint("How are you?");
    lcdSetCursor(0, 1);
    lcdPrint("A:Good B:OK C:Sad");
    
  } else if (currentMenu == MENU_GAMES) {
    // Games menu
    lcdSetCursor(0, 0);
    lcdPrint("Choose game:");
    lcdSetCursor(0, 1);
    lcdPrint("A:Mem B:React C:Bk");
  }
  
  // Update RGB based on mood (only when happiness changes)
  // Use VERY dim colors so text is visible
  if (pet.happiness > 70) {
    lcdSetRGB(0, 20, 5); // Very dim green (happy)
  } else if (pet.happiness > 40) {
    lcdSetRGB(20, 20, 0); // Very dim yellow (neutral)
  } else {
    lcdSetRGB(20, 0, 0); // Very dim red (sad)
  }
}

void feedPet() {
  unsigned long startTime = millis();
  
  pet.hunger = max(0, pet.hunger - 30);
  pet.happiness = min(100, pet.happiness + 10);
  
  lcdClear();
  lcdSetCursor(3, 0);
  lcdPrint("Nom nom!");
  lcdSetCursor(4, 1);
  lcdPrint("Yummy!");
  
  // Flash green, then return to mood color
  lastR = 255; lastG = 255; lastB = 255; // Force update
  lcdSetRGB(0, 30, 0); // Dim green flash
  delay(1500);
  lastR = 255; lastG = 255; lastB = 255; // Force update to mood color
  
  logInteraction(0, millis() - startTime, 1, -1); // Type 0 = feed
}

void playWithPet() {
  // Mini-game: Reaction test
  unsigned long startTime = millis();
  
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Press A when");
  lcdSetCursor(0, 1);
  lcdPrint("you see *");
  
  // Check for diagnostics during initial delay
  unsigned long delayStart = millis();
  while (millis() - delayStart < 2000) {
    updateButtons();
    if (checkDiagnosticsBackdoor()) {
      diagnosticsActive = true;
      diagnosticsPage = 0;
      lastDiagnosticsRefresh = 0;
      lcdClear();
      currentState = STATE_DIAGNOSTICS;
      return;
    }
    delay(50);
  }
  
  // Random delay with diagnostics check
  unsigned long randomDelay = random(1000, 2500);
  delayStart = millis();
  while (millis() - delayStart < randomDelay) {
    updateButtons();
    if (checkDiagnosticsBackdoor()) {
      diagnosticsActive = true;
      diagnosticsPage = 0;
      lastDiagnosticsRefresh = 0;
      lcdClear();
      currentState = STATE_DIAGNOSTICS;
      return;
    }
    delay(50);
  }
  
  // Show star
  lcdClear();
  lcdSetCursor(7, 0);
  lcdData('*');
  lcdSetCursor(7, 1);
  lcdData('*');
  
  unsigned long showTime = millis();
  bool pressed = false;
  
  while (millis() - showTime < 2000) {
    updateButtons();
    
    // Check for diagnostics backdoor even during game
    if (checkDiagnosticsBackdoor()) {
      diagnosticsActive = true;
      diagnosticsPage = 0;
      lastDiagnosticsRefresh = 0;
      lcdClear();
      currentState = STATE_DIAGNOSTICS;
      return;  // Exit game and go to diagnostics
    }
    
    if (buttonPressed(1)) { // Button A
      pressed = true;
      uint16_t reactionTime = millis() - showTime;
      
      pet.happiness = min(100, pet.happiness + 15);
      
      lcdClear();
      lcdSetCursor(4, 0);
      lcdPrint("Great!");
      lcdSetCursor(0, 1);
      char buf[17];
      snprintf(buf, sizeof(buf), "%d ms", reactionTime);
      lcdPrint(buf);
      lastR = 255; lastG = 255; lastB = 255; // Force update
      lcdSetRGB(0, 30, 0); // Dim green
      delay(1500);
      lastR = 255; lastG = 255; lastB = 255; // Force update to mood color
      
      logInteraction(1, reactionTime, 1, -1); // Type 1 = play
      break;
    }
    delay(10);
  }
  
  if (!pressed) {
    lcdClear();
    lcdSetCursor(3, 0);
    lcdPrint("Too slow!");
    lastR = 255; lastG = 255; lastB = 255; // Force update
    lcdSetRGB(30, 0, 0); // Dim red
    delay(1500);
    lastR = 255; lastG = 255; lastB = 255; // Force update to mood color
    
    logInteraction(1, 2000, 0, -1); // Failed
  }
}

void cleanPet() {
  unsigned long startTime = millis();
  
  pet.cleanliness = min(100, pet.cleanliness + 40);
  pet.happiness = min(100, pet.happiness + 5);
  
  lcdClear();
  lcdSetCursor(3, 0);
  lcdPrint("All clean!");
  lcdSetCursor(3, 1);
  lcdPrint("Thanks!");
  lastR = 255; lastG = 255; lastB = 255; // Force update
  lcdSetRGB(0, 20, 30); // Dim cyan
  delay(1500);
  lastR = 255; lastG = 255; lastB = 255; // Force update to mood color
  
  logInteraction(2, millis() - startTime, 1, -1); // Type 2 = clean
}

void showStats() {
  // Stats are shown in drawPetScreen, just handle navigation
  // This function is called when button is pressed in stats menu
}

void checkMood() {
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("How are you?");
  lcdSetCursor(0, 1);
  lcdPrint("A:Good B:OK C:Sad");
  
  unsigned long startTime = millis();
  int8_t mood = -1;
  
  while (millis() - startTime < 10000) { // 10 second timeout
    updateButtons();
    if (buttonPressed(1)) {
      mood = 0; // Good
      break;
    }
    if (buttonPressed(2)) {
      mood = 1; // OK
      break;
    }
    if (buttonPressed(3)) {
      mood = 2; // Sad
      break;
    }
    delay(50);
  }
  
  if (mood >= 0) {
    lcdClear();
    if (mood == 0) {
      lcdSetCursor(3, 0);
      lcdPrint("Great!");
      pet.happiness = min(100, pet.happiness + 5);
    } else if (mood == 1) {
      lcdSetCursor(5, 0);
      lcdPrint("OK");
    } else {
      lcdSetCursor(3, 0);
      lcdPrint("Sorry!");
      pet.happiness = max(0, pet.happiness - 5);
    }
    lcdSetCursor(0, 1);
    lcdPrint("Thanks!");
    
    logInteraction(3, millis() - startTime, 1, mood);
    delay(2000);
  }
  
  currentMenu = MENU_MAIN;
}

void playMemoryGame() {
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Memory Game!");
  lcdSetCursor(0, 1);
  lcdPrint("Remember seq ");  // Pad to 16
  
  // Check for diagnostics during initial delay
  unsigned long delayStart = millis();
  while (millis() - delayStart < 2000) {
    updateButtons();
    if (checkDiagnosticsBackdoor()) {
      diagnosticsActive = true;
      diagnosticsPage = 0;
      lastDiagnosticsRefresh = 0;
      lcdClear();
      currentState = STATE_DIAGNOSTICS;
      return;
    }
    delay(50);
  }
  
  // Generate sequence
  uint8_t seq[4];
  for (int i = 0; i < 4; i++) {
    seq[i] = random(1, 4); // 1, 2, or 3
  }
  
  // Show sequence
  for (int i = 0; i < 4; i++) {
    lcdClear();
    lcdSetCursor(6, 0);
    lcdData('A' + seq[i] - 1);
    
    // Check for diagnostics during display delay
    unsigned long delayStart = millis();
    while (millis() - delayStart < 600) {
      updateButtons();
      if (checkDiagnosticsBackdoor()) {
        diagnosticsActive = true;
        diagnosticsPage = 0;
        lastDiagnosticsRefresh = 0;
        lcdClear();
        currentState = STATE_DIAGNOSTICS;
        return;
      }
      delay(50);
    }
    
    lcdClear();
    delayStart = millis();
    while (millis() - delayStart < 200) {
      updateButtons();
      if (checkDiagnosticsBackdoor()) {
        diagnosticsActive = true;
        diagnosticsPage = 0;
        lastDiagnosticsRefresh = 0;
        lcdClear();
        currentState = STATE_DIAGNOSTICS;
        return;
      }
      delay(50);
    }
  }
  
  // Get input
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Repeat:");
  lcdSetCursor(0, 1);
  lcdPrint("Press A/B/C   ");  // Pad to 16
  
  uint8_t userSeq[4] = {0};
  unsigned long startTime = millis();
  
  for (int i = 0; i < 4; i++) {
    while (millis() - startTime < 15000) {
      updateButtons();
      
      // Check for diagnostics backdoor even during game
      if (checkDiagnosticsBackdoor()) {
        diagnosticsActive = true;
        diagnosticsPage = 0;
        lastDiagnosticsRefresh = 0;
        lcdClear();
        currentState = STATE_DIAGNOSTICS;
        return;  // Exit game and go to diagnostics
      }
      
      if (buttonPressed(1)) {
        userSeq[i] = 1;
        lcdSetCursor(i * 2, 1);
        lcdData('A');
        delay(300);
        break;
      }
      if (buttonPressed(2)) {
        userSeq[i] = 2;
        lcdSetCursor(i * 2, 1);
        lcdData('B');
        delay(300);
        break;
      }
      if (buttonPressed(3)) {
        userSeq[i] = 3;
        lcdSetCursor(i * 2, 1);
        lcdData('C');
        delay(300);
        break;
      }
      delay(50);
    }
  }
  
  // Check
  uint8_t correct = 0;
  for (int i = 0; i < 4; i++) {
    if (seq[i] == userSeq[i]) correct++;
  }
  
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Score:");
  lcdSetCursor(0, 1);
  char buf[17];
  snprintf(buf, sizeof(buf), "%d/4", correct);
  lcdPrint(buf);
  
  if (correct == 4) {
    pet.happiness = min(100, pet.happiness + 10);
    ledCorrect();
    lcdSetCursor(7, 0);
    lcdPrint("Perfect!");
  } else if (correct >= 2) {
    lcdSetCursor(7, 0);
    lcdPrint("Good!");
  } else {
    ledIncorrect();
  }
  
  logInteraction(4, millis() - startTime, correct == 4 ? 1 : 0, -1);
  delay(2500);
  currentMenu = MENU_MAIN;
}

bool checkTestDataBackdoor() {
  // Test Data Backdoor: Hold Button 1 + Button 3 together for 1.5 seconds to send test assessment
  // More forgiving: allows brief releases (up to 200ms)
  static unsigned long testDataStart = 0;
  static bool testDataActive = false;
  static bool testDataShown = false;
  static unsigned long lastBothPressed = 0;
  
  bool btn1 = (digitalRead(BTN1_PIN) == LOW);
  bool btn3 = (digitalRead(BTN3_PIN) == LOW);
  bool bothPressed = btn1 && btn3;
  
  if (bothPressed && !testDataActive) {
    // Both buttons just pressed
    testDataStart = millis();
    lastBothPressed = millis();
    testDataActive = true;
    testDataShown = false;
  } else if (bothPressed && testDataActive) {
    // Still holding both - update last pressed time
    lastBothPressed = millis();
    unsigned long elapsed = millis() - testDataStart;
    
    // Show countdown after 0.5 seconds with progress
    if (elapsed > 500 && !testDataShown) {
      lcdClear();
      lcdSetCursor(0, 0);
      lcdPrint("Test Data...");
      testDataShown = true;
    }
    
    if (testDataShown) {
      // Show progress bar
      uint8_t progress = (elapsed * 16) / 1500; // 0-16 chars for 1.5 seconds
      if (progress > 16) progress = 16;
      char progressBar[17] = "                ";
      for (uint8_t i = 0; i < progress; i++) {
        progressBar[i] = '=';
      }
      lcdSetCursor(0, 1);
      lcdPrintPadded(progressBar, 16);
    }
    
    if (elapsed > 1500) {
      // 1.5 seconds held - send test data
      testDataActive = false;
      testDataShown = false;
      return true;
    }
  } else if (testDataActive) {
    // One or both buttons released
    unsigned long timeSinceLastPress = millis() - lastBothPressed;
    
    // Allow brief release (up to 200ms) - more forgiving
    if (timeSinceLastPress > 200) {
      // Too long since both were pressed - cancel
      if (testDataShown) {
        lcdClear();
      }
      testDataActive = false;
      testDataShown = false;
    }
    // Otherwise, keep waiting (buttons might be pressed again soon)
  }
  
  return false;
}

void sendTestAssessmentData() {
  // Create test assessment data with varying scores
  // Cycles through different test scenarios
  static uint8_t testScenario = 0;
  
  // Clear last assessment
  memset(&lastAssessment, 0, sizeof(AssessmentResult));
  
  // Different test scenarios
  switch (testScenario % 4) {
    case 0: // Excellent assessment
      lastAssessment.orientation_score = 3;
      lastAssessment.memory_score = 3;
      lastAssessment.attention_score = 3;
      lastAssessment.executive_score = 3;
      lastAssessment.avg_response_time_ms = 2000;
      break;
    case 1: // Moderate assessment
      lastAssessment.orientation_score = 2;
      lastAssessment.memory_score = 2;
      lastAssessment.attention_score = 2;
      lastAssessment.executive_score = 2;
      lastAssessment.avg_response_time_ms = 3000;
      break;
    case 2: // Poor assessment
      lastAssessment.orientation_score = 1;
      lastAssessment.memory_score = 1;
      lastAssessment.attention_score = 1;
      lastAssessment.executive_score = 1;
      lastAssessment.avg_response_time_ms = 5000;
      break;
    case 3: // Mixed assessment
      lastAssessment.orientation_score = 3;
      lastAssessment.memory_score = 1;
      lastAssessment.attention_score = 2;
      lastAssessment.executive_score = 2;
      lastAssessment.avg_response_time_ms = 3500;
      break;
  }
  
  // Calculate totals
  lastAssessment.total_score = 
    lastAssessment.orientation_score +
    lastAssessment.memory_score +
    lastAssessment.attention_score +
    lastAssessment.executive_score;
  
  lastAssessment.timestamp = getCurrentTimestamp();
  
  // Determine alert level
  if (lastAssessment.total_score >= 10) {
    lastAssessment.alert_level = 0; // Green
  } else if (lastAssessment.total_score >= 7) {
    lastAssessment.alert_level = 1; // Yellow
  } else if (lastAssessment.total_score >= 4) {
    lastAssessment.alert_level = 2; // Orange
  } else {
    lastAssessment.alert_level = 3; // Red
  }
  
  // Show on LCD
  lcdClear();
  lcdSetCursor(0, 0);
  lcdPrint("Test Data Sent!");
  lcdSetCursor(0, 1);
  char scoreBuf[17];
  snprintf(scoreBuf, sizeof(scoreBuf), "Score: %d/12", lastAssessment.total_score);
  lcdPrint(scoreBuf);
  
  // Send via BLE
  sendAssessmentViaBLE();
  
  // Also send a test interaction
  logInteraction(0, 500, true, -1); // Feed interaction
  
  Serial.print("Test assessment sent: Score ");
  Serial.print(lastAssessment.total_score);
  Serial.print("/12, Alert Level ");
  Serial.println(lastAssessment.alert_level);
  
  // Cycle to next scenario
  testScenario++;
  
  delay(2000);
}

void handleReminder() {
  unsigned long now = millis();
  
  // Check buttons FIRST before doing anything else
  updateButtons();
  
  // Check for skip/postpone (Button 2 = skip for 1 hour, Button 3 = postpone 30 min)
  // Check buttons with priority - these should work immediately
  if (buttonPressed(2)) {
    // Skip: add 1 hour to last assessment time
    schedule.lastAssessmentTime += 3600000UL;
    overdueReminderShown = false;  // Reset overdue reminder flag
    reminderCooldownUntil = millis() + REMINDER_COOLDOWN_MS;  // Set cooldown
    saveSchedule();
    lcdClear();
    lcdSetCursor(0, 0);
    lcdPrint("Skipped 1h");
    delay(2000);
    reminderBlinkState = false;
    digitalWrite(LED_PIN, LOW);
    lcdSetRGB(0, 0, 0);
    // Exit reminder state and return to pet mode
    currentState = STATE_PET_NORMAL;
    return;
  }
  
  if (buttonPressed(3)) {
    // Postpone: add 30 minutes
    schedule.lastAssessmentTime += 1800000UL;
    overdueReminderShown = false;  // Reset overdue reminder flag
    reminderCooldownUntil = millis() + REMINDER_COOLDOWN_MS;  // Set cooldown
    saveSchedule();
    lcdClear();
    lcdSetCursor(0, 0);
    lcdPrint("Postponed 30m");
    delay(2000);
    reminderBlinkState = false;
    digitalWrite(LED_PIN, LOW);
    lcdSetRGB(0, 0, 0);
    // Exit reminder state and return to pet mode
    currentState = STATE_PET_NORMAL;
    return;
  }
  
  if (buttonPressed(1)) {
    // Start assessment
    currentState = STATE_ASSESSMENT;
    reminderBlinkState = false;
    digitalWrite(LED_PIN, LOW);
    lcdSetRGB(0, 0, 0);
    return;
  }
  
  // Check if reminder should be shown (but allow continuous display once triggered)
  // Only update check time if we're not already in reminder state
  if (now - lastReminderCheck < REMINDER_CHECK_INTERVAL_MS && !isAssessmentDue()) {
    return;
  }
  lastReminderCheck = now;
  
  if (!isAssessmentDue()) {
    return; // Not due yet
  }
  
  // Blink LED and show reminder on LCD
  if (now - reminderBlinkTime > REMINDER_BLINK_INTERVAL_MS) {
    reminderBlinkTime = now;
    reminderBlinkState = !reminderBlinkState;
    
    if (reminderBlinkState) {
      digitalWrite(LED_PIN, HIGH);
      lcdSetRGB(255, 100, 0); // Orange glow
    } else {
      digitalWrite(LED_PIN, LOW);
      lcdSetRGB(0, 0, 0);
    }
  }
  
  // Show reminder message (only update display occasionally to avoid flicker)
  static unsigned long lastDisplayUpdate = 0;
  if (now - lastDisplayUpdate > 500) {  // Update display every 500ms
    lastDisplayUpdate = now;
    lcdClear();
    if (schedule.assessmentOverdue && !overdueReminderShown) {
      // First time showing overdue - mark as shown
      overdueReminderShown = true;
      lcdSetCursor(0, 0);
      lcdPrint("Assessment!");
      lcdSetCursor(0, 1);
      lcdPrint("OVERDUE");
    } else {
      // Regular reminder (due but not overdue, or overdue already shown once)
      lcdSetCursor(0, 0);
      lcdPrint("Time for");
      lcdSetCursor(0, 1);
      lcdPrint("Assessment!");
    }
  }
  
  // Small delay to allow button processing
  delay(50);
}

bool checkBackdoor() {
  // Backdoor: Hold Button 1 + Button 2 together for 1.5 seconds to trigger assessment
  // More forgiving: allows brief releases (up to 200ms)
  static unsigned long backdoorStart = 0;
  static bool backdoorActive = false;
  static bool backdoorShown = false;
  static unsigned long lastBothPressed = 0;
  
  bool btn1 = (digitalRead(BTN1_PIN) == LOW);
  bool btn2 = (digitalRead(BTN2_PIN) == LOW);
  bool bothPressed = btn1 && btn2;
  
  if (bothPressed && !backdoorActive) {
    // Both buttons just pressed
    backdoorStart = millis();
    lastBothPressed = millis();
    backdoorActive = true;
    backdoorShown = false;
  } else if (bothPressed && backdoorActive) {
    // Still holding both - update last pressed time
    lastBothPressed = millis();
    unsigned long elapsed = millis() - backdoorStart;
    
    // Show countdown after 0.5 seconds with progress
    if (elapsed > 500 && !backdoorShown) {
      lcdClear();
      lcdSetCursor(0, 0);
      lcdPrint("Assessment...");
      backdoorShown = true;
    }
    
    if (backdoorShown) {
      // Show progress bar
      uint8_t progress = (elapsed * 16) / 1500; // 0-16 chars for 1.5 seconds
      if (progress > 16) progress = 16;
      char progressBar[17] = "                ";
      for (uint8_t i = 0; i < progress; i++) {
        progressBar[i] = '=';
      }
      lcdSetCursor(0, 1);
      lcdPrintPadded(progressBar, 16);
    }
    
    if (elapsed > 1500) {
      // 1.5 seconds held - trigger assessment
      backdoorActive = false;
      backdoorShown = false;
      return true;
    }
  } else if (backdoorActive) {
    // One or both buttons released
    unsigned long timeSinceLastPress = millis() - lastBothPressed;
    
    // Allow brief release (up to 200ms) - more forgiving
    if (timeSinceLastPress > 200) {
      // Too long since both were pressed - cancel
      if (backdoorShown) {
        lcdClear();
      }
      backdoorActive = false;
      backdoorShown = false;
    }
    // Otherwise, keep waiting (buttons might be pressed again soon)
  }
  
  return false;
}

bool checkDiagnosticsBackdoor() {
  // Diagnostics Backdoor: Hold Button 2 + Button 3 together for 1.5 seconds
  // More forgiving: allows brief releases (up to 200ms)
  static bool comboActive = false;
  static unsigned long comboStart = 0;
  static bool hintShown = false;
  static unsigned long lastBothPressed = 0;

  bool btn2 = (digitalRead(BTN2_PIN) == LOW);
  bool btn3 = (digitalRead(BTN3_PIN) == LOW);
  bool bothPressed = btn2 && btn3;

  if (bothPressed && !comboActive) {
    comboActive = true;
    comboStart = millis();
    lastBothPressed = millis();
    hintShown = false;
  } else if (bothPressed && comboActive) {
    // Still holding both - update last pressed time
    lastBothPressed = millis();
    unsigned long elapsed = millis() - comboStart;
    
    // Show countdown after 0.5 seconds with progress
    if (elapsed > 500 && !hintShown) {
      lcdClear();
      lcdSetCursor(0, 0);
      lcdPrint("Diagnostics...");
      hintShown = true;
    }
    
    if (hintShown) {
      // Show progress bar
      uint8_t progress = (elapsed * 16) / 1500; // 0-16 chars for 1.5 seconds
      if (progress > 16) progress = 16;
      char progressBar[17] = "                ";
      for (uint8_t i = 0; i < progress; i++) {
        progressBar[i] = '=';
      }
      lcdSetCursor(0, 1);
      lcdPrintPadded(progressBar, 16);
    }
    
    if (elapsed > 1500) {
      // 1.5 seconds held - trigger diagnostics
      comboActive = false;
      hintShown = false;
      return true;
    }
  } else if (comboActive) {
    // One or both buttons released
    unsigned long timeSinceLastPress = millis() - lastBothPressed;
    
    // Allow brief release (up to 200ms) - more forgiving
    if (timeSinceLastPress > 200) {
      // Too long since both were pressed - cancel
      if (hintShown) {
        lcdClear();
      }
      comboActive = false;
      hintShown = false;
    }
    // Otherwise, keep waiting (buttons might be pressed again soon)
  }

  return false;
}

void runDiagnosticsMode() {
  updateButtons();
  unsigned long now = millis();

  if (buttonPressed(1)) {
    diagnosticsPage = (diagnosticsPage + 1) % DIAGNOSTIC_PAGE_COUNT;
    lastDiagnosticsRefresh = 0;
  } else if (buttonPressed(2)) {
    diagnosticsPage = (diagnosticsPage + DIAGNOSTIC_PAGE_COUNT - 1) % DIAGNOSTIC_PAGE_COUNT;
    lastDiagnosticsRefresh = 0;
  }

  static bool exitHold = false;
  static unsigned long exitStart = 0;
  bool btn3 = (digitalRead(BTN3_PIN) == LOW);
  if (btn3 && !exitHold) {
    exitHold = true;
    exitStart = now;
  } else if (btn3 && exitHold) {
    if (now - exitStart > 1500) {
      exitHold = false;
      diagnosticsActive = false;
      lcdClear();
      currentState = STATE_PET_NORMAL;
      return;
    }
  } else if (!btn3) {
    exitHold = false;
  }

  if (now - lastDiagnosticsRefresh < 400) {
    return;
  }
  lastDiagnosticsRefresh = now;

  lcdClear();
  char line[17];

  switch (diagnosticsPage) {
    case 0: {
      if (wifiConnectedFlag) {
        snprintf(line, sizeof(line), "WiFi:ON %s", lastWifiIp);
      } else if (wifiEverConnected) {
        snprintf(line, sizeof(line), "WiFi:LAST %s", lastWifiIp);
      } else {
        snprintf(line, sizeof(line), "WiFi:OFF --");
      }
      lcdSetCursor(0, 0);
      lcdPrintPadded(line, 16);

      if (timeSynced && lastNtpSyncMs > 0) {
        unsigned long mins = (now - lastNtpSyncMs) / 60000UL;
        if (mins > 99) mins = 99;
        snprintf(line, sizeof(line), "Sync:%2lum ago", mins);
      } else if (hasWiFiCredentials()) {
        snprintf(line, sizeof(line), "Sync:pending...");
      } else {
        snprintf(line, sizeof(line), "Sync:disabled ");
      }
      lcdSetCursor(0, 1);
      lcdPrintPadded(line, 16);
      break;
    }
    case 1: {
      uint8_t queueCount = (queueTail + 20 - queueHead) % 20;
      snprintf(line, sizeof(line), "BLE:%s Q:%02u", deviceConnected ? "LINK" : "SCAN", queueCount);
      lcdSetCursor(0, 0);
      lcdPrintPadded(line, 16);

      snprintf(line, sizeof(line), "Alert:%d Score:%02d", lastAssessment.alert_level, lastAssessment.total_score);
      lcdSetCursor(0, 1);
      lcdPrintPadded(line, 16);
      break;
    }
    case 2: {
      bool b1 = (digitalRead(BTN1_PIN) == LOW);
      bool b2 = (digitalRead(BTN2_PIN) == LOW);
      bool b3 = (digitalRead(BTN3_PIN) == LOW);
      snprintf(line, sizeof(line), "Btn1:%d Btn2:%d", b1, b2);
      lcdSetCursor(0, 0);
      lcdPrintPadded(line, 16);

      snprintf(line, sizeof(line), "Btn3:%d hold exit", b3);
      lcdSetCursor(0, 1);
      lcdPrintPadded(line, 16);
      break;
    }
    case 3: {
      snprintf(line, sizeof(line), "Mood:%3d Hun:%3d", pet.happiness, pet.hunger);
      lcdSetCursor(0, 0);
      lcdPrintPadded(line, 16);
      snprintf(line, sizeof(line), "Clean:%3d Risk:%d", pet.cleanliness, lastAssessment.alert_level);
      lcdSetCursor(0, 1);
      lcdPrintPadded(line, 16);
      break;
    }
  }
}

void handlePetInput() {
  static unsigned long btn3HoldStart = 0;
  static bool btn3Holding = false;
  
  updateButtons();
  
  if (currentMenu == MENU_MAIN) {
    if (buttonPressed(1)) { // Feed
      feedPet();
    } else if (buttonPressed(2)) { // Play
      playWithPet();
    } else if (btn3Pressed && !btn3Last) { // Button 3 just pressed
      btn3HoldStart = millis();
      btn3Holding = true;
    } else if (!btn3Pressed && btn3Last && btn3Holding) {
      // Button 3 released
      unsigned long pressDuration = millis() - btn3HoldStart;
      if (pressDuration > 1000) {
        // Long press: Open menu
        currentMenu = MENU_STATS;
        lastMenuChange = millis();
      } else if (pressDuration > 50) {
        // Short press: Clean
        cleanPet();
      }
      btn3Holding = false;
    } else if (btn3Pressed && btn3Holding && (millis() - btn3HoldStart > 1000)) {
      // Still holding after 1 second - show menu hint
      lcdClear();
      lcdSetCursor(0, 0);
      lcdPrint("Menu...");
      delay(100);
    }
  } else if (currentMenu == MENU_STATS) {
    // Check for history viewer trigger (hold Button 1 for 1 second)
    static unsigned long btn1HoldStart = 0;
    static bool btn1Holding = false;
    
    if (btn1Pressed && !btn1Last) {
      btn1HoldStart = millis();
      btn1Holding = true;
    } else if (!btn1Pressed && btn1Last && btn1Holding) {
      unsigned long holdDuration = millis() - btn1HoldStart;
      if (holdDuration > 1000) {
        // Open history viewer
        historyViewerActive = true;
        historyViewerIndex = 0;
        currentState = STATE_HISTORY_VIEWER;
        return;
      }
      btn1Holding = false;
    }
    
    if (buttonPressed(1) && !btn1Holding) { // Next: Mood
      currentMenu = MENU_MOOD;
      lastMenuChange = millis();
    } else if (buttonPressed(2)) { // Next: Games
      currentMenu = MENU_GAMES;
      lastMenuChange = millis();
    } else if (buttonPressed(3)) { // Back to main
      currentMenu = MENU_MAIN;
    }
  } else if (currentMenu == MENU_MOOD) {
    if (buttonPressed(1) || buttonPressed(2) || buttonPressed(3)) {
      checkMood();
    }
  } else if (currentMenu == MENU_GAMES) {
    if (buttonPressed(1)) { // Memory game
      playMemoryGame();
      return;
    } else if (buttonPressed(2)) { // Reaction game
      playWithPet();
      return;
    } else if (buttonPressed(3)) { // Back
      currentMenu = MENU_MAIN;
    }
  }
  
  // Auto-return to main menu after 10 seconds in sub-menus
  if (currentMenu != MENU_MAIN && millis() - lastMenuChange > 10000) {
    currentMenu = MENU_MAIN;
  }
}

// ==== Main Setup ====
void setup() {
  // Initialize Serial FIRST before anything else
  Serial.begin(115200);
  delay(2000);  // Give Serial more time to initialize (ESP32-S3 needs this)
  
  // Force flush and test Serial immediately
  Serial.flush();
  Serial.println("\n\n\n");
  Serial.println("========================================");
  Serial.println("CogniPet Serial Test - If you see this,");
  Serial.println("Serial Monitor is working!");
  Serial.println("========================================");
  Serial.flush();
  delay(500);
  
  pinMode(LED_PIN, OUTPUT);
  pinMode(BTN1_PIN, INPUT_PULLUP);
  pinMode(BTN2_PIN, INPUT_PULLUP);
  pinMode(BTN3_PIN, INPUT_PULLUP);

  Serial.println("\n=== CogniPet Starting ===");
  Serial.println("Serial initialized");
  Serial.flush();

  // ESP32-S3 I2C setup - try with frequency specification
  Serial.print("Initializing I2C on SDA=");
  Serial.print(SDA_PIN);
  Serial.print(" SCL=");
  Serial.println(SCL_PIN);
  
  bool i2cStarted = Wire.begin(SDA_PIN, SCL_PIN, 100000); // 100kHz I2C speed
  if (!i2cStarted) {
    Serial.println("ERROR: I2C begin failed!");
  } else {
    Serial.println("I2C initialized successfully");
  }
  delay(200);
  
  Serial.println("Starting I2C scan...");
  i2cScan();
  
  // Try to turn off RGB immediately (before LCD init)
  Serial.println("Attempting to turn off RGB backlight...");
  lastR = 255; lastG = 255; lastB = 255; // Force update
  lcdSetRGB(0, 0, 0); // Turn OFF RGB
  delay(200);
  
  // Test LCD communication
  Serial.println("Testing LCD communication...");
  Wire.beginTransmission(LCD_ADDR);
  uint8_t lcdError = Wire.endTransmission();
  if (lcdError == 0) {
    Serial.println("LCD responds to I2C");
  } else {
    Serial.print("LCD I2C error: ");
    Serial.println(lcdError);
  }

  lcdInit();
  
  // Set RGB to very dim after LCD is initialized
  delay(200);
  lastR = 255; lastG = 255; lastB = 255; // Force update
  lcdSetRGB(0, 0, 0); // Keep it OFF initially
  delay(300);
  lcdSetRGB(0, 5, 10); // Very dim blue for startup
  
  // Check if first boot
  if (isFirstBoot()) {
    currentState = STATE_ASSESSMENT;
    lcdClear();
    lcdSetCursor(3, 0);
    lcdPrint("Welcome!");
  lcdSetCursor(0, 1);
    lcdPrint("First setup");
    delay(2000);
  } else {
    currentState = STATE_PET_NORMAL;
    initializePet();
  }
  
  // Initialize BLE
  Serial.println("Initializing BLE...");
  setupBLE();
  Serial.println("BLE setup complete");

  initializeTimeService();
  
  // Initialize scheduling and adaptive difficulty
  initializeSchedule();
  initializeDifficulty();
  
  // Load assessment history from NVS
  loadAssessmentHistory();
  
  Serial.println("=== CogniPet initialized successfully ===");
  Serial.println("Ready for use!");
  Serial.println("BLE Device Name: CogniPet");
  Serial.println("Waiting for BLE connection...");
}

// ==== Main Loop ====
void loop() {
  maintainTimeService();
  // Handle BLE connection
  if (!deviceConnected && oldDeviceConnected) {
    delay(500);
    pServer->startAdvertising();
    Serial.println("Start advertising");
    oldDeviceConnected = deviceConnected;
  }
  if (deviceConnected && !oldDeviceConnected) {
    oldDeviceConnected = deviceConnected;
    // BLE just connected - retry pending data
    Serial.println("BLE connected, retrying pending data...");
    retryPendingData();
  }
  
  // Retry pending data periodically when BLE is connected
  if (deviceConnected) {
    retryPendingData();
  }
  
  // Check for serial export command
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "EXPORT" || cmd == "export") {
      exportHistoryToSerial();
    }
  }
  
  // Diagnostics backdoor: Always accessible (even during games) - Hold Button 2 + Button 3
  // This is useful for troubleshooting during gameplay
  if (currentState != STATE_DIAGNOSTICS && checkDiagnosticsBackdoor()) {
    diagnosticsActive = true;
    diagnosticsPage = 0;
    lastDiagnosticsRefresh = 0;
    lcdClear();
    currentState = STATE_DIAGNOSTICS;
  }
  
  // Other backdoors only when in pet normal mode or reminder mode (not during games/assessments)
  // Also exclude when in games menu to prevent accidental triggers during gameplay
  bool canCheckBackdoors = (currentState == STATE_PET_NORMAL || currentState == STATE_REMINDER) 
                           && currentMenu != MENU_GAMES;
  
  if (canCheckBackdoors) {
    // Assessment backdoor: Hold Button 1 + Button 2
    if (checkBackdoor()) {
      lcdClear();
      lcdSetCursor(2, 0);
      lcdPrint("Backdoor!");
      lcdSetCursor(0, 1);
      lcdPrint("Assessment...");
      delay(1500);
      currentState = STATE_ASSESSMENT;
      currentMenu = MENU_MAIN;
    }
    
    // Test data backdoor: Hold Button 1 + Button 3
    if (checkTestDataBackdoor()) {
      sendTestAssessmentData();
    }
  }
  
  // Check for assessment reminders (only in pet normal mode, and not in cooldown)
  if (currentState == STATE_PET_NORMAL && 
      millis() >= reminderCooldownUntil &&  // Cooldown period expired
      isAssessmentDue()) {
    currentState = STATE_REMINDER;
  }
  
  switch(currentState) {
    case STATE_ASSESSMENT:
      runCognitiveAssessment();
      markBootComplete();
      break;
      
    case STATE_PET_NORMAL:
      updatePetStats();
      handlePetInput();
      
      // Only draw screen if still in pet mode (backdoor might have changed state)
      if (currentState == STATE_PET_NORMAL) {
        drawPetScreen();
      }
      delay(100);
      break;

    case STATE_DIAGNOSTICS:
      runDiagnosticsMode();
      break;
      
    case STATE_REMINDER:
      handleReminder();
      // If reminder was dismissed or assessment started, state will change
      if (!isAssessmentDue() || currentState == STATE_ASSESSMENT) {
        // Reminder handled, return to pet mode
        if (currentState == STATE_REMINDER) {
          currentState = STATE_PET_NORMAL;
        }
      }
      break;
      
    case STATE_HISTORY_VIEWER:
      handleHistoryViewer();
      break;
      
    default:
      currentState = STATE_PET_NORMAL;
      break;
  }
  
  delay(50);
}

