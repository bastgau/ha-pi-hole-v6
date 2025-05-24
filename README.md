# Pi-hole V6 Integration for Home Assistant

[![Maintenair : bastgau](https://img.shields.io/badge/maintener-bastgau-orange?logo=github&logoColor=%23959da5&labelColor=%232d333a)](https://github.com/bastgau)
[![Made with Python](https://img.shields.io/badge/Made_with-Python-blue?style=flat&logo=python&logoColor=%23959da5&labelColor=%232d333a)](https://www.python.org/)
[![Made for Home Assistant](https://img.shields.io/badge/Made_for-Homeassistant-blue?style=flat&logo=homeassistant&logoColor=%23959da5&labelColor=%232d333a)](https://www.home-assistant.io/)
[![GitHub Release](https://img.shields.io/github/v/release/bastgau/ha-pi-hole-v6?logo=github&logoColor=%23959da5&labelColor=%232d333a&color=%230e80c0)](https://github.com/bastgau/ha-pi-hole-v6/releases)
[![HACS validation](https://github.com/bastgau/ha-pi-hole-v6/actions/workflows/validate-for-hacs.yml/badge.svg)](https://github.com/bastgau/ha-pi-hole-v6/actions/workflows/validate-for-hacs.yml)
[![HASSFEST validation](https://github.com/bastgau/ha-pi-hole-v6/actions/workflows/validate-with-hassfest.yml/badge.svg)](https://github.com/bastgau/ha-pi-hole-v6/actions/workflows/validate-with-hassfest.yml)

<p align="center" width="100%">
    <img src="https://brands.home-assistant.io/_/pi_hole_v6/logo.png">
</p>

Original component : [Pi-hole](https://www.home-assistant.io/integrations/pi_hole/)

> The Pi-hole integration allows you to retrieve statistics and interact with a Pi-hole system.

## Description

Due to major changes in the Pi-hole API, the native Home Assistant integration was no longer functional. 

The "Pi-hole V6 Integration" adds compatibility with the new API in Home Assistant. This integration aims to restore compatibility and provide Pi-hole management directly from Home Assistant.

## Features

- Monitor Pi-hole status.
- Enable/Disable Pi-hole via Home Assistant.
- Retrieve filtering statistics.
- Compatibility with the Pi-hole V6 API.

The following sensors are currently implemented :

<p align="center" width="100%">
    <img src="https://raw.githubusercontent.com/bastgau/ha-pi-hole-v6/develop/img/release-v1.12.0.png" width="800">
</p>

> [!NOTE]
> To perform the `flush/arp`, `flush/logs` and `restartdns` actions, the *'Permit destructive actions via API'* option must be enabled in the Pi-hole options.

## Translation

The integration is currently translated in few langages :

- Czech (thanks [@kukulich](https://github.com/kukulich))
- Dutch (thanks [@jverlaan](https://github.com/jverlaan))
- English
- French
- German (thanks Christian)
- Greek (thanks [@ChriZathens](https://github.com/ChriZathens))
- Norwegian (thanks [@emigrating](https://github.com/emigrating))
- Polish (thanks [@jacksonafide](https://github.com/jacksonafide))
- Russian (thanks [@ProFiLeR4100](https://github.com/ProFiLeR4100))
- Portuguese (Brazil) (thanks [@tangobones](https://github.com/tangobones))
- Slovak (thanks [@milandzuris](https://github.com/milandzuris))
- Spanish (thanks [@dmbuil](https://github.com/dmbuil))
- Swedish (thanks [@aleexolsson](https://github.com/aleexolsson))
- Turkish (thanks [@habil](https://github.com/habil))
- Ukrainian (thanks [@ProFiLeR4100](https://github.com/ProFiLeR4100))

## Installation

### Installation via HACS

1. Add this repository as a custom repository to HACS:

[![Add Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bastgau&repository=ha-pi-hole-v6&category=Integration)

2. Use HACS to install the integration.
3. Restart Home Assistant.
4. Set up the integration using the UI:

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=pi_hole_v6)


### Manual Installation

1. Download the integration files from the GitHub repository.
2. Place the integration folder in the custom_components directory of Home Assistant.
3. Restart Home Assistant.
4. Set up the integration using the UI:

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=pi_hole_v6)

## Pi-hole Card

After installing this integration, you can enhance your Home Assistant setup with the `Pi-hole Card`.  

This lovelace card offers a comprehensive and user-friendly dashboard designed specifically for managing and monitoring your Pi-hole DNS ad blocker. It provides real-time statistics and intuitive controls, all presented in a visually appealing interface that aligns with Pi-hole's design aesthetics.

The card is developed by [@warmfire540](https://github.com/warmfire540).  
The installation instructions are available on the repository: [homeassistant-extras / pi-hole-card](https://github.com/homeassistant-extras/pi-hole-card/).

<p align="center" width="100%">
    <img src="https://github.com/homeassistant-extras/pi-hole-card/raw/main/assets/pihole-card.png" width="300">
</p>



## Debugging

It is possible to show the info and debug logs for the Pi-hole V6 integration, to do this you need to enable logging in the configuration.yaml, example below:

```
logger:
  default: warning
  logs:
    # Log for Pi-hole V6 integation
    custom_components.pi_hole_v6: debug
```

Logs do not remove sensitive information so careful what you share, check what you are about to share and blank identifying information.

## Frequently Asked Questions

### How do I configure the refresh frequency?

By default, the data is updated every 5 minutes. You can configure a different frequency as explained on the following [page](docs/guide-configuring-refresh.md).

## Support & Contributions

If you encounter any issues or wish to contribute to improving this integration, feel free to open an issue or a pull request on the GitHub repository.

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/bastgau)

Enjoy!

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=bastgau/ha-pi-hole-v6&type=Date)](https://www.star-history.com/#bastgau/ha-pi-hole-v6&Date)
