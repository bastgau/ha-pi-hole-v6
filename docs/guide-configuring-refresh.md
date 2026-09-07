## How do I configure the refresh frequency?

### Configure the service (recommanded solution)

On the Pi-hole V6 Integration page (_/config/integrations/integration/pi_hole_v6_), configure your service.

<img src="../img/integration-page.png" width="500">

In the pop-up window, enter the desired `Live refresh frequency` value in seconds.

<img src="../img/integration-configuration.png" width="500">

### The two refresh frequencies

The integration uses two independent update coordinators, each with its own option:

- **`Live refresh frequency`** — 120 seconds by default. Drives what must reflect the current state of
  your Pi-hole. Calls `blocking_status`, `groups`, `padd`, `summary`, `clients`, `dhcp/leases`,
  `auth/sessions` and `network/devices`.
- **`Statistics refresh frequency`** — 300 seconds by default. Drives the cumulative counters and the
  periodic checks, whose values only matter as a trend. Calls `info/messages` and `info/messages/count`.

The statistics frequency must be greater than or equal to the live refresh frequency. Raising it is the
recommended way to reduce the number of rows the cumulative counters write to the recorder database,
while the blocking status, the switches and the device trackers keep reacting quickly.

The activity summary is fetched by the fast coordinator because the client counters and the query rate
need it fresh. The cumulative counters read that same shared cache, they are simply written at the
slower rhythm, which is exactly where the saving comes from. No data is lost.

Pressing the `Refresh data` button refreshes both coordinators at once.

| Entity | Coordinator |
| --- | --- |
| `sensor.<service_name>_ads_blocked_today` | `stats` |
| `sensor.<service_name>_ads_percentage_blocked_today` | `stats` |
| `sensor.<service_name>_dns_queries_cached` | `stats` |
| `sensor.<service_name>_dns_queries_forwarded` | `stats` |
| `sensor.<service_name>_dns_queries_today` | `stats` |
| `sensor.<service_name>_dns_unique_domains` | `stats` |
| `sensor.<service_name>_domains_blocked` | `stats` |
| `sensor.<service_name>_ftl_info_message_count` | `stats` |
| `update.<service_name>_core_update_available` | `stats` |
| `update.<service_name>_docker_update_available` | `stats` |
| `update.<service_name>_ftl_update_available` | `stats` |
| `update.<service_name>_web_update_available` | `stats` |
| `binary_sensor.<service_name>_status` | `live` |
| `button.<service_name>_*` (all 6 actions) | `live` |
| `device_tracker.*` (one per network device) | `live` |
| `sensor.<service_name>_auth_sessions` | `live` |
| `sensor.<service_name>_configured_clients` | `live` |
| `sensor.<service_name>_cpu_use` | `live` |
| `sensor.<service_name>_dhcp_leases` | `live` |
| `sensor.<service_name>_dns_queries_frequency` | `live` |
| `sensor.<service_name>_dns_unique_clients` | `live` |
| `sensor.<service_name>_memory_use` | `live` |
| `sensor.<service_name>_remaining_until_blocking_mode` | `live` |
| `sensor.<service_name>_seen_clients` | `live` |
| `switch.<service_name>` | `live` |
| `switch.<service_name>_group_*` | `live` |
| `sensor.<service_name>_latest_data_refresh` | `live` and `stats` |

`latest_data_refresh` is the only entity written by both: its state reports whichever coordinator
refreshed last.

### Deactivate the default refresh (alternative solution)

In the integration page, you have to deactivate the automatic polling for the `Pi-hole V6` Integration.

#### 1. Open the system options

Click on the `System options` to open the options.

<img src="../img/manual-refresh-01.png" width="300">

#### 2. Deactivate the automatic polling

Uncheck the option `Enable polling for changes` to deactivate the automatic polling.

<img src="../img/manual-refresh-02.png" width="300">

### Create an Automation

#### 1. Access Settings

Open your Home Assistant interface. Click on the `Settings` icon.

#### 2. Navigate to Automations & Scenes
   
In the settings menu, select `Automations & Scenes`.

#### 3. Create a New Automation

Click on `Create automation` to start a new automation.  
Select `Create new automation` to begin the creation process.

#### 4. Access the YAML Editor

Once in the new automation, click on the `three dots` on the right side of the screen.

Select `Edit in YAML` to open the YAML editor.

#### 5. Write the YAML Code

In the YAML editor, you can now write the code to configure the refresh of your integration. Here is a basic example:

```yaml
alias: Force Pi-hole Refresh
description: "Refresh Pi-hole every minute"
triggers:
  - trigger: time_pattern
    minutes: /1
    hours: "*"
conditions: []
actions:
  - action: homeassistant.update_entity
    metadata: {}
    data:
      entity_id:
        - binary_sensor.pi_hole_status
mode: single
```

You can define the wanted frequency.

#### 6. Save and Test

After writing the code, `save` the automation then test the automation to ensure it works as expected.
