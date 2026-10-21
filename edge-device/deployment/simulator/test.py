import json
import sys
import time
import random
import argparse
import yaml

from scenarios import (
    ThermalRunawayScenario,
    MemoryLeakScenario,
    IntermittentErrorScenario,
    SilentDeviceScenario,
    STATUS_OFF,
    STATUS_BOOTING,
    STATUS_PREHEAT,
    STATUS_STANDBY,
    STATUS_BREWING,
    STATUS_UPDATING,
    STATUS_DEGRADED,
    STATUS_ERROR,
)


class MachineLifecycle:

  def __init__(self, cfg, rng: random.Random):
    self.cfg = cfg
    self.rng = rng
    self.state = STATUS_BOOTING
    self.seconds_in_state = 0.0
    self.uptime_seconds = 0.0  # Assurez-vous d'avoir un compteur d'uptime

    self._brew_timer = self._sample_range("standby_before_brew_seconds")
    self._update_timer = self._sample_range("standby_before_update_seconds")
    self._update_pending = True
    self._off_timer = None
    self._off_duration = self._sample_range("off_duration_seconds")

  def _sample_range(self, key):
    # Simulation de la méthode de tirage aléatoire selon votre config
    val = self.cfg.get(key, 10)
    if isinstance(val, list):
      return self.rng.uniform(val[0], val[1])
    return val

  def generate_payload(
      self, temperature_c, power_mw, heap_free_bytes, status, error_bits
  ):
    """Génère le dictionnaire de télémétrie pour le device."""
    payload = {
        "timestamp": int(time.time() * 1000),
        "device_id": self.cfg.get("device_id", "coffee_machine_01"),
        "uptime_ms": int(self.uptime_seconds * 1000),
        "temperature_c": round(temperature_c, 2),
        "power_consumption_mw": round(power_mw, 1),
        "heap_free_bytes": int(heap_free_bytes),
        "device_status": status,
        "error_code": error_bits,
    }
    return payload

def load_config(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def main():
  parser = argparse.ArgumentParser(description="Coffee machine data simulator")
  parser.add_argument(
      "--config", default="config.yaml", help="Path to config YAML file"
  )
  parser.add_argument(
      "--ground-truth",
      default="ground_truth.log",
      help="Path to instructor ground-truth log",
  )
  args = parser.parse_args()

  # Chargement de la config
  cfg = load_config(args.config)

  print("--- Contenu de la configuration (YAML) ---")
  print(yaml.dump(cfg, default_flow_style=False, allow_unicode=True))
  print("-" * 40)

  # Initialisation du cycle de vie et d'un générateur aléatoire
  rng = random.Random(42)
  machine = MachineLifecycle(cfg, rng)

  # Exemple de test pour vérifier la taille avec des valeurs fictives
  sample_payload = machine.generate_payload(
      temperature_c=85.678,
      power_mw=1250.4,
      heap_free_bytes=204800,
      status="STATUS_PREHEAT",
      error_bits=0,
  )

  # Affichage détaillé de chaque élément
  print("--- Analyse détaillée de chaque élément du payload ---")
  for key, value in sample_payload.items():
    val_type = type(value).__name__
    mem_size = sys.getsizeof(value)
    val_json = json.dumps({key: value})
    json_size = len(val_json.encode("utf-8"))

    print(f"• Clé : {key}")
    print(f"    - Valeur       : {value}")
    print(f"    - Type Python  : {val_type}")
    print(f"    - Taille RAM   : {mem_size} octets (objet Python)")
    print(f"    - Taille JSON  : {json_size} octets (texte réseau)")

  # Affichage de la taille totale du payload complet
  payload_string = json.dumps(sample_payload)
  total_json_size = len(payload_string.encode("utf-8"))
  print("-" * 50)
  print(f"-> Taille totale du payload JSON complet : {total_json_size} octets")

if __name__ == "__main__":
  main()