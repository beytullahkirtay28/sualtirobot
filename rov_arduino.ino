#include <Servo.h>

// --- PIN ---
const uint8_t MOTOR_PIN[6] = {3, 5, 6, 9, 10, 11};
const uint8_t KOL_PIN = 4;

// --- ESC (Bidirectional 30A, 1000-2000us) ---
const int ESC_MIN     = 1000;   // tam ters yon
const int ESC_NEUTRAL = 1500;   // dur
const int ESC_MAX     = 2000;   // tam ileri yon
const int ESC_RANGE   = 500;    // neutral +- range (tam guc)
const float ESC_DEADZONE = 0.05;  // |v| < bu degerse motor durur (titreme onler)

// --- SERVO (kol) ---
const int KOL_MIN = 0;
const int KOL_MAX = 180;
// Genis aralik: servo'nun tam 180 derece donmesi icin
// (1000-2000 araligi cogu dijital servoda sadece ~90 derece doner)
const int KOL_PWM_MIN = 500;    // 0 derece icin darbe genisligi (us)
const int KOL_PWM_MAX = 2500;   // 180 derece icin darbe genisligi (us)

// --- FAILSAFE ---
const unsigned long TIMEOUT_MS = 500;

// --- ARM ---
const unsigned long ARM_DELAY_MS = 3000;

Servo motor[6];
Servo kol;

// Kontrol eksenleri
float ileri = 0;   // +ileri / -geri      (sol stick Y)
float yaw   = 0;   // +saga / -sola donus (sol stick X)
float dikey = 0;   // +yukari / -asagi    (sag stick Y)
float roll  = 0;   // +saga egim / -sola  (sag stick X)
int   kol_aci = 90;

unsigned long son_veri_ms = 0;
String buffer = "";

int eksenToPwm(float v) {
  if (v >  1.0) v =  1.0;
  if (v < -1.0) v = -1.0;
  if (fabs(v) < ESC_DEADZONE) return ESC_NEUTRAL;   // kucuk titremeleri yut
  return ESC_NEUTRAL + (int)(v * ESC_RANGE);        // dogrusal orantili
}

void motorlariYaz(float v[6]) {
  for (int i = 0; i < 6; i++) motor[i].writeMicroseconds(eksenToPwm(v[i]));
}

void durdur() {
  for (int i = 0; i < 6; i++) motor[i].writeMicroseconds(ESC_NEUTRAL);
}

void mix() {
  // Yerlesim:
  //   M1 (pin 3)  on-sol  yatay
  //   M2 (pin 5)  on-sag  yatay
  //   M3 (pin 6)  arka-sol yatay
  //   M4 (pin 9)  arka-sag yatay
  //   M5 (pin 10) sol  dikey
  //   M6 (pin 11) sag  dikey
  //
  // Yatay 4 motor: hepsi ileri/geri yonunde paralel.
  //   Yaw, sol-taraf vs sag-taraf differential ile saglanir.
  // Dikey 2 motor: yukari/asagi.
  //   Roll, sol-dikey vs sag-dikey differential ile saglanir.
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

// Tek motor test: "M,idx,val"  (idx=0 -> hepsi neutral, idx 1..6)
void parseMotorTest(String s) {
  int c1 = s.indexOf(',');
  int c2 = s.indexOf(',', c1 + 1);
  if (c1 < 0 || c2 < 0) return;
  int idx   = s.substring(c1 + 1, c2).toInt();
  float val = s.substring(c2 + 1).toFloat();

  // Tum motorlari neutral'a al
  for (int i = 0; i < 6; i++) motor[i].writeMicroseconds(ESC_NEUTRAL);

  // Sadece istenen motoru calistir
  if (idx >= 1 && idx <= 6) {
    motor[idx - 1].writeMicroseconds(eksenToPwm(val));
  }
}

// Direkt kol acisi: "K,angle"
void parseKolDirect(String s) {
  int c1 = s.indexOf(',');
  if (c1 < 0) return;
  int a = s.substring(c1 + 1).toInt();
  if (a < KOL_MIN) a = KOL_MIN;
  if (a > KOL_MAX) a = KOL_MAX;
  kol_aci = a;
  kol.write(kol_aci);
}

// Standart joystick stream: "sol_x,sol_y,sag_x,sag_y[,kol_aci]"
void parseJoystick(String s) {
  float val[5] = {0, 0, 0, 0, (float)kol_aci};
  int idx = 0, start = 0;
  int n = s.length();
  for (int i = 0; i <= n && idx < 5; i++) {
    if (i == n || s[i] == ',') {
      val[idx++] = s.substring(start, i).toFloat();
      start = i + 1;
    }
  }
  if (idx < 4) return;   // bozuk paket -> atla

  yaw   =  val[0];   // sol_x  -> donus (saga +)
  ileri = -val[1];   // sol_y  -> ileri/geri (joystick Y ters)
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

void parse(String s) {
  if (s.length() == 0) return;

  if (s.startsWith("M,") || s.startsWith("m,")) {
    parseMotorTest(s);
  } else if (s.startsWith("K,") || s.startsWith("k,")) {
    parseKolDirect(s);
  } else {
    parseJoystick(s);
  }
  son_veri_ms = millis();
}

void setup() {
  Serial.begin(115200);

  for (int i = 0; i < 6; i++) {
    motor[i].attach(MOTOR_PIN[i]);
    motor[i].writeMicroseconds(ESC_NEUTRAL);
  }
  kol.attach(KOL_PIN, KOL_PWM_MIN, KOL_PWM_MAX);
  kol.write(kol_aci);

  delay(ARM_DELAY_MS);   // ESC arm
  son_veri_ms = millis();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      parse(buffer);
      buffer = "";
    } else if (c != '\r' && buffer.length() < 80) {
      buffer += c;
    }
  }

  if (millis() - son_veri_ms > TIMEOUT_MS) durdur();   // failsafe
}
