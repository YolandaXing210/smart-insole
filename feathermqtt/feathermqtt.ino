/***************************************************
README!! IMPORTANT!!

This code works with a Feather M0 with WINC1500 module.
API KEYS ARE REQUIRED. Contact Demi Hu dh785@cornell.edu for the keys.h file.
Or, create your own keys.h file containing the following:
#define AIO_USERNAME    "your adafruit io username"
#define AIO_KEY         "your adafruit io key"

IF USING CORNELL WIFI:
1. Run this code once. It will print the MAC Address to serial.
2. Go to https://dnsdb.cit.cornell.edu/dnsdb-cgi/mycomputers.cgi
3. Register your device using the MAC Address printed.
4. Run the code again.

IF USING HOME WIFI:
1. Change ssid to: char ssid[] = "Your Wifi Name";
2. Add this line: char pass[] = "Your Wifi Password";
3. Change Wifi.begin to: status = WiFi.begin(ssid, pass);
4. Run the code.

TIPS:
Lines of code that might require changing will have a comment containing "REPLACE ME" above.
CTRL+F to search for these lines.

/***************************************************



/***************************************************
  Adafruit MQTT Library WINC1500 Example

  Adafruit invests time and resources providing this open source code,
  please support Adafruit and open-source hardware by purchasing
  products from Adafruit!

  Written by Limor Fried/Ladyada for Adafruit Industries.
  MIT license, all text above must be included in any redistribution
 ****************************************************/
#include <SPI.h>
#include "Adafruit_MQTT.h"
#include "Adafruit_MQTT_Client.h"
#include <WiFi101.h>
#include "keys.h"

/************************* WiFI Setup *****************************/
#define WINC_CS   8
#define WINC_IRQ  7
#define WINC_RST  4
#define WINC_EN   2     // or, tie EN to VCC

// REPLACE ME WIFI
char ssid[] = "RedRover";
//char ssid[] = "SpectrumSetup-1F";     //  your network SSID (name)
// char pass[] = "littlegate012";    // your network password (use for WPA, or use as key for WEP)
int keyIndex = 0;                // your network key Index number (needed only for WEP)

int status = WL_IDLE_STATUS;

/************************* Adafruit.io Setup *********************************/

// #define AIO_SERVER      "io.adafruit.com"
// #define AIO_SERVERPORT  1883
#define AIO_SERVER      "broker.hivemq.com"
#define AIO_SERVERPORT  1883
// REPLACE ME ADAFRUIT IO SETUP
//#define AIO_USERNAME    "your adafruit io username"
//#define AIO_KEY         "your adafruit io key"

/************ Global State (you don't need to change this!) ******************/

//Set up the wifi client
WiFiClient client;
Adafruit_MQTT_Client mqtt(&client, AIO_SERVER, AIO_SERVERPORT, AIO_USERNAME, AIO_KEY);

// You don't need to change anything below this line!
#define halt(s) { Serial.println(F( s )); while(1);  }

/****************************** Feeds ***************************************/

// Setup a feed called 'photocell' for publishing.
// Notice MQTT paths for AIO follow the form: <username>/feeds/<feedname>

// REPLACE ME IO FEED NAME
Adafruit_MQTT_Publish insole = Adafruit_MQTT_Publish(&mqtt, "demihu/feeds/insole");

// Setup a feed called 'onoff' for subscribing to changes.
Adafruit_MQTT_Subscribe onoffbutton = Adafruit_MQTT_Subscribe(&mqtt, "demihu/feeds/onoff");

/****************************** RX/TX Setup ***************************************/
static constexpr uint8_t kPortAGroup = 0;
static constexpr uint8_t kPeripheralFunctionB = 1;

static constexpr uint8_t kRxPortPin = 11;  // D0 / RX / PA11
static constexpr uint8_t kTxPortPin = 10;  // D1 / TX / PA10

static constexpr uint8_t kRxAdcChannel = 19;
static constexpr uint8_t kTxAdcChannel = 18;

