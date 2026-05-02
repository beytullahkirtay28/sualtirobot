/*
 * RÜSUMAT 4 - Arduino Beyin
 * 6 BLDC ESC + 1 servo kontrol, Pi5 USB-Serial uzerinden komut alir.
 *
 * Ozellikler:
 * - char[] buffer (String yok, heap fragmentation yok)
 * - Watchdog timer (sketch hang olursa 2sn'de reset)
 * - 1 saniyede bir RDY heartbeat (Pi'nin handshake'i icin)
 * - 500ms failsafe (Pi kopukken motor durur)
 * - 3 farkli komut turu: joystick stream, motor test, kol direkt
 */

#include <Servo.h>
#include <avr/wdt.h>

// =================== AYARLAR ===================

// PIN tanimlari
const uint8_t MOTOR_PIN[6] = {3, 5, 6, 9, 10, 11};
const uint8_t KOL_PIN = 4;

// ESC (Bidirectional 30A, 1000-2000us)
const int ESC_MIN     = 1000;
const int ESC_NEUTRAL = 1500;
const int ESC_MAX     = 2000;
const int ESC_RANGE   = 500;
const float ESC_DEADZONE = 0.05;

// Servo (180 derece icin genis aralik)
const int KOL_MIN = 0;
const int KOL_MAX = 180;
const int KOL_PWM_MIN = 500;
const int KOL_PWM_MAX = 2500;

// Zaman ayarlari
const unsigned long TIMEOUT_MS    = 500;    // failsafe (Pi kopuk -> motor dur)
const unsigned long ARM_DELAY_MS  = 3000;   // ESC arming
const unsigned long HEARTBEAT_MS  = 1000;   // RDY frekans

// Buffer
const uint8_t BUF_SIZE = 96;

// =================== GLOBAL ===================

Servo motor[6];
Servo kol;

float ileri = 0;
float yaw   = 0;
float dikey = 0;
float roll  = 0;
int   kol_aci = 90;

unsigned long son_veri_ms      = 0;
unsigned long son_heartbeat_ms = 0;

char    buffer[BUF_SIZE];
uint8_t buf_len = 0;

// =================== HELPER ===================

int eksenToPwm(float v) {
  if (v >  1.0) v =  1.0;
  if (v < -1.0) v = -1.0;
  if (fabs(v) < ESC_DEADZONE) return ESC_NEUTRAL;
  return ESC_NEUTRAL + (int)(v * ESC_RANGE);
}

void motorlariYaz(float v[6]) {
  for (int i = 0; i < 6; i++) {
    motor[i].writeMicroseconds(eksenToPwm(v[i]));
  }
}

void durdur() {
  for (int i = 0; i < 6; i++) {
    motor[i].writeMicroseconds(ESC_NEUTRAL);
  }
}

void mix() {
  // Yerlesim: M1-M4 yatay, M5-M6 dikey
  // Yaw = sol/sag yatay differential, Roll = sol/sag dikey differential
  float v[6];
  v[0] = ileri + yaw;     // M1 on-sol
  v[1] = ileri - yaw;     // M2 on-sag
  v[2] = ileri + yaw;     // M3 arka-sol
  v[3] = ileri - yaw;     // M4 arka-sag
  v[4] = dikey + roll;    // M5 sol-dikey
  v[5] = dikey - roll;    // M6 sag-dikey

  // Tasma normalize
  float maks = 1.0;
  for (int i = 0; i < 6; i++) {
    float a = fabs(v[i]);
    if (a > maks) maks = a;
  }
  for (int i = 0; i < 6; i++) v[i] /= maks;

  motorlariYaz(v);
}

// =================== PARSE ===================

// "M,idx,val" -> tek motor test (idx 0 = hepsi durdur)
void parseMotorTest(const char* s) {
  // s = "idx,val"
  int idx = atoi(s);
  const char* p = strchr(s, ',');
  if (!p) return;
  float val = atof(p + 1);

  // Tum motorlari neutral, sadece istenen calisir
  for (int i = 0; i < 6; i++) {
    motor[i].writeMicroseconds(ESC_NEUTRAL);
  }
  if (idx >= 1 && idx <= 6) {
    motor[idx - 1].writeMicroseconds(eksenToPwm(val));
  }
}

