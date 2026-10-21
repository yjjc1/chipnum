"""Category taxonomy for semiconductor and electronic parts."""

from __future__ import annotations

CATEGORIES: dict[str, str] = {
    "mcu": "Microcontroller",
    "cpu": "CPU / Processor",
    "soc": "SoC / Application Processor",
    "gpu": "GPU / Graphics",
    "ai_accelerator": "AI Accelerator",
    "dsp": "DSP",
    "memory": "Memory",
    "analog": "Analog / Mixed-signal",
    "power": "Power Management",
    "power_module": "Power Module",
    "discrete": "Discrete Semiconductor",
    "transistor": "Transistor",
    "motor_driver": "Motor Driver",
    "logic": "Logic IC",
    "connectivity": "Connectivity",
    "wireless": "Wireless / RF",
    "rf": "RF Front-end",
    "digital_interface": "Digital Interface",
    "automotive": "Automotive",
    "sensor": "Sensor",
    "display": "Display Driver",
    "audio": "Audio",
    "programmable_logic": "Programmable Logic",
    "capacitor": "Capacitor",
    "inductor": "Inductor",
    "resistor": "Resistor",
    "foundry": "Foundry",
    "tooling": "Tooling / Debug",
    "unknown": "Unclassified",
}


def category_label(cat_id: str) -> str:
    """Return the human-readable label for a category id."""
    return CATEGORIES.get(cat_id, "Unclassified")