static void syncADC() {
  while (ADC->STATUS.bit.SYNCBUSY == 1) {}
}

static void disconnectSerial1Pads() {
  SERCOM0->USART.CTRLA.bit.ENABLE = 0;
  while (SERCOM0->USART.SYNCBUSY.bit.ENABLE) {}

  SERCOM0->USART.CTRLB.reg = 0;
  while (SERCOM0->USART.SYNCBUSY.bit.CTRLB) {}

  SERCOM0->USART.CTRLA.bit.SWRST = 1;
  while (SERCOM0->USART.SYNCBUSY.bit.SWRST || SERCOM0->USART.CTRLA.bit.SWRST) {}
}

static void routeRxTxPadsToAdc() {
  PORT->Group[kPortAGroup].DIRCLR.reg = (1ul << kRxPortPin) | (1ul << kTxPortPin);
  PORT->Group[kPortAGroup].OUTCLR.reg = (1ul << kRxPortPin) | (1ul << kTxPortPin);

  PORT->Group[kPortAGroup].PINCFG[kRxPortPin].reg = PORT_PINCFG_PMUXEN;
  PORT->Group[kPortAGroup].PINCFG[kTxPortPin].reg = PORT_PINCFG_PMUXEN;

  PORT->Group[kPortAGroup].PMUX[kTxPortPin >> 1].reg =
      PORT_PMUX_PMUXE(kPeripheralFunctionB) |
      PORT_PMUX_PMUXO(kPeripheralFunctionB);
}

static uint16_t readAdcChannel(uint8_t channel) {
  syncADC();
  ADC->INPUTCTRL.bit.MUXPOS = channel;
  syncADC();

  ADC->CTRLA.bit.ENABLE = 1;
  syncADC();

  ADC->SWTRIG.bit.START = 1;
  while (ADC->INTFLAG.bit.RESRDY == 0) {}
  ADC->INTFLAG.reg = ADC_INTFLAG_RESRDY;

  const uint16_t result = ADC->RESULT.reg;

  ADC->CTRLA.bit.ENABLE = 0;
  syncADC();

  return result;
}

static uint16_t analogReadRXDirect() {
  return readAdcChannel(kRxAdcChannel);
}

static uint16_t analogReadTXDirect() {
  return readAdcChannel(kTxAdcChannel);
}

/*************************** Sketch Code ************************************/

#define LEDPIN 13

// LED on
#define LED1 10
#define LED2 11

// Photodiodes, named as in "Smart Shoe Sensor Layout.pdf" (pins checked on the shoe with a press test)
#define PD1 A2
#define PD2 A1
#define PD3 PIN_SERIAL1_TX  // TX. PD3 and PD8 fibers are dead, so TX vs A0 between them is unconfirmed
#define PD4 A3
#define PD5 A4
#define PD6 A5
#define PD7 PIN_SERIAL1_RX  // RX
#define PD8 A0

const uint8_t pdPins[] = { PD1, PD2, PD3, PD4, PD5, PD6, PD7, PD8 };
const char* pdNames[] = { "PD1", "PD2", "PD3", "PD4", "PD5", "PD6", "PD7", "PD8"};
const uint8_t NUM_PDS  = 8;
char payload[64];   // CSV buffer for MQTT


