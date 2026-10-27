#pragma once
#include <Arduino.h>

// Simple line-based protocol: COMMAND,request_id\n
// Examples: STATUS,42 | STAND,43 | STOP,44 | CALIBRATE,45 | BALANCE,46
// Avoid actuator values over serial; the firmware owns safety limits.
class Communication {
 public:
  using CommandHandler = void (*)(const String&, const String&);
  void begin(Stream& stream) { stream_ = &stream; }
  unsigned long lastCommandMillis() const { return lastCommandMs_; }

  void poll(CommandHandler handler) {
    if (!stream_) return;
    while (stream_->available()) {
      const char c = (char)stream_->read();
      if (c == '\r') continue;
      if (c == '\n') {
        if (buffer_.length() > 0) {
          parseLine(buffer_, handler);
          buffer_ = "";
        }
      } else if (buffer_.length() < MAX_LINE) {
        buffer_ += c;
      } else {
        buffer_ = "";
        sendAck("0", false, "MESSAGE_TOO_LONG");
      }
    }
  }

  void sendAck(const String& id, bool ok, const String& detail) {
    emit("ACK," + id + "," + String(ok ? "OK" : "ERROR") + "," + detail);
  }
  void sendStatus(const String& id, const String& state, const String& fault) {
    emit("STATUS," + id + "," + state + "," + fault);
  }
  void sendBootStatus(bool ready, const String& state) {
    emit("BOOT,1," + String(ready ? "READY" : "NOT_READY") + "," + state);
  }
  void sendTelemetry(const String& state, float pitch, float gyro,
                     const String& fault, float output) {
    emit("TEL,1," + state + "," + String(pitch, 3) + "," +
         String(gyro, 3) + "," + fault + "," + String(output, 3));
  }

 private:
  static const uint8_t MAX_LINE = 80;
  Stream* stream_ = nullptr;
  String buffer_;
  unsigned long lastCommandMs_ = 0;

  void emit(const String& s) {
    if (stream_) stream_->println(s);
  }
  void parseLine(const String& line, CommandHandler handler) {
    const int comma = line.indexOf(',');
    if (comma <= 0) { sendAck("0", false, "BAD_FORMAT"); return; }
    const String cmd = line.substring(0, comma);
    String id = line.substring(comma + 1);
    if (id.length() == 0 || id.length() > 16) {
      sendAck("0", false, "BAD_REQUEST_ID"); return;
    }
    // Restrict command alphabet to simple uppercase names.
    for (unsigned int i = 0; i < cmd.length(); ++i) {
      if (!(cmd[i] >= 'A' && cmd[i] <= 'Z' || cmd[i] == '_')) {
        sendAck(id, false, "BAD_COMMAND"); return;
      }
    }
    lastCommandMs_ = millis();
    if (handler) handler(cmd, id);
  }
};