// "K,angle" -> direkt kol acisi
void parseKolDirect(const char* s) {
  int a = atoi(s);
  if (a < KOL_MIN) a = KOL_MIN;
  if (a > KOL_MAX) a = KOL_MAX;
  kol_aci = a;
  kol.write(kol_aci);
}

// "sol_x,sol_y,sag_x,sag_y[,kol_aci]" -> joystick stream
void parseJoystick(const char* s) {
  float val[5] = {0, 0, 0, 0, (float)kol_aci};
  uint8_t idx = 0;
  char num[16];
  uint8_t n = 0;

  for (uint8_t i = 0; ; i++) {
    char c = s[i];
    if (c == ',' || c == 0) {
      num[n] = 0;
      val[idx++] = atof(num);
      n = 0;
      if (c == 0 || idx >= 5) break;
    } else if (n < sizeof(num) - 1) {
      num[n++] = c;
    }
  }

  if (idx < 4) return;   // bozuk paket

  yaw   =  val[0];   // sol_x  -> donus
  ileri = -val[1];   // sol_y  -> ileri/geri (Y ters)
  roll  =  val[2];   // sag_x  -> yan egim
  dikey = -val[3];   // sag_y  -> yukari/asagi (Y ters)

  if (idx >= 5) {
    int a = (int)val[4];
    if (a < KOL_MIN) a = KOL_MIN;
    if (a > KOL_MAX) a = KOL_MAX;
    kol_aci = a;
    kol.write(kol_aci);
  }

  mix();
}

void parse(const char* s) {
  if (s[0] == 0) return;

  if ((s[0] == 'M' || s[0] == 'm') && s[1] == ',') {
    parseMotorTest(s + 2);
  } else if ((s[0] == 'K' || s[0] == 'k') && s[1] == ',') {
    parseKolDirect(s + 2);
  } else {
    parseJoystick(s);
  }
  son_veri_ms = millis();
}

// =================== SETUP / LOOP ===================

void setup() {
  // Watchdog kapat (boot'ta tetiklenmesin)
  wdt_disable();

  Serial.begin(115200);

  // Motor + servo init
  for (int i = 0; i < 6; i++) {
    motor[i].attach(MOTOR_PIN[i]);
    motor[i].writeMicroseconds(ESC_NEUTRAL);
  }
  kol.attach(KOL_PIN, KOL_PWM_MIN, KOL_PWM_MAX);
  kol.write(kol_aci);

  // ESC arm bekleme + seri buffer'i temiz tut
  unsigned long arm_start = millis();
  while (millis() - arm_start < ARM_DELAY_MS) {
    while (Serial.available()) Serial.read();
  }

  // Pi'ya hazir oldugumu bildir
  Serial.println("RDY");
  son_veri_ms = millis();
  son_heartbeat_ms = millis();

  // Watchdog'u 2 saniyeye ayarla. Loop hang olursa kendini resetler.
  wdt_enable(WDTO_2S);
}

void loop() {
  // Seri okuma
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      buffer[buf_len] = 0;
      parse(buffer);
      buf_len = 0;
    } else if (c != '\r' && buf_len < BUF_SIZE - 1) {
      buffer[buf_len++] = c;
    } else if (buf_len >= BUF_SIZE - 1) {
      // Buffer tasmasi: at, sifirla
      buf_len = 0;
    }
  }

  // Failsafe: Pi kopukken motorlari durdur
  if (millis() - son_veri_ms > TIMEOUT_MS) {
    durdur();
  }

  // Heartbeat: Pi'ya ben buradayim sinyali
  if (millis() - son_heartbeat_ms > HEARTBEAT_MS) {
    Serial.println("RDY");
    son_heartbeat_ms = millis();
  }

  // Watchdog'u besle
  wdt_reset();
}