void setup() {
  WiFi.setPins(WINC_CS, WINC_IRQ, WINC_RST, WINC_EN);

  while (!Serial);
  Serial.begin(115200);

  // Initialise the Client
  Serial.print(F("\nInit the WiFi module..."));
  // check for the presence of the breakout
  if (WiFi.status() == WL_NO_SHIELD) {
    Serial.println("WINC1500 not present");
    // don't continue:
    while (true);
  }
  Serial.println("ATWINC OK!");

  byte mac[6];
WiFi.macAddress(mac);

Serial.print("Device MAC Address: ");
for (int i = 5; i >= 0; i--) {
  if (mac[i] < 16) Serial.print("0");
  Serial.print(mac[i], HEX);
  if (i > 0) Serial.print(":");
}
Serial.println();
  
  pinMode(LEDPIN, OUTPUT);
  pinMode(LED1, OUTPUT);
  pinMode(LED2, OUTPUT);

  // turn LEDs on
  digitalWrite(LED1, HIGH);
  digitalWrite(LED2, HIGH);

  // read TX/RX
  analogReadResolution(12);
  analogReference(AR_DEFAULT);

  pinMode(10, OUTPUT);
  pinMode(11, OUTPUT);
  digitalWrite(10, HIGH);
  digitalWrite(11, HIGH);

  disconnectSerial1Pads();
  routeRxTxPadsToAdc();

  mqtt.subscribe(&onoffbutton);
}

// blank string for MQTT
uint32_t x=0;

void loop() {
  // Ensure the connection to the MQTT server is alive (this will make the first
  // connection and automatically reconnect when disconnected).  See the MQTT_connect
  // function definition further below.
  MQTT_connect();

  // this is our 'wait for incoming subscription packets' busy subloop
  Adafruit_MQTT_Subscribe *subscription;
  while ((subscription = mqtt.readSubscription(100))) { // change this to increase speed
    if (subscription == &onoffbutton) {
      Serial.print(F("Got: "));
      Serial.println((char *)onoffbutton.lastread);

      if (0 == strcmp((char *)onoffbutton.lastread, "OFF")) {
        digitalWrite(LEDPIN, LOW);
      }
      if (0 == strcmp((char *)onoffbutton.lastread, "ON")) {
        digitalWrite(LEDPIN, HIGH);
      }
    }
  }

  payload[0] = '\0';  // reset CSV buffer

for (uint8_t i = 0; i < NUM_PDS; i++) {
  //int value = analogRead(pdPins[i]);
  int value;

    // RX/TX can't use analogRead(), so they go through the direct ADC reads
    if (pdPins[i] == PIN_SERIAL1_RX) {
      value = analogReadRXDirect();
    }
    else if (pdPins[i] == PIN_SERIAL1_TX) {
      value = analogReadTXDirect();
    }
    else {
      value = analogRead(pdPins[i]);
    }

  char num[8];
  snprintf(num, sizeof(num), "%d", value);
  strncat(payload, num, sizeof(payload) - strlen(payload) - 1);

  if (i < NUM_PDS - 1) {
    strncat(payload, ",", sizeof(payload) - strlen(payload) - 1);
  }
}

Serial.print(F("\nSending PD readings:"));
Serial.print(payload);
Serial.print("... ");

if (!insole.publish(payload)) {
  Serial.println(F("Failed"));
} else {
  Serial.println(F("OK!"));
}

}

// Function to connect and reconnect as necessary to the MQTT server.
// Should be called in the loop function and it will take care if connecting.
void MQTT_connect() {
  int8_t ret;

  // attempt to connect to Wifi network:
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print("Attempting to connect to SSID: ");
    Serial.println(ssid);
    // Connect to WPA/WPA2 network. Change this line if using open or WEP network:
    status = WiFi.begin(ssid);  // no pass for RedRover

    // wait 10 seconds for connection:
    uint8_t timeout = 10;
    while (timeout && (WiFi.status() != WL_CONNECTED)) {
      timeout--;
      delay(1000);  
    }

    if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi connection failed, retrying...");
  }
  }
  
  // Stop if already connected.
  if (mqtt.connected()) {
    return;
  }

  Serial.print("Connecting to MQTT... ");

  while ((ret = mqtt.connect()) != 0) { // connect will return 0 for connected
       Serial.println(mqtt.connectErrorString(ret));
       Serial.println("Retrying MQTT connection in 5 seconds...");
       mqtt.disconnect();
       delay(5000);  // wait 5 seconds
  }
  Serial.println("MQTT Connected!");
}