#pragma once

#include <string>

namespace ar_assembly_guard {

enum class Decision { none, soft_pause, hard_stop, sensor_timeout };

class Hook {
 public:
  virtual ~Hook() = default;
  virtual void prepareForMotion() = 0;
  virtual void arm() = 0;
  virtual Decision poll(std::string &reason) = 0;
  virtual void publishState(const std::string &state,
                            const std::string &detail) = 0;
};

extern Hook *active_hook;

}  // namespace ar_assembly_guard
