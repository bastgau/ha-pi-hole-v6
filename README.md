# Pi-Hole V6 Integration for Home Assistant

[![Maintenair : bastgau](https://img.shields.io/badge/maintener-bastgau-orange?logo=github&logoColor=%23959da5&labelColor=%232d333a)](https://github.com/bastgau)
[![Made with Python](https://img.shields.io/badge/Made_with-Python-blue?style=flat&logo=python&logoColor=%23959da5&labelColor=%232d333a)](https://www.python.org/)
[![Made for Home Assistant](https://img.shields.io/badge/Made_for-Homeassistant-blue?style=flat&logo=homeassistant&logoColor=%23959da5&labelColor=%232d333a)](https://www.home-assistant.io/)
[![GitHub Release](https://img.shields.io/github/v/release/bastgau/ha-pi-hole-v6?logo=github&logoColor=%23959da5&labelColor=%232d333a&color=%230e80c0)](https://github.com/bastgau/ha-custom-universal-media-player/releases)
[![HACS validation](https://github.com/bastgau/ha-pi-hole-v6/actions/workflows/validate-for-hacs.yml/badge.svg)](https://github.com/bastgau/ha-custom-universal-media-player/actions/workflows/validate-for-hacs.yml)
[![HASSFEST validation](https://github.com/bastgau/ha-pi-hole-v6/actions/workflows/validate-with-hassfest.yml/badge.svg)](https://github.com/bastgau/ha-custom-universal-media-player/actions/workflows/validate-with-hassfest.yml)

<p align="center" width="100%">
    <img src="https://brands.home-assistant.io/_/pi_hole_v6/logo.png">
</p>

Original component : [Pi-hole](https://www.home-assistant.io/integrations/pi_hole/)

> The Pi-hole integration allows you to retrieve statistics and interact with a Pi-hole system.

## Description

Due to major changes in the Pi-Hole API, the native Home Assistant integration was no longer functional. 

The "Pi-Hole V6 Integration" adds compatibility with the new API in Home Assistant. This integration aims to restore compatibility and provide Pi-Hole management directly from Home Assistant.

## Features

- Monitor Pi-Hole status.
- Enable/Disable Pi-Hole via Home Assistant.
- Retrieve filtering statistics.
- Compatibility with the Pi-Hole V6 API.

The following sensors are currently implemented :

<p align="center" width="100%">
    <img src="img/release-v1.6.0.png" width="600">
</p>

## Translation

The integration is currently translated in few langages :

- Czech (thanks [@kukulich](https://github.com/kukulich))
- English
- French

## Installation

### Installation via HACS

1. Open Home Assistant and go to HACS.
2. Navigate to "Integrations" and click on "Add a custom repository".
3. Add the GitHub repository URL of the integration.
4. Search for "Pi-Hole V6 Integration" and install it.
5. Restart Home Assistant.

### Manual Installation

1. Download the integration files from the GitHub repository.
2. Place the integration folder in the custom_components directory of Home Assistant.
3. Restart Home Assistant.


### Support & Contributions

If you encounter any issues or wish to contribute to improving this integration, feel free to open an issue or a pull request on the GitHub repository.

Enjoy!
