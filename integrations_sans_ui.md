# Intégrations Home Assistant sans UI (config YAML uniquement)

Généré depuis le package `homeassistant` 2026.7.0 installé dans le dev container. Liste des intégrations de type `hub` (des intégrations tierces classiques, hors helpers/system/virtual internes) qui n'ont pas de `config_flow` — elles ne peuvent donc être configurées que via `configuration.yaml`, pas via l'UI (Paramètres > Appareils et services).

**Total : 301 intégrations**, triées par nombre d'installations décroissant (source : Home Assistant Analytics).

| # | Domaine | Nom | Installations | Description | Classe IoT | Documentation |
|---|---|---|---|---|---|---|
| 1 | `hassio` | Home Assistant Supervisor | 418 163 | Support for Hass.io. | local_polling | [lien](https://www.home-assistant.io/integrations/hassio) |
| 2 | `rest_command` | RESTful Command | 31 993 | Support for exposing regular REST commands as services. | local_push | [lien](https://www.home-assistant.io/integrations/rest_command) |
| 3 | `shell_command` | Shell Command | 31 928 | Expose regular shell commands as services. | local_push | [lien](https://www.home-assistant.io/integrations/shell_command) |
| 4 | `command_line` | Command Line | 23 668 | The command_line component. | local_polling | [lien](https://www.home-assistant.io/integrations/command_line) |
| 5 | `modbus` | Modbus | 15 793 | Support for Modbus. | local_polling | [lien](https://www.home-assistant.io/integrations/modbus) |
| 6 | `python_script` | Python Scripts | 11 725 | Component to allow running Python scripts. | — | [lien](https://www.home-assistant.io/integrations/python_script) |
| 7 | `telegram` | Telegram | 9 059 | The telegram component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/telegram) |
| 8 | `emulated_hue` | Emulated Hue | 4 985 | Support for local control of entities by emulating a Philips Hue bridge. | local_push | [lien](https://www.home-assistant.io/integrations/emulated_hue) |
| 9 | `mqtt_room` | MQTT Room Presence | 3 887 | The mqtt_room component. | local_push | [lien](https://www.home-assistant.io/integrations/mqtt_room) |
| 10 | `prometheus` | Prometheus | 3 239 | Support for Prometheus metrics export. | assumed_state | [lien](https://www.home-assistant.io/integrations/prometheus) |
| 11 | `snmp` | SNMP | 3 213 | The SNMP integration. | local_polling | [lien](https://www.home-assistant.io/integrations/snmp) |
| 12 | `intent_script` | Intent Script | 3 026 | Handle intents with scripts. | — | [lien](https://www.home-assistant.io/integrations/intent_script) |
| 13 | `universal` | Universal media player | 2 706 | The universal component. | calculated | [lien](https://www.home-assistant.io/integrations/universal) |
| 14 | `evohome` | Honeywell Total Connect Comfort (Europe) | 2 022 | Support for (EMEA/EU-based) Honeywell TCC systems. | cloud_polling | [lien](https://www.home-assistant.io/integrations/evohome) |
| 15 | `meteoalarm` | MeteoAlarm | 1 611 | The meteoalarm component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/meteoalarm) |
| 16 | `amcrest` | Amcrest | 1 396 | Support for Amcrest IP cameras. | local_polling | [lien](https://www.home-assistant.io/integrations/amcrest) |
| 17 | `homematic` | Homematic | 1 343 | Support for HomeMatic devices. | local_push | [lien](https://www.home-assistant.io/integrations/homematic) |
| 18 | `mqtt_statestream` | MQTT Statestream | 1 311 | Publish simple item state changes via MQTT. | local_push | [lien](https://www.home-assistant.io/integrations/mqtt_statestream) |
| 19 | `bluetooth_le_tracker` | Bluetooth LE Tracker | 1 036 | The bluetooth_le_tracker component. | local_push | [lien](https://www.home-assistant.io/integrations/bluetooth_le_tracker) |
| 20 | `envisalink` | Envisalink | 891 | Support for Envisalink devices. | local_push | [lien](https://www.home-assistant.io/integrations/envisalink) |
| 21 | `signal_messenger` | Signal Messenger | 889 | The signalmessenger component. | cloud_push | [lien](https://www.home-assistant.io/integrations/signal_messenger) |
| 22 | `rflink` | RFLink | 851 | Support for Rflink devices. | assumed_state | [lien](https://www.home-assistant.io/integrations/rflink) |
| 23 | `emby` | Emby | 850 | The emby component. | local_push | [lien](https://www.home-assistant.io/integrations/emby) |
| 24 | `folder` | Folder | 843 | The folder component. | local_polling | [lien](https://www.home-assistant.io/integrations/folder) |
| 25 | `yamaha` | Yamaha Network Receivers | 806 | The yamaha component. | local_polling | [lien](https://www.home-assistant.io/integrations/yamaha) |
| 26 | `free_mobile` | Free Mobile | 770 | The free_mobile component. | cloud_push | [lien](https://www.home-assistant.io/integrations/free_mobile) |
| 27 | `bitcoin` | Bitcoin | 712 | The Bitcoin integration. | cloud_polling | [lien](https://www.home-assistant.io/integrations/bitcoin) |
| 28 | `twilio_sms` | Twilio SMS | 683 | The twilio_sms component. | cloud_push | [lien](https://www.home-assistant.io/integrations/twilio_sms) |
| 29 | `browser` | Browser | 652 | Support for launching a web browser on the host machine. | local_push | [lien](https://www.home-assistant.io/integrations/browser) |
| 30 | `google_wifi` | Google Wifi | 645 | The google_wifi component. | local_polling | [lien](https://www.home-assistant.io/integrations/google_wifi) |
| 31 | `luci` | OpenWrt (luci) | 574 | The luci component. | local_polling | [lien](https://www.home-assistant.io/integrations/luci) |
| 32 | `flux` | Flux | 548 | The flux component. | calculated | [lien](https://www.home-assistant.io/integrations/flux) |
| 33 | `torque` | Torque | 479 | The torque component. | local_push | [lien](https://www.home-assistant.io/integrations/torque) |
| 34 | `limitlessled` | LimitlessLED | 472 | The limitlessled component. | assumed_state | [lien](https://www.home-assistant.io/integrations/limitlessled) |
| 35 | `notify_events` | Notify.Events | 458 | The notify_events component. | cloud_push | [lien](https://www.home-assistant.io/integrations/notify_events) |
| 36 | `matrix` | Matrix | 453 | The Matrix bot component. | cloud_push | [lien](https://www.home-assistant.io/integrations/matrix) |
| 37 | `proxy` | Camera Proxy | 445 | The proxy component. | — | [lien](https://www.home-assistant.io/integrations/proxy) |
| 38 | `microsoft` | Microsoft Text-to-Speech (TTS) | 436 | Support for Microsoft integration. | cloud_push | [lien](https://www.home-assistant.io/integrations/microsoft) |
| 39 | `twilio_call` | Twilio Call | 431 | The twilio_call component. | cloud_push | [lien](https://www.home-assistant.io/integrations/twilio_call) |
| 40 | `worxlandroid` | Worx Landroid | 414 | The worxlandroid component. | local_polling | [lien](https://www.home-assistant.io/integrations/worxlandroid) |
| 41 | `keyboard_remote` | Keyboard Remote | 409 | Receive signals from a keyboard and use it as a remote control. | local_push | [lien](https://www.home-assistant.io/integrations/keyboard_remote) |
| 42 | `no_ip` | No-IP.com | 407 | Integrate with NO-IP Dynamic DNS service. | cloud_polling | [lien](https://www.home-assistant.io/integrations/no_ip) |
| 43 | `keba` | Keba Charging Station | 401 | Support for KEBA charging stations. | local_polling | [lien](https://www.home-assistant.io/integrations/keba) |
| 44 | `compensation` | Compensation | 397 | The Compensation integration. | calculated | [lien](https://www.home-assistant.io/integrations/compensation) |
| 45 | `amazon_polly` | Amazon Polly | 373 | Support for Amazon Polly integration. | cloud_push | [lien](https://www.home-assistant.io/integrations/amazon_polly) |
| 46 | `google_maps` | Google Maps | 349 | The google_maps component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/google_maps) |
| 47 | `hp_ilo` | HP Integrated Lights-Out (ILO) | 346 | The HP Integrated Lights-Out (iLO) component. | local_polling | [lien](https://www.home-assistant.io/integrations/hp_ilo) |
| 48 | `pioneer` | Pioneer | 335 | The pioneer component. | local_polling | [lien](https://www.home-assistant.io/integrations/pioneer) |
| 49 | `ffmpeg_motion` | FFmpeg Motion | 317 | The ffmpeg_motion component. | calculated | [lien](https://www.home-assistant.io/integrations/ffmpeg_motion) |
| 50 | `comed_hourly_pricing` | ComEd Hourly Pricing | 289 | The comed_hourly_pricing component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/comed_hourly_pricing) |
| 51 | `serial` | Serial | 287 | The serial component. | local_polling | [lien](https://www.home-assistant.io/integrations/serial) |
| 52 | `ihc` | IHC Controller | 285 | Support for IHC devices. | local_push | [lien](https://www.home-assistant.io/integrations/ihc) |
| 53 | `flic` | Flic | 281 | The flic component. | local_push | [lien](https://www.home-assistant.io/integrations/flic) |
| 54 | `remote_rpi_gpio` | Raspberry Pi Remote GPIO | 279 | Support for controlling GPIO pins of a Raspberry Pi. | local_push | [lien](https://www.home-assistant.io/integrations/remote_rpi_gpio) |
| 55 | `intesishome` | IntesisHome | 264 | Intesishome platform. | cloud_push | [lien](https://www.home-assistant.io/integrations/intesishome) |
| 56 | `noaa_tides` | NOAA Tides | 260 | The noaa_tides component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/noaa_tides) |
| 57 | `comfoconnect` | Zehnder ComfoAir Q | 256 | Support to control a Zehnder ComfoAir Q350/450/600 ventilation unit. | local_push | [lien](https://www.home-assistant.io/integrations/comfoconnect) |
| 58 | `iperf3` | Iperf3 | 246 | Support for Iperf3 network measurement tool. | local_polling | [lien](https://www.home-assistant.io/integrations/iperf3) |
| 59 | `syslog` | Syslog | 245 | The syslog component. | local_push | [lien](https://www.home-assistant.io/integrations/syslog) |
| 60 | `panasonic_bluray` | Panasonic Blu-Ray Player | 232 | The Panasonic Blu-Ray Player integration. | local_polling | [lien](https://www.home-assistant.io/integrations/panasonic_bluray) |
| 61 | `maxcube` | eQ-3 MAX! | 231 | Support for the MAX! Cube LAN Gateway. | local_polling | [lien](https://www.home-assistant.io/integrations/maxcube) |
| 62 | `xiaomi_tv` | Xiaomi TV | 229 | The xiaomi_tv component. | assumed_state | [lien](https://www.home-assistant.io/integrations/xiaomi_tv) |
| 63 | `supla` | SUPLA | 224 | Support for Supla devices. | cloud_polling | [lien](https://www.home-assistant.io/integrations/supla) |
| 64 | `zoneminder` | ZoneMinder | 224 | Support for ZoneMinder. | local_polling | [lien](https://www.home-assistant.io/integrations/zoneminder) |
| 65 | `openhardwaremonitor` | Open Hardware Monitor | 220 | The openhardwaremonitor component. | local_polling | [lien](https://www.home-assistant.io/integrations/openhardwaremonitor) |
| 66 | `hikvisioncam` | Hikvision | 217 | The Hikvision integration. | local_polling | [lien](https://www.home-assistant.io/integrations/hikvisioncam) |
| 67 | `clicksend` | ClickSend SMS | 208 | The clicksend component. | cloud_push | [lien](https://www.home-assistant.io/integrations/clicksend) |
| 68 | `telnet` | Telnet | 208 | The telnet component. | local_polling | [lien](https://www.home-assistant.io/integrations/telnet) |
| 69 | `familyhub` | Samsung Family Hub | 203 | The familyhub component. | local_polling | [lien](https://www.home-assistant.io/integrations/familyhub) |
| 70 | `ffmpeg_noise` | FFmpeg Noise | 201 | The ffmpeg_noise component. | calculated | [lien](https://www.home-assistant.io/integrations/ffmpeg_noise) |
| 71 | `emoncms_history` | Emoncms History | 194 | Support for sending data to Emoncms. | local_polling | [lien](https://www.home-assistant.io/integrations/emoncms_history) |
| 72 | `emulated_kasa` | Emulated Kasa | 184 | Support for local power state reporting by emulating TP-Link Kasa plugs. | local_push | [lien](https://www.home-assistant.io/integrations/emulated_kasa) |
| 73 | `synology_srm` | Synology SRM | 182 | The Synology SRM component. | local_polling | [lien](https://www.home-assistant.io/integrations/synology_srm) |
| 74 | `marytts` | MaryTTS | 181 | Support for MaryTTS integration. | local_push | [lien](https://www.home-assistant.io/integrations/marytts) |
| 75 | `synology_chat` | Synology Chat | 181 | The synology_chat component. | cloud_push | [lien](https://www.home-assistant.io/integrations/synology_chat) |
| 76 | `apprise` | Apprise | 179 | The apprise component. | cloud_push | [lien](https://www.home-assistant.io/integrations/apprise) |
| 77 | `mqtt_json` | MQTT JSON | 175 | The mqtt_json component. | local_push | [lien](https://www.home-assistant.io/integrations/mqtt_json) |
| 78 | `eufy` | EufyHome | 172 | Support for EufyHome devices. | local_polling | [lien](https://www.home-assistant.io/integrations/eufy) |
| 79 | `schluter` | Schluter | 167 | The Schluter DITRA-HEAT integration. | cloud_polling | [lien](https://www.home-assistant.io/integrations/schluter) |
| 80 | `manual_mqtt` | Manual MQTT Alarm Control Panel | 166 | The manual_mqtt component. | local_push | [lien](https://www.home-assistant.io/integrations/manual_mqtt) |
| 81 | `linux_battery` | Linux Battery | 163 | The linux_battery component. | local_polling | [lien](https://www.home-assistant.io/integrations/linux_battery) |
| 82 | `demo` | Demo | 156 | Set up the demo environment that mimics interaction with devices. | calculated | [lien](https://www.home-assistant.io/integrations/demo) |
| 83 | `lifx_cloud` | LIFX Cloud | 146 | The lifx_cloud component. | cloud_push | [lien](https://www.home-assistant.io/integrations/lifx_cloud) |
| 84 | `mqtt_eventstream` | MQTT Eventstream | 144 | Connect two Home Assistant instances via MQTT. | local_polling | [lien](https://www.home-assistant.io/integrations/mqtt_eventstream) |
| 85 | `tcp` | TCP | 144 | The tcp component. | local_polling | [lien](https://www.home-assistant.io/integrations/tcp) |
| 86 | `itach` | Global Caché iTach TCP/IP to IR | 143 | Support for itach devices. | assumed_state | [lien](https://www.home-assistant.io/integrations/itach) |
| 87 | `itunes` | Apple iTunes | 140 | The itunes component. | local_polling | [lien](https://www.home-assistant.io/integrations/itunes) |
| 88 | `joaoapps_join` | Joaoapps Join | 139 | Support for Joaoapps Join services. | cloud_push | [lien](https://www.home-assistant.io/integrations/joaoapps_join) |
| 89 | `netdata` | Netdata | 139 | The netdata component. | local_polling | [lien](https://www.home-assistant.io/integrations/netdata) |
| 90 | `fail2ban` | Fail2Ban | 138 | The Fail2Ban integration. | local_polling | [lien](https://www.home-assistant.io/integrations/fail2ban) |
| 91 | `nsw_fuel_station` | NSW Fuel Station Price | 138 | The nsw_fuel_station component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/nsw_fuel_station) |
| 92 | `aquostv` | Sharp Aquos TV | 136 | The aquostv component. | local_polling | [lien](https://www.home-assistant.io/integrations/aquostv) |
| 93 | `rmvtransport` | RMV | 130 | The rmvtransport component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/rmvtransport) |
| 94 | `xiaomi` | Xiaomi | 128 | The xiaomi component. | local_polling | [lien](https://www.home-assistant.io/integrations/xiaomi) |
| 95 | `ubus` | OpenWrt (ubus) | 127 | The ubus component. | local_polling | [lien](https://www.home-assistant.io/integrations/ubus) |
| 96 | `sony_projector` | Sony Projector | 126 | The sony_projector component. | local_polling | [lien](https://www.home-assistant.io/integrations/sony_projector) |
| 97 | `denon` | Denon Network Receivers | 120 | The Denon Network Receivers integration. | local_polling | [lien](https://www.home-assistant.io/integrations/denon) |
| 98 | `wirelesstag` | Wireless Sensor Tags | 117 | Support for Wireless Sensor Tags. | cloud_push | [lien](https://www.home-assistant.io/integrations/wirelesstag) |
| 99 | `doods` | DOODS - Dedicated Open Object Detection Service | 110 | The doods component. | local_polling | [lien](https://www.home-assistant.io/integrations/doods) |
| 100 | `iammeter` | IamMeter | 108 | Iammeter integration. | local_polling | [lien](https://www.home-assistant.io/integrations/iammeter) |
| 101 | `lightwave` | Lightwave | 105 | Support for device connected via Lightwave WiFi-link hub. | assumed_state | [lien](https://www.home-assistant.io/integrations/lightwave) |
| 102 | `alpha_vantage` | Alpha Vantage | 104 | The Alpha Vantage component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/alpha_vantage) |
| 103 | `aprs` | APRS | 104 | The APRS component. | cloud_push | [lien](https://www.home-assistant.io/integrations/aprs) |
| 104 | `tellstick` | TellStick | 104 | Support for Tellstick. | assumed_state | [lien](https://www.home-assistant.io/integrations/tellstick) |
| 105 | `lacrosse` | LaCrosse | 103 | The lacrosse component. | local_polling | [lien](https://www.home-assistant.io/integrations/lacrosse) |
| 106 | `ohmconnect` | OhmConnect | 103 | The OhmConnect integration. | cloud_polling | [lien](https://www.home-assistant.io/integrations/ohmconnect) |
| 107 | `discogs` | Discogs | 102 | The discogs component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/discogs) |
| 108 | `nissan_leaf` | Nissan Leaf | 100 | Support for the Nissan Leaf Carwings/Nissan Connect API. | cloud_polling | [lien](https://www.home-assistant.io/integrations/nissan_leaf) |
| 109 | `transport_nsw` | Transport NSW | 99 | The transport_nsw component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/transport_nsw) |
| 110 | `voicerss` | VoiceRSS | 99 | Support for VoiceRSS integration. | cloud_push | [lien](https://www.home-assistant.io/integrations/voicerss) |
| 111 | `freedns` | FreeDNS | 97 | Integrate with FreeDNS Dynamic DNS service at freedns.afraid.org. | cloud_push | [lien](https://www.home-assistant.io/integrations/freedns) |
| 112 | `norway_air` | Om Luftkvalitet i Norge (Norway Air) | 96 | The norway_air component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/norway_air) |
| 113 | `xmpp` | Jabber (XMPP) | 94 | The xmpp component. | cloud_push | [lien](https://www.home-assistant.io/integrations/xmpp) |
| 114 | `route53` | AWS Route53 | 92 | Update the IP addresses of your Route53 DNS records. | cloud_push | [lien](https://www.home-assistant.io/integrations/route53) |
| 115 | `ads` | ADS | 91 | Support for Automation Device Specification (ADS). | local_push | [lien](https://www.home-assistant.io/integrations/ads) |
| 116 | `channels` | Channels | 91 | The channels component. | local_polling | [lien](https://www.home-assistant.io/integrations/channels) |
| 117 | `bt_smarthub` | BT Smart Hub | 90 | The bt_smarthub component. | local_polling | [lien](https://www.home-assistant.io/integrations/bt_smarthub) |
| 118 | `zabbix` | Zabbix | 90 | Support for Zabbix. | local_polling | [lien](https://www.home-assistant.io/integrations/zabbix) |
| 119 | `uk_transport` | UK Transport | 89 | The uk_transport component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/uk_transport) |
| 120 | `osramlightify` | Osramlightify | 84 | The osramlightify component. | local_polling | [lien](https://www.home-assistant.io/integrations/osramlightify) |
| 121 | `pushsafer` | Pushsafer | 84 | The Pushsafer integration. | cloud_push | [lien](https://www.home-assistant.io/integrations/pushsafer) |
| 122 | `firmata` | Firmata | 82 | Support for Arduino-compatible Microcontrollers through Firmata. | local_push | [lien](https://www.home-assistant.io/integrations/firmata) |
| 123 | `yandextts` | Yandex TTS | 81 | Support for the yandex speechkit tts integration. | cloud_push | [lien](https://www.home-assistant.io/integrations/yandextts) |
| 124 | `kef` | KEF | 80 | The KEF Wireless Speakers component. | local_polling | [lien](https://www.home-assistant.io/integrations/kef) |
| 125 | `vasttrafik` | Västtrafik | 80 | The vasttrafik component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/vasttrafik) |
| 126 | `geo_rss_events` | GeoRSS | 78 | The geo_rss_events component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/geo_rss_events) |
| 127 | `ddwrt` | DD-WRT | 75 | The ddwrt component. | local_polling | [lien](https://www.home-assistant.io/integrations/ddwrt) |
| 128 | `harman_kardon_avr` | Harman Kardon AVR | 75 | The harman_kardon_avr component. | local_polling | [lien](https://www.home-assistant.io/integrations/harman_kardon_avr) |
| 129 | `swiss_hydrological_data` | Swiss Hydrological Data | 75 | The swiss_hydrological_data component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/swiss_hydrological_data) |
| 130 | `ebusd` | ebusd | 68 | Support for Ebusd daemon for communication with eBUS heating systems. | local_polling | [lien](https://www.home-assistant.io/integrations/ebusd) |
| 131 | `gtfs` | General Transit Feed Specification (GTFS) | 67 | The gtfs component. | local_polling | [lien](https://www.home-assistant.io/integrations/gtfs) |
| 132 | `seven_segments` | Seven Segments OCR | 67 | The seven_segments component. | local_polling | [lien](https://www.home-assistant.io/integrations/seven_segments) |
| 133 | `linksys_smart` | Linksys Smart Wi-Fi | 66 | The Linksys Smart Wi-Fi integration. | local_polling | [lien](https://www.home-assistant.io/integrations/linksys_smart) |
| 134 | `mediaroom` | Mediaroom | 66 | The mediaroom component. | local_polling | [lien](https://www.home-assistant.io/integrations/mediaroom) |
| 135 | `pocketcasts` | Pocket Casts | 65 | The pocketcasts component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/pocketcasts) |
| 136 | `citybikes` | CityBikes | 64 | The citybikes component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/citybikes) |
| 137 | `hdmi_cec` | HDMI-CEC | 64 | Support for HDMI CEC. | local_push | [lien](https://www.home-assistant.io/integrations/hdmi_cec) |
| 138 | `nad` | NAD | 64 | The nad component. | local_polling | [lien](https://www.home-assistant.io/integrations/nad) |
| 139 | `rejseplanen` | Rejseplanen | 64 | The rejseplanen component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/rejseplanen) |
| 140 | `llamalab_automate` | LlamaLab Automate | 62 | The llamalab_automate component. | cloud_push | [lien](https://www.home-assistant.io/integrations/llamalab_automate) |
| 141 | `worldtidesinfo` | World Tides | 61 | The worldtidesinfo component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/worldtidesinfo) |
| 142 | `kaiterra` | Kaiterra | 60 | Support for Kaiterra devices. | cloud_polling | [lien](https://www.home-assistant.io/integrations/kaiterra) |
| 143 | `starlingbank` | Starling Bank | 60 | The starlingbank component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/starlingbank) |
| 144 | `baidu` | Baidu | 58 | Support for Baidu integration. | cloud_push | [lien](https://www.home-assistant.io/integrations/baidu) |
| 145 | `facebook` | Facebook Messenger | 56 | The facebook component. | cloud_push | [lien](https://www.home-assistant.io/integrations/facebook) |
| 146 | `device_sun_light_trigger` | Presence-based Lights | 54 | Support to turn on lights based on the states. | calculated | [lien](https://www.home-assistant.io/integrations/device_sun_light_trigger) |
| 147 | `qrcode` | QR Code | 54 | The QR code component. | calculated | [lien](https://www.home-assistant.io/integrations/qrcode) |
| 148 | `fortios` | FortiOS | 49 | Fortinet FortiOS integration. | local_polling | [lien](https://www.home-assistant.io/integrations/fortios) |
| 149 | `tomato` | Tomato | 49 | The Tomato integration. | local_polling | [lien](https://www.home-assistant.io/integrations/tomato) |
| 150 | `aws` | Amazon Web Services (AWS) | 44 | Support for Amazon Web Services (AWS). | cloud_push | [lien](https://www.home-assistant.io/integrations/aws) |
| 151 | `ombi` | Ombi | 44 | Support for Ombi. | local_polling | [lien](https://www.home-assistant.io/integrations/ombi) |
| 152 | `tank_utility` | Tank Utility | 44 | The tank_utility component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/tank_utility) |
| 153 | `twitter` | X | 44 | The twitter component. | cloud_push | [lien](https://www.home-assistant.io/integrations/twitter) |
| 154 | `qvr_pro` | QVR Pro | 43 | Support for QVR Pro NVR software by QNAP. | local_polling | [lien](https://www.home-assistant.io/integrations/qvr_pro) |
| 155 | `shodan` | Shodan | 43 | The shodan component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/shodan) |
| 156 | `google_pubsub` | Google Pub/Sub | 42 | Support for Google Cloud Pub/Sub. | cloud_push | [lien](https://www.home-assistant.io/integrations/google_pubsub) |
| 157 | `spc` | Vanderbilt SPC | 42 | Support for Vanderbilt (formerly Siemens) SPC alarm systems. | local_push | [lien](https://www.home-assistant.io/integrations/spc) |
| 158 | `nilu` | Norwegian Institute for Air Research (NILU) | 41 | The nilu component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/nilu) |
| 159 | `danfoss_air` | Danfoss Air | 39 | Support for Danfoss Air HRV. | local_polling | [lien](https://www.home-assistant.io/integrations/danfoss_air) |
| 160 | `digital_ocean` | Digital Ocean | 39 | Support for Digital Ocean. | local_polling | [lien](https://www.home-assistant.io/integrations/digital_ocean) |
| 161 | `delijn` | De Lijn | 37 | The delijn component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/delijn) |
| 162 | `yandex_transport` | Yandex Transport | 37 | Service for obtaining information about closer bus from Transport Yandex Service. | cloud_polling | [lien](https://www.home-assistant.io/integrations/yandex_transport) |
| 163 | `clicksend_tts` | ClickSend TTS | 36 | The clicksend_tts component. | cloud_push | [lien](https://www.home-assistant.io/integrations/clicksend_tts) |
| 164 | `garadget` | Garadget | 36 | The garadget component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/garadget) |
| 165 | `rss_feed_template` | RSS Feed Template | 36 | Support to export sensor values via RSS feed. | local_push | [lien](https://www.home-assistant.io/integrations/rss_feed_template) |
| 166 | `sisyphus` | Sisyphus | 36 | Support for controlling Sisyphus Kinetic Art Tables. | local_push | [lien](https://www.home-assistant.io/integrations/sisyphus) |
| 167 | `thingspeak` | ThingSpeak | 36 | Support for submitting data to Thingspeak. | cloud_push | [lien](https://www.home-assistant.io/integrations/thingspeak) |
| 168 | `london_air` | London Air | 34 | The london_air component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/london_air) |
| 169 | `mvglive` | MVG | 34 | The mvglive component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/mvglive) |
| 170 | `quantum_gateway` | Quantum Gateway | 34 | The quantum_gateway component. | local_polling | [lien](https://www.home-assistant.io/integrations/quantum_gateway) |
| 171 | `switchmate` | Switchmate SimplySmart Home | 34 | The switchmate component. | local_polling | [lien](https://www.home-assistant.io/integrations/switchmate) |
| 172 | `foobot` | Foobot | 33 | The foobot component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/foobot) |
| 173 | `mochad` | Mochad | 33 | Support for CM15A/CM19A X10 Controller using mochad daemon. | local_polling | [lien](https://www.home-assistant.io/integrations/mochad) |
| 174 | `blockchain` | Blockchain.com | 32 | The blockchain component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/blockchain) |
| 175 | `clickatell` | Clickatell | 32 | The clickatell component. | cloud_push | [lien](https://www.home-assistant.io/integrations/clickatell) |
| 176 | `currencylayer` | currencylayer | 32 | The currencylayer component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/currencylayer) |
| 177 | `aqualogic` | AquaLogic | 31 | Support for AquaLogic devices. | local_push | [lien](https://www.home-assistant.io/integrations/aqualogic) |
| 178 | `ephember` | EPH Controls | 31 | The ephember component. | local_polling | [lien](https://www.home-assistant.io/integrations/ephember) |
| 179 | `etherscan` | Etherscan | 31 | The etherscan component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/etherscan) |
| 180 | `mfi` | Ubiquiti mFi mPort | 31 | The Ubiquiti mFI mPort integration. | local_polling | [lien](https://www.home-assistant.io/integrations/mfi) |
| 181 | `sendgrid` | SendGrid | 31 | The sendgrid integration. | cloud_push | [lien](https://www.home-assistant.io/integrations/sendgrid) |
| 182 | `opple` | Opple | 30 | The Opple integration. | local_polling | [lien](https://www.home-assistant.io/integrations/opple) |
| 183 | `push` | Push | 30 | The push component. | local_push | [lien](https://www.home-assistant.io/integrations/push) |
| 184 | `russound_rnet` | Russound RNET | 30 | The russound_rnet component. | local_polling | [lien](https://www.home-assistant.io/integrations/russound_rnet) |
| 185 | `atome` | Atome Linky | 28 | Support for Atome devices connected to a Linky Energy Meter. | cloud_polling | [lien](https://www.home-assistant.io/integrations/atome) |
| 186 | `uvc` | Ubiquiti UniFi Video | 28 | The uvc component. | local_polling | [lien](https://www.home-assistant.io/integrations/uvc) |
| 187 | `aruba` | Aruba | 27 | The Aruba integration. | local_polling | [lien](https://www.home-assistant.io/integrations/aruba) |
| 188 | `neurio_energy` | Neurio energy | 27 | The neurio_energy component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/neurio_energy) |
| 189 | `recswitch` | Ankuoo REC Switch | 27 | The recswitch component. | local_polling | [lien](https://www.home-assistant.io/integrations/recswitch) |
| 190 | `rtorrent` | rTorrent | 26 | The rtorrent component. | local_polling | [lien](https://www.home-assistant.io/integrations/rtorrent) |
| 191 | `hddtemp` | hddtemp | 25 | The hddtemp component. | local_polling | [lien](https://www.home-assistant.io/integrations/hddtemp) |
| 192 | `temper` | TEMPer | 24 | The TEMPer integration. | local_polling | [lien](https://www.home-assistant.io/integrations/temper) |
| 193 | `meraki` | Meraki | 23 | The meraki component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/meraki) |
| 194 | `reddit` | Reddit | 23 | Reddit Component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/reddit) |
| 195 | `tmb` | Transports Metropolitans de Barcelona | 23 | Support for Transports Metropolitans de Barcelona. | local_polling | [lien](https://www.home-assistant.io/integrations/tmb) |
| 196 | `irish_rail_transport` | Irish Rail Transport | 22 | The irish_rail_transport component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/irish_rail_transport) |
| 197 | `nx584` | NX584 | 22 | Support for NX584 alarm control panels. | local_push | [lien](https://www.home-assistant.io/integrations/nx584) |
| 198 | `sky_hub` | Sky Hub | 21 | The Sky Hub integration. | local_polling | [lien](https://www.home-assistant.io/integrations/sky_hub) |
| 199 | `egardia` | Egardia | 20 | Interfaces with Egardia/Woonveilig alarm control panel. | local_polling | [lien](https://www.home-assistant.io/integrations/egardia) |
| 200 | `graphite` | Graphite | 20 | Support for sending data to a Graphite installation. | local_push | [lien](https://www.home-assistant.io/integrations/graphite) |
| 201 | `ted5000` | The Energy Detective TED5000 | 20 | The ted5000 component. | local_polling | [lien](https://www.home-assistant.io/integrations/ted5000) |
| 202 | `arwn` | Ambient Radio Weather Network | 19 | The arwn component. | local_push | [lien](https://www.home-assistant.io/integrations/arwn) |
| 203 | `openerz` | Open ERZ | 18 | The Open ERZ API integration. | cloud_polling | [lien](https://www.home-assistant.io/integrations/openerz) |
| 204 | `minio` | Minio | 17 | Minio component. | cloud_push | [lien](https://www.home-assistant.io/integrations/minio) |
| 205 | `pulseaudio_loopback` | PulseAudio Loopback | 17 | The pulseaudio_loopback component. | local_polling | [lien](https://www.home-assistant.io/integrations/pulseaudio_loopback) |
| 206 | `remember_the_milk` | Remember The Milk | 17 | Support to interact with Remember The Milk. | cloud_push | [lien](https://www.home-assistant.io/integrations/remember_the_milk) |
| 207 | `vlc` | VLC media player | 17 | The vlc component. | local_polling | [lien](https://www.home-assistant.io/integrations/vlc) |
| 208 | `fixer` | Fixer | 16 | The fixer component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/fixer) |
| 209 | `linode` | Linode | 16 | Support for Linode. | cloud_polling | [lien](https://www.home-assistant.io/integrations/linode) |
| 210 | `melissa` | Melissa | 16 | Support for Melissa climate. | cloud_polling | [lien](https://www.home-assistant.io/integrations/melissa) |
| 211 | `netio` | Netio | 16 | The netio component. | local_polling | [lien](https://www.home-assistant.io/integrations/netio) |
| 212 | `sinch` | Sinch SMS | 15 | Component to integrate with Sinch SMS API. | cloud_push | [lien](https://www.home-assistant.io/integrations/sinch) |
| 213 | `haveibeenpwned` | HaveIBeenPwned | 13 | The haveibeenpwned component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/haveibeenpwned) |
| 214 | `repetier` | Repetier-Server | 13 | Support for Repetier-Server sensors. | local_polling | [lien](https://www.home-assistant.io/integrations/repetier) |
| 215 | `serial_pm` | Serial Particulate Matter | 13 | The serial_pm component. | local_polling | [lien](https://www.home-assistant.io/integrations/serial_pm) |
| 216 | `sesame` | Sesame Smart Lock | 13 | The sesame component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/sesame) |
| 217 | `supervisord` | Supervisord | 13 | The supervisord component. | local_polling | [lien](https://www.home-assistant.io/integrations/supervisord) |
| 218 | `cisco_ios` | Cisco IOS | 12 | The cisco_ios component. | local_polling | [lien](https://www.home-assistant.io/integrations/cisco_ios) |
| 219 | `xs1` | EZcontrol XS1 | 12 | Support for the EZcontrol XS1 gateway. | local_polling | [lien](https://www.home-assistant.io/integrations/xs1) |
| 220 | `concord232` | Concord232 | 11 | The concord232 component. | local_polling | [lien](https://www.home-assistant.io/integrations/concord232) |
| 221 | `upc_connect` | UPC Connect Box | 11 | The upc_connect component. | local_polling | [lien](https://www.home-assistant.io/integrations/upc_connect) |
| 222 | `zestimate` | Zestimate | 11 | The zestimate component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/zestimate) |
| 223 | `foursquare` | Foursquare | 10 | Support for the Foursquare (Swarm) API. | cloud_push | [lien](https://www.home-assistant.io/integrations/foursquare) |
| 224 | `message_bird` | MessageBird | 10 | The message_bird component. | cloud_push | [lien](https://www.home-assistant.io/integrations/message_bird) |
| 225 | `anel_pwrctrl` | Anel NET-PwrCtrl | 9 | The anel_pwrctrl component. | local_polling | [lien](https://www.home-assistant.io/integrations/anel_pwrctrl) |
| 226 | `cisco_mobility_express` | Cisco Mobility Express | 8 | Component to embed Cisco Mobility Express. | local_polling | [lien](https://www.home-assistant.io/integrations/cisco_mobility_express) |
| 227 | `cisco_webex_teams` | Cisco Webex Teams | 8 | Component to integrate the Cisco Webex cloud. | cloud_push | [lien](https://www.home-assistant.io/integrations/cisco_webex_teams) |
| 228 | `gitlab_ci` | GitLab-CI | 8 | The gitlab_ci component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/gitlab_ci) |
| 229 | `kankun` | Kankun | 8 | The kankun component. | local_polling | [lien](https://www.home-assistant.io/integrations/kankun) |
| 230 | `edimax` | Edimax | 7 | The Edimax integration. | local_polling | [lien](https://www.home-assistant.io/integrations/edimax) |
| 231 | `kira` | Kira | 7 | KIRA interface to receive UDP packets from an IR-IP bridge. | local_push | [lien](https://www.home-assistant.io/integrations/kira) |
| 232 | `openalpr_cloud` | OpenALPR Cloud | 7 | The openalpr_cloud component. | cloud_push | [lien](https://www.home-assistant.io/integrations/openalpr_cloud) |
| 233 | `rocketchat` | Rocket.Chat | 7 | The rocketchat component. | cloud_push | [lien](https://www.home-assistant.io/integrations/rocketchat) |
| 234 | `viaggiatreno` | Trenitalia ViaggiaTreno | 7 | The viaggiatreno component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/viaggiatreno) |
| 235 | `yeelightsunflower` | Yeelight Sunflower | 7 | The yeelightsunflower component. | local_polling | [lien](https://www.home-assistant.io/integrations/yeelightsunflower) |
| 236 | `azure_service_bus` | Azure Service Bus | 6 | The Azure Service Bus integration. | cloud_push | [lien](https://www.home-assistant.io/integrations/azure_service_bus) |
| 237 | `blackbird` | Monoprice Blackbird Matrix Switch | 6 | The blackbird component. | local_polling | [lien](https://www.home-assistant.io/integrations/blackbird) |
| 238 | `flexit` | Flexit | 6 | The flexit component. | local_polling | [lien](https://www.home-assistant.io/integrations/flexit) |
| 239 | `proliphix` | Proliphix | 6 | The proliphix component. | local_polling | [lien](https://www.home-assistant.io/integrations/proliphix) |
| 240 | `apache_kafka` | Apache Kafka | 5 | Support for Apache Kafka. | local_push | [lien](https://www.home-assistant.io/integrations/apache_kafka) |
| 241 | `flock` | Flock | 5 | The flock component. | cloud_push | [lien](https://www.home-assistant.io/integrations/flock) |
| 242 | `oasa_telematics` | OASA Telematics | 5 | The OASA Telematics component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/oasa_telematics) |
| 243 | `qwikswitch` | QwikSwitch QSUSB | 5 | Support for Qwikswitch devices. | local_push | [lien](https://www.home-assistant.io/integrations/qwikswitch) |
| 244 | `volkszaehler` | Volkszaehler | 5 | The volkszaehler component. | local_polling | [lien](https://www.home-assistant.io/integrations/volkszaehler) |
| 245 | `w800rf32` | WGL Designs W800RF32 | 5 | Support for w800rf32 devices. | local_push | [lien](https://www.home-assistant.io/integrations/w800rf32) |
| 246 | `ecoal_boiler` | eSterownik eCoal.pl Boiler | 4 | Support to control ecoal/esterownik.pl coal/wood boiler controller. | local_polling | [lien](https://www.home-assistant.io/integrations/ecoal_boiler) |
| 247 | `gc100` | Global Caché GC-100 | 4 | Support for controlling Global Cache gc100. | local_polling | [lien](https://www.home-assistant.io/integrations/gc100) |
| 248 | `iglo` | iGlo | 4 | The iglo component. | local_polling | [lien](https://www.home-assistant.io/integrations/iglo) |
| 249 | `oem` | OpenEnergyMonitor WiFi Thermostat | 4 | The oem component. | local_polling | [lien](https://www.home-assistant.io/integrations/oem) |
| 250 | `oru` | Orange and Rockland Utility (ORU) | 4 | The Orange and Rockland Utility smart energy meter integration. | cloud_polling | [lien](https://www.home-assistant.io/integrations/oru) |
| 251 | `ripple` | Ripple | 4 | The ripple component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/ripple) |
| 252 | `statsd` | StatsD | 4 | Support for sending data to StatsD. | local_push | [lien](https://www.home-assistant.io/integrations/statsd) |
| 253 | `tapsaff` | Taps Aff | 4 | The tapsaff component. | local_polling | [lien](https://www.home-assistant.io/integrations/tapsaff) |
| 254 | `zhong_hong` | ZhongHong | 4 | The zhong_hong component. | local_push | [lien](https://www.home-assistant.io/integrations/zhong_hong) |
| 255 | `arest` | aREST | 3 | The arest component. | local_polling | [lien](https://www.home-assistant.io/integrations/arest) |
| 256 | `arris_tg2492lg` | Arris TG2492LG | 3 | The Arris TG2492LG integration. | local_polling | [lien](https://www.home-assistant.io/integrations/arris_tg2492lg) |
| 257 | `bizkaibus` | Bizkaibus | 3 | The Bizkaibus bus tracker component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/bizkaibus) |
| 258 | `fido` | Fido | 3 | The Fido integration. | cloud_polling | [lien](https://www.home-assistant.io/integrations/fido) |
| 259 | `futurenow` | P5 FutureNow | 3 | The futurenow component. | local_polling | [lien](https://www.home-assistant.io/integrations/futurenow) |
| 260 | `numato` | Numato USB GPIO Expander | 3 | Support for controlling GPIO pins of a Numato Labs USB GPIO expander. | local_push | [lien](https://www.home-assistant.io/integrations/numato) |
| 261 | `raspyrfm` | RaspyRFM | 3 | The raspyrfm component. | assumed_state | [lien](https://www.home-assistant.io/integrations/raspyrfm) |
| 262 | `xeoma` | Xeoma | 3 | The xeoma component. | local_polling | [lien](https://www.home-assistant.io/integrations/xeoma) |
| 263 | `dublin_bus_transport` | Dublin Bus | 2 | The dublin_bus_transport component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/dublin_bus_transport) |
| 264 | `ebox` | EBox | 2 | The EBox integration. | cloud_polling | [lien](https://www.home-assistant.io/integrations/ebox) |
| 265 | `kitchen_sink` | Everything but the Kitchen Sink | 2 | The Kitchen Sink integration contains demonstrations of various odds and ends. | calculated | [lien](https://www.home-assistant.io/integrations/kitchen_sink) |
| 266 | `mythicbeastsdns` | Mythic Beasts DNS | 2 | Support for Mythic Beasts Dynamic DNS service. | cloud_push | [lien](https://www.home-assistant.io/integrations/mythicbeastsdns) |
| 267 | `pilight` | Pilight | 2 | Component to create an interface to a Pilight daemon. | local_push | [lien](https://www.home-assistant.io/integrations/pilight) |
| 268 | `x10` | Heyu X10 | 2 | The x10 component. | local_polling | [lien](https://www.home-assistant.io/integrations/x10) |
| 269 | `bbox` | Bbox | 1 | The Bbox integration. | local_polling | [lien](https://www.home-assistant.io/integrations/bbox) |
| 270 | `elv` | ELV PCA | 1 | The Elv integration. | local_polling | [lien](https://www.home-assistant.io/integrations/elv) |
| 271 | `fleetgo` | FleetGO | 1 | The FleetGO component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/fleetgo) |
| 272 | `greeneye_monitor` | GreenEye Monitor (GEM) | 1 | Support for monitoring a GreenEye Monitor energy monitor. | local_push | [lien](https://www.home-assistant.io/integrations/greeneye_monitor) |
| 273 | `heatmiser` | Heatmiser | 1 | The heatmiser component. | local_polling | [lien](https://www.home-assistant.io/integrations/heatmiser) |
| 274 | `idteck_prox` | IDTECK Proximity Reader | 1 | Component for interfacing RFK101 proximity card readers. | local_push | [lien](https://www.home-assistant.io/integrations/idteck_prox) |
| 275 | `kiwi` | KIWI | 1 | The kiwi component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/kiwi) |
| 276 | `kwb` | KWB Easyfire | 1 | The kwb component. | local_polling | [lien](https://www.home-assistant.io/integrations/kwb) |
| 277 | `thinkingcleaner` | Thinking Cleaner | 1 | Support for Thinkingcleaner devices. | local_polling | [lien](https://www.home-assistant.io/integrations/thinkingcleaner) |
| 278 | `ziggo_mediabox_xl` | Ziggo Mediabox XL | 1 | The ziggo_mediabox_xl component. | local_polling | [lien](https://www.home-assistant.io/integrations/ziggo_mediabox_xl) |
| 279 | `actiontec` | Actiontec | 0 | The Actiontec integration. | local_polling | [lien](https://www.home-assistant.io/integrations/actiontec) |
| 280 | `bt_home_hub_5` | BT Home Hub 5 | 0 | The bt_home_hub_5 component. | local_polling | [lien](https://www.home-assistant.io/integrations/bt_home_hub_5) |
| 281 | `cmus` | cmus | 0 | The cmus component. | local_polling | [lien](https://www.home-assistant.io/integrations/cmus) |
| 282 | `cppm_tracker` | Aruba ClearPass | 0 | Add support for ClearPass Policy Manager. | local_polling | [lien](https://www.home-assistant.io/integrations/cppm_tracker) |
| 283 | `everlights` | EverLights | 0 | The everlights component. | local_polling | [lien](https://www.home-assistant.io/integrations/everlights) |
| 284 | `hitron_coda` | Rogers Hitron CODA | 0 | The hitron_coda component. | local_polling | [lien](https://www.home-assistant.io/integrations/hitron_coda) |
| 285 | `horizon` | Unitymedia Horizon HD Recorder | 0 | The horizon component. | local_polling | [lien](https://www.home-assistant.io/integrations/horizon) |
| 286 | `lw12wifi` | LAGUTE LW-12 | 0 | The lw12wifi component. | local_polling | [lien](https://www.home-assistant.io/integrations/lw12wifi) |
| 287 | `pencom` | Pencom | 0 | The pencom component. | local_polling | [lien](https://www.home-assistant.io/integrations/pencom) |
| 288 | `raincloud` | Melnor RainCloud | 0 | Support for Melnor RainCloud sprinkler water timer. | cloud_polling | [lien](https://www.home-assistant.io/integrations/raincloud) |
| 289 | `sigfox` | Sigfox | 0 | The sigfox component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/sigfox) |
| 290 | `sighthound` | Sighthound | 0 | The sighthound integration. | cloud_polling | [lien](https://www.home-assistant.io/integrations/sighthound) |
| 291 | `skybeacon` | Skybeacon | 0 | The skybeacon component. | local_polling | [lien](https://www.home-assistant.io/integrations/skybeacon) |
| 292 | `slide` | Slide | 0 | Component for the Slide API. | cloud_polling | [lien](https://www.home-assistant.io/integrations/slide) |
| 293 | `solaredge_local` | SolarEdge Local | 0 | The SolarEdge Local Integration. | local_polling | [lien](https://www.home-assistant.io/integrations/solaredge_local) |
| 294 | `startca` | Start.ca | 0 | The Start.ca integration. | cloud_polling | [lien](https://www.home-assistant.io/integrations/startca) |
| 295 | `thomson` | Thomson | 0 | The Thomson integration. | local_polling | [lien](https://www.home-assistant.io/integrations/thomson) |
| 296 | `travisci` | Travis-CI | 0 | The travisci component. | cloud_polling | [lien](https://www.home-assistant.io/integrations/travisci) |
| 297 | `versasense` | VersaSense | 0 | Support for VersaSense MicroPnP devices. | local_polling | [lien](https://www.home-assistant.io/integrations/versasense) |
| 298 | `lannouncer` | LANnouncer | — | The lannouncer component. | local_push | [lien](https://www.home-assistant.io/integrations/lannouncer) |
| 299 | `msteams` | Microsoft Teams | — | The Microsoft Teams component. | cloud_push | [lien](https://www.home-assistant.io/integrations/msteams) |
| 300 | `tplink_lte` | TP-Link LTE | — | The tplink_lte integration. | local_polling | [lien](https://www.home-assistant.io/integrations/tplink_lte) |
| 301 | `zengge` | Zengge | — | The zengge component. | local_polling | [lien](https://www.home-assistant.io/integrations/zengge) |
